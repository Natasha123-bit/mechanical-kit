"""part/shaft.py —— 轴类画法规则包（P-01、P-03~P-05）。

P-02（轴肩线画满大直径）已并进 L2-14：那条判据不需要零件类型，只要有 calc 段表就能跑，
放在 L2 里 `--part` 不传也生效；part 层只留轴类专属的画法。


数据来源：`calc.json` 的 `派生.段界/半径/台阶/圆角` 与 `键`（契约见 `calc.schema.md`）。
几何一律从图上看：轴线取最长水平中心线，X0 取轮廓最左点，**不读 data-name 配对**
（自绘图用 Ⅰ/Ⅱ 命名，样例用 cylinder generator，配对必错）。
"""

from ..common import _util as U

RULES = []
ROMAN = "ⅠⅡⅢⅣⅤⅥⅦⅧ"


def _axis_y(ctx):
    """轴线 y：最长的水平中心线（退化时取水平轮廓的中位）。"""
    best = None
    for x1, y1, x2, y2, a in U.segs(ctx, ("centerline",)):
        if abs(y1 - y2) < 1e-6:
            ln = abs(x2 - x1)
            if best is None or ln > best[0]:
                best = (ln, (y1 + y2) / 2)
    return None if best is None else best[1]


def _x0(ctx):
    xs = [min(float(a["x1"]), float(a["x2"])) for t, a, _ in ctx.els
          if t == "line" and a.get("data-role") == "outline"]
    return min(xs) if xs else None


def _derive(calc):
    d = calc.get("派生") or {}
    jie, rad = d.get("段界"), d.get("半径")
    if not isinstance(jie, list) or not isinstance(rad, list) or len(jie) < 2:
        return None
    steps = d.get("台阶") or []
    names = []
    if steps:
        names = [steps[0].get("左段")] + [s.get("右段") for s in steps]
    while len(names) < len(rad):
        names.append(ROMAN[len(names)] if len(names) < len(ROMAN) else str(len(names) + 1))
    return [{"i": i, "名": names[i], "x0": jie[i], "x1": jie[i + 1], "r": rad[i]}
            for i in range(len(rad))]


def p01(ctx):
    """每段上下各一条母线，距轴线 = 半径（±0.05），覆盖段长 ≥95%。"""
    segs = _derive(ctx.calc)
    my, x0 = _axis_y(ctx), _x0(ctx)
    if not segs:
        return "未检查", "calc 没有 派生.段界/半径"
    if my is None or x0 is None:
        return "未检查", "图上找不到轴线或轮廓左端，定不了 X0"
    hor = [(y1, (x1, x2)) for x1, y1, x2, y2, a in U.segs(ctx, ("outline",))
           if abs(y1 - y2) < 1e-6]
    ch = float((ctx.calc.get("派生") or {}).get("倒角") or 0)
    fil = (ctx.calc.get("派生") or {}).get("圆角") or []

    def allow(i, side):
        """母线在端部本来就缩进：外端是倒角 C，台阶端是圆角 R。"""
        if side == "L":
            if i == 0:
                return ch
            return float(fil[i - 1].get("R") or 0) if i - 1 < len(fil) else 0.0
        if i == len(segs) - 1:
            return ch
        return float(fil[i].get("R") or 0) if i < len(fil) else 0.0

    bad, ok = [], 0
    for s in segs:
        need0 = x0 + s["x0"] + allow(s["i"], "L")
        need1 = x0 + s["x1"] - allow(s["i"], "R")
        for sgn, word in ((-1, "上"), (1, "下")):
            ty = my + sgn * s["r"]
            spans = [sp for y, sp in hor if abs(y - ty) <= 0.05]
            gaps = U.cover(spans, need0, need1, tol=0.6)
            if gaps:
                bad.append("段%s %s母线（y=%.2f）缺 %.1fmm，起自 x=%.1f"
                           % (s["名"], word, ty, sum(b - a for a, b in gaps), gaps[0][0]))
            else:
                ok += 1
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:3]))
    return "通过", "%d 段上下母线都在（±0.05mm，覆盖全段）" % (ok // 2)


def p03(ctx):
    """圆角半径与 calc 圆角表一致，且圆心落在该台阶面上。"""
    segs = _derive(ctx.calc)
    x0 = _x0(ctx)
    fil = (ctx.calc.get("派生") or {}).get("圆角") or []
    if not fil:
        return "未检查", "calc 没有 派生.圆角"
    if segs is None or x0 is None:
        return "未检查", "图上找不到轮廓左端"
    arcs = U.arcs(ctx, ("outline",))
    if not arcs:
        return "未检查", "图上没有圆弧（outline 的 A 命令 / circle）"
    bad, ok = [], 0
    for f in fil:
        xi = x0 + float(f["肩"]) if x0 else None
        R = float(f["R"])
        hit = [c for c in arcs if abs(abs(c[2]) - R) <= 0.02
               and xi is not None and abs(c[0] - xi) <= max(2.0 * R, 1.0)]
        if hit:
            ok += 1
        else:
            near = [round(abs(c[2]), 2) for c in arcs
                    if xi is not None and abs(c[0] - xi) <= 2.0 * R + 1]
            bad.append("肩 x=%.1f 应 R%.1f，附近弧半径 %s" % (xi or 0, R, near[:4] or "无"))
    if bad:
        return "不通过", "；".join(bad[:3])
    return "通过", "%d 处圆角半径与 calc 一致、圆心在该台阶面上" % ok


def p04(ctx):
    """键槽长圆：两母线间距 = b、端半圆 r = b/2、全长 = 槽长。"""
    keys = ctx.calc.get("键") or {}
    if not keys:
        return "未检查", "calc 没有 键"
    items = [(t, a) for t, a, _ in ctx.els if a.get("data-role") == "key-outline"]
    if not items:
        return "未检查", "图上没有键槽轮廓（key-outline）"
    arcs = U.arcs(ctx, ("key-outline",))
    hor = [(a, (float(a["y1"]), float(a["y2"]))) for t, a in items
           if t == "line" and abs(float(a["y1"]) - float(a["y2"])) < 1e-6]
    bad, ok = [], 0
    for seg_name, k in sorted(keys.items()):
        b = float(k.get("b") or 0)
        L = float(k.get("槽长") or 0)
        if not b or not L:
            continue
        mine = [a for a, _ in hor if str(a.get("data-name", "")).find(seg_name) >= 0]
        mine_arc = [c for c in arcs if str(c[4].get("data-name", "")).find(seg_name) >= 0]
        if not mine or not mine_arc:
            # 名字对不上就用全场（单键槽图也说得通）
            mine = mine or [a for a, _ in hor]
            mine_arc = mine_arc or arcs
        if len(mine) < 2 or not mine_arc:
            bad.append("段%s 键槽轮廓不全（母线 %d 条、端弧 %d 个）" % (seg_name, len(mine), len(mine_arc)))
            continue
        ys = sorted(float(a["y1"]) for a in mine)
        wid = ys[-1] - ys[0]
        rr = [c[2] for c in mine_arc]
        xs = [float(a["x1"]) for a in mine] + [float(a["x2"]) for a in mine] + \
             [c[0] for c in mine_arc]
        span = max(xs) - min(xs) + max(rr or [0]) * 2 if rr else max(xs) - min(xs)
        if abs(wid - b) > 0.05:
            bad.append("段%s 槽宽 %.2f ≠ b=%g" % (seg_name, wid, b))
        elif any(abs(r - b / 2) > 0.05 for r in rr):
            bad.append("段%s 端半圆 r=%s ≠ b/2=%.1f" % (seg_name, [round(r, 2) for r in rr], b / 2))
        elif L and abs(span - L) > 0.15:
            bad.append("段%s 键槽全长 %.2f ≠ 槽长 %g" % (seg_name, span, L))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    if not ok:
        return "未检查", "没有可判的键槽"
    return "通过", "%d 处键槽：槽宽 = b、端半圆 = b/2、全长 = 槽长" % ok


def p05(ctx):
    """断面弧拟合半径 = 该段 d/2；槽底距圆心 = r − t1（缺口朝 +x）。"""
    segs = _derive(ctx.calc)
    keys = (ctx.calc.get("键") or {})
    if not segs or not keys:
        return "未检查", "calc 缺 段界/半径 或 键"
    arcs = U.arcs(ctx, ("section-outline",))
    if not arcs:
        return "未检查", "断面没有圆弧（A 命令）"
    items = [(float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]), a)
             for t, a, _ in ctx.els
             if t == "line" and a.get("data-role") == "section-outline"]
    if not items:
        return "未检查", "断面没有直线轮廓"
    groups = U.cluster([(min(i[0], i[2]), min(i[1], i[3]), max(i[0], i[2]), max(i[1], i[3]), i[4])
                        for i in items], gap=10.0)
    bad, ok, seen, uniq = [], 0, [], set()
    for g in groups:
        # 归属：弧的包围盒与该簇相交（不是看圆心远近——圆心在 30mm 外）
        cand = [c for c in arcs
                if c[0] + c[2] >= g[0] - 1 and c[0] - c[2] <= g[2] + 1
                and c[1] + c[2] >= g[1] - 1 and c[1] - c[2] <= g[3] + 1]
        cand = [c for c in cand if c[2] > 2.0]          # 槽根 R0.3 圆角不是轮廓主体
        if not cand:
            continue
        main = max(cand, key=lambda c: c[2])
        r, cx = main[2], main[0]
        if (round(cx, 1), round(r, 1)) in uniq:      # 同一断面被切成两簇时不重复判
            continue
        uniq.add((round(cx, 1), round(r, 1)))
        seg = min(segs, key=lambda s: abs(s["r"] - r))
        if abs(seg["r"] - r) > 0.05:
            bad.append("断面拟合 r=%.2f 与任何段半径都对不上" % r)
            continue
        seen.append(seg["名"])
        k = keys.get(seg["名"])
        # 槽底＝该断面里那条竖直轮廓线（水平的两条是槽壁，别混进来）
        xs = [i[0] for i in items
              if abs(i[0] - i[2]) < 1e-6 and g[0] - 1 <= i[0] <= g[2] + 1]
        if not k or not xs:
            continue
        t1 = float(k.get("t1") or 0)
        xb = max(xs)
        exp = cx + r - t1
        if abs(xb - exp) > 0.15:
            bad.append("段%s 槽底 x=%.2f，应为 cx+r−t1=%.2f" % (seg["名"], xb, exp))
        else:
            ok += 1
    if bad:
        return "不通过", "；".join(bad[:3])
    if not ok:
        return "未检查", "断面里没有带键槽的段"
    names = []
    for n in seen:
        if n not in names:
            names.append(n)
    return "通过", "%d 个断面：拟合半径 = d/2、槽底 = cx+r−t1（段 %s）" % (len(uniq), "、".join(names[:3]))


RULES = [
    ("P-01", "每段上下母线的半径 = d/2 且覆盖全段", "VIEW-13", "必", p01),
    ("P-03", "圆角半径与 calc 一致、圆心在台阶面上", "GEO-01", "必", p03),
    ("P-04", "键槽长圆：宽 = b、端弧 = b/2、全长 = 槽长", "VIEW-10", "必", p04),
    ("P-05", "断面弧半径 = d/2、槽底 = cx+r−t1", "VIEW-09", "必", p05),
]
