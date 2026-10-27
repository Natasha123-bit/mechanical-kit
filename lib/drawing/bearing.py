# -*- coding: utf-8 -*-
"""bearing.py —— 滚动轴承的画法（《机械制图》ch8 §8-8，图8-63/8-64、表8-9，p.250–253）

依据：books/drawing/handoff-ch08/A-bearing.json（A 角色逐线核过表8-9 与图8-64 的页图）
  表8-9 6000 型规定画法 [核]：外圈/内圈轮廓 thick + 45° 细实线剖面线（内外圈**同向**）；
          钢球为圆（直径约 0.6A，圆内不画剖面线），球心画细点画线十字；
          保持架、倒角省略不画（正文 p.253）。
  图8-64(a) 通用画法 [核]：外接矩形 B×D + 粗十字（不与线框接触）+ 角部 2B/3×2A/3 台阶。
  图8-64(b) 特征画法 [核]：矩形 + 与轴线成 30° 的粗实线（长 2B/3）+ 斜十字。
  图8-64(c) [核]：轴线以上按规定画法、以下按通用画法（同一轴承上下两半两种画法）。
  附表22 p.302 [核]：6206 → d=30、D=62、B=16。

硬约束：只走 lib.drawing._prim 原语；线型只用 thick/thin/center/hidden/wavy。
未收录的轴承型号一律 NotImplementedError（"待查附表22"），不按规律外推。
"""
import math
import sys
from pathlib import Path
MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path: sys.path.insert(0, str(MDKIT))
from lib.drawing._prim import 图形, 校验图元, 线, 圆, 弧, 矩形, 文, 剖面线, 尺寸H, 尺寸V, 拼

球径系数 = 0.6          # 球径 ≈ 0.6A：A-bearing 记「按图上比例约 0.6A，书未标注」
十字臂系数 = 0.3        # 通用画法十字长度「不注，随矩形取」（表8-9 备注）：取 0.3·min(B,D) 为臂长
剖面间距 = 2.0          # 45° 剖面线间距（细实线）

# 只做显式映射，不做规律外推：6206 见附表22 p.302；6208 书内附表22 未取到该行
_轴承表 = {
    "6206": dict(d=30.0, D=62.0, B=16.0, 来源="附表22 p.302 [核]"),
    "6208": dict(d=40.0, D=80.0, B=18.0, 来源="GB/T 276 尺寸系列(02)［待核：书内附表22 未取到该行］"),
}


def 轴承代号(代号="6206"):
    """按代号返回 d/D/B。依据：附表22 p.302 [核]（6206 已核对：06 → 6×5=30）。"""
    if 代号 not in _轴承表:
        raise NotImplementedError(f"轴承 {代号!r} 的 d/D/B 待查附表22")
    out = dict(代号=代号)
    out.update(_轴承表[代号])
    return out


# ============================================================ 半视图小工具
def _缺口矩形(x0, y0, x1, y1, cx, cy, r):
    """矩形 [x0,x1]×[y0,y1] 挖掉以 (cx,cy) 为心、半径 r 的半圆，得到剖面线用的多边形。

    钢球圆心正好落在环带的某一条横边上（球心节圆 = 内外圈分界），落在哪条边上就往那个方向
    挖掉半个球：圆心在下边 → 挖上半圆；圆心在上边 → 挖下半圆。这样剖面线不会进入球内
    （表8-9：滚动体不画剖面线）。球面轮廓按 12° 取样（多边形逼近）。
    """
    def 弧(a1, a2):
        n = max(2, int(abs(a2 - a1) / 12))
        return [(cx + r * math.cos(math.radians(a1 + (a2 - a1) * i / n)),
                 cy + r * math.sin(math.radians(a1 + (a2 - a1) * i / n))) for i in range(n + 1)]

    if abs(cy - y0) < 1e-9:            # 圆心在底边：挖上半圆（180°→0°，经圆顶）
        return ([(x0, y0), (cx - r, y0)] + 弧(180, 0)
                + [(cx + r, y0), (x1, y0), (x1, y1), (x0, y1)])
    if abs(cy - y1) < 1e-9:            # 圆心在顶边：挖下半圆（360°→180°，经圆底）
        return ([(x0, y0), (x1, y0), (x1, y1), (cx + r, y1)] + 弧(360, 180)
                + [(cx - r, y1), (x0, y1)])
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]      # 球未与该环带相交：整块剖面


def _规定半(g, 侧, cx, cy, xA, B, A, d, D):
    """规定画法的半视图（侧=+1 画轴线以上，−1 画以下）。依据：表8-9 p.253 [核]。"""
    ya, ym, yi = cy + 侧 * D / 2, cy + 侧 * (D / 2 - A / 2), cy + 侧 * d / 2
    bc = cy + 侧 * (D + d) / 4                        # 球心节圆 D0/2，正好在内外圈分界上
    rb = 球径系数 * A / 2                            # 半径 = 0.3A
    def 横边(y):
        """环带的水平边；若钢球压在边上，就在球径范围内断开（滚动体不剖，球内不许有线）。"""
        if abs(y - bc) < rb - 1e-9:
            half = math.sqrt(rb * rb - (y - bc) ** 2)
            return [线(xA, y, cx - half, y), 线(cx + half, y, xA + B, y)]
        return [线(xA, y, xA + B, y)]

    for y1, y2 in ((ym, ya), (yi, ym)):               # 外圈（靠 D）、内圈（靠 d），各厚 A/2
        lo, hi = min(y1, y2), max(y1, y2)
        for y in (lo, hi):
            g.加(*横边(y))
        g.加(线(xA, lo, xA, hi), 线(xA + B, lo, xA + B, hi))
        g.加(剖面线(_缺口矩形(xA, lo, xA + B, hi, cx, bc, rb),
                    spacing=剖面间距, angle=45.0))   # 内外圈同向剖面线（表8-9 硬要求）
    g.加(圆(cx, bc, rb))                             # 滚动体：圆，球内不画剖面线
    臂 = 1.2 * rb
    g.加(线(cx - 臂, bc, cx + 臂, bc, "center"),       # 球心细点画线十字
         线(cx, bc - 臂, cx, bc + 臂, "center"))


def _通用半(g, cx, cy, xA, B, A, d, D):
    """通用画法的半视图：B×A 矩形（r=d/2→D/2）+ 粗十字。依据：图8-64(a)(c) p.252 [核]。

    矩形下边即 r=d/2 的「d 与 A 的界线」（表8-9 通用画法注），内孔不得被填平。
    """
    y_内, y_外 = cy - d / 2, cy - D / 2
    g.加(矩形(xA, y_外, B, y_内 - y_外))
    臂 = 十字臂系数 * min(B, D)
    ym = cy - (D + d) / 4
    g.加(线(cx - 臂, ym, cx + 臂, ym), 线(cx, ym - 臂, cx, ym + 臂))


# ============================================================ 画法
def 轴承画法(d=30.0, D=62.0, B=16.0, 类型="深沟球", 画法="规定", 半剖=True,
          cx=80.0, cy=100.0):
    """滚动轴承（轴线水平，轴线过 y=cy）。返回 图形。

    依据：表8-9 6000 型规定画法 p.253 [核]；图8-64 通用/特征/规定画法 p.252 [核]；
          附表22 p.302 [核] 6206 = 30/62/16。
      画法="规定"：上半（半剖=True 时只有上半）外圈矩形 D/2→D/2−A/2 + 内圈矩形 d/2→d/2+A/2，
                  轮廓 thick + 45° 同向剖面线；钢球 r=0.3A，球心 (cx, cy+(D+d)/4)，球内不剖面，
                  球心 center 十字；保持架、倒角不画。
      半剖=True：下半改通用画法（B×D/2 矩形 + 粗十字，无剖面线无球），即图8-64(c)。
      画法="通用"：B×D 矩形 + 粗十字 + 角部 2B/3×2A/3 台阶。
      画法="特征"：B×D 矩形 + 30° 粗斜线（长 2B/3）+ 斜十字。
    A=(D−d)/2 为径向总厚，表8-9 的一切比例都以 A、A/2 为基准。
    """
    if 类型 != "深沟球":
        raise NotImplementedError(
            f"类型={类型!r} 待实现：圆锥滚子需 T/C/B 与 15° 滚道（表8-9 p.253），推力球需 T 与两垫圈")
    if 画法 not in ("规定", "通用", "特征"):
        raise ValueError(f"画法 取 '规定'/'通用'/'特征'，收到 {画法!r}")
    if not (0 < d < D):
        raise ValueError(f"必须 0 < d < D，收到 d={d}、D={D}")
    if B <= 0:
        raise ValueError("宽度 B 必须 > 0")
    A = (D - d) / 2
    xA, xB = cx - B / 2, cx + B / 2
    g = 图形()

    g.加(线(xA - 6, cy, xB + 6, cy, "center"))         # 轴线 center

    if 画法 == "规定":
        if 半剖:
            _规定半(g, +1, cx, cy, xA, B, A, d, D)     # 上半：规定画法
            _通用半(g, cx, cy, xA, B, A, d, D)         # 下半：通用画法
        else:
            _规定半(g, +1, cx, cy, xA, B, A, d, D)
            _规定半(g, -1, cx, cy, xA, B, A, d, D)
    elif 画法 == "通用":
        g.加(矩形(xA, cy - D / 2, B, D))                # 外接矩形 B×D
        g.加(线(xA, cy + d / 2, xB, cy + d / 2, "thick"),   # d 与 A 的界线（内孔不得填平）
             线(xA, cy - d / 2, xB, cy - d / 2, "thick"))
        臂 = 十字臂系数 * min(B, D)
        ym = cy - (D + d) / 4                           # 十字置于 A 带内、让开右上角台阶
        g.加(线(cx - 臂, ym, cx + 臂, ym), 线(cx, ym - 臂, cx, ym + 臂))   # 粗十字，不接触线框
        g.加(矩形(xB - 2 * B / 3, cy + D / 2 - 2 * A / 3, 2 * B / 3, 2 * A / 3))  # 角部台阶
    else:                                              # 特征
        g.加(矩形(xA, cy - D / 2, B, D))
        g.加(线(xA, cy + d / 2, xB, cy + d / 2, "thick"),
             线(xA, cy - d / 2, xB, cy - d / 2, "thick"))
        长 = 2 * B / 3
        yc = cy + (D + d) / 4
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        g.加(线(cx - 长 / 2 * c, yc - 长 / 2 * s, cx + 长 / 2 * c, yc + 长 / 2 * s))  # 30° 粗斜线
        臂 = 十字臂系数 * min(B, D)
        g.加(线(cx - 臂 * c, yc - 臂 * s, cx + 臂 * c, yc + 臂 * s),                  # 斜十字（30°）
             线(cx + 臂 * s, yc - 臂 * c, cx - 臂 * s, yc + 臂 * c))                  # 斜十字（120°）

    g.注(f"d={d:g}、D={D:g}、B={B:g}；A=(D−d)/2={A:g}，内外圈径向厚各 A/2={A / 2:g}",
         f"球心节圆 D0=(D+d)/2={(D + d) / 2:g}，球心轴向在 B/2={B / 2:g} 处")
    if 画法 == "规定":
        g.注(f"滚动体为圆，直径按图上比例约 0.6A={0.6 * A:g}（书未标注数值）")
        g.注("内外圈剖面线同向（45°）；滚动体不画剖面线；保持架与倒角省略不画（p.253）")
        g.注("上半规定画法 + 下半通用画法（图8-64c）：同一轴承两半用不同画法"
             if 半剖 else "上下两半均按规定画法绘制")
    elif 画法 == "通用":
        g.注("通用画法：外接矩形 B×D + 粗十字（不得与线框相接）+ 角部 2B/3×2A/3 台阶（图8-64a）")
        g.注("矩形内不画剖面线；不必确切表示外形轮廓、载荷特征和结构特征")
    else:
        g.注("特征画法：矩形 + 与轴线成 30° 的粗实线（长 2B/3）+ 斜十字（图8-64b）")
        g.注("表8-9 6000 型另有「十字 + 台阶（B/8、2B/3）」写法，本函数按图8-64b 实现")
    if 半剖 and 画法 != "规定":
        g.注("半剖 仅对 画法='规定' 生效，本次未使用")

    g.参数 = dict(d=d, D=D, B=B, A=A, A半=A / 2, D0=(D + d) / 2,
                  球半径=球径系数 * A / 2 if 画法 == "规定" else None,
                  球心y=[cy + s * (D + d) / 4 for s in ((+1,) if 半剖 else (+1, -1))]
                  if 画法 == "规定" else [],
                  类型=类型, 画法=画法, 半剖=半剖)
    g.范围(xA - 8, cy - D / 2 - 5, xB + 8, cy + D / 2 + 5)
    return g


# ============================================================ 自检
def _自检():
    out = []
    for 参 in (dict(画法="规定", 半剖=True), dict(画法="规定", 半剖=False),
               dict(画法="通用"), dict(画法="特征")):
        g = 轴承画法(**参)
        ok, msg = 校验图元(g.elems)
        assert ok, msg
        q = g.参数
        out.append((f"轴承画法{参}", f"{msg}；图元 {len(g)}"))
        out.append(("  几何", f"d/2={q['d'] / 2:g} D/2={q['D'] / 2:g} A/2={q['A半']:g} "
                              f"球心半径 D0/2={q['D0'] / 2:g} 球半径={q['球半径']}"))
    for 代 in ("6206", "6208"):
        out.append((f"轴承代号 {代}", str(轴承代号(代))))
    for bad in (dict(代号="6209"),):
        try:
            轴承代号(**bad)
        except NotImplementedError as e:
            out.append(("应报错 6209", str(e)))
    try:
        轴承画法(类型="圆锥滚子")
    except NotImplementedError as e:
        out.append(("应报错 圆锥滚子", str(e)[:50]))
    return out


if __name__ == "__main__":
    for k, v in _自检():
        print(f"{k}: {v}")
