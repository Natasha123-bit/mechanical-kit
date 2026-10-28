"""common/table.py —— 表格（G-31、G-32）。

标题栏、参数表都是格子：文字压格线、图形串进表格，是图纸最常见的“看着别扭但查不出”的错。
几何一律走 `measure.py` 的实测包围盒（CHK-06），不看属性坐标。
"""

from . import _util as U

GRID_ROLES = ("title-grid", "table-grid")
GRAPH_ROLES = ("outline", "section-outline", "key-outline", "hidden", "centerline",
               "hatch", "dimension", "extension", "arrow", "leader", "roughness",
               "datum", "tolerance-frame", "tolerance-symbol")

RULES = []


def _grid_lines(ctx):
    return U.segs(ctx, GRID_ROLES)


def r_g31(ctx):
    """表格里的文字不压格线（净距 < 0 才算压）。"""
    if not ctx.bounds:
        return "未检查", "没提供 --bounds（表格判定要用实测框）"
    lines = _grid_lines(ctx)
    if not lines:
        return "未检查", "图上没有 title-grid / table-grid"
    boxes = [b for b in ctx.bounds.get("boxes", []) if b.get("role") in GRID_ROLES]
    if not boxes:
        return "未检查", "表格没有包围盒"
    reg = (min(b["xmin"] for b in boxes), min(b["ymin"] for b in boxes),
           max(b["xmax"] for b in boxes), max(b["ymax"] for b in boxes))
    bad, n = [], 0
    for t, tb in U.text_boxes(ctx):
        if tb["xmax"] < reg[0] - 1 or tb["xmin"] > reg[2] + 1 \
                or tb["ymax"] < reg[1] - 1 or tb["ymin"] > reg[3] + 1:
            continue
        n += 1
        for x1, y1, x2, y2, _a in lines:
            d = U.box_cap_dist(tb, (x1, y1, x2, y2, 0.125, "grid"))
            if d < 0:
                bad.append("%r 压格线（净距 %.2f）" % (t.get("t", "")[:10], d))
                break
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:3]))
    if n == 0:
        return "未检查", "表格区域内没有文字"
    return "通过", "表格内 %d 个文字都不压格线（格线 %d 条）" % (n, len(lines))


def r_g32(ctx):
    """图形不得串进标题栏 / 参数表的矩形区域。"""
    if not ctx.bounds:
        return "未检查", "没提供 --bounds（要实测框才判侵入）"
    boxes = ctx.bounds.get("boxes", [])
    regs = [b for b in boxes if b.get("role") in GRID_ROLES]
    if not regs:
        return "未检查", "图上没有 title-grid / table-grid"
    # 按 data-name 分组，避免参数表与标题栏被并成一个大框
    groups = {}
    for b in regs:
        groups.setdefault(b.get("name") or "?", []).append(b)
    bad = []
    for nm, g in groups.items():
        x0 = min(b["xmin"] for b in g)
        y0 = min(b["ymin"] for b in g)
        x1 = max(b["xmax"] for b in g)
        y1 = max(b["ymax"] for b in g)
        inside = [b for b in boxes
                  if b.get("role") in GRAPH_ROLES
                  and b["xmin"] < x1 - 0.01 and b["xmax"] > x0 + 0.01
                  and b["ymin"] < y1 - 0.01 and b["ymax"] > y0 + 0.01]
        if inside:
            sample = "、".join("%s" % b.get("role") for b in inside[:3])
            bad.append("%s 区域内有 %d 个图形图元（%s）" % (nm, len(inside), sample))
    if bad:
        return "不通过", "；".join(bad[:3])
    return "通过", "%d 个表格区域（%s）都没有图形串入" % (
        len(groups), "、".join(sorted(groups)[:3]))


RULES = [
    ("G-31", "表格文字不压格线", "LAY-02", "必", r_g31),
    ("G-32", "图形不串进标题栏/参数表", "LAY-03", "必", r_g32),
]
