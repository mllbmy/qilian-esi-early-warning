# -*- coding: utf-8 -*-
"""
生态安全预警方法管线原型（prototype）
====================================
方向 A：DPSIR 指标体系 → 极差标准化 → 熵权法 + AHP 组合权重 → ESI 生态安全指数
         → GM(1,1) 灰色预测 → 预警分级 → GeoDetector 驱动因子 → 精度检验

用法：
  from eco_security import pipeline
  results = pipeline.run(indicator_matrix, directions, labels, ...)

说明：本原型用演示数据验证管线可运行；正式研究替换为真实案例区数据即可。
依赖：numpy, scipy（GeoDetector 部分用纯 numpy 实现，无需额外包）
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------------------
# 1. 极差标准化
# ---------------------------------------------------------------------------
def minmax_normalize(X: np.ndarray, directions: list[int]) -> np.ndarray:
    """X: (n_samples, m_indicators)；directions: +1 正向 / -1 负向。
    返回标准化矩阵 X' ∈ [0,1]。"""
    X = np.asarray(X, dtype=float)
    Xn = np.zeros_like(X)
    for j, d in enumerate(directions):
        col = X[:, j]
        lo, hi = col.min(), col.max()
        if hi - lo < 1e-12:
            Xn[:, j] = 1.0
        elif d >= 0:
            Xn[:, j] = (col - lo) / (hi - lo)
        else:
            Xn[:, j] = (hi - col) / (hi - lo)
    return Xn


# ---------------------------------------------------------------------------
# 2. 熵权法
# ---------------------------------------------------------------------------
def entropy_weights(Xn: np.ndarray) -> np.ndarray:
    """基于标准化矩阵计算熵权 w^E。"""
    n, m = Xn.shape
    P = Xn / (Xn.sum(axis=0, keepdims=True) + 1e-12)
    # 处理 0 值：0 ln 0 = 0
    P = np.clip(P, 1e-12, 1.0)
    e = -1.0 / np.log(n) * (P * np.log(P)).sum(axis=0)
    d = 1.0 - e
    w = d / (d.sum() + 1e-12)
    return w


# ---------------------------------------------------------------------------
# 3. AHP 权重（特征向量法 + 一致性检验）
# ---------------------------------------------------------------------------
def ahp_weights(cmp: np.ndarray) -> tuple[np.ndarray, float, float]:
    """cmp: 判断矩阵 (m, m)。返回 (w^A, CI, CR)。"""
    cmp = np.asarray(cmp, dtype=float)
    m = cmp.shape[0]
    eigvals, eigvecs = np.linalg.eig(cmp)
    i = int(np.argmax(eigvals.real))
    w = np.abs(eigvecs[:, i].real)
    w = w / w.sum()
    lam = eigvals.real[i]
    CI = (lam - m) / (m - 1)
    RI = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32,
          8: 1.41, 9: 1.45, 10: 1.49}.get(m, 1.49)
    CR = CI / RI if RI > 0 else 0.0
    return w, CI, CR


# ---------------------------------------------------------------------------
# 4. 组合权重
# ---------------------------------------------------------------------------
def combined_weights(w_ahp: np.ndarray, w_ent: np.ndarray, alpha: float = 0.5) -> np.ndarray:
    """线性组合：w = alpha * w^A + (1-alpha) * w^E"""
    return alpha * np.asarray(w_ahp) + (1.0 - alpha) * np.asarray(w_ent)


# ---------------------------------------------------------------------------
# 5. 生态安全指数 ESI
# ---------------------------------------------------------------------------
def esi_series(Xn: np.ndarray, w: np.ndarray) -> np.ndarray:
    """ESI_i = sum_j w_j * X'_{ij}，返回每个样本的 ESI。"""
    return Xn @ w


# ---------------------------------------------------------------------------
# 6. GM(1,1) 灰色预测
# ---------------------------------------------------------------------------
def gm11_forecast(x0: np.ndarray, n_pred: int = 5) -> tuple[np.ndarray, np.ndarray, float, float]:
    """GM(1,1) 建模与预测。
    返回 (预测值序列(含原始期之后 n_pred 个), 拟合值, 后验差比值 C, 小误差概率 P)。
    """
    x0 = np.asarray(x0, dtype=float)
    n = len(x0)
    x1 = np.cumsum(x0)
    z1 = 0.5 * (x1[1:] + x1[:-1])
    B = np.column_stack([-z1, np.ones(n - 1)])
    Y = x0[1:]
    theta, *_ = np.linalg.lstsq(B, Y, rcond=None)  # theta = [a, b]
    a, b = theta
    # 拟合值（后验检验用）
    x1_hat = (x0[0] - b / a) * np.exp(-a * np.arange(1, n + 1)) + b / a
    x0_hat = np.empty(n)
    x0_hat[0] = x0[0]
    x0_hat[1:] = np.diff(x1_hat)
    # 残差检验
    e = x0 - x0_hat
    S1 = x0.std(ddof=1)
    S2 = e.std(ddof=1) if n > 2 else 0.0
    C = S2 / S1 if S1 > 1e-12 else 0.0
    em = e.mean()
    P = np.mean(np.abs(e - em) < 0.6745 * S1) if S1 > 1e-12 else 1.0
    # 预测
    future = np.empty(n_pred)
    for k in range(n_pred):
        t = n + k + 1
        future[k] = (1 - np.exp(a)) * (x0[0] - b / a) * np.exp(-a * (t - 1))
    return future, x0_hat, C, P


# ---------------------------------------------------------------------------
# 7. 预警分级
# ---------------------------------------------------------------------------
def classify_warning(esi: np.ndarray, thresholds=None) -> list[str]:
    """默认五级：安全[0.8,1] 较安全[0.6,0.8) 轻警[0.4,0.6) 中警[0.2,0.4) 重警[0,0.2)。"""
    if thresholds is None:
        thresholds = [0.2, 0.4, 0.6, 0.8]
    levels = ["重警", "中警", "轻警", "较安全", "安全"]
    out = []
    for v in esi:
        lv = 0
        for i, t in enumerate(thresholds):
            if v >= t:
                lv = i + 1
        out.append(levels[lv])
    return out


# ---------------------------------------------------------------------------
# 8. GeoDetector 因子探测器（q 统计量）
# ---------------------------------------------------------------------------
def geodetector_q(y: np.ndarray, x_discrete: np.ndarray) -> float:
    """q = 1 - sum_h (N_h * sigma_h^2) / (N * sigma^2)
    y: 连续因变量；x_discrete: 离散化后的因子（整数分层）。"""
    y = np.asarray(y, dtype=float)
    xd = np.asarray(x_discrete, dtype=int)
    N = len(y)
    var_total = y.var(ddof=0)
    if var_total < 1e-12:
        return 0.0
    ssw = 0.0
    for h in np.unique(xd):
        mask = xd == h
        Nh = mask.sum()
        ssw += Nh * y[mask].var(ddof=0)
    return 1.0 - ssw / (N * var_total)


# ---------------------------------------------------------------------------
# 9. 统一管线
# ---------------------------------------------------------------------------
def run(X: np.ndarray, directions: list[int], cmp: np.ndarray,
        alpha: float = 0.5, n_pred: int = 5):
    """完整管线。X: (n, m) 原始指标；directions: ±1；cmp: AHP 判断矩阵。"""
    Xn = minmax_normalize(X, directions)
    w_ent = entropy_weights(Xn)
    w_ahp, CI, CR = ahp_weights(cmp)
    w = combined_weights(w_ahp, w_ent, alpha)
    esi = esi_series(Xn, w)
    future, fitted, C, P = gm11_forecast(esi, n_pred)
    levels = classify_warning(esi)
    fut_levels = classify_warning(future)
    return {
        "X_norm": Xn,
        "w_entropy": w_ent,
        "w_ahp": w_ahp,
        "CI": CI, "CR": CR,
        "w_combined": w,
        "esi": esi,
        "esi_fitted": fitted,
        "warning_levels": levels,
        "esi_forecast": future,
        "forecast_levels": fut_levels,
        "gm_C": C, "gm_P": P,
    }


if __name__ == "__main__":
    # 演示数据：10 年 × 8 项指标（DPSIR）
    rng = np.random.default_rng(42)
    X = rng.uniform(0.2, 1.0, size=(10, 8))
    directions = [+1, +1, -1, +1, +1, -1, +1, +1]
    cmp = np.ones((8, 8))  # 简化：等权判断矩阵（CR=0）
    r = run(X, directions, cmp, n_pred=5)
    np.set_printoptions(precision=4, suppress=True)
    print("熵权:", r["w_entropy"])
    print("组合权重:", r["w_combined"])
    print("ESI 序列:", r["esi"])
    print("预警等级:", r["warning_levels"])
    print("GM(1,1) 预测:", r["esi_forecast"])
    print("预测预警:", r["forecast_levels"])
    print("精度检验  C=%.4f  P=%.4f" % (r["gm_C"], r["gm_P"]))
    # GeoDetector 演示：5 个空间单元 × 因子
    y = np.array([0.85, 0.62, 0.45, 0.31, 0.72])
    f = np.array([1, 1, 2, 3, 2])
    print("GeoDetector q(演示): %.4f" % geodetector_q(y, f))
