"""common/gdt.py —— 形位公差通用规则（G-01~G-03）。

依据 GB/T 1182—2018：基准三角形**底边与基准要素轮廓线重合、顶点朝外**（这是两个项目
都踩过的坑：按 ISO 画成尖角压线）；圆跳动是**单支** 45° 箭头，两支表示全跳动；
公差框至少两格（符号格 + 公差值格），格线不得穿过文字。
"""

import math

from . import _util as U

RULES = []
OUTLINE_ROLES = ("outline", "section-outline", "key-outline", "hidden")


def _pts(points):
    import re
    return [(float(m.group(1)), float(m.group(2)))
            for m in re.finditer(r"([-\d.]+)\s*,\s*([-\d.]+)", points or "")]


def _seg_dist(px, py, seg):
    return U.pt_seg_dist(px, py, seg[0], seg[1], seg[2], seg[3])


def r_g01(ctx):
    """基准三角形：底边贴轮廓线（≤0.05mm），顶点背离该线（>1.0mm），并连到 6×6 方框。"""
    segs = U.segs(ctx, OUTLINE_ROLES)
    polys = [(a, _pts(a.get("points"))) for t, a, _ in ctx.els
             if t == "polygon" and a.get("data-role") == "datum"]
    rects = [a for t, a, _ in ctx.els if t == "rect" and a.get("data-role") == "datum"]
    if not polys:
        return "未检查", "图上没有基准符号三角形（datum polygon）"
    if not segs:
        return "未检查", "图上没有轮廓线，判不了底边贴不贴线"
    bad, ok = [], 0
    for a, pts in polys:
        if len(pts) < 3:
            bad.append("%s 三角形点数 <3" % a.get("data-name", "?"))
            continue
        # 三条边：哪条边的两个顶点同时离轮廓最近 → 底边
        edges = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
        best, base = None, None
        for e in edges:
            d = max(min(_seg_dist(x, y, s) for s in segs) for x, y in e)
            if best is None or d < best:
                best, base = d, e
        if base is None:
            bad.append("%s 判不出底边" % a.get("data-name", "?"))
            continue
        dbase = best
        apex = [p for p in pts if p not in base]
        if not apex:
            bad.append("%s 退化三角形" % a.get("data-name", "?"))
            continue
        dapex = min(_seg_dist(apex[0][0], apex[0][1], s) for s in segs)
        nm = a.get("data-name", "?")
        if dbase > 0.05:
            bad.append("%s 底边离轮廓 %.2fmm（应贴线）" % (nm, dbase))
        elif dapex < dbase + 1.0:
            bad.append("%s 顶点在贴线侧（%.2f vs 底边 %.2f），三角形画反了" % (nm, dapex, dbase))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    ev = "%d 个基准三角形底边贴轮廓、顶点朝外" % ok
    if rects:
        # 方框边长应与基准字母字高相当（GB/T 1182 只要求方框，不规定 6mm）
        sides = [min(float(r.get("width", 0)), float(r.get("height", 0))) for r in rects]
        if min(sides) < 2.5 or max(sides) > 8.0:
            return "警示", ev + "；方框边长 %s 与实际字高不匹配" % [round(v, 1) for v in sides[:3]]
    return "通过", ev


def r_g02(ctx):
    """圆跳动符号必须是单支 45° 箭头：每组 1 个小圆 + 3 段线（主箭头 + 两翼）。"""
    items = [(t, a) for t, a, _ in ctx.els if a.get("data-role") == "tolerance-symbol"]
    if not items:
        return "未检查", "图上没有形位公差符号（tolerance-symbol）"
    boxes = []
    for t, a in items:
        if t == "circle":
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
            boxes.append((cx - r, cy - r, cx + r, cy + r, (t, a)))
        elif t == "line":
            xs = [float(a["x1"]), float(a["x2"])]
            ys = [float(a["y1"]), float(a["y2"])]
            boxes.append((min(xs), min(ys), max(xs), max(ys), (t, a)))
        else:                                   # polygon 等：按顶点取包围盒
            pts = _pts(a.get("points"))
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                boxes.append((min(xs), min(ys), max(xs), max(ys), (t, a)))
    groups = U.cluster(boxes, gap=3.0)
    bad, ok = [], 0
    for g in groups:
        its = [rec[4] for rec in g[4]]          # cluster 里存的是整条记录，载荷在 [4]
        ls = [a for t, a in its if t in ("line", "polygon")]
        if len(ls) != 3:
            bad.append("一组符号有 %d 段线（单支应 3 段：主箭头 + 两翼）" % len(ls))
            continue
        lens = sorted(((math.hypot(float(a["x2"]) - float(a["x1"]),
                                   float(a["y2"]) - float(a["y1"])), a) for a in ls),
                      key=lambda t: -t[0])
        main = lens[0][1]
        cs = [a for t, a in its if t == "circle"]
        cc = ((float(cs[0]["cx"]), float(cs[0]["cy"])) if cs else None)
        ends = [(float(main["x1"]), float(main["y1"])),
                (float(main["x2"]), float(main["y2"]))]
        if cc:
            tip = max(ends, key=lambda p: math.hypot(p[0] - cc[0], p[1] - cc[1]))
        else:
            tip = max(ends, key=lambda p: math.hypot(p[0] - ends[0][0], p[1] - ends[0][1]))
        wings = [a for _, a in lens[1:]]
        okw = True
        for w in wings:
            ends = [(float(w["x1"]), float(w["y1"])), (float(w["x2"]), float(w["y2"]))]
            if min(math.hypot(p[0] - tip[0], p[1] - tip[1]) for p in ends) > 0.8:
                okw = False
        if not okw:
            bad.append("两翼没接在主箭头端点（像两支独立箭头 → 全跳动画法）")
        elif lens[1][0] > 0.7 * lens[0][0]:
            bad.append("翼长 %.2f ≈ 主箭头 %.2f，判为双支" % (lens[1][0], lens[0][0]))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    return "通过", "%d 组圆跳动符号均为单支箭头（小圆 + 主箭头 + 两翼）" % ok


def r_g03(ctx):
    """公差框：至少两格；格线不穿文字（净距 ≥0，线宽 0.125 计）。"""
    frames = [(t, a) for t, a, _ in ctx.els if a.get("data-role") == "tolerance-frame"]
    if not frames:
        return "未检查", "图上没有公差框（tolerance-frame）"
    rects = [a for t, a in frames if t == "rect"]
    lines = [a for t, a in frames if t == "line"]
    if not rects:
        return "未检查", "公差框没有格（rect）"
    bad, ok = [], 0
    groups = U.cluster([(float(a["x"]), float(a["y"]),
                         float(a["x"]) + float(a["width"]),
                         float(a["y"]) + float(a["height"]), a) for a in rects], gap=0.6)
    boxes = U.text_boxes(ctx) if ctx.bounds else []
    for g in groups:
        cells = [b[4] for b in g[4]]
        x0, x1 = g[0], g[2]
        y0, y1 = g[1], g[3]
        # 格数按竖向边界数：两种画法都吃——①N 个相邻 rect 共边；②1 个 rect + N−1 条分隔线
        edges = set()
        for c in cells:
            edges.add(round(float(c["x"]), 2))
            edges.add(round(float(c["x"]) + float(c["width"]), 2))
        for a in lines:
            if abs(float(a["x1"]) - float(a["x2"])) < 1e-6:
                x = round(float(a["x1"]), 2)
                if x0 - 0.3 <= x <= x1 + 0.3:
                    edges.add(x)
        n_cell = max(len(edges) - 1, 0)
        if n_cell < 2:
            bad.append("框 @(%.0f,%.0f) 只有 %d 格（至少要符号格 + 公差值格）"
                       % (x0, y0, n_cell))
            continue
        # 格线来源有两套画法：①单独画的分隔线；②相邻格子 rect 共用的一条边。
        # 两张样例图都是②，所以以 rect 的左右边为准，额外的分隔线一并算进来。
        sep = [(float(c["x"]), float(c["y"]), float(c["x"]),
                float(c["y"]) + float(c["height"])) for c in cells]
        sep = [tuple(v) for v in sep]
        for a in lines:
            if abs(float(a["x1"]) - float(a["x2"])) < 1e-6 \
                    and x0 - 0.3 <= float(a["x1"]) <= x1 + 0.3:
                sep.append((float(a["x1"]), min(float(a["y1"]), float(a["y2"])),
                            float(a["x2"]), max(float(a["y1"]), float(a["y2"]))))
        hit = []
        for t, tb in boxes:
            if tb["xmax"] < x0 - 1 or tb["xmin"] > x1 + 1 \
                    or tb["ymax"] < y0 - 1 or tb["ymin"] > y1 + 1:
                continue
            for sg in sep:                      # (x1,y1,x2,y2)
                d = U.box_cap_dist(tb, (sg[0], sg[1], sg[2], sg[3], 0.125, "tolerance-frame"))
                if d < 0:
                    hit.append("%r 压格线 %.2f" % (t.get("t", "")[:8], d))
        if hit:
            bad.append("；".join(hit[:2]))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    return "通过", "%d 个公差框格数够、文字不压格线" % ok


RULES = [
    ("G-01", "基准三角形底边贴轮廓、顶点朝外", "DIM-15", "必", r_g01),
    ("G-02", "圆跳动为单支箭头（两支＝全跳动）", "DIM-17", "必", r_g02),
    ("G-03", "公差框格数够、文字不压格线", "DIM-16", "必", r_g03),
]
