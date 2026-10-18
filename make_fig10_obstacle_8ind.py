# -*- coding: utf-8 -*-
r"""Fig. 10 —— obstacle degrees under the EIGHT-indicator primary specification
(2005--2023), with the nine-indicator set kept as an explicitly labelled contrast panel.

CALCULATION SPECIFICATION (the "口径"; see data/results_obstacle_8ind.csv)
-------------------------------------------------------------------------
The primary specification is *defined* as: take the archived nine-indicator
obstacle table ``data/results_obstacle.csv`` (columns = the nine candidate
indicators; every row already normalised to sum to 1 in that table), **delete the
ecological land proportion X9** -- the exact duplicate of grassland + forest +
water that the de-redundancy step removes (Sec. 2.1 / Table 2 of the manuscript)
-- and **renormalise each year's row back to 1**:

    O*_8(i,j) = O*_9(i,j) / (1 - O*_9(i,X9)),   j != X9

This is the archived-table transform, and it is what the manuscript quotes in
Sec. 4.10 and Sec. 5.3 (recovery phase water 0.274 > forest 0.260 > grassland
0.127; plateau phase grassland change rate 0.384 > cropland 0.218 > water 0.099;
the 0.218 cropland plateau value used in Sec. 5.3/5.4).  The two steps above
reproduce every one of those quoted phase means **digit for digit**:

    2005-2010   water 0.273776  forest 0.260331  grassland 0.127082  cropland 0.099850
    2011-2023   g. change rate 0.383767  cropland 0.217862  water 0.098605

(dropping the ecological land column without the second renormalisation step
returns 0.273781 / 0.260336 / 0.127083 / 0.099854 / 0.383764 / 0.217860 /
0.098605, i.e. differs only in the sixth decimal because the archived rows carry
4-decimal rounding; the renormalisation removes that residual inconsistency.)

No value in this figure is hand-entered: everything is read from
``data/results_obstacle.csv`` and transformed by the two lines above.  The
allocation-free cross-check against the independently re-weighted R28 pipeline
(``run_r28_t7_obstacle.py``, scenario ``drop_X9``, combined weights alpha=0.4)
gives the same ranking but shifts the plateau-phase grassland change rate to
0.369 and cropland to 0.212, which is the recomputation agreement quoted in
Sec. 4.10 ("reproduces them to within 0.014").

LAYOUT
------
Top panel  : eight-indicator primary specification -- the five indicators named
             in the text carry the DPSIR layer colours used by
             make_fig_trends.py / make_fig_weights.py and are labelled at the
             2023 end of their curves; the remaining three recede to light grey.
Bottom     : explicit contrast panel, nine-indicator set -- the eight shared
             indicators in light grey and the retained ecological land proportion
             highlighted, so the reader can see exactly what the nine-indicator
             reading adds instead of the two sets being mixed into one curve.

JMS compliance (guide Sec. 5.7): "Words in figures must be in Times New Roman.
Suggested figure sizes are 7-8 cm or 14-16 cm at width with font size at 8-9
point."  -> every label is drawn in Times New Roman (jms_style, resolved to
C:/Windows/Fonts/times.ttf, embedded as TimesNewRomanPSMT); the canvas is drawn
at the inserted width 0.92\linewidth = 15.27 cm (the 14-16 cm option) so all text
prints at its nominal size, and every text element is set to 8-9 pt.

Outputs: figures/fig_obstacle.pdf (vector) + figures/fig_obstacle.png (600 dpi)
         data/results_obstacle_8ind.csv (the primary annual obstacle degrees)
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoMinorLocator

import jms_style  # JMS guideline Sec. 6: Times New Roman 8-9 pt

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------
# 1) data: nine-indicator archive -> eight-indicator primary specification
# --------------------------------------------------------------------------
NINE = pd.read_csv(os.path.join(BASE, "data", "results_obstacle.csv"), index_col=0)
years = NINE.index.astype(int).values
X9 = "\u751f\u6001\u7528\u5730"                       # ecological land proportion
assert X9 in NINE.columns, "archived table has no ecological-land column"

row9 = NINE.sum(axis=1)
assert np.allclose(row9, 1.0, atol=1e-3), "archived table is not row-normalised"

EIGHT = NINE.drop(columns=[X9])
den = 1.0 - NINE[X9]
EIGHT = EIGHT.div(den, axis=0)
EIGHT = EIGHT.div(EIGHT.sum(axis=1), axis=0)          # exact renormalisation to 1
assert np.allclose(EIGHT.sum(axis=1), 1.0, atol=1e-12)

EN = {"\u964d\u6c34": "Precipitation", "\u6c14\u6e29": "Temperature",
      "\u8349\u5730": "Grassland", "\u68ee\u6797": "Forest",
      "\u6c34\u57df": "Water", "\u88f8\u5730/\u8352\u6f20": "Barren/degraded",
      "\u519c\u7530": "Cropland",
      "\u8349\u5730\u53d8\u5316\u7387": "Grassland\nchange rate",
      X9: "Ecological land\n(nine-indicator only)"}
assert set(EN) == set(NINE.columns), "column naming changed in results_obstacle.csv"

# DPSIR layer colours, identical to make_fig_trends.py / make_fig_weights.py
COL = {"\u964d\u6c34": "#1f6f9f", "\u6c14\u6e29": "#5aa9cf",
       "\u8349\u5730": "#14532d", "\u68ee\u6797": "#2e8b57",
       "\u6c34\u57df": "#52b788", "\u88f8\u5730/\u8352\u6f20": "#a52633",
       "\u519c\u7530": "#d1495b", "\u8349\u5730\u53d8\u5316\u7387": "#b06c1f",
       X9: "#5a4a8a"}
C_GREY = "#c3c9cf"
INK, GRID = "#14181c", "#dce2e8"

# the five indicators named in Sec. 4.10 / Sec. 5.3 carry the layer colours
KEY = ["\u6c34\u57df", "\u68ee\u6797", "\u8349\u5730",
       "\u8349\u5730\u53d8\u5316\u7387", "\u519c\u7530"]
GREY = [c for c in EIGHT.columns if c not in KEY]

# phase means actually plotted (printed for the record)
p1, p2 = EIGHT.loc[2005:2010].mean(), EIGHT.loc[2011:2023].mean()
x1, x2 = NINE[X9].loc[2005:2010].mean(), NINE[X9].loc[2011:2023].mean()
print("eight-indicator phase means, 2005-2010:")
print(p1.sort_values(ascending=False).round(6).to_string())
print("eight-indicator phase means, 2011-2023:")
print(p2.sort_values(ascending=False).round(6).to_string())
print("contrast (b): ecological land phase mean 2005-2010 = %.6f, 2011-2023 = %.6f"
      % (x1, x2))

# --------------------------------------------------------------------------
# 2) figure
# --------------------------------------------------------------------------
# JMS guideline Sec. 5.7: "Suggested figure sizes are 7-8 cm or 14-16 cm at width
# with font size at 8-9 point."  This figure is inserted at 0.92\linewidth =
# 15.27 cm = 6.012 in, i.e. inside the 14-16 cm option, and the canvas is drawn at
# exactly that width so every label below prints at its nominal point size
# (all text 8-9 pt: ticks/labels 8, axis titles 9).
fig, (ax, axc) = plt.subplots(
    2, 1, figsize=(6.012, 4.29), sharex=True,
    gridspec_kw={"height_ratios": [3.0, 1.22], "hspace": 0.12},
    layout="constrained")

# ---- top panel: eight-indicator primary specification -------------------
for c in GREY:
    ax.plot(years, EIGHT[c].values, color=C_GREY, lw=0.9, zorder=1)
for c in KEY:
    v = EIGHT[c].values
    ax.plot(years, v, color=COL[c], lw=1.5, zorder=3)
    ax.plot([years[-1]], [v[-1]], "o", ms=3.2, color=COL[c], zorder=4)
    ax.text(2023.5, v[-1], EN[c],
            fontsize=8.0, color=COL[c], linespacing=1.1,
            ha="left", va="center", zorder=4)

ax.axvline(2010.5, color=INK, lw=0.8, ls=(0, (3, 2)), zorder=2)
ax.text(2007.75, 1.035, "Recovery phase", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=8, color="#4a5560")
ax.text(2016.75, 1.035, "Plateau phase", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=8, color="#4a5560")
ax.text(0.0, 1.035, "(a)", transform=ax.transAxes, ha="left", va="bottom",
        fontsize=8.5, fontweight="bold", color=INK)

ax.set_ylim(0, 0.5)
ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5])
ax.yaxis.set_minor_locator(AutoMinorLocator(2))
ax.set_ylabel("Annual obstacle degree", fontsize=9)

# ---- bottom panel: nine-indicator contrast ------------------------------
for c in EIGHT.columns:                       # the eight shared indicators
    axc.plot(years, NINE[c].values, color=C_GREY, lw=0.8, zorder=1)
axc.plot(years, NINE[X9].values, color=COL[X9], lw=1.5, zorder=3)
axc.plot([years[-1]], [NINE[X9].values[-1]], "o", ms=3.2, color=COL[X9], zorder=4)
axc.text(2023.5, NINE[X9].values[-1], EN[X9], fontsize=8.0, color=COL[X9],
         linespacing=1.1, ha="left", va="center", zorder=4)
axc.axvline(2010.5, color=INK, lw=0.8, ls=(0, (3, 2)), zorder=2)
axc.text(0.0, 1.06, "(b) Contrast: nine-indicator set",
         transform=axc.transAxes, ha="left", va="bottom",
         fontsize=8.0, fontweight="bold", color=INK)
axc.set_ylim(0, 0.5)                          # same range as (a): nothing clipped
axc.set_yticks([0, 0.25, 0.5])
axc.set_yticklabels(["0.0", "0.25", "0.5"])
axc.yaxis.set_minor_locator(AutoMinorLocator(2))
axc.set_ylabel("Obstacle\ndegree", fontsize=8, linespacing=1.15)
axc.set_xlabel("Year", fontsize=9)

# ---- shared axis cosmetics ---------------------------------------------
for a in (ax, axc):
    a.set_xlim(2004.6, 2027.4)                # right extension for end labels
    a.set_xticks([2005, 2008, 2011, 2014, 2017, 2020, 2023])
    a.xaxis.set_minor_locator(AutoMinorLocator(2))
    a.tick_params(labelsize=8, length=2.0, pad=1.5)
    a.tick_params(which="minor", length=1.2, colors="#9aa7b2")
    a.grid(axis="both", color=GRID, lw=0.5, ls=(0, (4, 2)), zorder=0)
    for s in ("top", "right"):
        a.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        a.spines[s].set_color("#9aa7b2")
        a.spines[s].set_linewidth(0.6)

fig.legend(handles=[
    Line2D([], [], color=C_GREY, lw=0.9,
           label="(a) other primary-set indicators: "
                 + ", ".join(EN[c] for c in GREY)),
    Line2D([], [], color=C_GREY, lw=0.8,
           label="(b) the eight indicators shared with panel (a)"),
], loc="outside lower center", ncol=1, fontsize=8.0, frameon=False,
    handlelength=1.6, handletextpad=0.5, borderaxespad=0.0)

# --------------------------------------------------------------------------
# 3) outputs
# --------------------------------------------------------------------------
FIG = os.path.join(BASE, "figures")
fig.savefig(os.path.join(FIG, "fig_obstacle.pdf"))
fig.savefig(os.path.join(FIG, "fig_obstacle.png"), dpi=600)

out = EIGHT.copy()
out.index.name = "year"
out.round(8).to_csv(os.path.join(BASE, "data", "results_obstacle_8ind.csv"),
                    encoding="utf-8-sig")
print("saved figures/fig_obstacle.pdf/.png (8-ind primary + 9-ind contrast panel); "
      "row sums = %.12f; primary recovery leader = %s %.4f, plateau leader = %s %.4f"
      % (EIGHT.sum(axis=1).mean(),
         EN[p1.idxmax()].replace("\n", " "), p1.max(),
         EN[p2.idxmax()].replace("\n", " "), p2.max()))
print("cropland plateau mean (Sec. 5.3 value) = %.6f -> %.3f"
      % (p2["\u519c\u7530"], round(p2["\u519c\u7530"], 3)))