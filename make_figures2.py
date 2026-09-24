# -*- coding: utf-8 -*-
"""图6(权重)与图7(县域ESI): 统一学术配色"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
os.makedirs(FIG, exist_ok=True)

BLUE = "#2166ac"
GREEN = "#1b7837"
ORANGE = "#e07b39"
RED = "#b2182b"

plt.rcParams.update({"font.family": "Arial", "font.size": 9,
                     "mathtext.fontset": "custom", "mathtext.rm": "Arial",
                     "mathtext.it": "Arial:italic", "mathtext.bf": "Arial:bold",
                     "axes.labelsize": 10, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
                     "axes.edgecolor": "#444444", "axes.linewidth": 0.8,
                     "savefig.dpi": 600, "figure.dpi": 100})

# ---- Fig 6: 指标组合权重 ----
w = pd.read_csv(os.path.join(BASE, "data", "results_weights.csv"))
labels = {"X1_降水mm": "Precipitation", "X2_气温C": "Temperature", "X3_草地占比%": "Grassland",
          "X4_森林占比%": "Forest", "X5_水域占比%": "Water", "X6_裸地荒漠%": "Barren",
          "X7_农田占比%": "Cropland", "X8_草地变化率": "Grass change", "X9_生态用地%": "Eco land"}
w["lab"] = w["indicator"].map(labels)
w = w.sort_values("combined_w")
fig, ax = plt.subplots(figsize=(7.2, 4.2))
bars = ax.barh(w["lab"], w["combined_w"], color=BLUE, alpha=0.88)
for i, v in enumerate(w["combined_w"]):
    ax.text(v + 0.003, i, f"{v:.3f}", va="center", fontsize=7.5)
ax.set_xlabel("Combined weight (α = 0.4)")
ax.set_xlim(0, 0.25)
ax.grid(axis="x", alpha=0.25, lw=0.4)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig6_weights.png")); plt.close()

# ---- Fig 7: 县域 ESI ----
cnt = pd.read_csv(os.path.join(BASE, "data", "results_county_esi.csv")).sort_values("esi_2020")
PN = {"肃南": "Sunan", "天祝": "Tianzhu", "祁连": "Qilian", "德令哈": "Delingha", "肃北": "Subei",
      "门源": "Menyuan", "刚察": "Gangcha", "山丹": "Shandan", "天峻": "Tianjun",
      "民乐": "Minle", "阿克塞": "Aksai"}
cnt["unit"] = cnt["unit"].map(PN).fillna(cnt["unit"])
fig, ax = plt.subplots(figsize=(6.8, 4.6))
colors = [RED if v < 0.2 else (ORANGE if v < 0.35 else GREEN) for v in cnt["esi_2020"]]
ax.barh(cnt["unit"], cnt["esi_2020"], color=colors, alpha=0.88)
for i, v in enumerate(cnt["esi_2020"]):
    ax.text(v + 0.008, i, f"{v:.3f}", va="center", fontsize=7.5)
ax.axvline(0.4, color="#888888", ls="--", lw=0.8)
ax.text(0.405, -0.6, "mild-warning threshold", fontsize=7, color="#888888")
ax.set_xlabel("ESI (2020)"); ax.set_xlim(0, 0.55)
ax.grid(axis="x", alpha=0.25, lw=0.4)
plt.tight_layout(); plt.savefig(os.path.join(FIG, "fig7_county_esi.png")); plt.close()

print("saved fig6/fig7")