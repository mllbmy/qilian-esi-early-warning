# -*- coding: utf-8 -*-
"""渲染规范数学公式（matplotlib mathtext → 高清 PNG，供 Word 插入）"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "equations")
os.makedirs(OUT, exist_ok=True)

EQUATIONS = {
    "eq1_norm_pos": r"$x'_{ij}=\frac{x_{ij}-\min_j}{\max_j-\min_j}$",
    "eq2_norm_neg": r"$x'_{ij}=\frac{\max_j-x_{ij}}{\max_j-\min_j}$",
    "eq3_weight":   r"$w_j=\alpha\,w^A_j+(1-\alpha)\,w^E_j,\quad \alpha\in[0,1]$",
    "eq4_esi":      r"$\mathrm{ESI}_i=\sum_{j=1}^{m}w_j\,x'_{ij},\quad \mathrm{ESI}\in[0,1]$",
    "eq5_gm":       r"$\hat{x}^{(0)}(k+1)=\left(1-e^{\hat{a}}\right)\left(x^{(0)}(1)-\frac{\hat{b}}{\hat{a}}\right)e^{-\hat{a}k}$",
    "eq6_q":        r"$q=1-\frac{\sum_{h=1}^{L}N_h\,\sigma_h^2}{N\,\sigma^2}$",
}

for name, tex in EQUATIONS.items():
    fig = plt.figure(figsize=(8, 1.1))
    fig.text(0.5, 0.5, tex, ha="center", va="center", fontsize=20)
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=300, bbox_inches="tight",
                pad_inches=0.08, transparent=True)
    plt.close(fig)
    print("渲染:", name)

print("公式图已保存至", OUT)
