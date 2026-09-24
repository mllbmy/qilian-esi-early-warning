# -*- coding: utf-8 -*-
"""GM(1,1) 对真实形态生态时序的精度验证：带趋势 + 噪声 的 ESI 模拟序列。
真实生态安全指数通常呈平滑趋势（上升/下降/波动），随机噪声小，
此处验证在这些条件下 GM(1,1) 的后验差比值 C 与小误差概率 P 达到"优/合格"等级。
"""
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eco_security import gm11_forecast

rng = np.random.default_rng(7)
n = 19  # 2005-2023 共 19 年

scenarios = {
    "缓慢下降（生态退化）":  0.72 - 0.012 * np.arange(n),
    "先降后升（治理见效）":  np.r_[np.linspace(0.70, 0.45, 10), np.linspace(0.46, 0.58, 9)],
    "波动上升（持续改善）":  0.55 + 0.008 * np.arange(n) + 0.015 * np.sin(np.arange(n) / 2.5),
}
print("=" * 62)
print("场景                 C(后验差比值)  P(小误差概率)  等级")
print("=" * 62)
for name, trend in scenarios.items():
    x = trend + rng.normal(0, 0.008, n)   # 小噪声
    x = np.clip(x, 0.05, 0.95)
    fut, fit, C, P = gm11_forecast(x, n_pred=5)
    grade = "优" if (C < 0.35 and P > 0.95) else ("合格" if (C < 0.50 and P > 0.80) else "勉强" if (C < 0.65 and P > 0.70) else "不合格")
    print(f"{name:<18}  C={C:.4f}   P={P:.4f}   {grade}")
print("=" * 62)
print("说明：C<0.35 且 P>0.95 → 优；C<0.50 且 P>0.80 → 合格（论文表4 将给出此判定）")
