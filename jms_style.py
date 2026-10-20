# -*- coding: utf-8 -*-
"""JMS 图件统一排版基线（Journal of Mountain Science 投稿指南 §5.7 / §6）。

硬约束（本模块是唯一出口，任何出图脚本 import 后即生效）：
1. 画布宽度 = 最终印刷插入宽度 **16.00 cm**（figsize 宽 = 16/2.54 in）。
   禁止"先画大画布、再在 Word 里缩到 16 cm"——那会让 8 pt 变 6.5 pt。
2. 图内文字 **Times New Roman**，字号 **8–9 pt**（正文/刻度 8，轴标题/分区标题 9）。
3. 不用 mathtext 下标／上标：matplotlib 会把下标压到 0.7 倍（9 pt -> 6.3 pt），
   直接违反 8–9 pt 下限。改用 Unicode 上下标（⁻¹ ² ᵢ ₙ ₜ ×）或拆成两个同字号 text。
   mathtext 仍指向 Times New Roman，防止任何残留公式回退到 STIX/DejaVu。
4. PDF 用 Type 42（TrueType 嵌入），文字保持矢量。

用法：
    import jms_style
    fig = jms_style.figure(height_cm=10.2)          # 宽固定 16.00 cm
    ...
    jms_style.save(fig, "fig3_esi_timeseries")      # -> figures/<name>.pdf + .png
"""
import os

import matplotlib

# ---- 字体注册：显式把 Windows 版 Times New Roman 四款字重喂给 matplotlib ----
from matplotlib import font_manager as _fm

_FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
for _f in ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"):
    _p = os.path.join(_FONT_DIR, _f)
    if os.path.exists(_p):
        try:
            _fm.fontManager.addfont(_p)
        except Exception:       # 已注册 / 只读环境：忽略
            pass

# ---- 尺寸常量 ----
WIDTH_CM = 16.00
WIDTH_IN = WIDTH_CM / 2.54

# ---- 字号（JMS：8–9 pt） ----
FS_BODY = 8.0      # 正文标注、刻度数字、图例
FS_AXIS = 9.0      # 轴标题
FS_TITLE = 9.0     # 面板标题 / 分区标题
FS_MIN, FS_MAX = 8.0, 9.0

matplotlib.rcParams.update({
    # 字体：全 Times New Roman
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Tinos", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "custom",
    "mathtext.rm": "Times New Roman",
    "mathtext.it": "Times New Roman:italic",
    "mathtext.bf": "Times New Roman:bold",
    "mathtext.sf": "Times New Roman",
    "mathtext.fallback": "stix",
    # 字号
    "font.size": FS_BODY,
    "axes.titlesize": FS_TITLE,
    "axes.labelsize": FS_AXIS,
    "xtick.labelsize": FS_BODY,
    "ytick.labelsize": FS_BODY,
    "legend.fontsize": FS_BODY,
    "figure.titlesize": FS_TITLE,
    # 嵌入与渲染
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "svg.fonttype": "none",
    "figure.dpi": 110,
    "savefig.dpi": 600,
    "axes.unicode_minus": False,      # U+2212 负号（TNR 有该字形，且比 ASCII '-' 规范）
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.6,
    "xtick.direction": "out",
    "ytick.direction": "out",
})


def figure(height_cm, width_cm=WIDTH_CM, **kw):
    """建图：宽度锁定 16.00 cm，高度按内容给（cm）。返回 (fig, ax) 或 fig。"""
    import matplotlib.pyplot as plt
    fig = plt.figure(figsize=(width_cm / 2.54, height_cm / 2.54), **kw)
    return fig


def subplots(height_cm, nrows=1, ncols=1, width_cm=WIDTH_CM, **kw):
    """plt.subplots 的 16 cm 宽包装。"""
    import matplotlib.pyplot as plt
    return plt.subplots(nrows, ncols,
                        figsize=(width_cm / 2.54, height_cm / 2.54), **kw)


def check_fonts(*names):
    """确认 Times New Roman 已解析（找不到就报错，避免静默回退 DejaVu）。"""
    path = _fm.findfont(_fm.FontProperties(family="Times New Roman"), fallback_to_default=False)
    assert "times" in os.path.basename(path).lower(), path
    return path


def shrink_pdf(pdf_path, dpi_target=300, quality=90):
    """PDF 瘦身：把**底图栅格**重采样到 dpi_target 并转成 JPEG(DCT) 压缩。

    只动图像流：文字、刻度、线划仍是矢量对象，字号/字体/画布完全不变
    （落盘后会再用 pymupdf 逐 span 复算，见 figures/JMS_figure_audit.tsv）。
    """
    import pymupdf
    doc = pymupdf.open(pdf_path)
    doc.rewrite_images(dpi_target=dpi_target, quality=quality,
                       lossy=True, lossless=True, color=True, gray=True)
    tmp = pdf_path + ".tmp"
    doc.save(tmp, garbage=3, deflate=True)
    doc.close()
    os.replace(tmp, pdf_path)


def save(fig, stem, outdir=None, png_dpi=600, tight_png=True,
         pdf_dpi=None, raster_dpi=None, raster_quality=90):
    """落盘：PDF 严格保持 figsize（画布宽 = 16.00 cm，禁止 bbox_inches 改动），
    另存预览 PNG。返回 (pdf_path, png_path)。

    pdf_dpi         : PDF 里栅格（imshow 底图）的采样 dpi；矢量文字不受影响
    raster_dpi      : 若给出，落盘后用 shrink_pdf 把底图栅格压到该 dpi 的 JPEG
    raster_quality  : JPEG 质量（近无损，默认 90）
    """
    if outdir is None:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
    os.makedirs(outdir, exist_ok=True)
    pdf = os.path.join(outdir, stem + ".pdf")
    png = os.path.join(outdir, stem + ".png")
    if pdf_dpi:
        fig.savefig(pdf, dpi=pdf_dpi)      # 不传 bbox_inches：页宽 == figsize 宽
    else:
        fig.savefig(pdf)
    if raster_dpi:
        shrink_pdf(pdf, dpi_target=raster_dpi, quality=raster_quality)
    if tight_png:
        fig.savefig(png, dpi=png_dpi, bbox_inches="tight", pad_inches=0.02)
    else:
        fig.savefig(png, dpi=png_dpi)
    return pdf, png
