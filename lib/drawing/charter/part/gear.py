"""part/gear.py —— 齿轮类画法规则包（P-11~P-13）。

数据来源：`calc.json` 的 `派生`（d/da/df/rim_d/hole_Rc…）与 `输入`（齿宽 b、结构尺寸）。
齿部定位一律靠 `data-feature`（tip / root / pitch / bore / hole…），不看图层顺序。
"""

import re

from ..common import _util as U

RULES = []
NUM = re.compile(r"[-−]?\d+(?:\.\d+)?")
DIA = re.compile(r"φ\s*([-−]?\d+(?:\.\d+)?)")          # φ 后面紧跟的数字才是直径
TOL = re.compile(r"\b[A-Za-z]{1,3}\s*\d+(?:\.\d+)?")   # H7 / h11 / JS9 这类公差带
CNT = re.compile(r"\d+\s*[×xX]\s*")                     # 6×φ20 里的“6×”是数量


GEOM_ROLES = ("outline", "section-outline", "centerline")


def _feat(ctx, wants):
    """[(tag, a)]：data-feature 命中、且角色是轮廓/中心线的图元。

    只看 data-feature 会把尺寸线也捞进来（φ126h11 那条界线就带 feature=tip），
    所以角色要一起卡。
    """
    out = []
    for tag, a, _ in ctx.els:
        f = str(a.get("data-feature") or "")
        if f in wants and a.get("data-role") in GEOM_ROLES:
            out.append((tag, a))
    return out


def _cls(a):
    return set(str(a.get("class") or "").split())


def p11(ctx):
    """齿部三线（GB/T 4459.2）：

    - 轴向剖视：齿顶、齿根都是可见轮廓 → 粗实线；分度线 → 细点画线
    - 端面视图：齿顶圆粗实线、**齿根圆细实线**、分度圆细点画线（不是三个都粗）
    """
    views = {}
    for tag, a in _feat(ctx, {"tip", "root", "pitch"}):
        views.setdefault(a.get("data-view") or "?", {})[a.get("data-feature")] = a
    for tag, a in _feat(ctx, {"tip.circle", "root.circle", "pitch.circle"}):
        key = a.get("data-feature", "").split(".")[0]
        views.setdefault(a.get("data-view") or "?", {})[key] = a
    if not views:
        return "未检查", "图上没有 data-feature = tip/root/pitch 的齿部图元"
    bad, ok = [], 0
    for v, d in sorted(views.items()):
        if "tip" not in d or "root" not in d:
            bad.append("%s 视图缺齿顶或齿根线" % v)
            continue
        if "pitch" not in d:
            bad.append("%s 视图缺分度线" % v)
            continue
        w = {k: _cls(d[k]) for k in ("tip", "root", "pitch")}
        sect = any(a.get("data-role") == "hatch" and a.get("data-view") == v for _t, a, _x in ctx.els)
        root_want = "thick" if sect else "thin"
        if "thick" not in w["tip"]:
            bad.append("%s 齿顶不是粗实线（%s）" % (v, sorted(w["tip"])))
        elif root_want not in w["root"]:
            bad.append("%s 齿根应为%s（%s）" % (v, "粗实线" if sect else "细实线", sorted(w["root"])))
        elif "center" not in w["pitch"]:
            bad.append("%s 分度线不是细点画线（%s）" % (v, sorted(w["pitch"])))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    return "通过", "%d 个视图的齿部三线对（齿顶/齿根粗、分度点画）" % ok


def p12(ctx):
    """剖面线只落在实体里：不进轴孔、不进腹板孔，且在本视图断面轮廓范围内。"""
    hatch = [(float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]), a)
             for t, a, _ in ctx.els if t == "line" and a.get("data-role") == "hatch"]
    if not hatch:
        return "未检查", "图上没有剖面线"
    if not ctx.bounds:
        return "未检查", "没提供 --bounds"
    boxes = ctx.bounds.get("boxes", [])
    holes = [b for b in boxes if str(b.get("feature") or "") in
             ("bore", "hole", "bore.edge", "hub.bore")]
    sec = [b for b in boxes if b.get("role") == "section-outline"]
    if not sec:
        return "未检查", "没有断面轮廓包围盒"
    reg = (min(b["xmin"] for b in sec), min(b["ymin"] for b in sec),
           max(b["xmax"] for b in sec), max(b["ymax"] for b in sec))
    bad, ok = [], 0
    for x1, y1, x2, y2, a in hatch:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if not (reg[0] - 0.05 <= mx <= reg[2] + 0.05 and reg[1] - 0.05 <= my <= reg[3] + 0.05):
            bad.append("剖面线中点 (%.1f,%.1f) 在断面轮廓之外" % (mx, my))
            continue
        hit = [b for b in holes
               if b["xmin"] - 0.05 <= mx <= b["xmax"] + 0.05
               and b["ymin"] - 0.05 <= my <= b["ymax"] + 0.05]
        if hit:
            bad.append("剖面线中点 (%.1f,%.1f) 落在 %s 里"
                       % (mx, my, hit[0].get("feature") or hit[0].get("role")))
            continue
        ok += 1
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:3]))
    return "通过", "%d 条剖面线全在实体内（避开轴孔/腹板孔）" % ok


def p13(ctx):
    """图上标的尺寸读数必须与计算书一致：直径集、线性集各一一对应。"""
    d = ctx.calc.get("派生") or {}
    g = (ctx.calc.get("输入") or {}).get("几何") or {}
    st = (ctx.calc.get("输入") or {}).get("结构") or {}
    if not d:
        return "未检查", "calc 没有 派生"
    want_dia = {k: float(v) for k, v in {
        "bore": st.get("bore"), "hub_d": st.get("hub_d"), "rim_d": d.get("rim_d"),
        "df": d.get("df"), "d": d.get("d"), "da": d.get("da"),
        "hole_d": st.get("hole_d"),
        "hole_pcd": (2 * float(d["hole_Rc"])) if d.get("hole_Rc") is not None else None,
    }.items() if v is not None}
    want_lin = {k: float(v) for k, v in {
        "b": g.get("b"), "hub_l": st.get("hub_l"), "web_t": st.get("web_t"),
    }.items() if v is not None}
    if not want_dia and not want_lin:
        return "未检查", "calc 缺直径/线性尺寸字段"
    seen_dia, seen_lin, bad = [], [], []
    for t, a, tx in ctx.els:                # ctx.els 第三项是元素文本
        if t != "text" or a.get("data-role") != "dimension":
            continue
        txt = (tx or "").strip()
        if not txt:
            continue
        for n in DIA.findall(txt):
            seen_dia.append((float(n.replace("−", "-")), txt))
        rest = CNT.sub(" ", TOL.sub(" ", DIA.sub(" ", txt)))
        for n in NUM.findall(rest):
            seen_lin.append((float(n.replace("−", "-")), txt))
    if not seen_dia and not seen_lin:
        return "未检查", "图上没有可解析的尺寸读数"
    for n, txt in seen_dia:
        if n == 6 and abs((want_dia.get("hole_d") or -1) - 6) < 1e-6:
            continue
        if not any(abs(n - v) < 0.02 for v in want_dia.values()):
            bad.append("标注 %r 的直径 %.4g 不在计算书直径集 %s 里"
                       % (txt, n, sorted(round(v, 2) for v in want_dia.values())))
    for n, txt in seen_lin:
        if not any(abs(n - v) < 0.02 for v in want_lin.values()):
            bad.append("标注 %r 的 %.4g 不在计算书线性集 %s 里"
                       % (txt, n, sorted(round(v, 2) for v in want_lin.values())))
    miss = []
    for k, v in want_dia.items():
        if k == "hole_pcd":
            continue
        if not any(abs(n - v) < 0.02 for n, _ in seen_dia):
            miss.append("%s=%.4g" % (k, v))
    for k, v in want_lin.items():
        if not any(abs(n - v) < 0.02 for n, _ in seen_lin):
            miss.append("%s=%.4g" % (k, v))
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:3]))
    if miss:
        return "警示", "读数都在计算书里，但这些没标：%s" % "、".join(miss[:4])
    return "通过", "直径 %d 个读数、线性 %d 个读数都与计算书对应，无多余无遗漏" % (
        len(seen_dia), len(seen_lin))


RULES = [
    ("P-11", "齿部三线：齿顶/齿根粗实线、分度细点画线", "VIEW-13", "必", p11),
    ("P-12", "剖面线只在实体内（不串轴孔/腹板孔）", "VIEW-14", "必", p12),
    ("P-13", "标注读数与计算书的直径/线性尺寸一一对应", "CHK-03", "必", p13),
]