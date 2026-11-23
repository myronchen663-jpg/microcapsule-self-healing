# 模型、集成与评分

五个模型分别预测修复效率 H 与强度折损 Q。
四个模型各用 150 个训练 family 的 1,500 行。
`mixed_gp` 按各端点的模型种子洗牌训练 family。
它依次取完整 family，累计最多 600 行。
校准拟合、校准评估各用 25 个 family 的 250 行。
测试使用 50 个 family 的 500 行。
分区标记在训练表的 `split` 列中。

## 模型与预测区间

Elastic Net、随机森林和贝叶斯模型先对数值特征做中位数插补。
这三个模型再标准化数值特征，对类别特征做独热编码。
CatBoost 对数值特征做中位数插补，保留原尺度。
CatBoost 保留原始类别字符串。
`mixed_gp` 对数值特征做中位数插补和标准化。
它将类别编码为整数，用 Hamming 相似度比较类别。

| 模型 | 拟合设置 | 预测抽样 |
|---|---|---|
| elastic_net | alpha=0.025，l1_ratio=0.35，max_iter=10000；6 个 family-bootstrap 子模型 | 随机选子模型，加标准差 s 的正态噪声 |
| random_forest | 主模型 250 棵树，depth=8，leaf=2，max_features=0.8；5 个子模型各 125 棵树 | 随机选主模型或子模型，加标准差 0.35s 的正态噪声 |
| catboost | iterations=280，depth=4，learning_rate=0.055，l2_leaf_reg=6，RMSE；3 个种子成员，单线程 | 随机选成员，加标准差 0.45s 的正态噪声 |
| mixed_gp | Matérn-3/2×Hamming 核；length_scale=1.3，categorical_rho=0.65，variance=1，noise=0.08；optimizer=None，normalize_y=True；每端点 600 行 | 按高斯过程均值与标准差抽正态变量；标准差下限 1e-8 |
| bayesian_multilevel | y 标准化；α~N(0,1)，β~N(0,0.7²)，τ~HalfNormal(0.6)，family 随机效应~N(0,τ²)（τ 为标准差），σ~HalfNormal(1)；Student-t 自由度 5；ADVI 1500 步，后验 300 个抽样 | 固定效应线性预测加 t 噪声；预测时省略训练 family 随机效应 |

s 为拟合残差相对其中位数的绝对偏差中位数乘 1.4826，下限为 1e-6。
每次预测使用 240 个抽样。
校准预测种子为模型种子加 11；测试预测种子加 17。
候选预测种子单独列在配置中。

区间校准先对校准 family 排序并洗牌。
每个校准拟合 family 随机取一行，共 25 行。
用绝对残差除以预测标准差构造分数。
预测标准差按 ddof=1 计算，下限为 1e-8。
有效标准差比例至少为 0.80 时采用标准化分数。
否则使用绝对残差分数。
分位水平为 min(1,ceil((n+1)×0.90)/n)，采用 higher 分位数。
预测均值及区间裁到 H 的 [−10, 140] 与 Q 的 [−5, 40]。
模型资格根据校准评估 family 的覆盖率 t 区间上界判断。
上界须有限且至少为 0.90。
测试区间须有限，未裁剪区间宽度须有限且为正。
两个端点均合格的模型进入集成。
`mixed_gp` 的修复效率覆盖上界低于 0.90。
运行后见 `model_metrics.csv` 中对应模型与端点的行。
覆盖均值为 `calibration_coverage`，上界为 `calibration_coverage_upper`。
因此它的点权重及全部重抽样权重为 0。
其余四个模型进入集成，名单由资格计算得到。
权重计算前要求合格模型恰好四个。
数量不符时，错误提示列出实际合格模型。

## 联合事件与集成权重

联合事件为 H≥60 且 Q≤15。
两个端点独立拟合，抽样按相同序号配对。
用裁剪前抽样计数 k，每模型概率为 (k+0.5)/241。
端点间相关结构采用独立假设。

权重使用测试集的预测与校准区间。
测试预测先写成 CSV，再用 pandas 默认浮点解析器读回。
这一步保留权重计算所需的数值路径。
包内输入数据和结果对照使用 round_trip 解析。
对 50 个测试 family 做 2,000 次有放回 bootstrap。
每次计算两个端点的 RMSE、区间覆盖率与残差。
R 为各模型 RMSE 除以同端点的最小 RMSE。

```text
C = 0.5 × sum_endpoint(((coverage−0.90)/0.05)²)
quality = −2×ln(sqrt(R_H×R_Q)) − 0.25×C
soft = softmax(quality)
rho_mk = (abs(corr_H,mk)+abs(corr_Q,mk))/2
redundancy_m = 1 + sum_other(soft_k×clip((rho_mk−0.60)/0.40,0,1))
adjusted = normalize(soft/redundancy)
weight = 0.05 + 0.80×adjusted
```

残差先转成正态分位分数，再计算相关系数。
并列残差采用平均秩。
bootstrap 权重取均值，再搜索与等权的混合系数。
搜索从 0 至 1，步长为 0.001。
取首个使最大权重≤0.55 且有效模型数≥2.50 的系数。
有效模型数为 1/sum(weight²)。
参考权重列在配置的 `reference_weights` 中。
代码重算权重，参考值只用于对照。

```text
p0 = sum(weight×p_model)
delta = sqrt(sum(weight×(p_model−p0)²))
delta_ind = abs(p0−sum(weight×p_H×p_Q))
```

## 概率校准

校准标签是仿真目标是否满足联合事件。
拟合采用带脊惩罚的单调 beta 映射。

```text
mapped = sigmoid(alpha + beta×ln(p0) − gamma×ln(1−p0))
P = (1−lambda)×p0 + lambda×mapped
penalty = ridge×sum((theta−[0,1,1])²)
```

概率计算的裁剪范围为 1e-6 至 1−1e-6。
α 限于 [−10,10]，β、γ 限于 [0,10]。
优化器为 L-BFGS-B，maxiter=500，ftol=1e-12，gtol=1e-8。
校准共五轮，从 0 起算。
第 0 轮是恒等映射，λ 固定为 0。
第 1 至 4 轮的脊惩罚依次为 8、4、2、1。
这四轮在校准拟合 family 上做五折交叉验证。
这四轮的 λ 从 {0,0.25,0.50,0.75,1} 中按 Brier 选择。
最小 Brier 的差在 1e-8 内时取较小 λ。
校准评估指标通过 2,000 次 family bootstrap 给出边界。
选轮按未达门数、归一化缺口、Brier、ECE、NLL、负 BSS、负 AUC 和轮次排序。
完整指标阈值及连续两轮改进不足的停止条件见 `code/calibrate.py` 与 `code/score.py`。

参考结果选中从 0 起算的第 3 轮，ridge=2，λ=0.5。
最终参数来自全部 50 个校准 family 的重拟合。
参考 θ 见配置的 `reference_calibrator.theta`。
代码重新选轮并重拟合，参考 θ 只用于对照。
参考校准状态为有条件通过，G_cal=0.85。
其核心点指标达到条件。
期望校准误差（ECE）的上界、Brier 技能分数（BSS）的下界未达门槛。
运行后见 `parameters.json` 的 `rounds` 中 `round_id=3` 的记录。
对应键为 `ece_u95`、`bss_l95`、`core_pass` 与 `all_pass`。
各项缺口见同一记录的 `failure_gaps`。

## 概率区间、分数与排名

执行 2,000 次概率 bootstrap。
每次抽取 Beta(k+0.5,240−k+0.5)，配合同序号的权重抽样。
校准器按全部校准 family 另做有放回 bootstrap。
校准器优化失败时使用全量重拟合参数，并记录失败次数。
概率 bootstrap 的 2.5% 与 97.5% 分位为 P_L、P_U。

```text
W = P_U−P_L
h = W/2
S = clip(100×(0.75×P+0.25×P_L)−20×h−10×delta
         −5×(1−G_cal)−5×(1−G_path),0,100)
```

G_path 为 1。process_factor 为 0。
工艺因子取常量 0，作为单独一列输出。
分数使用上式所列各项。
Q_clip 由裁剪率与边界质量构造，具体式见 `code/score.py`。
置信指标为 G_cal×Q_clip×clip(1−W/0.60,0,1)×clip(1−delta/0.30,0,1)。
排序键依次为分数降序、P_L 降序、P 降序、delta 升序、置信指标降序、候选编号升序。
percentile=100×(2048−rank)/2047。

| 档位 | 必须同时满足 |
|---|---|
| A | S≥75，P≥0.75，P_L≥0.60，W≤0.25 |
| B | S≥60，P≥0.60，P_L≥0.40，W≤0.35 |
| C | S≥40，P≥0.30 |
| D | 其余 |

从最高满足档位取值。最终档位等于基础档位。
参考表分布为 A=7、B=78、C=153、D=1810。
pi20 是 bootstrap 中进入前 20 的比例。
rank_q90 是 bootstrap 名次的 90% 分位。
loo_rank_max 是逐一删去进入集成的模型并重新归一化后的最差名次。
稳定标记要求 pi20≥0.50、rank_q90≤80 且 loo_rank_max≤100。
选入标记要求档位为 A 或 B，且 P_L≥0.40。

## 随机流与参考结果对照

bootstrap 种子由生成种子、采样名称和序号确定。
派生公式见 `code/numerics.py` 的 `seed32`。
模型拟合与候选预测种子已按整数写在配置中。
行编号保留 family 与行内序号的字典序。

概率 bootstrap 的分量按以下顺序排列：
`bayesian_multilevel`、`catboost`、`elastic_net`、`mixed_gp`、`random_forest`。
每个候选依次为五个分量抽取 Beta 变量。
随后取进入集成的四个分量，保持双精度数组布局与求和顺序。
零权重分量也消耗随机数，从而确定其余分量的抽样位置。
数值对照按零偏差检查，报告同时列出浮点位模式差异数。
已实跑环境与环境敏感性见 `DATA_GENERATION.md` 的“复现程度”。
