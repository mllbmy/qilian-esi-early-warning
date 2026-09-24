# -*- coding: utf-8 -*-
"""v12 定稿校验：继承 verify_v11（含 R5-M1/M2/m1），另加 R5-M3 图5/CN图7 可读性重构断言。"""
import glob
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

PC = os.path.dirname(os.path.abspath(__file__))
# 2026-09-22 两刊分列：交付下按期刊前缀命名（JNC_*/JMS_*），此处兼容旧名
DLV = os.path.join(os.path.dirname(PC), "交付")
MAT = os.path.join(DLV, "JNC_投稿材料") if os.path.isdir(os.path.join(DLV, "JNC_投稿材料")) \
      else os.path.join(DLV, "投稿材料")
env = dict(os.environ, PYTHONIOENCODING="utf-8")
fails = []


def chk(cond, msg):
    print("  %s  %s" % ("PASS " if cond else "FAIL ", msg))
    if not cond:
        fails.append(msg)


r = subprocess.run([sys.executable, os.path.join(PC, "verify_v11.py")],
                   capture_output=True, text=True, encoding="utf-8",
                   errors="replace", env=env)
print(r.stdout.rstrip())
if "verify_v11: ALL PASS" not in (r.stdout or ""):
    fails.append("verify_v11 未全部通过")

print("\n[H] v12 专项（R5-M3：图5/CN图7 可读性重构，最低方案四件套）")

# ---- 脚本参数断言（make_figures.py 图5 块）----
py = open(os.path.join(PC, "make_figures.py"), encoding="utf-8").read()
chk("vmin=0.05, vmax=0.60" in py, "M3-1 vmin/vmax 已数据驱动（0.05–0.60，viridis 全程发色）")
chk("cmap=\"viridis\", s=24" in py, "M3-2 点径 s=24（20–30 区间内）")
chk("from matplotlib import patheffects" in py
    and "patheffects.withStroke(linewidth=2.2, foreground=\"white\")" in py,
    "M3-3 县名白描边（withStroke）已启用")
chk("ax.grid(alpha=0.12" in py, "M3-4 网格淡化 alpha=0.12（≤0.3）")

# ---- 像素级断言（实测基准：dark 43% / teal 90.8 万 / green 5.1 万 / yellow 1.6 万 / 中高位 31%）----
im = np.array(Image.open(os.path.join(PC, "figures", "fig5_spatial_esi.png")).convert("RGB")).astype(int)
rr, gg, bb = im[..., 0], im[..., 1], im[..., 2]


def near(c, tol=25):
    return int(((abs(rr - c[0]) < tol) & (abs(gg - c[1]) < tol) & (abs(bb - c[2]) < tol)).sum())


white = int(((rr > 245) & (gg > 245) & (bb > 245)).sum())
colored = int(rr.size - white)
dark = near((68, 1, 84))          # viridis 0.00
teal = near((33, 145, 140))       # viridis 0.50
green = near((94, 201, 98))       # viridis 0.78
yellow = int(((rr > 225) & (gg > 210) & (bb < 95)).sum())  # viridis 1.00
midhigh = teal + green + yellow
print("     像素: colored=%d dark=%.1f%% teal=%d green=%d yellow=%d midhigh=%.1f%%"
      % (colored, 100.0 * dark / max(colored, 1), teal, green, yellow,
         100.0 * midhigh / max(colored, 1)))
chk(100.0 * dark / max(colored, 1) < 60, "暗端占比 < 60%（不再整图暗紫蓝）")
chk(teal > 300000, "teal 像素充足（东侧中高值可见，实测 %d）" % teal)
chk(green > 10000 and yellow > 3000, "green(%d)/yellow(%d) 端存在（最高值发色）" % (green, yellow))
chk(100.0 * midhigh / max(colored, 1) > 20, "中高位合计 > 20%（东高西低梯度肉眼可辨）")

# ---- CN 图7 同源同步 ----
cn_build = open(os.path.join(PC, "build_word_cn.py"), encoding="utf-8").read()
chk("fig5_spatial_esi.png" in cn_build, "CN 图6 引用的正是 fig5_spatial_esi.png（同源）")
png_t = os.path.getmtime(os.path.join(PC, "figures", "fig5_spatial_esi.png"))
docx_t = os.path.getmtime(os.path.join(PC, "out", "论文_CN_latest.docx"))
chk(png_t < docx_t, "CN docx 已在新图之后重建（时间戳 %s < %s）"
    % (png_t, docx_t))

# ---- 投稿材料终检（Qoder F1/F2）：版本引用不过期 + Highlights 术语语序统一 ----
tex_f = open(os.path.join(PC, "manuscript.tex"), encoding="utf-8").read()
chk("\\section*{Highlights}" not in tex_f,
    "F2 正文已无 Highlights 段（v20 起独立文件提交，两者不重复）")
hl_txt = open(os.path.join(MAT, "Highlights.txt"),
              encoding="utf-8").read()
chk("objective-subjective" not in hl_txt and "subjective-objective weighting ratio" in hl_txt,
    "F2 Highlights.txt 项 3 语序已同步")
_mat_glob = sorted(glob.glob(os.path.join(MAT, "cover_letter_*.md")))
cl_txt = open(_mat_glob[-1], encoding="utf-8").read()   # 跟随最新日期的材料副本
# F1 改为"跟随最新冻结稿"而非硬编码版本号：材料里写到的稿本文件必须真实存在
_ref_file, _ref_ver, _ref_dir = None, None, None
for _d in sorted([x for x in os.listdir(DLV)
                  if re.search(r"(^|_)v\d+_\d{4}-\d{2}-\d{2}$", x)
                  and os.path.isdir(os.path.join(DLV, x))],
                 key=lambda s: int(re.search(r"v(\d+)", s).group(1)), reverse=True):
    _v = "v" + re.search(r"v(\d+)", _d).group(1)
    _dt = _d.split("_")[-1]
    for _ext in (".docx", ".pdf"):      # 投稿主体可为 Word（须知要求可编辑源文件）或 PDF
        _cand = "论文_EN_%s_%s%s" % (_v, _dt, _ext)
        if _cand in cl_txt:
            _ref_file, _ref_ver, _ref_dir = _cand, _v, _d
            break
    if _ref_file:
        break
chk(_ref_file is not None and _ref_dir is not None
    and os.path.isfile(os.path.join(DLV, _ref_dir, _ref_file))
    and "v10_2026-09-20" not in cl_txt,
    "F1 cover letter 指向的稿本真实存在（%s/%s）且无 v10 过期引用"
    % (_ref_dir or "?", _ref_file or "未匹配到现行稿本"))
sh_txt = open(sorted(glob.glob(os.path.join(MAT, "投稿材料说明_*.md")))[-1],
               encoding="utf-8").read()   # 跟随最新日期材料
chk(_ref_ver is not None and _ref_ver in sh_txt and "v10_2026-09-20" not in sh_txt,
    "投稿材料说明指向现行稿本 %s 且无 v10 过期引用" % _ref_ver)

print("\n[I] 新图注入断言（概念框架图 + 指标趋势图，v15/v16 图件轮）")

for fn in ("fig_dpsir_framework.pdf", "fig_dpsir_framework.png",
           "fig_indicator_trends.pdf", "fig_indicator_trends.png"):
    chk(os.path.isfile(os.path.join(PC, "figures", fn)), "figures/%s 存在" % fn)

for fn in ("fig_dpsir_framework.pdf", "fig_indicator_trends.pdf"):
    out = subprocess.run(["pdffonts", os.path.join(PC, "figures", fn)],
                         capture_output=True, text=True, encoding="utf-8",
                         errors="replace", env=env).stdout or ""
    chk(("Arial" in out) or ("Times" in out), "%s 使用 TNR/Arial 字体" % fn)

chk("fig2_workflow" not in tex_f and "fig:workflow" not in tex_f,
    "正文已不再引用技术路线图（v17 精简：EN 由 7 图回到 6 图）")


def spread(fn):
    im = np.array(Image.open(os.path.join(PC, "figures", fn)).convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    white = int(((r > 245) & (g > 245) & (b > 245)).sum())
    colored = int(r.size - white)
    q = (im // 16).astype(int)
    ncolors = len(np.unique((q[..., 0] << 16) | (q[..., 1] << 8) | q[..., 2]))
    return 100.0 * colored / max(1, r.size), ncolors


cf_c, cf_n = spread("fig_dpsir_framework.png")
chk(cf_c > 2 and cf_n > 150, "框架图非空白且色相充足（扁平图式；colored %.1f%%, 色数 %d）" % (cf_c, cf_n))

# ---- 框架图"投稿版"版式锁（v18 集成 Qoder 美化 rev1：无死白画布 / 无边缘裁切 / 字号不缩水）----
import re as _re
_fw = os.path.join(PC, "figures", "fig_dpsir_framework.pdf")
_pg = subprocess.run(["pdfinfo", _fw], capture_output=True, text=True,
                     encoding="utf-8", errors="replace", env=env).stdout or ""
_mm = _re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", _pg)
_fw_w, _fw_h = float(_mm.group(1)) / 72.0, float(_mm.group(2)) / 72.0
_fw_sc = (472.03123 / 72.0) / _fw_w
chk(abs(_fw_w - 6.34) < 0.06 and abs(_fw_h - 4.99) < 0.08,
    "框架图页面=内容尺寸（无死白画布）：%.2f x %.2f in" % (_fw_w, _fw_h))
chk(_fw_sc > 0.97, "框架图 1.0\\linewidth 缩放 %.3f（≈1，不缩字）" % _fw_sc)
chk(8.0 * _fw_sc >= 7.5, "框架图最小有效字号 %.2f pt（≥7.5）" % (8.0 * _fw_sc))
_fw_im = np.array(Image.open(os.path.join(PC, "figures", "fig_dpsir_framework.png"))
                  .convert("RGB")).astype(int)
_fw_nw = ~((_fw_im[..., 0] > 250) & (_fw_im[..., 1] > 250) & (_fw_im[..., 2] > 250))
_rg = np.zeros(_fw_nw.shape, bool)
_rg[:2, :] = _rg[-2:, :] = True
_rg[:, :2] = _rg[:, -2:] = True
chk(int(_fw_nw[_rg].sum()) == 0, "框架图最外 2px 无非白像素（外框线未被裁切）")
_fy, _fx = np.where(_fw_nw)
_fw_dead = 1 - (_fx.max() - _fx.min()) * (_fy.max() - _fy.min()) / _fw_nw.size
chk(_fw_dead < 0.05, "框架图死白 %.1f%%（<5%%；rev0 曾 17.7%%）" % (_fw_dead * 100))
chk(os.path.isfile(os.path.join(PC, "beautify_framework.py")),
    "beautify_framework.py 存在（框架图投稿版生成器）")
tf_c, tf_n = spread("fig_indicator_trends.png")
chk(tf_c > 1 and tf_n > 100, "趋势图 9 面板齐全（线图；colored %.1f%%, 色数 %d）" % (tf_c, tf_n))

ind_csv = open(os.path.join(PC, "data", "results_indicators.csv"), encoding="utf-8").read()
chk(len(ind_csv.splitlines()) == 20, "results_indicators.csv = 表头 + 19 年")
chk("39.6" in ind_csv.replace(",", "") and "228.0" in ind_csv.replace(",", ""),
    "指标年值已落盘（ecoland 2010=39.6, precip 2005=228.0）")

chk("figures/fig_dpsir_framework.pdf" in tex_f and "\\label{fig:framework}" in tex_f,
    "tex 已引用框架图并有 label fig:framework")
chk("figures/fig_indicator_trends.pdf" in tex_f and "\\label{fig:trends}" in tex_f,
    "tex 已引用趋势图并有 label fig:trends")

cn_build2 = open(os.path.join(PC, "build_word_cn.py"), encoding="utf-8").read()
chk("fig_dpsir_framework.png" in cn_build2 and "fig_indicator_trends.png" in cn_build2,
    "CN 构建器已引用两新图")
chk("图6  2020 年点尺度 ESI 空间分布" in cn_build2, "CN 点尺度图为 图6（与 EN Fig.6 同号）")
chk("表7  地理探测器交互探测（2020）" in cn_build2, "CN 交互为 表7（与 EN Table 7 同号，不再有交互热力图）")
chk(all(k not in cn_build2 for k in ("fig6_weights.png", "fig7_county_esi.png", "fig8_interaction.png")),
    "三张图版已退役（权重/县域/交互 改为 表4/表6/表7，与 EN 同号）")

# ---- v16 图件重绘（Graphviz 自动排版 + 成品印刷尺寸设计）----
for fn in ("figures/fig_dpsir_framework.dot", "figures/fig2_workflow.dot"):
    chk(os.path.isfile(os.path.join(PC, fn)), "%s 存在（图件可复现源）" % fn)
chk(os.path.isfile(os.path.join(PC, "make_figs_graphviz.py")),
    "make_figs_graphviz.py 存在（含 -Tplain 几何审计）")
gv_build = open(os.path.join(PC, "make_figs_graphviz.py"), encoding="utf-8").read()
chk("重叠" in gv_build and "穿过节点" in gv_build, "Graphviz 审计含节点重叠/边穿节点检查")
wf_dot = open(os.path.join(PC, "figures", "fig2_workflow.dot"), encoding="utf-8").read()
_strip = ["#d98b8b", "#e0b184", "#ecdc9a", "#b9d7a8", "#7fae87"]
chk(all(c in wf_dot for c in _strip), "路线图五级阈值带配色齐全（低值暖→高值绿，与图5 同向）")
chk("\\includegraphics[width=1.0\\linewidth]{figures/fig_dpsir_framework.pdf}" in tex_f,
    "框架图按整幅宽（1.0\\linewidth）插入（保证等效字号 > 7 pt）")

# ---- v19：CN↔EN 逐号对应锁（图/表/公式编号 + 图件序列 + 表内数值）----
r2 = subprocess.run([sys.executable, os.path.join(PC, "verify_cn_en_align.py")],
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", env=env)
print(r2.stdout.rstrip())
if "verify_cn_en_align: ALL PASS" not in (r2.stdout or ""):
    fails.append("verify_cn_en_align 未全部通过")

# ---- v21：R6 复核新增锁定（声明唯一性 / 表图全引用 / Word 数字-单位渲染）----
import re

print("\n[J] 声明段唯一性（Word 不得重复输出；R6 HIGH-1）")
from docx import Document as _Doc
_EN_DECL = ["Data availability", "CRediT authorship contribution statement",
            "Declaration of competing interest", "Funding",
            "Declaration of generative AI and AI-assisted technologies in the writing process"]
_CN_DECL = ["数据可用性", "作者贡献声明（CRediT）", "利益冲突声明", "基金资助",
            "生成式人工智能与人工智能辅助技术使用声明"]
_word_ps = {}
_J_dir, _J_fns = None, {}
for _d in sorted([x for x in os.listdir(DLV)
                  if re.search(r"(^|_)v\d+_\d{4}-\d{2}-\d{2}$", x)
                  and os.path.isdir(os.path.join(DLV, x))],
                 key=lambda s: int(re.search(r"v(\d+)", s).group(1)), reverse=True):
    _v = "v" + re.search(r"v(\d+)", _d).group(1)
    _dt = _d.split("_")[-1]
    if os.path.isfile(os.path.join(DLV, _d, "论文_EN_%s_%s.docx" % (_v, _dt))):
        _J_dir = _d
        _J_fns = {"EN": "论文_EN_%s_%s.docx" % (_v, _dt), "CN": "论文_CN_%s_%s.docx" % (_v, _dt)}
        break
for _lab, _fn in _J_fns.items():
    _path = os.path.join(DLV, _J_dir, _fn)
    _word_ps[_lab] = [p.text.strip() for p in _Doc(_path).paragraphs]
    _keys = _EN_DECL if _lab == "EN" else _CN_DECL
    _cnts = {k: sum(1 for t in _word_ps[_lab] if t.startswith(k)) for k in _keys}
    chk(all(v == 1 for v in _cnts.values()), "%s Word 五段声明各恰好 1 次 %s" % (_lab, _cnts))

print("\n[K] 每个表/图 label 都在正文被引用（须知：引用所有表格与图）")
for _m in re.finditer(r"\\label\{(tab|fig):([^}]*)\}", tex_f):
    _key = "%s:%s" % (_m.group(1), _m.group(2))
    _n = len(re.findall(r"\\ref\{%s\}" % re.escape(_key), tex_f))
    chk(_n >= 1, "%s 被正文引用 %d 次" % (_key, _n))

print("\n[L] Word 数字–单位渲染（细空格保留 + 内联上标）")
_en_txt = " ".join(_word_ps["EN"])
chk(("mm yr" in _en_txt) and ("⁻¹" in _en_txt), "EN Word 单位渲染为 'mm yr⁻¹'（细空格 + Unicode 上标）")
_bad_unit = re.findall(r"\d(?:mm|yr|°C|m\b)", _en_txt)
chk(not _bad_unit, "EN Word 无数字-单位粘连（命中 %s）" % (_bad_unit[:5] or "无"))
chk("\\ref{tab:data}" in tex_f, "表 1 已在正文被引用（R6 HIGH-2）")

print("\n[M] 表 7 交互值与权威 CSV 三位小数逐一相等（R8-1 回归锁）")
_PAIR2LAB = {"grass+barren": ("Grassland", "Barren"), "precip+barren": ("Precipitation", "Barren"),
             "precip+grass": ("Precipitation", "Grassland"), "temp+barren": ("Temperature", "Barren"),
             "temp+grass": ("Temperature", "Grassland"), "temp+precip": ("Temperature", "Precipitation")}
_int_rows = {}
with open(os.path.join(PC, "data", "results_interaction_detector.csv"), encoding="utf-8") as _f:
    next(_f)
    for _ln in _f:
        _c = _ln.strip().split(",")
        if len(_c) >= 4:
            _int_rows[_c[0]] = _c[1:4]
_int_tab = tex_f.split("\\label{tab:interaction}")[1].split("\\end{table}")[0]
chk(len(_int_rows) == 6 and len(_PAIR2LAB) == 6, "交互探测 CSV 六对齐全（%d）" % len(_int_rows))
for _pair in sorted(_int_rows):
    _kw = _PAIR2LAB.get(_pair)
    if not _kw:
        chk(False, "CSV 组合 %s 未登记到表 7 行名映射" % _pair)
        continue
    _line = [l for l in _int_tab.split("\n") if _kw[0] in l and _kw[1] in l]
    if len(_line) != 1:
        chk(False, "表 7 中 %s 行匹配 %d 条" % (_pair, len(_line)))
        continue
    _got = re.findall(r"\d+\.\d\d\d", _line[0])
    _want = ["%.3f" % round(float(x), 3) for x in _int_rows[_pair]]
    chk(_got == _want, "表 7 %-18s = %s（CSV 三位舍入 %s）" % (_pair, _got, _want))

print("\n[N] 顶层投稿材料与最新冻结副本一致（Qoder R8 观察项）")
import hashlib as _hl
_mat_work = MAT
_mat_free = os.path.join(DLV, _ref_dir or "", "投稿材料")
_bad = []
if not os.path.isdir(_mat_free):
    _bad.append("冻结集投稿材料目录缺失")
else:
    _ext = (".md", ".txt", ".docx")
    _setw = set(f for f in os.listdir(_mat_work) if f.endswith(_ext))
    _setf = set(f for f in os.listdir(_mat_free) if f.endswith(_ext))
    for _f in sorted(_setw | _setf):                      # 双向：任一侧缺失都报警
        _a, _b = os.path.join(_mat_work, _f), os.path.join(_mat_free, _f)
        if not os.path.isfile(_a):
            _bad.append(_f + "(顶层缺失)")
        elif not os.path.isfile(_b):
            _bad.append(_f + "(冻结集中缺失)")
        elif _hl.md5(open(_a, "rb").read()).hexdigest() != _hl.md5(open(_b, "rb").read()).hexdigest():
            _bad.append(_f + "(md5 不一致)")
chk(not _bad, "顶层投稿材料与 %s 副本双向齐全且 md5 一致（%s）" % (_ref_dir, _bad or "全部一致"))

print("\n[O] 材料文档内部引用的材料文件名指向现行材料（防改名后引用不跟随）")
_PREF = ("cover_letter", "投稿材料说明", "投稿执行清单", "数据DOI回填说明", "Qoder复核任务书")
_stale = []
for _f in sorted(os.listdir(MAT)):
    if not _f.endswith(".md"):
        continue
    _s = open(os.path.join(MAT, _f), encoding="utf-8").read()
    for _m in re.finditer(r"(%s)_\\d{4}-\\d{2}-\\d{2}\\.md" % "|".join(_PREF), _s):
        _ref = _m.group(0)
        if not os.path.isfile(os.path.join(MAT, _ref)):
            _stale.append("%s 引用 %s" % (_f, _ref))
chk(not _stale, "材料自引用均指向现行材料（%s）" % (_stale or "无过期引用"))

print("\n" + ("verify_v12: ALL PASS" if not fails else "verify_v12: %d FAIL" % len(fails)))
sys.exit(1 if fails else 0)