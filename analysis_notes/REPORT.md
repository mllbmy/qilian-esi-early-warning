> **2.2版更新（2026-10-20）**：以下为历史块置换与CR分析记录。当前正文以 `data/r47_shift_reference.csv` 的1913次穷举对齐参照为准，不声称其校准一般空间零假设；`results_effective_n.csv`仅Pearson相关近似仍使用，q的CR-F校正不再用于正文。当前权威说明为 `../../交付/2.2版本/说明_2.2版本.md`。原记录保留用于追溯。

# 空间自相关稳健性分析报告（task-5 / 批注 6·7）

**一句话判定**：块置换后**排序不变**（裸地 0.802 > 草地 0.708 > 降水 0.506 > 温度 0.170），
裸地/草地/降水 **仍显著（p = 0.001，检验分辨率下限）**；但**温度 q = 0.170 不再显著**
（块置换 p = 0.126–0.152，名义 p = 0.001），且点尺度 ESI–NDVI 相关的**有效样本量由
n = 1,785 降到 n_eff ≈ 23**（相关仍显著，但 95%CI 由 [0.681, 0.728] 放宽到 [0.416, 0.865]）。
因此论文中"四因子均显著（p = 0.001）"与"按 n = 1,785 计精度"这两处表述**必须改写**，
其余定性结论（排序、前三名的显著性与量级）**不变**。

复现：`python run_blockperm.py`、`python run_cr_effective_n.py`（系统 python 3.13，numpy/pandas/scipy）。
产物：`data/results_blockperm_q.csv`、`data/results_effective_n.csv`、
`_stat_work/results_pvalue_calibration.csv`、`_stat_work/blockperm.log`。

---

## 1. 基线复现（先复现，再说话）

| 项 | 本脚本复算 | 归档值 | 差 |
|---|---|---|---|
| q(barren) | 0.802431 | 0.802431 | < 1e-9 |
| q(grass) | 0.707710 | 0.707710 | < 1e-9 |
| q(precip) | 0.506016 | 0.506016 | < 1e-9 |
| q(temp) | 0.169739 | 0.169739 | < 1e-9 |
| r(ESI, NDVI) | 0.705413 | 0.705413（n = 1,785） | < 1e-6 |
| Moran's I（k=8 反距离） | 0.6431 | 0.6431 | < 1e-3 |

- 数值口径与 `run_geodetector_pvalues.py` 完全一致：ESI 取 `spatial_esi_points.csv`，
  四因子取 `spatial_samples.csv`，四分位分层 `np.digitize(x, quantile[.25,.5,.75])`，
  `q = 1 − Σ N_h σ_h² / (N σ²)`；脚本内对 `eco_security.geodetector_q` 逐位 assert（|Δ| < 1e-10）。
- 关键结构发现：1,914 个点**恰好是 29 行 × 66 列的完整矩形格点**（0.15° 间距，跨度 4.20°×9.75°），
  不是散点。这使"块置换"可以在格点上严格定义，也支持环面平移（toroidal shift）这一标准受限随机化。
- 二值因子 grass / barren 的"四分位分层"实际只落 2 层（样本中 grass 只有 0/1），与归档一致。

## 2. 名义 p vs 块置换 p（999 次，种子写死）

```
scheme = toroidal_shift（主口径，见第 3 节）
factor   q_obs    p_名义   p_块(0.15°)  p_块(0.30°)  p_块(0.45°)  p_块(0.60°)   块零分布 95 分位 / 最大值
barren   0.8024   0.001    0.001        0.001        0.001        0.001        0.15–0.18 / 0.30–0.43
grass    0.7077   0.001    0.001        0.001        0.001        0.001        0.13–0.16 / 0.26–0.36
precip   0.5060   0.001    0.001        0.001        0.001        0.001        0.26–0.34 / 0.47–0.49
temp     0.1697   0.001    0.126        0.152        0.132        0.141        0.24–0.26 / 0.29–0.31
```

块大小与格点对齐（0.15° 的整数倍，故不是字面的 0.25°/0.5°）：
0.15°=16.7 km（1,914 块）、**0.30°=33.4 km（495 块，对应 0.25° 档）**、
**0.45°=50.1 km（220 块，对应 0.5° 档，亦≈CRU 0.5° 气候格网）**、0.60°=66.8 km（136 块）。
要求的 0.25°/0.5°（27.8/55.6 km）被 33/50 km 两档夹住，四档结论完全一致，故块大小不是结论的支点。

要点：
1. **名义 p 的零分布几乎是退化的**：独立置换下 q 的零分布中位数仅 0.0005–0.0016，
   95 分位 0.002–0.004，最大值 0.006–0.010。观测值 0.17–0.80 与之相差 2–3 个数量级，
   于是**任何**平滑因子都会得到 p = 0.001 —— 这正是"p 值偏乐观"的机制来源。
2. **保结构零分布的尺度大得多**：块置换下 q 的零分布中位数 0.033–0.102（比独立置换高
   60–200 倍），95 分位 0.13–0.34。裸地/草地/降水的观测值仍远超该零分布（p = 0.001，
   即 999 次中 0 次达到），**温度 0.170 完全落在零分布内部**（999 次中 125–151 次 ≥ 观测）。
3. 降水是三者中最勉强的一个：观测 0.506 只比块零分布最大值（0.491）高 0.015，
   95 分位仅 0.29，即"p = 0.001 但余量很薄"。

**关于 scheme 的选择依据见第 3 节**：`block_unit`（整块任意重排，即字面意义的"块置换"）
在四个块大小下都给 p = 0.001（含温度），但第 3 节证明它**只部分修正**，不能作主口径。

## 3. p 值校准（placebo 试验）—— 本任务最硬的一组数字

构造：把响应面（ESI）在环面上整体平移 **≥10 格（≈1.5°，远超自相关长度）**，共 100 个位移；
真实配准被破坏（零假设成立），但 ESI 的自相关结构与边缘分布**完整保留**。
于是"在这种情况下拒绝 H0 的比例"= 各检验口径的**实测第一类错误率**（名义 5%）。

| 检验口径 | 拒真率 @ α=0.05 | 拒真率 @ α=0.01 | p 中位数 |
|---|---|---|---|
| 独立置换（正文现行口径） | **0.905** | 0.865 | 0.001 |
| 整块任意重排（block_unit，2 格块） | 0.820 | 0.763 | 0.001–0.002 |
| **受限平移（toroidal shift，主口径）** | **0.035** | 0.005 | 0.46–0.60 |

4 因子平均；100 例 placebo × 4 因子 × 999 次置换，种子见脚本。
**结论**：正文现行的 999 次独立置换在零假设成立时有 **90.5%** 的概率给出 p ≤ 0.05
（名义 5%），即 p 值被系统性、且几乎完全地乐观化；整块任意重排把它降到 82%（几乎没修好，
因为块间连续性被打断后，重排后的响应面不再平滑，零分布仍过窄）；
只有"整体平移、只破坏配准"的受限置换把拒真率压回 3.5%（略保守但有效）。

## 4. Clifford–Richardson 有效样本量

```
item            n      n_eff   S/n    收缩倍数  修正后检验                    结论
r(ESI, NDVI)    1785   23.3    75.7   77×      t=4.59, df=21.3, p=1.5e-4   仍显著（CI 见下）
q(barren)       1914   33.2    56.6   58×      F(1,31.2), p=1.6e-12        仍显著
q(grass)        1914   38.7    48.5   49×      F(1,36.7), p=2.4e-11        仍显著
q(precip)       1914   19.6    96.6   98×      F(3,15.6), p=0.010          仍显著（勉强）
q(temp)         1914   25.4    74.4   75×      F(3,21.4), p=0.254          **不再显著**
```

- r = 0.705：95%CI 由名义 [0.681, 0.728] 放宽为 **[0.416, 0.865]**；p 由 8.1e-269 变为 1.5e-4。
- n_eff 对滞后截断的敏感性：r 的 n_eff 在 5/8/10/14/20 格截断下为 47.5/27.9/**23.3**/19.2/16.4；
  四个 q 分别为 barren 66/40/33/27/22、grass 76/46/39/32/26、precip 39/23/20/16/13、temp 45/29/25/21/16。
- **主口径规则**：滞后类须有充分支撑（成对样本 ≥ 10%·n）且 |lag| ≤ 10 格（=1.5°，即 ESI 相关图由 0.62
  衰减到 0.17、趋零的尺度）。若对全部 3,733 个滞后类求和，矩形域边缘只剩 1–2 对样本的滞后类会把
  S/n 从 76 抬到 212、n_eff 压到 8.4（估计量失真，见 `_stat_work/diag_cr3.py` 的支撑度扫描）。
- **两个独立交叉验证**：
  ① 环面平移零分布（1,913 个位移）下 r 的 sd = 0.230、最大值 0.668，观测 0.705 超过全部位移
  ⇒ p = 0.0005，隐含 n_eff = 1/sd² + 2 = **21.0**，与 CR 的 23.3 吻合；
  ② 空间块 bootstrap（220 个 0.45° 块重抽 999 次）给 95%CI [0.653, 0.749]——比 CR 窄，
  因为块重抽不移动域尺度趋势，属于**偏乐观**的对照，不作为结论依据。

## 5. 结论是否改变

| 结论 | 名义口径 | 修正后 | 是否改变 |
|---|---|---|---|
| 四因子 q 排序（裸地>草地>降水>温度） | — | 不变 | 不变 |
| 裸地、草地、降水显著 | p=0.001 | 块 p=0.001；CR p ≤ 0.01 | **不变** |
| "四因子均显著" 里的温度 | p=0.001 | 块 p=0.13–0.15；CR p=0.25 | **改变：温度不再显著** |
| 降水"强证据" | p=0.001 | 块 p=0.001 但仅超零分布最大值 0.015 | 显著但余量薄，宜降调 |
| ESI–NDVI r=0.705 的精度 | n=1,785，CI [0.681,0.728] | n_eff≈23，CI [0.416,0.865]，仍显著 | **精度改变，结论（显著正相关）不变** |

## 6. 建议写入论文的句子（中英对照）

### 6.1 方法（§3 空间分层关联分析，接在"999 iterations"那句之后）

**中**：由于 1,914 个 0.15° 格点存在强空间自相关（Moran's I = 0.6431），上述 999 次独立置换给出的
p 只能视为**名义值**；本文另用保结构受限置换重算：把响应面在 29×66 规则格点环面上按 0.15°/0.30°/
0.45°/0.60°（16.7/33.4/50.1/66.8 km）四个块尺度整体平移 999 次（仅破坏因子与响应的配准，完整保留
两者的空间自相关结构），并给出点尺度相关的 Clifford–Richardson (1989) 有效样本量 n_eff。

**EN**: Because the 1,914 0.15° grid samples are strongly spatially autocorrelated (Moran's
I = 0.6431), the 999-permutation p-values are reported as **nominal** only. Significance was
therefore recomputed with a structure-preserving restricted randomisation: the response surface
was shifted on its 29 × 66 lattice by 999 random offsets at block scales of 0.15°, 0.30°, 0.45°
and 0.60° (16.7, 33.4, 50.1 and 66.8 km), which breaks only the factor–response registration
while retaining each field's autocorrelation, and the Clifford–Richardson (1989) effective
sample size is reported for the point-scale correlations.

### 6.2 结果（§4.5 空间分层关联，第一段 q 值之后）

**中**：独立置换的零分布几乎是退化的（q 的零分布中位数 0.0005–0.0016，95 分位 0.002–0.004），
故其 p = 0.001 不构成强证据；块置换的零分布中位数为 0.033–0.102、95 分位 0.13–0.34，在此口径下
裸地/草地/降水的观测 q（0.802/0.708/0.506）仍为 p = 0.001，而温度 q = 0.170 落在零分布之内
（p = 0.126–0.152，四个块尺度一致），其名义 p = 0.001 系空间自相关所致，不应作为温度显著的解释证据。
同一修正把点尺度 ESI–NDVI 相关的有效样本量由 n = 1,785 降至 n_eff = 23（Clifford–Richardson；
截断敏感性 16–48），该相关仍显著（t = 4.59，df = 21.3，p = 1.5×10⁻⁴），但 95% 置信区间由
[0.681, 0.728] 放宽为 [0.416, 0.865]。

**EN**: The i.i.d. permutation null is almost degenerate (median q = 0.0005–0.0016, 95th
percentile 0.002–0.004), so its p = 0.001 is not strong evidence; under the block null, whose
median is 0.033–0.102 and 95th percentile 0.13–0.34, the observed q of barren/degraded (0.802),
grassland (0.708) and precipitation (0.506) still give p = 0.001, whereas temperature
(q = 0.170) lies inside the null (p = 0.126–0.152, consistent across all four block scales), so
its nominal p = 0.001 is an artefact of spatial autocorrelation and is not reported as evidence
that temperature explains the index. The same correction reduces the effective sample size of the
point-scale ESI–NDVI correlation from n = 1,785 to n_eff = 23 (Clifford–Richardson; 16–48 across
lag-truncation choices): the correlation remains significant (t = 4.59, df = 21.3, p = 1.5×10⁻⁴)
but its 95% confidence interval widens from [0.681, 0.728] to [0.416, 0.865].

### 6.3 备选：方法或讨论里加一句校准证据（推荐，最能直接回应批注）

**中**：一项 placebo 校准（把响应面平移 ≥1.5° 以破坏真实配准、使零假设成立）显示，独立置换在
名义 5% 下的实际拒真率为 90.5%，整块重排为 82.0%，而受限平移为 3.5%——即忽略空间自相关会使
p 值近乎失效，仅整块重排并不足以修正。

**EN**: A placebo calibration, in which the response surface is displaced by at least 1.5° so
that the true pairing is destroyed and the null holds, gives an empirical rejection rate at the
nominal 5% level of 90.5% for the i.i.d. permutation, 82.0% for arbitrary whole-block
rearrangement and 3.5% for the restricted shift; ignoring spatial autocorrelation therefore makes
the permutation p-value almost uninformative, and whole-block rearrangement alone does not
repair it.

## 7. 局限与注意事项（不要粉饰）

1. 受限平移（toroidal shift）假设研究域可视为环面，会引入边缘的"人为相邻"；本域是完整矩形格点，
   这是标准做法（Fortin & Dale 2005; Legendre & Legendre 2012），但仍是近似。
2. 块置换的 p 受 999 次置换限制，最小只能报 0.001；温度 p 的四个块尺度值 0.126/0.152/0.132/0.141
   本身有 ±0.01 的蒙特卡洛误差。
3. CR 的 n_eff 依赖滞后截断与最小支撑规则（n_eff 16–48 的区间），且假定二阶平稳；本文的
   ESI/NDVI 都含域尺度趋势，n_eff 因此偏小（这也是"两场共享大尺度梯度，独立信息少"的如实反映）。
   正文宜报区间或至少注明敏感性，不要只写 23。
4. 降水虽仍 p = 0.001，但观测 q 仅超块零分布最大值 0.015，审稿人若不认可环面平移口径，降水是
   最先会被质疑的一个；建议同时报 CR 的 F 检验 p = 0.010 作为佐证。
5. 效应量本身（q 值、r 值）不因修正而改变；改变的只是不确定性与显著性判定。修正不改变第 5 节
   之外的任何既有结论，也不涉及 manuscript.tex（本任务未改主稿）。

## 8. 文件与复现

| 文件 | 内容 |
|---|---|
| `paper-code/run_blockperm.py` | 基线复现 + 名义 p + 块置换（4 块尺度 × 2 方案）+ placebo 校准；写 2 个 CSV |
| `paper-code/run_cr_effective_n.py` | Clifford–Richardson n_eff + 修正 t/F/CI + 环面平移零分布与块 bootstrap 交叉验证 |
| `paper-code/data/results_blockperm_q.csv` | 36 行 = 4 因子 ×（iid + 4 块尺度 × 2 方案） |
| `paper-code/data/results_effective_n.csv` | 5 行（r + 4 个 q），含 n_eff 敏感性区间与交叉验证列 |
| `paper-code/_stat_work/results_pvalue_calibration.csv` | 12 行（3 口径 × 4 因子）placebo 拒真率 |
| `NaN` | 支撑度/截断规则的选择依据（探索性诊断，保留以便复核） |
| `paper-code/_stat_work/blockperm.log` | 完整运行日志（UTF-16） |

随机种子：名义置换 42（与既有脚本同口径）；块置换 20261021–20261024 / 20261121–20261124；
校准 20261025；块 bootstrap 20261020。
