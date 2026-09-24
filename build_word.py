# -*- coding: utf-8 -*-
"""生成论文 Word 版（与 manuscript.tex 内容一致，含图、表、公式文本）"""
import os
import pandas as pd
from word_style import add_equation, make_three_line, heading_cn, EQ1, EQ2, EQ3, EQ4, EQ5, EQ6

EQMAP = {"eq1_norm_pos": EQ1, "eq2_norm_neg": EQ2, "eq3_weight": EQ3,
         "eq4_esi": EQ4, "eq5_gm": EQ5, "eq6_q": EQ6}

def h1(text):
    return heading_cn(doc, text, 15)

def h2(text):
    return heading_cn(doc, text, 12.5)

def eq(img, num):
    builder = EQMAP.get(img.replace(".png", ""))
    if builder is None:
        raise ValueError("未知公式: " + img)
    return add_equation(doc, builder(), num)

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "论文第一版-Word版.docx")

doc = Document()
# 页面与默认字体
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
normal = doc.styles["Normal"]
normal.font.name = "Times New Roman"
normal.font.size = Pt(12)
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

def set_cn(run):
    rPr = run._element.get_or_add_rPr()
    rPr.get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")

def para(text, size=12, bold=False, align=None, italic=False, indent=False):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size); r.bold = bold; r.italic = italic
    set_cn(r)
    if align is not None: p.alignment = align
    if indent: p.paragraph_format.first_line_indent = Pt(size * 2)
    p.paragraph_format.space_after = Pt(4)
    return p

def fig(img, caption, w=14.5):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.add_run().add_picture(os.path.join(FIG, img), width=Cm(w))
    cp = doc.add_paragraph(); cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = cp.add_run(caption); r.font.size = Pt(9.5); r.bold = True; set_cn(r)

def _vcenter_content(table):
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
    for row in table.rows:
        for cell in row.cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER

def table(headers, rows, caption, widths=None):
    para(caption, 10.5, bold=True)
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htxt in enumerate(headers):
        cell = t.rows[0].cells[i]; cell.paragraphs[0].add_run(htxt).bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.paragraphs[0].runs[0].font.size = Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.add_run(str(v)).font.size = Pt(9)
    make_three_line(t)
    _vcenter_content(t)
    return t

# ================= 标题页 =================
para("Ecological Security Early-Warning Assessment and Driving Factors of the Qilian Mountain National Park: An Integrated DPSIR–GM(1,1)–GeoDetector Framework", 16, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
para("[First Author a,*, Second Author a, Third Author b]", 11, align=WD_ALIGN_PARAGRAPH.CENTER)
para("a [University], City, China; b [Institution], City, China", 10, align=WD_ALIGN_PARAGRAPH.CENTER)
para("* Corresponding author: author1@university.edu.cn", 10, align=WD_ALIGN_PARAGRAPH.CENTER)
para("Target journal: Global Ecology and Conservation (Elsevier)", 9, align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()

# ================= 摘要 =================
h1("Abstract")
para("Nature reserves are critical for biodiversity conservation, yet their management often lacks quantitative early-warning tools that translate monitoring data into actionable signals. This study develops an integrated framework—combining the Driving–Pressure–State–Impact–Response (DPSIR) indicator system, combined subjective–objective weighting (analytic hierarchy process [AHP] and entropy method), the grey GM(1,1) model, and the GeoDetector method—to assess and forecast ecological security (ES) in the Qilian Mountain National Park (QMNP), China, over 2005–2023. An ecological security index (ESI) was constructed from nine indicators using real climate (CRU TS) and land-cover (CLCD) data. The regional ESI fluctuated within 0.26–0.71, peaking at 0.709 in 2010 and declining to 0.486 in 2023 (mild warning); warning grades were robust to the weighting ratio α (0–1). Forecasts for 2024–2028 from GM(1,1), NGBM, and ARIMA indicate a gradual decline, with NGBM outperforming GM(1,1) and ARIMA performing worst. GeoDetector identified barren proportion (q = 0.80) and grassland proportion (q = 0.71) as dominant drivers, with all factor interactions enhancing. We propose zonal management recommendations; the framework is transferable to other nature reserves.")
para("Keywords: ecological security; early warning; DPSIR; GM(1,1); GeoDetector; Qilian Mountain National Park", 10, bold=True)
doc.add_paragraph()

# ================= 1 Introduction =================
h1("1. Introduction")
h2("1.1 Background")
para("Global biodiversity is declining at an unprecedented rate: vertebrate population sizes have fallen by an average of 68% since 1970, terrestrial mammal biomass has decreased by at least 85% since the late Pleistocene, and illegal wildlife trade is valued at up to USD 23 billion per year [1,2]. Habitat loss, climate change, and poaching jointly threaten ecosystem stability. Protected areas (PAs) have become the cornerstone of in-situ biodiversity conservation worldwide.")
para("Yet the effectiveness of PAs is constrained by limited monitoring capacity. Conventional field surveys are labor-intensive and difficult to sustain over large or inaccessible areas; camera traps and remote sensing provide richer data but require systematic analytical frameworks to translate raw observations into management decisions [3,4]. A recurring gap is the absence of early-warning information: ecological degradation is often detected only after it has become severe, leaving little room for preventive intervention.")
para("This monitoring-to-warning gap has been repeatedly identified by conservation initiatives. For example, international calls to reduce illegal wildlife trade have proposed cloud-based monitoring platforms that combine sensor networks, remote sensing, and artificial intelligence to deliver real-time alerts for habitat threats [1,3]; the early-warning decision module of such platforms typically rests on composite ecological-security indicators. Formalizing and empirically validating this warning module with real data—rather than leaving it at the level of a platform blueprint—is therefore a direct contribution to the conservation-monitoring agenda.")
para("An ecological security (ES) perspective offers such a systematic formalization. ES assessment compresses multidimensional environmental, social, and economic information into a composite index trackable over time and space, providing a quantitative basis for zoning, monitoring, and early warning [5,6]. We adopt this perspective and apply it to a national park where habitat integrity directly underpins wildlife conservation outcomes.")
h2("1.2 Research status and knowledge gaps")
para("The PSR and DPSIR frameworks are widely used to organize ES indicator systems [7,8]. Subjective weighting (AHP) [9], objective weighting (entropy method), and their combinations are mainstream. Grey models (GM(1,1)) [10] are favored for small-sample ES time series; Liu et al. integrated DPSIR, combined weights, GM(1,1), and GeoDetector into a reserve-scale early-warning framework [5]. The GeoDetector method [11,12] quantifies factor contributions to spatial ES heterogeneity [13–15].")
para("Knowledge gaps remain: (1) reserve-scale studies usually apply the DPSIR–GM(1,1)–GeoDetector components in isolation or with a single weighting scheme; (2) the sensitivity of ES results to the weighting ratio α is rarely tested; (3) the suitability of GM(1,1) for non-monotonic ES series is seldom diagnosed; and (4) few studies translate early-warning results into zonal management recommendations.")
h2("1.3 Contributions")
para("(1) An integrated DPSIR–combined-weight–GM(1,1)–GeoDetector framework tailored to a national nature reserve, with monotonicity diagnostics and an NGBM/ARIMA robustness comparison. (2) A weight-ratio sensitivity analysis (α = 0–1) demonstrating that warning grades are robust to the subjective–objective balance. (3) A real-data evidence chain (temporal trend, robustness, forecast, spatial drivers) for QMNP over 2005–2023, with a 5-year forecast. (4) Zonal management recommendations, with fully reproducible data and code.")

# ================= 2 Study area =================
h1("2. Study area and data")
h2("2.1 Study area")
para("The Qilian Mountain National Park (QMNP) is located in the northeastern margin of the Qinghai–Tibet Plateau, spanning the border of Gansu and Qinghai provinces (Fig. 1). The park protects typical alpine ecosystems—glaciers, snowfields, alpine meadows, and desert steppes—that provide critical water services for the Hexi Corridor. The study region (36.0–40.5°N, 93.5–103.5°E) has an annual mean temperature of 0.8–2.0 °C and annual precipitation of 167–284 mm over 2005–2023. Analysis units include the whole region and 11 counties (Tianzhu, Sunan, Subei, Aksai, Minle, Shandan, Menyuan, Qilian, Gangcha, Delingha, Tianjun).")
fig("fig1_study_area.png", "Fig. 1. Study area and county locations in the Qilian Mountain region.")
h2("2.2 Data sources")
table(["Data type", "Indicators", "Source", "Period"],
      [["Climate", "precipitation (mm), mean temperature (°C)", "CRU TS 4.10", "2005–2023"],
       ["Land cover", "proportions of grassland, forest, water, cropland, barren", "CLCD 30 m", "2005–2023"]],
      "Table 1. Data sources used in this study.")

# ================= 3 Methodology =================
h1("3. Methodology")
h2("3.1 Study framework")
para("Following the DPSIR framework [7,8], nine indicators cover the criteria layers: Driving forces (precipitation, temperature), Pressure (barren/degraded and cropland proportions), State (grassland, forest, water proportions), Impact (grassland change rate), and Response (ecological land proportion) (Table 2). The workflow is shown in Fig. 2.")
table(["Criteria layer", "Indicator", "Unit", "Direction"],
      [["Driving (D)", "Annual precipitation", "mm", "+"],
       ["Driving (D)", "Annual mean temperature", "°C", "+"],
       ["Pressure (P)", "Barren/degraded proportion", "%", "−"],
       ["Pressure (P)", "Cropland proportion", "%", "−"],
       ["State (S)", "Grassland proportion", "%", "+"],
       ["State (S)", "Forest proportion", "%", "+"],
       ["State (S)", "Water proportion", "%", "+"],
       ["Impact (I)", "Grassland change rate", "% yr⁻¹", "+"],
       ["Response (R)", "Ecological land proportion", "%", "+"]],
      "Table 2. The DPSIR indicator system (+/−: positive/negative directions).")
fig("fig2_workflow.png", "Fig. 2. Methodological workflow of the integrated framework.")
h2("3.2 Data preprocessing")
para("CLCD 30 m land-cover rasters (Albers projection) were clipped to the study region by reprojecting the geographic bounding box into the source projection and reading the corresponding window. Land-cover proportions were computed per epoch (2005, 2010, 2015, 2020, 2023) and linearly interpolated to annual values. CRU TS 4.10 monthly grids were aggregated to annual precipitation and temperature at both the regional scale and the 11 county centroids. All computations used Python 3.13 with xarray, rasterio, and pyproj.")
h2("3.3 Data standardization")
eq("eq1_norm_pos.png", 1)
eq("eq2_norm_neg.png", 2)
h2("3.4 Combined weighting")
para("Entropy weights: ej = −(1/ln n) Σi pij ln pij, pij = x′ij / Σi x′ij, wEj = (1 − ej) / Σj (1 − ej). AHP weights follow the principal-eigenvector method with CR = CI/RI < 0.1 [9]. The combined weight is:")
eq("eq3_weight.png", 3)
para("with α = 0.4 baseline and a full sensitivity analysis over α = 0–1.")
h2("3.5 Ecological security index")
eq("eq4_esi.png", 4)
h2("3.6 GM(1,1) forecasting and warning classification")
para("The GM(1,1) model [10] uses the first-order accumulated series with least-squares estimates (â, b̂):")
eq("eq5_gm.png", 5)
para("Model quality: posterior-variance ratio C = S2/S1 and small-error probability P; grades: excellent (C<0.35, P>0.95), qualified (C<0.50, P>0.80), barely qualified (C<0.65, P>0.70). Warning grades: safe [0.8,1], relatively safe [0.6,0.8), mild warning [0.4,0.6), medium warning [0.2,0.4), severe warning [0,0.2).")
h2("3.7 GeoDetector")
eq("eq6_q.png", 6)

# ================= 4 Results =================
h1("4. Results")
h2("4.1 Indicator weights")
fig("fig6_weights.png", "Fig. 6. Combined indicator weights (α = 0.4).")
para("Entropy weighting identifies grassland change rate (w = 0.245) and cropland proportion (w = 0.171) as the most informative signals, indicating that grassland dynamics and human land-use pressure dominate the temporal variation of ES.")
h2("4.2 ESI time series and warning grades")
fig("fig3_esi_timeseries.png", "Fig. 3. Observed ESI (2005–2023) and forecasts (2024–2028) with warning-level bands.")
para("The regional ESI rose from 0.258 (medium warning) in 2005 to a peak of 0.709 (relatively safe) in 2010, then declined and fluctuated within 0.45–0.59 (mild warning), reaching 0.486 in 2023.")
h2("4.3 Forecast comparison")
fc = pd.read_csv(os.path.join(BASE, "data", "results_forecast_comparison.csv"))
table(["Model", "RMSE", "MAE", "C", "P", "Grade", "2024 forecast", "2028 forecast"],
      [["GM(1,1)", 0.052, 0.036, 0.597, 0.789, "barely qualified", f'{fc["gm11"].iloc[0]:.3f}', f'{fc["gm11"].iloc[-1]:.3f}'],
       ["NGBM (γ=0.20)", 0.038, 0.028, 0.442, 0.895, "qualified", f'{fc["ngbm"].iloc[0]:.3f}', f'{fc["ngbm"].iloc[-1]:.3f}'],
       ["ARIMA(0,1,1)", 0.098, 0.067, 1.086, 0.632, "unqualified", f'{fc["arima"].iloc[0]:.3f}', f'{fc["arima"].iloc[-1]:.3f}']],
      "Table 5. Forecast comparison on the 2005–2023 ESI series.")
para("NGBM outperformed GM(1,1), and ARIMA performed worst, validating the grey-model choice for small-sample, non-stationary reserve-scale ES series [16]. All forecasts indicate a mild-warning state with a gradual decline (NGBM: 0.446→0.394), signaling persistent degradation risk without intervention.")
h2("4.4 Robustness to the weighting ratio α")
alpha_df = pd.read_csv(os.path.join(BASE, "data", "results_alpha_sensitivity.csv"))
fig("fig4_alpha_sensitivity.png", "Fig. 4. Sensitivity of the 2023 ESI to the weighting ratio α.")
para(f"Sensitivity analysis over α = 0–1 shows the 2023 ESI ranges from {alpha_df['esi_2023'].min():.3f} to {alpha_df['esi_2023'].max():.3f}, but the warning grade remains 'mild warning' for all α values. The early-warning conclusion is robust to the subjective–objective weighting balance.")
h2("4.5 County-level ESI and spatial driving factors")
fig("fig7_county_esi.png", "Fig. 7. County-level ESI (2020).")
fig("fig5_spatial_esi.png", "Fig. 5. Spatial distribution of point ESI (2020).")
para("County ESI (2020), computed with the same combined weights as the regional analysis, ranks Sunan (0.466) and Tianzhu (0.395) highest and Aksai (0.074) lowest; the pattern is modulated by local land-cover composition rather than a strict east–west gradient. GeoDetector on 1,914 grid samples identified barren proportion (q = 0.80) and grassland proportion (q = 0.71) as dominant drivers. The interaction detector shows all factor pairs enhance jointly, with temperature×barren (q = 0.849) strongest (Table 7).")
fig("fig8_interaction.png", "Fig. 8. GeoDetector interaction q (2020).")

# ================= 5 Discussion =================
h1("5. Discussion")
h2("5.1 Ecological security changes and their drivers")
para("The 2005–2010 ESI recovery is consistent with large-scale ecological restoration and wetter years; the subsequent mild-warning plateau reflects persistent barren-dominated land cover (~56%) and climate fluctuation. The dominant weighting of grassland dynamics corroborates the importance of alpine meadow ecosystems, in line with findings that grassland degradation is the leading ecological-security constraint in alpine regions [14,15]. The east–west gradient and GeoDetector results indicate that aridity and vegetation cover—not temperature—control spatial heterogeneity [13].")
para("For wildlife and biodiversity conservation, the mild-warning state and projected decline carry a concrete message: habitat integrity in the Qilian Mountain region is not improving, and monitoring programs relying on static habitat assessment may miss slow degradation. The ESI-based early-warning signal formalized here is precisely the decision-support input that conservation-monitoring platforms need—linking raw environmental data to warning grades that can trigger management action [3,4].")
h2("5.2 Methodological reflections")
para("The α-sensitivity analysis demonstrates that warning grades are invariant to the weighting ratio, supporting the reliability of combined-weight approaches. The forecast comparison shows that NGBM better captures non-monotonic ESI dynamics than GM(1,1), while ARIMA is unsuitable for short, non-stationary series [16]. Compared with previous DPSIR-based assessments [5,7,8], our framework adds: (i) an explicit weighting-ratio robustness check, (ii) a three-model forecast comparison with monotonicity diagnostics, and (iii) spatial factor attribution with interaction detection (Fig. 9).")
fig("fig_compare.png", "Fig. 9. Comparison with representative reserve-scale ecological-security studies.")
h2("5.3 Management implications")
para("(1) Mild-warning zones should prioritize grassland restoration and grazing regulation; the arid western counties (Aksai, Delingha) require desertification monitoring and water-resource management. (2) Cropland expansion at the agropastoral ecotone should be controlled. (3) The five-level warning classification enables an ESI-threshold-triggered response mechanism aligned with QMNP zoning, operationalizing early warning for habitat and wildlife conservation.")
h2("5.4 Limitations and future work")
para("Limitations include the regional aggregation (county-level ESI is static, based on centroid windows pending finer boundaries), the interpolation of land cover between five epochs, and the moderate accuracy of grey models on non-monotonic series (addressed via the NGBM/ARIMA comparison). Future work should incorporate higher-temporal-resolution land cover, couple the ESI with wildlife population indicators, and extend the framework to a multi-reserve comparison.")

# ================= 6 Conclusion =================
h1("6. Conclusion")
para("(1) An integrated DPSIR–combined-weight–GM(1,1)–GeoDetector framework was applied to QMNP with fully real, open data, and the pipeline is reproducible. (2) The regional ESI ranged 0.26–0.71 over 2005–2023; since 2011 the region has remained in a mild-warning state (2023 ESI = 0.486). (3) Forecasts for 2024–2028 indicate a gradual decline (NGBM: 0.446→0.394), signaling persistent degradation risk. (4) Warning grades are robust to the weighting ratio, and grassland dynamics and cropland pressure dominate; GeoDetector identified aridity (barren proportion) as the primary spatial driver. (5) We recommend integrating ESI-based early warning into QMNP adaptive management; the framework is transferable to other nature reserves.")

# ================= 声明与参考文献 =================
h1("Data availability")
para("Climate data are from CRU TS 4.10 (open); land cover is from CLCD v1.0 (open, Zenodo). Analysis code is available from the authors upon request.")
h1("References")
refs = ["[1] WWF. Living Planet Report 2020. WWF International, 2020.",
        "[2] IPCC. Climate Change 2014: Impacts, Adaptation, and Vulnerability. Cambridge Univ. Press, 2014.",
        "[3] Kerry R.G., et al. An overview of remote monitoring methods in biodiversity conservation. Environ. Sci. Pollut. Res., 2022, 29(53): 80179–80221.",
        "[4] Bijl G., et al. A narrative review on the use of camera traps and machine learning in wildlife research. Columella, 2022, 9(2): 47.",
        "[5] Liu Y., et al. An integrated ecological security early-warning framework in the national nature reserve based on the gray model. J. Nat. Conserv., 2023, 73: 126394.",
        "[6] Spatiotemporal Differentiation of Land Ecological Security in Jinan, China. Front. Environ. Sci., 2022, 10: 824254.",
        "[7] Ecological security evaluation of wetlands in Changbai Mountain area based on DPSIRM model. Ecol. Indic., 2024.",
        "[8] Spatial-temporal evolution and driving factors of ecological security based on DPSIR-DEA: Three Gorges reservoir area. Ecol. Indic., 2023.",
        "[9] Saaty T.L. The Analytic Hierarchy Process. McGraw-Hill, 1980.",
        "[10] Deng J.L. Control problems of grey systems. Syst. Control Lett., 1982, 1(5): 288–294.",
        "[11] Wang J.F., Zhang T.L., Fu B.J. A measure of spatial stratified heterogeneity. Ecol. Indic., 2016, 67: 250–256.",
        "[12] Wang J.F., Hu Y. Environmental health risk detection with GeogDetector. Environ. Model. Softw., 2012, 33: 114–115.",
        "[13] Long-Term Dynamic Monitoring and Driving Force Analysis of Eco-Environmental Quality in China. Remote Sens., 2024, 16(6): 1028.",
        "[14] Anthropogenic activities amplify spatiotemporal variations in regional ecological security patterns: West Liaohe River Basin. 2026.",
        "[15] Integrating Landscape Ecological Risk and Ecosystem Services for Ecological Zoning in the Qilian Mountain National Park. Ecosyst. Health Sustain., 2024.",
        "[16] Althobaiti S., Shabri A. Prediction of CO2 emissions using NGBM(1,1) compared with GM(1,1). J. Phys. Conf. Ser., 2022, 2259: 012011.",
        "[17] Harris I., et al. CRU TS4.10. Univ. East Anglia Climatic Research Unit, 2025.",
        "[18] Yang J., Huang X. The 30 m annual land cover datasets in China (CLCD). Zenodo, 2023."]
for r in refs:
    para(r, 9.5)

doc.save(OUT)
print("OK:", OUT)
