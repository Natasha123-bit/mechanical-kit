"""common / part 规则包的公共几何与样式读取。

规矩：**只读 ctx，不碰全局**；拿不到输入就返回「未检查」并说清缺什么，
绝不静默当通过（CHK-08）。
"""

import math
import re

from ..check_rules import HALF_W, box_cap_dist, capsules, pt_seg_dist  # noqa: F401（供子模块直接用）

# ---------------------------------------------------------------- 样式表


def css(root):
    """把 <style> 里 `.class{prop:value;...}` 拆成 {class: {prop: value}}。"""
    out = {}
    for st in root.iter("{http://www.w3.org/2000/svg}style"):
        for m in re.finditer(r"\.([\w-]+)\s*\{([^}]*)\}", st.text or ""):
            cls, body = m.group(1), m.group(2)
            props = {}
            for decl in body.split(";"):
                if ":" in decl:
                    k, v = decl.split(":", 1)
                    props[k.strip()] = v.strip()
            out.setdefault(cls, {}).update(props)
    return out


def font_faces(root):
    """@font-face 里定义的族名列表（小写）。"""
    txt = "".join((st.text or "") for st in root.iter("{http://www.w3.org/2000/svg}style"))
    return [m.group(1).strip("'\" ").lower()
            for m in re.finditer(r"@font-face\s*\{[^}]*font-family\s*:\s*([^;}]+)", txt)]


def classes(a):
    return str(a.get("class") or "").split()


def stroke_width(a, style):
    """图元实际线宽（mm）：元素上的 stroke-width 优先，其次 class 里的。"""
    if a.get("stroke-width"):
        try:
            return float(a["stroke-width"])
        except ValueError:
            pass
    for c in classes(a):
        v = style.get(c, {}).get("stroke-width")
        if v:
            try:
                return float(v)
            except ValueError:
                pass
    return None


def dash(a, style):
    for c in classes(a):
        v = style.get(c, {}).get("stroke-dasharray")
        if v:
            return v
    return a.get("stroke-dasharray")


# ---------------------------------------------------------------- 几何


def segs(ctx, roles, tag_filter=None):
    """角色的直线段 [(x1,y1,x2,y2,a)]，只取 <line>（弧从 arcs() 取）。"""
    out = []
    for tag, a, _ in ctx.els:
        if tag != "line" or a.get("data-role") not in roles:
            continue
        if tag_filter and not tag_filter(a):
            continue
        out.append((float(a["x1"]), float(a["y1"]),
                    float(a["x2"]), float(a["y2"]), a))
    return out


def circle3(p0, p1, p2):
    """三点定圆 → (cx, cy, r)；共线返回 None。"""
    (x1, y1), (x2, y2), (x3, y3) = p0, p1, p2
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-9:
        return None
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1)
          + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3)
          + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    return ux, uy, math.hypot(x1 - ux, y1 - uy)


def arcs(ctx, roles, sample=0.5):
    """圆弧：<circle> 与 <path> 的 A 段 → [(cx, cy, r, role, a, p0, p1)]。

    圆心用弧上三点定圆（SVG 的 large-arc/sweep 在 gbdraw 的 y 翻转下容易读反，
    三点定圆不依赖这两个标志）。
    """
    from ..check_rules import _arc_points, _path_cmds
    out = []
    for tag, a, _ in ctx.els:
        if a.get("data-role") not in roles:
            continue
        if tag == "circle":
            out.append((float(a["cx"]), float(a["cy"]), float(a["r"]),
                        a.get("data-role"), a, None, None))
        elif tag == "path":
            for cmd, nums, p0, p1 in _path_cmds(a.get("d", "")):
                if cmd != "A" or len(nums) < 7:
                    continue
                pts = _arc_points(p0, p1, nums[0], nums[1], nums[2],
                                  int(nums[3]), int(nums[4]))
                if len(pts) < 3:
                    continue
                c = circle3(pts[0], pts[len(pts) // 2], pts[-1])
                if c:
                    out.append((c[0], c[1], c[2], a.get("data-role"), a, p0, p1))
    return out


def cluster(items, gap=8.0, key=None):
    """按 bbox 邻接把图元聚成簇（L1-11 里验证过的做法：不靠 data-name 配对）。"""
    key = key or (lambda it: (min(it[0], it[2]), min(it[1], it[3]),
                              max(it[0], it[2]), max(it[1], it[3])))
    boxes = []
    for it in items:
        b = list(key(it))
        boxes.append([b[0], b[1], b[2], b[3], [it]])
    out = []
    for b in boxes:
        for c in out:
            if not (b[2] < c[0] - gap or b[0] > c[2] + gap
                    or b[3] < c[1] - gap or b[1] > c[3] + gap):
                c[0], c[1] = min(c[0], b[0]), min(c[1], b[1])
                c[2], c[3] = max(c[2], b[2]), max(c[3], b[3])
                c[4].extend(b[4])
                break
        else:
            out.append(b)
    return out


def cover(seg_span, need0, need1, tol=0.05):
    """一维覆盖：把 [a,b] 线段并起来，返回没盖住的区间列表 [(g0,g1)]。"""
    spans = sorted((min(a, b), max(a, b)) for a, b in seg_span
                   if min(a, b) <= need1 + tol and max(a, b) >= need0 - tol)
    gaps, cur = [], need0
    for a, b in spans:
        if a > cur + tol:
            gaps.append((cur, min(a, need1)))
        cur = max(cur, b)
        if cur >= need1 - tol:
            break
    if cur < need1 - tol:
        gaps.append((cur, need1))
    return [g for g in gaps if g[1] - g[0] > tol]


def text_boxes(ctx):
    """[(text dict, 几何框)]，框走 ctx.text_geom()（墨迹优先，退化到 bbox 内缩）。"""
    if not ctx.bounds:
        return []
    return [(t, ctx.text_geom(t)) for t in ctx.bounds["texts"]]
