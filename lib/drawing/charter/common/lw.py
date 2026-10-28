"""common/lw.py —— 线宽分层（G-21、G-22）。

依据 GB/T 4457.4—2002：粗实线 0.5、细线/点画线 0.25、剖面线 0.18、尺寸线 0.2（mm，A3 1:1）。
这两条只读 CSS 与图元 class，不看几何——所以不受 transform 影响。
"""

from . import _util as U

WIDTH_OK = (0.5, 0.25, 0.18, 0.2)
WANT = {"thick": 0.5, "thin": 0.25, "center": 0.25, "hidden": 0.25,
        "hatch": 0.18, "dimline": 0.2, "ra": 0.2}
# GB/T 4457.4 只规定“粗线 d、细线 d/2”两档；0.25/0.2/0.18 是项目内部的细分档次。
# 所以这里只硬判“粗类必须 0.5、细类必须 <0.5 且在登记档位内”，不把 0.2 vs 0.25 判成错。
ROLE_THICK = ("outline", "section-outline", "key-outline")
# GB/T 4459.2：端面视图里齿根圆用细实线、分度圆与均布孔中心圆用细点画线——
# 这几个图元的 role 仍是 outline，但 class 合法地不是 thick，登记豁免（别把标准画法判成错）。
EXEMPT = {"root.circle", "pitch.circle", "hole.circle"}
ROLE_THIN = {"centerline": (0.25, 0.2), "hatch": (0.18, 0.25),
             "dimension": (0.2, 0.25), "extension": (0.2, 0.25), "hidden": (0.25,)}

RULES = []


def r_g21(ctx):
    """CSS 里每个 class 的线宽都要落在 0.5/0.25/0.18/0.2 四档，关键 class 要对号。"""
    style = U.css(ctx.root)
    got = {}
    for cls, props in style.items():
        v = props.get("stroke-width")
        if v:
            try:
                got[cls] = float(v)
            except ValueError:
                pass
    if not got:
        return "未检查", "CSS 里没有 stroke-width"
    bad = ["%s=%s" % (c, w) for c, w in got.items()
           if not any(abs(w - t) < 1e-6 for t in WIDTH_OK)]
    miss = ["%s 应 %.2f 实为 %.2f" % (c, w, got[c]) for c, w in WANT.items()
            if c in got and abs(got[c] - w) > 1e-6]
    if bad:
        return "不通过", "线宽不在四档内：%s" % "、".join(bad[:4])
    if miss:
        return "不通过", "；".join(miss[:3])
    return "通过", "%d 个 class 线宽都在 %s 档内（含 thick 0.5 / dimline 0.2 / hatch 0.18 对号）" % (
        len(got), "/".join("%.2f" % w for w in WIDTH_OK))


def r_g22(ctx):
    """图元角色与线宽对不上就报（粗实轮廓不能是 0.25，剖面线不能是 0.5）。"""
    style = U.css(ctx.root)
    seen, bad = {}, []
    for tag, a, _ in ctx.els:
        role = a.get("data-role")
        if role not in ROLE_THICK and role not in ROLE_THIN:
            continue
        w = U.stroke_width(a, style)
        if w is None:
            continue
        seen[role] = seen.get(role, 0) + 1
        if role in ROLE_THICK:
            if str(a.get("data-feature") or "") in EXEMPT:
                continue
            if abs(w - 0.5) > 1e-6:
                bad.append("%s(%s)=%.2f，粗实线应为 0.50" % (role, a.get("data-name") or tag, w))
        elif not any(abs(w - ok) < 1e-6 for ok in ROLE_THIN[role]):
            bad.append("%s(%s)=%.2f，不在细线档 %s 内"
                       % (role, a.get("data-name") or tag, w, ROLE_THIN[role]))
    if not seen:
        return "未检查", "图元没有可解析的线宽"
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:3]))
    return "通过", "%d 个图元的角色与线宽对得上（粗 %s；细 %s）" % (
        sum(seen.values()), "、".join(sorted(ROLE_THICK)),
        "、".join("%s %s" % (r, "/".join("%.2f" % v for v in ROLE_THIN[r]))
                  for r in sorted(ROLE_THIN)))


RULES = [
    ("G-21", "线宽只有 0.5/0.25/0.18/0.2 四档且关键 class 对号", "SHT-07", "必", r_g21),
    ("G-22", "粗实线 0.5、细线在登记档内（角色↔线宽）", "SHT-06", "必", r_g22),
]