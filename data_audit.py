# -*- coding: utf-8 -*-
"""数据核对（用户要求的"数据核对"专项）：论文正文行文引用的每个关键数值，
都必须在 data/*.csv 中找得到（含容差）；找不到的列出来人工判断。"""
import os

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")


def load_numeric():
    """把 data/ 下所有 csv 的数值单元收集成集合（浮点数，容差后比对）。"""
    vals = []
    files = sorted(f for f in os.listdir(DATA) if f.lower().endswith(".csv"))
    for f in files:
        path = os.path.join(DATA, f)
        try:
            txt = open(path, encoding="utf-8-sig", errors="replace").read()
        except Exception:
            continue
        for tok in txt.replace(",", " ").split():
            try:
                vals.append(float(tok))
            except ValueError:
                pass
    return files, vals


def found(vals, v, tol=0.003):
    return any(abs(x - v) <= tol for x in vals)


FILES, VALS = load_numeric()

# (数值, 容差, 出处说明)
CHECKS = [
    (0.258, "ESI 2005"), (0.709, "ESI 峰值 2010"), (0.486, "ESI 2023"),
    (0.425, "α=0 纯熵 2023 ESI"), (0.578, "α=1 纯 AHP 2023 ESI"),
    (0.446, "NGBM 2024 预测"), (0.394, "NGBM 2028 预测"),
    (0.358, "NGBM 2024 区间下界"), (0.533, "NGBM 2024 区间上界"),
    (0.306, "NGBM 2028 区间下界"), (0.482, "NGBM 2028 区间上界"),
    (0.038, "NGBM RMSE"), (0.029, "NGBM MAE"), (0.442, "NGBM C"), (0.895, "NGBM P"),
    (0.052, "GM RMSE"), (0.035, "GM MAE"), (0.597, "GM C"), (0.789, "GM P"),
    (0.098, "ARIMA RMSE"), (0.067, "ARIMA MAE"), (1.086, "ARIMA C"), (0.632, "ARIMA P"),
    (0.510, "GM 2024 预测"), (0.493, "GM 2028 预测"), (0.488, "ARIMA 2024/2028 预测"),
    (0.466, "Sunan ESI 2020"), (0.395, "Tianzhu"), (0.390, "Qilian"),
    (0.366, "Delingha"), (0.344, "Subei"), (0.306, "Menyuan"),
    (0.289, "Gangcha"), (0.260, "Shandan"), (0.251, "Tianjun"),
    (0.166, "Minle"), (0.074, "Aksai"),
    (0.802, "barren q"), (0.708, "grassland q"), (0.506, "precipitation q"),
    (0.170, "temperature q"),
    (0.643, "Moran's I"),
    (0.849, "交互 temp×barren"), (0.833, "交互 precip×barren"),
    (0.818, "交互 grass×barren"), (0.808, "交互 precip×grass"),
    (0.723, "交互 temp×grass"), (0.530, "交互 temp×precip"),
    (0.206, "组合权重 草地变化率"), (0.136, "组合权重 生态用地"),
    (0.128, "组合权重 水域"), (0.120, "组合权重 森林"),
    (0.245, "熵权 草地变化率"), (0.171, "熵权 耕地占比"),
    (0.233, "障碍度 水域(恢复期)"), (0.221, "障碍度 森林(恢复期)"),
    (0.151, "障碍度 生态用地(恢复期)"), (0.364, "障碍度 草地变化率(平稳期)"),
    (0.081, "D 权重"), (0.438, "S 权重"), (0.149, "I 权重"), (0.250, "R 权重"),
    (0.0034, "CR"), (5.015, "λmax"),
    (0.034, "滚动回测 NGBM RMSE"),
]
# 分析计数/斜率等不逐值核对项（来源固定，另行说明）
print("数据文件 %d 个：%s" % (len(FILES), ", ".join(FILES)))
print("\n数值逐项核对（容差 0.003；在任意 data/*.csv 中找得到即 PASS）：")
nfail = 0
for v, desc in CHECKS:
    ok = found(VALS, v)
    if not ok:
        nfail += 1
    print("  %s  %.3f  %s" % ("PASS" if ok else "FAIL", v, desc))
print("\n结论：%d 项全部找到" % (len(CHECKS) - nfail) if nfail == 0
      else "结论：%d/%d 命中；未命中 %d 项需人工复核" % (len(CHECKS) - nfail, len(CHECKS), nfail))

# 特别核对：障碍度 0.364/0.206 与耕地组合权重 0.119 等
for v, desc in [(0.119, "组合权重 耕地"), (0.111, "熵权 降水"), (0.063, "熵权 气温"),
                (0.103, "组合 草地"), (0.083, "组合 降水"), (0.054, "组合 气温"),
                (0.051, "组合 裸地"), (0.075, "熵权 草地"), (0.059, "熵权 生态用地"),
                (0.115, "熵权 水域"), (0.058, "熵权 裸地")]:
    ok = found(VALS, v)
    if not ok:
        nfail += 1
        print("  FAIL  %.3f  %s（表内值，未在 CSV 找到）" % (v, desc))
print("（若全 PASS 则表内权重与 CSV 一致）")