# -*- coding: utf-8 -*-
"""R32: Fig. 6 (alpha sensitivity) for the eight-indicator primary specification.

Data: data/r28_alpha_grade_matrix.csv, scenario=drop_X9 (eight indicators, primary) and
scenario=baseline9 (nine-indicator contrast).  The same output filenames as the older
single-curve script are used, so the manuscript include path is unchanged.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(BASE, "figures")
import jms_style  # noqa: F401  (JMS §6: figure text 8-9 pt)

BLUE, GRAY, RED, GREEN = "#2166ac", "#7a7a7a", "#b2182b", "#1b7837"
m = pd.read_csv(os.path.join(BASE, "data", "r28_alpha_grade_matrix.csv"))
piv = m.pivot_table(index="alpha", columns="scenario", values="esi_2023")
assert {"drop_X9", "baseline9"} <= set(piv.columns), piv.columns
a = piv.index.values
prim = piv["drop_X9"].values
base = piv["baseline9"].values

fig, ax = plt.subplots(figsize=(7.0, 4.2))
ax.fill_between(a, 0.4, 0.6, color="#f4d03f", alpha=0.4, label="Mild-warning zone")
ax.plot(a, prim, "-o", color=BLUE, lw=2, ms=5.5, zorder=4,
        label="Eight indicators (primary)")
ax.plot(a, base, "--s", color=GRAY, lw=1.4, ms=4.0, zorder=3,
        label="Nine indicators (contrast)")
ax.axhline(0.4, color=RED, ls="--", lw=1.1, label="Medium-warning threshold (0.4)")
ax.axhline(0.6, color=GREEN, ls="--", lw=1.1, label="Relatively-safe threshold (0.6)")
ax.text(0.5, 0.55, "ESI 2023, eight indicators: %.3f-%.3f\nnine indicators: %.3f-%.3f"
        "\nGrade: mild warning (all $\\alpha$)" % (prim.min(), prim.max(), base.min(), base.max()),
        ha="center", fontsize=8.0,
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=BLUE, alpha=0.9))
ax.set_xlabel(r"Weighting ratio $\alpha$ (0 = entropy only, 1 = AHP only)")
ax.set_ylabel("ESI 2023")
ax.set_xlim(0, 1)
ax.set_ylim(0.35, 0.62)
ax.legend(fontsize=8, loc="lower right")
ax.grid(alpha=0.25, lw=0.4)
plt.tight_layout()
plt.savefig(os.path.join(FIG, "fig4_alpha_sensitivity.pdf"))
plt.savefig(os.path.join(FIG, "fig4_alpha_sensitivity.png"))
plt.close()
print("eight-indicator alpha endpoints: %.6f (a=0) -> %.6f (a=1)" % (prim[0], prim[-1]))
print("nine-indicator  alpha endpoints: %.6f (a=0) -> %.6f (a=1)" % (base[0], base[-1]))
print("alpha values:", ", ".join("%.1f" % x for x in a))