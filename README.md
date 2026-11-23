# 微胶囊自修复训练包

本包能重新生成训练数据、训练五个模型、给 2,048 个候选配方评分。训练数据是仿真数据,模型的训练、校准和测试用的都是仿真数据。训练数据由程序「生成器」生成,生成器参照一批微胶囊自修复材料的文献设计。文献实测值单独放在一张文献表里,只用于计算修复效率的中位数锚点。锚点用来校正仿真修复效率的整体水平。

## 安装与运行

已实跑核对的环境:macOS arm64、Python 3.11,依赖版本见 `code/requirements.txt`。在其他环境运行时,可自行调整依赖版本。每次运行输出逐项偏差表,用来查看调整后的差别。

在终端进入本目录。
使用 CPU 和可用的 C/C++ 编译器。

```bash
python3.11 -m venv ../training-env
../training-env/bin/python -m pip install -r code/requirements.txt
../training-env/bin/python -B code/run_pipeline.py --output ../training-results
```

每次运行使用一个尚不存在的输出目录。
计算从包内 CSV 读取数据。
运行时保持单线程，并把编译缓存放在输出目录中。

输出包括重新生成的训练数据、候选、预测、评分和参数。
`generated_candidates.csv` 保存重新生成的候选。
`candidate_generation_comparison.json` 记录候选逐位对照结果。
`comparison.csv` 与 `comparison.json` 逐列列出偏差。
`draws.npz` 保存候选及校准行的预测抽样。
`weight_bootstrap.npy` 保存集成权重抽样。
`calibration_p0.npy` 保存校准行的集成概率。
`calibrator_bootstrap.csv` 保存重抽样校准器参数与拟合状态。
`probability_bootstrap.npy`、`rank_bootstrap.npy` 和 `loo_ranks.npy` 保存稳定性计算结果。
`environment.json` 记录实际环境与运行时间。

## 数据与方法

`data/training_data.csv` 含 2,500 行，划分单位是仿真 family。
`data/candidates.csv` 含候选编号与七个输入列。
两个参考表按候选编号与候选表逐行对齐。
`data/literature_anchor.csv` 保留锚点测量值与文献定位信息。
`data/literature_sources.csv` 列出文献条目、题名、发表年份与 DOI。
`data/literature_design_conditions.csv` 保存 132 条设计条件，供重算范围与类别次数。

五个模型为 `bayesian_multilevel`、`catboost`、`elastic_net`、`mixed_gp`、`random_forest`。
代码根据校准评估族的区间覆盖率计算资格。
其中四个模型进入集成。
`mixed_gp` 因修复效率区间覆盖不合格，权重为 0。
每个模型分别预测修复效率与强度折损。
联合事件为修复效率不低于 60%，且强度折损不高于 15%。
概率校准的标签来自仿真目标值。

字段定义见 `docs/DATA_DICTIONARY.md`。
生成公式与复现说明见 `docs/DATA_GENERATION.md`。
假设及文献来源见 `docs/ASSUMPTIONS_AND_SOURCES.md`。
模型、集成、校准和评分方法见 `docs/METHOD.md`。
