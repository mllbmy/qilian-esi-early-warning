# -*- coding: utf-8 -*-
"""JMS 指南 §6（R10 MEDIUM-2）：图内文字 Times New Roman 8–9 pt。

各出图脚本在 import matplotlib 之后 import 本模块即可统一字体；
仅改字体呈现，不改任何数据/坐标/数值（符合重排红线）。
"""
import matplotlib

matplotlib.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Tinos", "Nimbus Roman", "DejaVu Serif"],
    "mathtext.fontset": "stix",        # 数学符号也用衬线，匹配 TNR
    "font.size": 9,                     # 正文标签 8–9 pt
    "axes.titlesize": 9,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "pdf.fonttype": 42,
    "axes.unicode_minus": False,
})