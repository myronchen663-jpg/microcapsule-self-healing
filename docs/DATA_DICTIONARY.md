# 数据字典

数值单元格保留表内精度。三个候选表按候选编号升序排列。
训练表保持生成顺序。所有连续值使用双精度。
区间端点与下面的数值范围均包含端点。
五个模型均有预测列；四个进入集成。mixed_gp 因区间覆盖不合格而权重为 0。

## training_data.csv

共 2,500 行、18 列。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `capsule_content_wt_pct` | 微胶囊质量分数 | wt% | 0.5 至 20.0 |
| `capsule_d50_um` | 胶囊粒径中位数 | µm | 30.0 至 450.0 |
| `heal_temperature_C` | 修复温度 | °C | 20.0 至 100.0 |
| `heal_time_h` | 修复时间 | h | 2.0 至 96.0 |
| `initial_crack_opening_um` | 初始裂纹开口 | µm | 5.0 至 250.0 |
| `healing_chemistry_family` | 修复化学体系 | 类别 | EPOXY_AMINE_DUAL_CAPSULE、ROMP_DCPD_METATHESIS、SOLVENT_ASSISTED_EPOXY |
| `interface_treatment_family` | 界面处理 | 类别 | SHELL_GRAFT_OR_COVALENT、SILANE_EPOXY、SILANE_AMINO、NONE_OR_UNTREATED |
| `syn_row_id` | 仿真行编号 | 无 | SYN::0001::001 至 SYN::0250::010 |
| `syn_scenario_family_id` | 仿真情景族；各划分间互斥 | 无 | SYN_FAMILY_0001 至 SYN_FAMILY_0250 |
| `evidence_label` | 仿真证据标签，保留 SYN | 无 | SYN |
| `data_origin` | 数据来源标签，保留 SYNTHETIC_PRIMARY | 无 | SYNTHETIC_PRIMARY |
| `eta_k_pct` | 修复效率；修复后与原始断裂韧性之比的百分数 | % | -10.0 至 135.58518262798728 |
| `eta_k_mean_pct` | 修复效率的无噪均值，经支撑域裁剪 | % | -8.097749956375763 至 125.90745461986381 |
| `eta_k_aleatoric_sd_pct` | 修复效率抽样噪声标准差 | 百分点 | 4.500885414812195 至 8.906760911695233 |
| `strength_penalty_pct` | 原始强度折损 | % | -4.252362288958209 至 24.146887191376678 |
| `strength_penalty_mean_pct` | 强度折损的无噪均值，经支撑域裁剪 | % | -0.6636895408694237 至 20.938778233022635 |
| `strength_penalty_aleatoric_sd_pct` | 强度折损抽样噪声标准差 | 百分点 | 1.6 |
| `split` | 训练、校准拟合、校准评估或测试分区 | 类别 | test、train、calibration_eval、calibration_fit |

## candidates.csv

共 2,048 行、8 列。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `candidate_id` | 候选编号；三个候选表的连接键 | 无 | CANDIDATE_00001 至 CANDIDATE_02048 |
| `capsule_content_wt_pct` | 微胶囊质量分数 | wt% | 0.50721279110335 至 19.980616319357832 |
| `capsule_d50_um` | 胶囊粒径中位数 | µm | 30.074795169108587 至 448.93121523421905 |
| `heal_temperature_C` | 修复温度 | °C | 20.05817573946425 至 99.94908945219171 |
| `heal_time_h` | 修复时间 | h | 2.00033821046308 至 95.98430463449664 |
| `initial_crack_opening_um` | 初始裂纹开口 | µm | 5.002580882693803 至 249.67590297641524 |
| `healing_chemistry_family` | 修复化学体系 | 类别 | ROMP_DCPD_METATHESIS、EPOXY_AMINE_DUAL_CAPSULE、SOLVENT_ASSISTED_EPOXY |
| `interface_treatment_family` | 界面处理 | 类别 | NONE_OR_UNTREATED、SILANE_AMINO、SILANE_EPOXY、SHELL_GRAFT_OR_COVALENT |

## reference_predictions.csv

共 2,048 行、31 列。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `candidate_id` | 候选编号；三个候选表的连接键 | 无 | CANDIDATE_00001 至 CANDIDATE_02048 |
| `bayesian_multilevel__eta_prediction` | bayesian_multilevel 的修复效率预测抽样均值，经支撑域裁剪 | % | 8.167628398423911 至 72.7412835601086 |
| `bayesian_multilevel__eta_lower90` | bayesian_multilevel 的修复效率90% 区间下界，经支撑域裁剪 | % | -10.0 至 2.96140942772589 |
| `bayesian_multilevel__eta_upper90` | bayesian_multilevel 的修复效率90% 区间上界，经支撑域裁剪 | % | 75.42579450006893 至 140.0 |
| `bayesian_multilevel__penalty_prediction` | bayesian_multilevel 的强度折损预测抽样均值，经支撑域裁剪 | % | 4.835087838919872 至 14.805329321021336 |
| `bayesian_multilevel__penalty_lower90` | bayesian_multilevel 的强度折损90% 区间下界，经支撑域裁剪 | % | -5.0 至 5.790349035165412 |
| `bayesian_multilevel__penalty_upper90` | bayesian_multilevel 的强度折损90% 区间上界，经支撑域裁剪 | % | 12.991126657731444 至 33.8315430901622 |
| `catboost__eta_prediction` | catboost 的修复效率预测抽样均值，经支撑域裁剪 | % | -10.0 至 101.79399552176402 |
| `catboost__eta_lower90` | catboost 的修复效率90% 区间下界，经支撑域裁剪 | % | -10.0 至 73.26368036639444 |
| `catboost__eta_upper90` | catboost 的修复效率90% 区间上界，经支撑域裁剪 | % | 16.682223196462097 至 131.8391137812451 |
| `catboost__penalty_prediction` | catboost 的强度折损预测抽样均值，经支撑域裁剪 | % | -0.4879822936421421 至 20.6556639831725 |
| `catboost__penalty_lower90` | catboost 的强度折损90% 区间下界，经支撑域裁剪 | % | -5.0 至 15.842796639072699 |
| `catboost__penalty_upper90` | catboost 的强度折损90% 区间上界，经支撑域裁剪 | % | 4.58417924694653 至 25.4685313272723 |
| `elastic_net__eta_prediction` | elastic_net 的修复效率预测抽样均值，经支撑域裁剪 | % | -3.3669655570568056 至 80.17798193021216 |
| `elastic_net__eta_lower90` | elastic_net 的修复效率90% 区间下界，经支撑域裁剪 | % | -10.0 至 19.400169883447063 |
| `elastic_net__eta_upper90` | elastic_net 的修复效率90% 区间上界，经支撑域裁剪 | % | 60.534923328661336 至 140.0 |
| `elastic_net__penalty_prediction` | elastic_net 的强度折损预测抽样均值，经支撑域裁剪 | % | -0.26608186025179004 至 20.278449084217574 |
| `elastic_net__penalty_lower90` | elastic_net 的强度折损90% 区间下界，经支撑域裁剪 | % | -5.0 至 15.185054143342967 |
| `elastic_net__penalty_upper90` | elastic_net 的强度折损90% 区间上界，经支撑域裁剪 | % | 4.5074592879162445 至 25.37184402509218 |
| `mixed_gp__eta_prediction` | mixed_gp 的修复效率预测抽样均值，经支撑域裁剪 | % | -9.463480323548051 至 120.43334438940555 |
| `mixed_gp__eta_lower90` | mixed_gp 的修复效率90% 区间下界，经支撑域裁剪 | % | -10.0 至 99.25382515392036 |
| `mixed_gp__eta_upper90` | mixed_gp 的修复效率90% 区间上界，经支撑域裁剪 | % | -2.8346993631334794 至 140.0 |
| `mixed_gp__penalty_prediction` | mixed_gp 的强度折损预测抽样均值，经支撑域裁剪 | % | -0.2687249154705904 至 19.727899033537096 |
| `mixed_gp__penalty_lower90` | mixed_gp 的强度折损90% 区间下界，经支撑域裁剪 | % | -5.0 至 13.978318971586514 |
| `mixed_gp__penalty_upper90` | mixed_gp 的强度折损90% 区间上界，经支撑域裁剪 | % | 2.806315753031825 至 26.98103161597203 |
| `random_forest__eta_prediction` | random_forest 的修复效率预测抽样均值，经支撑域裁剪 | % | -6.132992535251725 至 96.89300307870884 |
| `random_forest__eta_lower90` | random_forest 的修复效率90% 区间下界，经支撑域裁剪 | % | -10.0 至 67.30872952023508 |
| `random_forest__eta_upper90` | random_forest 的修复效率90% 区间上界，经支撑域裁剪 | % | 19.27276123089212 至 140.0 |
| `random_forest__penalty_prediction` | random_forest 的强度折损预测抽样均值，经支撑域裁剪 | % | 0.2840625573135539 至 19.033921768531506 |
| `random_forest__penalty_lower90` | random_forest 的强度折损90% 区间下界，经支撑域裁剪 | % | -5.0 至 13.923749619472785 |
| `random_forest__penalty_upper90` | random_forest 的强度折损90% 区间上界，经支撑域裁剪 | % | 4.288693982862893 至 30.62239675523243 |

## reference_scores.csv

共 2,048 行、40 列。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `candidate_id` | 候选编号；三个候选表的连接键 | 无 | CANDIDATE_00001 至 CANDIDATE_02048 |
| `P_cal` | 校准后的联合事件概率 | 无 | 0.017484406281195214 至 0.8344408066032034 |
| `P_L` | 校准概率 bootstrap 的下分位点 | 无 | 0.011481057057401782 至 0.7673890768948873 |
| `P_U` | 校准概率 bootstrap 的上分位点 | 无 | 0.025738801822456855 至 0.9031387406655591 |
| `S` | 综合分数 | 分 | 0.11203059756544975 至 77.28262994911566 |
| `grade` | 最终分档 | 类别 | D、B、C、A |
| `rank` | 确定性排序的名次 | 名次 | 1 至 2048 |
| `percentile` | 按名次换算的百分位 | % | 0.0 至 100.0 |
| `pi20` | bootstrap 排名进入前 20 的比例 | 无 | 0.0 至 1.0 |
| `rank_q90` | bootstrap 名次的 90% 分位 | 名次 | 4.0 至 2048.0 |
| `loo_rank_max` | 逐一删去一个进入集成的模型后的最差名次 | 名次 | 2 至 2048 |
| `stable_flag` | 满足稳定性条件为 1，否则为 0 | 无 | 0 至 1 |
| `eligible_flag` | 满足选入条件为 1，否则为 0 | 无 | 0 至 1 |
| `p0` | 校准前的加权联合事件概率 | 无 | 0.026424637165826947 至 0.8521244486645084 |
| `P` | 与 P_cal 相同的概率数值 | 无 | 0.017484406281195214 至 0.8344408066032034 |
| `W` | 概率区间全宽 P_U−P_L | 无 | 0.01391683050129146 至 0.1809366615490155 |
| `h` | 概率区间半宽 W/2 | 无 | 0.00695841525064573 至 0.09046833077450775 |
| `delta` | 进入集成的四个模型概率的加权标准差 | 无 | 0.017616009104662468 至 0.45077442909852644 |
| `delta_ind` | p0 与加权边际概率乘积之差的绝对值 | 无 | 7.550857773402919e-06 至 0.01476231827736571 |
| `clip_rate_max` | 进入集成的模型、端点的最大抽样裁剪比例 | 无 | 0.1875 至 0.8083333333333333 |
| `boundary_mass_max` | 进入集成的模型、端点的最大支撑边界质量 | 无 | 0.1875 至 0.8083333333333333 |
| `Q_clip` | 由裁剪率和边界质量构造的因子 | 无 | 0.27380952380952384 至 1.0 |
| `G_cal` | 校准状态因子 | 无 | 0.85 |
| `G_path` | 概率计算路径因子 | 无 | 1.0 |
| `probability_confidence` | 校准、裁剪、区间宽度和模型分歧共同构造的置信指标 | 无 | 0.0 至 0.6513758394805504 |
| `base_grade` | 由分数、概率和区间得到的基础分档；与 grade 相同 | 类别 | D、B、C、A |
| `k_joint__bayesian_multilevel` | bayesian_multilevel 的联合事件成立次数 | 次 | 36 至 91 |
| `p_model__bayesian_multilevel` | bayesian_multilevel 的平滑联合事件概率 | 无 | 0.15145228215767634 至 0.3796680497925311 |
| `k_joint__catboost` | catboost 的联合事件成立次数 | 次 | 0 至 240 |
| `p_model__catboost` | catboost 的平滑联合事件概率 | 无 | 0.002074688796680498 至 0.9979253112033195 |
| `k_joint__elastic_net` | elastic_net 的联合事件成立次数 | 次 | 0 至 170 |
| `p_model__elastic_net` | elastic_net 的平滑联合事件概率 | 无 | 0.002074688796680498 至 0.7074688796680498 |
| `k_joint__mixed_gp` | mixed_gp 的联合事件成立次数 | 次 | 0 至 237 |
| `p_model__mixed_gp` | mixed_gp 的平滑联合事件概率 | 无 | 0.002074688796680498 至 0.9854771784232366 |
| `k_joint__random_forest` | random_forest 的联合事件成立次数 | 次 | 0 至 240 |
| `p_model__random_forest` | random_forest 的平滑联合事件概率 | 无 | 0.002074688796680498 至 0.9979253112033195 |
| `calibration_round` | 从 0 开始计数的校准轮次 | 无 | 3 |
| `calibration_ridge` | 最终校准器的脊惩罚强度 | 无 | 2.0 |
| `process_factor` | 工艺因子；常量 0 | 无 | 0.0 |
| `calibration_lambda_mix` | 校准映射与恒等映射的混合系数 | 无 | 0.5 |

## literature_anchor.csv

共 32 行、5 列。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `paper_id` | `literature_sources.csv` 中的条目编号；两表以此连接 | 无 | P1、P10、P12、P13、P14、P17、P28 |
| `eta_k_pct` | 修复效率；修复后与原始断裂韧性之比的百分数 | % | 0 至 106.8 |
| `citation_title` | 文献题名 | 文本 | 见文献表逐行内容 |
| `publication_year` | 发表年份 | 年 | 2001 至 2025 |
| `publication_doi` | 文献 DOI | 文本 | 见文献表逐行内容 |


## literature_sources.csv

共 30 行、4 列。
此表列出文献批次的全部条目。
`paper_id` 与 `literature_anchor.csv` 使用同一套编号。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `paper_id` | 本清单的条目编号；与锚点表的连接键 | 无 | P1 至 P30 |
| `citation_title` | 文献题名 | 文本 | 见本表逐行内容 |
| `publication_year` | 发表年份 | 年 | 2001 至 2025 |
| `publication_doi` | 文献 DOI | 文本 | 见本表逐行内容 |

## literature_design_conditions.csv

共 132 行、9 列。
每行是一条文献设计条件，`paper_id` 连接文献条目。
空单元格表示缺失，`UNKNOWN` 保留为类别值。
各数值列的范围按有限数值计算。

| 列名 | 含义 | 单位 | 取值或范围 |
|---|---|---|---|
| `condition_id` | 设计条件编号；条目编号加条目内行序号，从 1 开始 | 无 | 本表内唯一 |
| `paper_id` | `literature_sources.csv` 中的条目编号 | 无 | P1 至 P30 |
| `capsule_content_wt_pct` | 微胶囊质量分数 | wt% | 0 至 20 |
| `capsule_size_proxy_um` | 胶囊尺寸代理值 | µm | 39.5 至 460 |
| `heal_temperature_C` | 修复温度 | °C | −10 至 142 |
| `heal_time_h` | 修复时间 | h | 0.0556 至 48 |
| `initial_crack_opening_um` | 初始裂纹开口 | µm | 20 至 25 |
| `healing_chemistry_family` | 修复化学体系 | 类别 | 见本表逐行内容 |
| `interface_treatment_family` | 界面处理 | 类别 | 见本表逐行内容 |

这张表记录的是尺寸代理值，粒径量级参照它。
用 D50 表示仿真输入属于建模设定。
初始裂纹开口的输入范围在文献范围基础上外扩，以覆盖更宽的设计空间。
输入设定与文献范围的对照见 `ASSUMPTIONS_AND_SOURCES.md`。
