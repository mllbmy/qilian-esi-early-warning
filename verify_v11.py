# -*- coding: utf-8 -*-
"""v11 定稿校验：继承 verify_v10 全部断言，另加 R5-M1/M2 专项。
M1: CN 首页“目标期刊”行已删除；M2: 图5 换 CVD 安全色图、全图 Arial、示意图与线图均为矢量 PDF。
"""
import os
import re
import subprocess
import sys

# 路径自解析：仓库克隆/解压到任意目录均可运行
BASE = os.path.dirname(os.path.abspath(__file__))
PC = BASE
env = dict(os.environ, PYTHONIOENCODING="utf-8")
fails = []


def chk(cond, msg):
    print("  %s  %s" % ("PASS " if cond else "FAIL ", msg))
    if not cond:
        fails.append(msg)


r = subprocess.run([sys.executable, os.path.join(PC, "verify_v10.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
print(r.stdout.rstrip())
if "verify_v10: ALL PASS" not in (r.stdout or ""):
    fails.append("verify_v10 未全部通过")

print("\n[G] v11 专项（R5：M1 CN 首页清理 + M2 图件技术升级）")

# ---- M1: CN 首页“目标期刊”行 ----
from docx import Document
d = Document(os.path.join(PC, "out", "论文_CN_latest.docx"))
txt = "\n".join(p.text for p in d.paragraphs)
chk("目标期刊" not in txt and "中科院" not in txt and "订阅" not in txt,
    "M1 CN 首页已无“目标期刊/中科院/订阅”字样")

# ---- M2①: 图5 配色 ----
mf = open(os.path.join(PC, "make_figures.py"), encoding="utf-8").read()
chk('cmap="viridis"' in mf and 'cmap="RdYlGn"' not in mf,
    "M2① make_figures.py 图5 已用 viridis（无 RdYlGn）")
from PIL import Image
import numpy as np
im = np.array(Image.open(os.path.join(PC, "figures", "fig5_spatial_esi.png")).convert("RGB")).astype(int)
r_, g_, b_ = im[..., 0], im[..., 1], im[..., 2]
rg_red = int(((abs(r_ - 215) < 25) & (abs(g_ - 25) < 25) & (abs(b_ - 28) < 25)).sum())   # RdYlGn #d7191c
rg_grn = int(((abs(r_ - 26) < 25) & (abs(g_ - 150) < 25) & (abs(b_ - 65) < 25)).sum())   # RdYlGn #1a9641
vir_dk = int(((abs(r_ - 68) < 25) & (abs(g_ - 1) < 25) & (abs(b_ - 84) < 25)).sum())     # viridis #440154
vir_yl = int(((r_ > 225) & (g_ > 210) & (b_ < 95)).sum())                                # viridis #fde725
print("     像素计数: RdYlGn红=%d RdYlGn绿=%d viridis深紫=%d viridis黄=%d" % (rg_red, rg_grn, vir_dk, vir_yl))
chk(rg_red < 50 and rg_grn < 50 and vir_dk > 1000 and vir_yl > 500,
    "M2① 图5 PNG: 无 RdYlGn 红/绿端、viridis 端点色存在")

# ---- M2②: 矢量 PDF 内嵌字体核验（JMS 换刊后为 Times New Roman；兼容 Arial）----
for f in ["fig2_workflow.pdf", "fig3_esi_timeseries.pdf", "fig4_alpha_sensitivity.pdf"]:
    out = subprocess.run(["pdffonts", os.path.join(PC, "figures", f)],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", env=env).stdout
    chk(("Arial" in out) or ("Times" in out), "M2② %s 内嵌 TNR/Arial 字体" % f)

# ---- M2③: 图2/3/4 矢量 PDF + tex 引用切换 ----
for f in ["fig2_workflow.pdf", "fig3_esi_timeseries.pdf", "fig4_alpha_sensitivity.pdf"]:
    chk(os.path.exists(os.path.join(PC, "figures", f)), "M2③ figures/%s 存在" % f)
tex = open(os.path.join(PC, "manuscript.tex"), encoding="utf-8").read()
for f in ["fig_dpsir_framework.pdf", "fig_indicator_trends.pdf",
          "fig3_esi_timeseries.pdf", "fig4_alpha_sensitivity.pdf"]:
    chk(tex.count("figures/" + f) == 1, "M2③ tex 已引用矢量 PDF 图 %s" % f)
chk("fig2_workflow.pdf" not in tex,
    "M2③ 技术路线图已从正文移除（v17 精简：EN 由 7 图回到 6 图）")
chk(tex.count(".png}") == 2, "M2③ tex 仅剩 2 处 PNG 引用（图1/图5，位图保留）")

# ---- M2 卫生: 无被取代旧图块的回归陷阱 ----
mf3 = open(os.path.join(PC, "make_fig3_clean.py"), encoding="utf-8").read()
chk("fig3_esi_timeseries.pdf" in mf3, "M2 make_fig3_clean.py 输出矢量+PNG")
m28 = open(os.path.join(PC, "make_fig2_fig8.py"), encoding="utf-8").read()
chk('savefig(os.path.join(FIG, "fig2_workflow.png")' not in m28,
    "M2 make_fig2_fig8.py 不再输出旧版图2（无覆盖陷阱）")
mm = open(os.path.join(PC, "make_figures.py"), encoding="utf-8").read()
chk('savefig(os.path.join(FIG, "fig3_esi_timeseries.png")' not in mm,
    "M2 make_figures.py 不再输出旧版图3（无覆盖陷阱）")

# ---- m1: 标题已删括号（用户裁定）----
chk("(Including the Qilian Mountain National Park)" not in tex,
    "m1 EN 标题不再含 (Including the Qilian Mountain National Park)")
first_paras = "\n".join(p.text for p in d.paragraphs[:6])
chk("祁连山区域生态安全预警：时序动态、预测与空间驱动因子" in first_paras and "（含祁连山国家公园）" not in first_paras,
    "m1 CN 首页标题（R11 去数模化版）已删「（含祁连山国家公园）」")

# ---- 编译产物状态（本机已重编; 读 log 佐证）----
log = open(os.path.join(PC, "manuscript.log"), encoding="utf-8", errors="replace").read()
m = re.search(r"Output written on.*\((\d+) pages", log)
pg = int(m.group(1)) if m else -1
chk(pg in (14, 15, 16, 17), "EN 编译页数 14–17（实际 %s；v3 加图轮新增 4 图后上浮至 17）" % pg)
chk("Citation " not in log or "undefined" not in log, "无未定义引用")

print("\n" + ("verify_v11: ALL PASS" if not fails else "verify_v11: %d FAIL" % len(fails)))
sys.exit(1 if fails else 0)