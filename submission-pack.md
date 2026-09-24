# 投稿准备包（方向 A+T3 · 祁连山生态安全预警）

## 一、Cover Letter（投稿信模板）

```
[Date]

Dear Editor-in-Chief,

We are pleased to submit our manuscript entitled "Ecological Security Early-Warning
Assessment and Driving Factors of the Qilian Mountain National Park: An Integrated
DPSIR–GM(1,1)–GeoDetector Framework" for consideration for publication in Global
Ecology and Conservation.

Nature reserves are central to biodiversity conservation, yet most lack quantitative
early-warning tools that translate monitoring data into management actions. In this
study we develop an integrated DPSIR–combined-weight–GM(1,1)–GeoDetector framework
and apply it to the Qilian Mountain National Park, China, using fully open, real data
(CRU TS climate and CLCD 30 m land cover, 2005–2023). Our key findings are:

1. The regional ecological security index (ESI) peaked in 2010 (0.699) and has since
   remained in a mild-warning state (2023: 0.463), with the warning grade robust to
   the subjective–objective weighting ratio (α = 0–1 sensitivity analysis).
2. Forecasts for 2024–2028 (GM(1,1), NGBM, and ARIMA comparison) indicate a gradual
   decline, signaling persistent degradation risk without intervention.
3. GeoDetector identified barren/degraded proportion (q = 0.80) and grassland
   proportion (q = 0.71) as the dominant drivers of spatial ecological security.

The framework is transferable to other protected areas, and all data and code are
reproducible. We believe the manuscript fits the scope of Global Ecology and
Conservation and will be of interest to reserve managers and conservation scientists.

All authors have approved the manuscript and agree with its submission. The work is
original and has not been published or submitted elsewhere.

Sincerely,
[Corresponding author name, affiliation, email]
```

## 二、目标期刊格式要求（投稿前核对）

### 首选：Global Ecology and Conservation（Elsevier, 2区）
- 篇幅：全文建议 ≤8000 词（不含参考文献）；摘要 ≤300 词
- 图表：图 ≤8 幅、表 ≤5 个；图 300 dpi 以上（TIFF/EPS/PDF）；色彩图免费在线
- 结构：Abstract / 1. Introduction / 2. Materials and methods / 3. Results / 4. Discussion / 5. Conclusion / Declarations / References
- 参考文献：Elsevier numeric 或 author-date 风格（按期刊指南）
- 需附：Highlights（3-5 条，每条 ≤85 字符）、Declarations（利益冲突/数据可用性/基金）、建议审稿人 3-5 位
- 投稿系统：Editorial Manager (ees.elsevier.com)

### 备选：Ecological Modelling（Elsevier, 2区）
- 强调模型方法创新；需更详细的模型公式与验证（我们已有 NGBM/ARIMA 对比支撑）

## 三、投稿前检查清单

- [ ] 英文润色（已含 writing_audit 纪律扫描；建议再找英语母语润色）
- [ ] 图表渲染（Fig.1 研究区图、Fig.2 技术路线、Fig.3 ESI 时序、Fig.4 α 敏感性、Fig.5 空间 ESI 分布）
- [ ] 文献补全至 60+ 并统一 BibTeX 格式
- [ ] 数据可用性声明 + 代码仓库（GitHub）公开
- [ ] Highlights 撰写
- [ ] 作者信息与单位、ORCID、基金号
- [ ] 图表标题与文中引用一一对应（Table 1-5, Fig 1-5）
- [ ] 格式转换：Markdown → LaTeX 期刊模板（elsarticle）或 Word 模板

## 四、当前论文资产清单（paper-code/）

| 文件 | 内容 |
|---|---|
| full-paper-draft.md | 全文初稿（真实数据） |
| results-*.csv (4) | ESI/权重/α敏感性/预测对比 |
| qilian_climate.csv / qilian_landcover.csv / results_county_esi.csv / spatial_esi_points.csv | 真实数据与空间结果 |
| eco_security/ | 方法管线代码（可复现） |
| 参考文献.bib / 参考文献库-方向A.md | 文献库（35+ 条） |
| introduction/methodology/results/discussion 各草稿 | 分章节草稿 |
