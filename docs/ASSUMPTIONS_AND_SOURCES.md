# 假设与文献来源

本数据由程序「生成器」仿真产生,生成器在阅读一批微胶囊自修复材料文献后设计。

- **文献数据**确定锚点。锚点是一个参照值,生成器用它校正仿真修复效率的整体水平。锚点取修复效率的中位数 55.85%,来自 7 篇文献的 32 个测量值。
- **文献范围**确定 5 个输入取值范围的量级。这 5 个输入是:胶囊含量、胶囊粒径、修复温度、修复时间和初始裂纹开口。胶囊粒径下限、修复时间上限和初始裂纹开口的取值范围,在文献范围基础上向外放宽。这样放宽,是为了覆盖更宽的设计空间。
- **文献规律**确定机理项的方向。机理项指生成器公式中描述物理规律的几个部分。例如,胶囊含量越高,可用的修复剂越多,并逐渐饱和。胶囊粒径要与初始裂纹开口匹配。
- **建模设定**确定机理项的具体函数和生成器公式中各系数的数值。

## 文献数据计算

锚点中位数的来源分类为「文献数据计算」。
以下测量保存在 `data/literature_anchor.csv`。
文献条目见 `data/literature_sources.csv`。

| 条目 | 题名 | DOI | 测量行数 |
|---|---|---|---|
| P1 | Autonomic Healing of Polymer Composites | 10.1038/35057232 | 1 |
| P10 | Self-Healing Polymeric Materials Using Epoxy/Mercaptan as the Healant | 10.1021/ma800028d | 4 |
| P12 | Self-Healing Epoxy Composite with Heat-Resistant Healant | 10.1021/am201182j | 6 |
| P13 | Self-Healing Thermoset Using Encapsulated Epoxy-Amine Healing Chemistry | 10.1016/j.polymer.2011.12.005 | 7 |
| P14 | Effects of Dual Component Microcapsules of Resin and Curing Agent on the Self-Healing Efficiency of Epoxy | 10.1016/j.compositesb.2013.06.006 | 4 |
| P17 | Self-Healing of a High Temperature Cured Epoxy Using Poly(dimethylsiloxane) Chemistry | 10.1016/j.polymer.2010.06.050 | 8 |
| P28 | Self-Healing Imidazole-Cured Epoxy Using Microencapsulated Epoxy-Amine Chemistry | 10.3390/polym17172391 | 2 |

这组测量值的中位数为 55.85%。
把该统计量用于仿真截距属于建模设定。

## 设定值与文献表中的范围或类别

范围、记录数和类别次数均由 `data/literature_design_conditions.csv` 算出。
这张表含 132 条设计条件。
各数值列按有限数值计算最小值、最大值与个数。
类别按行计数，同一论文的不同条件各计一次。
范围用于选择输入量级，各范围均包含端点。

| 输入 | 设定值 | 文献表中的范围 | 数值记录数 | 来源分类与说明 |
|---|---|---|---|---|
| 胶囊含量 | 0.5 至 20 wt% | 0 至 20 wt% | 87 | 参照文献范围设定；下限与上限均取在文献范围内 |
| 胶囊粒径 | 30 至 450 µm | 尺寸代理值 39.5 至 460 µm | 53 | 参照文献范围设定；下限在文献范围基础上外扩至 30 µm，以覆盖更宽的设计空间；上限取在文献范围内 |
| 修复温度 | 20 至 100 °C | −10 至 142 °C | 55 | 参照文献范围设定；下限与上限均取在文献范围内 |
| 修复时间 | 2 至 96 h | 0.0556 至 48 h | 55 | 参照文献范围设定；下限取在文献范围内；上限在文献范围基础上外扩至 96 h，以覆盖更宽的设计空间 |
| 初始裂纹开口 | 5 至 250 µm | 20 至 25 µm | 9 | 参照文献范围设定；下限与上限均在文献范围基础上外扩，以覆盖更宽的设计空间 |

这张表记录的是尺寸代理值，粒径量级参照它。
用 D50 表示输入属于建模设定。
下表列出配置使用的类别。

| 输入 | 类别 | 文献表中出现次数 | 来源分类 |
|---|---|---|---|
| 化学体系 | `ROMP_DCPD_METATHESIS` | 34 | 参照文献范围设定 |
| 化学体系 | `EPOXY_AMINE_DUAL_CAPSULE` | 11 | 参照文献范围设定 |
| 化学体系 | `SOLVENT_ASSISTED_EPOXY` | 4 | 参照文献范围设定 |
| 界面处理 | `NONE_OR_UNTREATED` | 65 | 参照文献范围设定 |
| 界面处理 | `SILANE_AMINO` | 0 | 建模设定 |
| 界面处理 | `SILANE_EPOXY` | 0 | 建模设定 |
| 界面处理 | `SHELL_GRAFT_OR_COVALENT` | 0 | 建模设定 |

## 参照文献规律的机理项

可用量项的增加及饱和方向参照文献规律。
P7 报告：单位裂纹面积得到的修复剂质量，与胶囊直径和胶囊质量分数的乘积成正比（文献 PDF 第 3 页，公式 (5)）。
P24 报告：定向微胶囊含量高于 5 wt% 时，按修复面积与损伤面积之比计的修复率达到饱和（文献 PDF 第 7 页，图 6a）。
桥接项的尺寸匹配方向参照文献规律。
P7 报告：送达的修复剂足以填满裂纹体积时，修复效果最好（文献 PDF 第 4 页，第 4.1 节）。
P7 还报告：胶囊尺寸和含量可按裂纹尺寸选取（文献 PDF 第 7 至 8 页，第 4.2 节与第 5 节）。
题名与 DOI 见 `data/literature_sources.csv` 的同名条目。
具体函数和系数属于建模设定。
两项公式见 `DATA_GENERATION.md` 中的 A 与 B。

## 配置项的来源分类

配置路径与取值见下表。
数值种子控制随机抽样。
`reference_weights` 与 `reference_calibrator` 保存仿真流程的计算结果。
这两组数值用于运行结果对照,来源分类记为「对照值」。

| 配置项 | 取值 | 来源分类 |
|---|---|---|
| `design_space.capsule_content_wt_pct` | `[0.5, 20.0]` | 参照文献范围设定 |
| `design_space.capsule_d50_um` | `[30.0, 450.0]` | 参照文献范围设定 |
| `design_space.heal_temperature_C` | `[20.0, 100.0]` | 参照文献范围设定 |
| `design_space.heal_time_h` | `[2.0, 96.0]` | 参照文献范围设定 |
| `design_space.initial_crack_opening_um` | `[5.0, 250.0]` | 参照文献范围设定 |
| `chemistries.ROMP_DCPD_METATHESIS.probability` | `0.4` | 建模设定 |
| `chemistries.ROMP_DCPD_METATHESIS.activation_temperature_C` | `38.0` | 建模设定 |
| `chemistries.ROMP_DCPD_METATHESIS.activation_time_h` | `18.0` | 建模设定 |
| `chemistries.ROMP_DCPD_METATHESIS.eta_offset_pct` | `5.0` | 建模设定 |
| `chemistries.ROMP_DCPD_METATHESIS.penalty_offset_pct` | `0.5` | 建模设定 |
| `chemistries.EPOXY_AMINE_DUAL_CAPSULE.probability` | `0.35` | 建模设定 |
| `chemistries.EPOXY_AMINE_DUAL_CAPSULE.activation_temperature_C` | `52.0` | 建模设定 |
| `chemistries.EPOXY_AMINE_DUAL_CAPSULE.activation_time_h` | `24.0` | 建模设定 |
| `chemistries.EPOXY_AMINE_DUAL_CAPSULE.eta_offset_pct` | `1.0` | 建模设定 |
| `chemistries.EPOXY_AMINE_DUAL_CAPSULE.penalty_offset_pct` | `1.5` | 建模设定 |
| `chemistries.SOLVENT_ASSISTED_EPOXY.probability` | `0.25` | 建模设定 |
| `chemistries.SOLVENT_ASSISTED_EPOXY.activation_temperature_C` | `32.0` | 建模设定 |
| `chemistries.SOLVENT_ASSISTED_EPOXY.activation_time_h` | `36.0` | 建模设定 |
| `chemistries.SOLVENT_ASSISTED_EPOXY.eta_offset_pct` | `-4.0` | 建模设定 |
| `chemistries.SOLVENT_ASSISTED_EPOXY.penalty_offset_pct` | `-0.5` | 建模设定 |
| `interfaces.NONE_OR_UNTREATED.eta_effect_pct` | `0.0` | 建模设定 |
| `interfaces.NONE_OR_UNTREATED.penalty_effect_pct` | `0.8` | 建模设定 |
| `interfaces.SILANE_AMINO.eta_effect_pct` | `4.0` | 建模设定 |
| `interfaces.SILANE_AMINO.penalty_effect_pct` | `-1.0` | 建模设定 |
| `interfaces.SILANE_EPOXY.eta_effect_pct` | `3.0` | 建模设定 |
| `interfaces.SILANE_EPOXY.penalty_effect_pct` | `-0.8` | 建模设定 |
| `interfaces.SHELL_GRAFT_OR_COVALENT.eta_effect_pct` | `5.0` | 建模设定 |
| `interfaces.SHELL_GRAFT_OR_COVALENT.penalty_effect_pct` | `-0.4` | 建模设定 |
| `allowed_chemistry_interface_pairs[0]` | `["ROMP_DCPD_METATHESIS", "NONE_OR_UNTREATED"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[1]` | `["ROMP_DCPD_METATHESIS", "SILANE_AMINO"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[2]` | `["ROMP_DCPD_METATHESIS", "SILANE_EPOXY"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[3]` | `["EPOXY_AMINE_DUAL_CAPSULE", "NONE_OR_UNTREATED"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[4]` | `["EPOXY_AMINE_DUAL_CAPSULE", "SILANE_AMINO"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[5]` | `["EPOXY_AMINE_DUAL_CAPSULE", "SHELL_GRAFT_OR_COVALENT"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[6]` | `["SOLVENT_ASSISTED_EPOXY", "NONE_OR_UNTREATED"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[7]` | `["SOLVENT_ASSISTED_EPOXY", "SILANE_EPOXY"]` | 建模设定 |
| `allowed_chemistry_interface_pairs[8]` | `["SOLVENT_ASSISTED_EPOXY", "SHELL_GRAFT_OR_COVALENT"]` | 建模设定 |
| `mechanism.eta_intercept_pct` | `7.0` | 建模设定 |
| `mechanism.eta_scale_pct` | `112.0` | 建模设定 |
| `mechanism.content_half_saturation_wt_pct` | `4.0` | 建模设定 |
| `mechanism.content_overload_start_wt_pct` | `15.0` | 建模设定 |
| `mechanism.content_overload_slope_pct_per_wt_pct` | `1.5` | 建模设定 |
| `mechanism.ideal_d50_to_crack_ratio` | `1.8` | 建模设定 |
| `mechanism.log_ratio_width` | `0.85` | 建模设定 |
| `mechanism.activation_temperature_width_C` | `12.0` | 建模设定 |
| `mechanism.activation_log_time_width` | `1.1` | 建模设定 |
| `mechanism.anchor_reference_eta_pct` | `70.0` | 建模设定 |
| `mechanism.anchor_intercept_weight` | `0.25` | 建模设定 |
| `mechanism.family_eta_sd_pct` | `4.0` | 建模设定 |
| `mechanism.eta_noise_floor_pct` | `4.5` | 建模设定 |
| `mechanism.eta_noise_fraction` | `0.035` | 建模设定 |
| `mechanism.penalty_content_slope` | `0.82` | 建模设定 |
| `mechanism.penalty_size_slope_per_100um` | `0.7` | 建模设定 |
| `mechanism.penalty_family_sd_pct` | `1.0` | 建模设定 |
| `mechanism.penalty_noise_sd_pct` | `1.6` | 建模设定 |
| `plausibility.eta_k_pct` | `[-10.0, 140.0]` | 建模设定 |
| `plausibility.strength_penalty_pct` | `[-5.0, 40.0]` | 建模设定 |
| `sampling.seed` | `20260809` | 建模设定 |
| `sampling.n_families` | `250` | 建模设定 |
| `sampling.rows_per_family` | `10` | 建模设定 |
| `sampling.family_split_seed` | `2005808381` | 建模设定 |
| `sampling.calibration_split_seed` | `2096815078` | 建模设定 |
| `sampling.candidate_grid_seed` | `1623432794` | 建模设定 |
| `sampling.candidate_rows` | `2048` | 建模设定 |
| `sampling.predictive_draws` | `240` | 建模设定 |
| `sampling.weight_bootstraps` | `2000` | 建模设定 |
| `sampling.calibration_bootstraps` | `2000` | 建模设定 |
| `sampling.rank_bootstraps` | `2000` | 建模设定 |
| `model_seeds.eta_k_pct.bayesian_multilevel` | `686458851` | 建模设定 |
| `model_seeds.eta_k_pct.catboost` | `25571775` | 建模设定 |
| `model_seeds.eta_k_pct.elastic_net` | `815680487` | 建模设定 |
| `model_seeds.eta_k_pct.random_forest` | `526307936` | 建模设定 |
| `model_seeds.eta_k_pct.mixed_gp` | `1950442060` | 建模设定 |
| `model_seeds.strength_penalty_pct.bayesian_multilevel` | `248715638` | 建模设定 |
| `model_seeds.strength_penalty_pct.catboost` | `1193694087` | 建模设定 |
| `model_seeds.strength_penalty_pct.elastic_net` | `428145381` | 建模设定 |
| `model_seeds.strength_penalty_pct.random_forest` | `12132905` | 建模设定 |
| `model_seeds.strength_penalty_pct.mixed_gp` | `783589340` | 建模设定 |
| `candidate_draw_seeds.bayesian_multilevel.eta_k_pct` | `1660120756` | 建模设定 |
| `candidate_draw_seeds.bayesian_multilevel.strength_penalty_pct` | `1660120757` | 建模设定 |
| `candidate_draw_seeds.catboost.eta_k_pct` | `1660120856` | 建模设定 |
| `candidate_draw_seeds.catboost.strength_penalty_pct` | `1660120857` | 建模设定 |
| `candidate_draw_seeds.elastic_net.eta_k_pct` | `1660120956` | 建模设定 |
| `candidate_draw_seeds.elastic_net.strength_penalty_pct` | `1660120957` | 建模设定 |
| `candidate_draw_seeds.random_forest.eta_k_pct` | `1660121156` | 建模设定 |
| `candidate_draw_seeds.random_forest.strength_penalty_pct` | `1660121157` | 建模设定 |
| `candidate_draw_seeds.mixed_gp.eta_k_pct` | `1660121056` | 建模设定 |
| `candidate_draw_seeds.mixed_gp.strength_penalty_pct` | `1660121057` | 建模设定 |
| `model_profile.bootstrap_models` | `6` | 建模设定 |
| `model_profile.rf_trees` | `250` | 建模设定 |
| `model_profile.catboost_iterations` | `280` | 建模设定 |
| `model_profile.catboost_ensemble` | `3` | 建模设定 |
| `model_profile.advi_steps` | `1500` | 建模设定 |
| `model_profile.posterior_draws` | `300` | 建模设定 |
| `model_profile.gp_max_rows` | `600` | 建模设定 |
| `reference_weights.bayesian_multilevel` | `0.1348151350066195` | 对照值 |
| `reference_weights.catboost` | `0.39709877384434517` | 对照值 |
| `reference_weights.elastic_net` | `0.1691654494543321` | 对照值 |
| `reference_weights.random_forest` | `0.29892064169470295` | 对照值 |
| `reference_weights.mixed_gp` | `0.0` | 对照值 |
| `reference_calibrator.theta` | `[0.18703841965511422, 1.365735727509419, 0.7983951373349465]` | 对照值 |
| `reference_calibrator.ridge` | `"2.0"` | 对照值 |
| `reference_calibrator.lambda_mix` | `0.5` | 对照值 |
| `reference_calibrator.round` | `3` | 对照值 |

## 结构与建模假设

| 假设 | 来源分类 |
|---|---|
| 250 个 family，每个 10 行；family 中心与行内抖动的采样分布 | 建模设定 |
| 加性抖动系数 0.07、乘性抖动标准差 0.16 | 建模设定 |
| 可用量项的具体函数与系数；增加及饱和方向参照文献规律 | 建模设定 |
| 桥接项的具体函数与系数；尺寸匹配方向参照文献规律 | 建模设定 |
| 温度与时间活化函数、过载函数、强度折损函数 | 建模设定 |
| 粒径中位数作为仿真输入；界面处理效应作为对先验敏感的情景因子 | 建模设定 |
| family 偏移采用正态分布；两端点观测噪声独立；均值和观测值按支撑域裁剪 | 建模设定 |
| 文献中位数转为截距偏移；参考值 70、权重 0.25 | 建模设定 |
| 按 family 划分训练、校准与测试；每族抽一行校准区间 | 建模设定 |
| 五个模型的结构、先验、超参数、随机种子和预测噪声 | 建模设定 |
| 区间覆盖资格规则决定哪些模型进入集成 | 建模设定 |
| 新候选的贝叶斯预测省略训练 family 随机效应 | 建模设定 |
| 修复效率阈值 60%、强度折损阈值 15% | 建模设定 |
| 独立端点预测按抽样序号配对；联合计数加 0.5 平滑 | 建模设定 |
| 权重质量项、相关去冗、权重下限和等权混合条件 | 建模设定 |
| 校准器形式、脊惩罚、混合系数搜索、指标阈值与选轮规则 | 建模设定 |
| bootstrap 次数、概率区间、分数、分档和稳定性阈值 | 建模设定 |
| 工艺因子取常量 0，计算路径因子取常量 1；校准有条件通过时因子为 0.85 | 建模设定 |
| 候选按配置中的组合顺序分配行数，并在每个组合内做拉丁超立方抽样 | 建模设定 |

这些假设的具体数值与公式见配置、代码及 `METHOD.md`。
仿真校准标签由仿真目标值产生。
本包的训练表含仿真证据标签，文献测量保存在独立的锚点表中。
