# 数据生成与复现

训练数据是仿真数据，由生成器产生。
生成器使用文献锚点与建模设定的机理项。
它生成 250 个仿真 family，每个 family 含 10 行。
两端点的噪声独立抽样。

## 文献锚点

`literature_anchor.csv` 含 32 个修复效率值，来自七个文献条目。
生成器直接计算这列数据的中位数。
排序后的中间两值是 51.7 和 60，中位数为 55.85%。
各条目的行数为 P1：1、P10：4、P12：6、P13：7、P14：4、P17：8、P28：2。
本表即用于锚点的全部 32 个测量值。
生成脚本遇到空表或非有限值会报错。

## 生成公式

记 c 为含量，d 为粒径，w 为裂纹开口，T 为温度，t 为时间。
下标 chem 与 iface 分别表示化学体系和界面处理。
参数均在 `code/generator_config.json` 中。

```text
A = 1 − exp(−c/4)
B = exp(−0.5 × [ln((d/w)/1.8)/0.85]²)
activation = logistic((T−T_chem)/12 + ln(t/t_chem)/1.1)
anchor_shift = 0.25 × (median(literature_anchor.eta_k_pct) − 70)
mu_eta = 7 + 112×A×B×activation + offset_eta_chem + effect_eta_iface
         + anchor_shift + family_eta − 1.5×max(c−15,0)
sd_eta = 4.5 + 0.035×abs(mu_eta)
mu_penalty = 0.82×c + 0.7×d/100 + offset_penalty_chem
             + effect_penalty_iface + family_penalty
sd_penalty = 1.6
```

logistic 的指数输入先裁到 −35 至 35。
比值下限为 1e-6，时间保护下限为 0.1 h。
每行分别从两个正态分布抽取目标值。
修复效率裁到 −10 至 140%，强度折损裁到 −5 至 40%。
无噪均值列也做相同裁剪。
噪声标准差由裁剪前的均值计算。

## family 与行内变化

先从允许的化学体系与界面处理组合抽样。
每个组合的权重等于该化学体系的配置概率，再对全部组合归一化。
含量与温度中心均匀抽样；粒径、时间和开口中心按对数均匀抽样。
family 的修复效率偏移服从标准差 4 的正态分布。
强度折损偏移的标准差为 1。
同一 family 内的含量、温度加上标准差为域宽 0.07 倍的噪声。
粒径、时间和开口乘以 exp(N(0,0.16²))。
行内输入随后裁回配置中的设计域。

## 种子、划分与浮点读回

生成种子为 20260809。
一个 `numpy.default_rng` 按 family、行及端点顺序消耗随机数。
family 划分种子为 2005808381。
校准 family 再划分种子为 2096815078。
候选网格种子为 1623432794。
`generate_candidates` 按配置重新生成候选。
流水线先逐位核对候选，再读取已有候选表用于预测。
候选按九个允许组合分别做拉丁超立方抽样（Latin hypercube）。
组合顺序见配置中的 `allowed_chemistry_interface_pairs`。
每个组合使用 `scipy.stats.qmc.LatinHypercube` 的默认设置。
抽样维度按 `design_space` 中五个输入的顺序排列。
前五个组合各 228 行，后四个各 227 行。
每个组合的种子为网格种子加从 0 起算的组合序号。
粒径、时间和开口使用对数坐标，含量和温度使用线性坐标。
设单位抽样为 u，范围端点为 lower、upper。
线性变换为 lower+u×(upper−lower)。
对数变换为 exp(ln(lower)+u×(ln(upper)−ln(lower)))。
按组合顺序拼接各段，再按行顺序编候选编号。
编号从 `CANDIDATE_00001` 到 `CANDIDATE_02048`。
重新生成的候选写入 `generated_candidates.csv`。
候选逐位对照见 `candidate_generation_comparison.json`。
同一对照也写入 `comparison.csv` 与 `comparison.json`。
全部模型种子与候选预测种子见配置中的 `model_seeds` 和 `candidate_draw_seeds`。

包内输入 CSV 使用 `float_precision="round_trip"` 读取。
训练后写出的测试预测 CSV 用 pandas 默认浮点解析器读回，再计算权重。
流水线先比较重新生成的内存帧与训练 CSV。
比较结果写入输出目录的 `generation_comparison.json`。
报告同时给出数值偏差和浮点位模式差异数。
本机核对中，生成帧与 CSV 读回帧的数值逐位一致。
模型的训练输入为 CSV 读回的帧。

## 复现程度

已实跑核对的环境:macOS arm64、Python 3.11,依赖版本见 `code/requirements.txt`。在其他环境运行时,可自行调整依赖版本。每次运行输出逐项偏差表,用来查看调整后的差别。
本机使用的 Python 完整版本为 3.11.15。
依赖使用 `code/requirements.txt` 中的固定版本，计算保持单线程。
关键版本为 NumPy 2.4.6、pandas 2.3.3、SciPy 1.17.1。
scikit-learn 为 1.9.0，CatBoost 为 1.2.10。
PyMC 为 5.28.5，PyTensor 为 2.38.3。

生成数据与训练 CSV 的浮点读回值逐位一致。
重新生成的候选与候选 CSV 逐位一致。
五个模型的全部候选点预测、90% 区间与联合事件计数均与参考逐位一致。
集成点权重与配置中的对照值逐位一致。
最终校准器的点参数与配置中的对照值数值一致。
概率区间、分数、排名、分档与各稳定性列的最大偏差和不符数均为 0。
校准器重抽样中有 2 次优化失败。
这些行按方法规则使用全量重拟合参数。
运行后见 `calibrator_bootstrap.csv` 的 `bootstrap_fit_fallback` 列。
该列为 1 的行数即失败次数。

校准器的重抽样拟合对输入浮点数的末位敏感。
测试预测的读回方式会改变权重与校准概率的末位。
这类变化可改变优化器的停止分支，并传到区间和分数。
因此，复现需保留测试预测的读回方式、分量顺序和数组布局。

每次运行输出的 `comparison.csv` 与 `comparison.json` 给出逐项偏差。
`table` 与 `column` 定位核对量。
`max_abs_difference` 记录最大数值偏差，`mismatch_count` 记录不符数。
`bitwise_difference_count` 记录已核对量的浮点位模式差异数。
