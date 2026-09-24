# -*- coding: utf-8 -*-
"""JMS 图件导出：TIFF、≥600 dpi、宽度按 15 cm（JMS 允许 14–16 cm）反算

Figure 1  fig1_study_area.png       （地形 + 国家公园 + 县域）
Figure 2  fig_dpsir_framework.pdf   （DPSIR 框架）
Figure 3  fig_indicator_trends.pdf  （九项指标趋势）
Figure 4  fig3_esi_timeseries.pdf   （ESI 实测与预测 + 预警分级）
Figure 5  fig4_alpha_sensitivity.pdf（α 敏感性）
Figure 6  fig5_spatial_esi.png      （ESI 空间分布）
Figure 7  fig_weights.pdf           （熵权/AHP/组合权重对比）
Figure 8  fig_geodetector_q.pdf     （单因子 q 值）
Figure 9  fig_interaction.pdf       （交互探测 q 值）
Figure 10 fig_obstacle.pdf          （障碍因子逐年构成）

科学内容零改动：只做分辨率与格式转换（不改绘图代码、不改数据）。
"""
import io
import os
import subprocess
import sys

from PIL import Image

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(BASE, "figures")
OUT = os.path.join(BASE, "jms", "figures_tiff")
TMP = os.path.join(OUT, "_tmp")
WIDTH_CM = 15.0                      # JMS：单栏 7–8 cm / 通栏 14–16 cm
WIDTH_IN = WIDTH_CM / 2.54
TARGET_PX = round(WIDTH_IN * 600)    # 600 dpi 时 15 cm 对应像素宽
DPI = 600

MAP = [
    (1, "fig1_study_area.png", "Topography, the Qilian Mountain National Park and county locations"),
    (2, "fig_dpsir_framework.pdf", "Conceptual framework of the DPSIR causal chain"),
    (3, "fig_indicator_trends.pdf", "Temporal trends of the nine DPSIR indicators, 2005-2023"),
    (4, "fig3_esi_timeseries.pdf", "Observed ESI (2005-2023) and forecasts (2024-2028) with warning-level bands"),
    (5, "fig4_alpha_sensitivity.pdf", "Sensitivity of the 2023 ESI to the weighting ratio alpha"),
    (6, "fig5_spatial_esi.png", "Spatial distribution of point ESI (2020)"),
    (7, "fig_weights.pdf", "Entropy, AHP, and combined (alpha=0.4) weights of the nine DPSIR indicators"),
    (8, "fig_geodetector_q.pdf", "Single-factor detection q statistics (2020)"),
    (9, "fig_interaction.pdf", "Interaction-detector q values for the six factor pairs"),
    (10, "fig_obstacle.pdf", "Annual obstacle-degree profiles of the nine indicators, 2005-2023"),
]

os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
rows, warns = [], []

for n, fn, cap in MAP:
    src = os.path.join(FIG, fn)
    if not os.path.isfile(src):
        warns.append("Figure %d 源文件缺失：%s" % (n, fn))
        continue
    dst = os.path.join(OUT, "JMS_Figure_%d.tif" % n)
    if fn.lower().endswith(".pdf"):
        pre = os.path.join(TMP, "f%d" % n)
        r = 600
        png = pre + ".png"
        for _ in range(3):                     # 若 PDF 物理尺寸偏大导致等效 dpi 不足，则提高栅格化分辨率
            if os.path.isfile(png):
                os.remove(png)
            subprocess.run(["pdftocairo", "-png", "-r", str(r), "-singlefile", src, pre],
                           check=True, capture_output=True)
            im = Image.open(png)
            eff = im.size[0] / WIDTH_IN        # 等效 600 dpi 判据
            if eff >= DPI - 1:
                break
            r = int(r * DPI / eff) + 2
    else:
        png = os.path.join(TMP, "f%d_src.png" % n)
        im = Image.open(src)
        eff = im.size[0] / WIDTH_IN
        if eff < DPI - 1:
            warns.append("Figure %d 源图仅 %.0f dpi（<600），需重出：%s" % (n, eff, fn))
        im.convert("RGB").save(png)
    im = Image.open(png)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    # 按 600 dpi × 15 cm 的目标像素宽缩放（源分辨率更高时用 Lanczos 降采样，画质无损）
    if im.size[0] != TARGET_PX:
        h = max(1, round(im.size[1] * TARGET_PX / im.size[0]))
        im = im.resize((TARGET_PX, h), Image.LANCZOS)
    im.save(dst, format="TIFF", compression="tiff_lzw", dpi=(DPI, DPI))
    chk = Image.open(dst)
    eff = chk.size[0] / WIDTH_IN
    rows.append((n, fn, "%d x %d" % chk.size, "%.0f" % eff, "%.1f" % (os.path.getsize(dst) / 1024 / 1024), cap))
    print("Figure %d  %-26s -> %s  %dx%d px | 15cm 宽等效 %.0f dpi | %.1f MB"
          % (n, fn, os.path.basename(dst), chk.size[0], chk.size[1], eff,
             os.path.getsize(dst) / 1024 / 1024))

man = ["JMS 图件清单（TIFF，%d dpi，宽 %.1f cm；文件名为 JMS_Figure_N.tif）" % (DPI, WIDTH_CM), ""]
man += ["Figure %d | 源文件 %s | 像素 %s | 等效 dpi %s | 大小 %s MB | 图注：%s" % r for r in rows]
io.open(os.path.join(OUT, "manifest.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(man) + "\n")

print()
if warns:
    print("⚠️ 警告 %d 条：" % len(warns))
    for w in warns:
        print("   -", w)
else:
    print("全部图件达标：%d/%d 张 TIFF，等效 dpi ≥ %d" % (len(rows), len(MAP), DPI))
sys.exit(1 if warns else 0)