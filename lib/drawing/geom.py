# -*- coding: utf-8 -*-
"""geom.py —— 几何作图：等分圆周/正多边形、斜度、锥度、圆弧连接、四心椭圆

依据：图1-23 p.16 / 图1-24 p.17 / 图1-25 p.17 [核]；图1-26 p.18 [核]；图1-28 p.19 [核]；
      表1-7 p.20–21 [核]；图1-30 p.20 [核]；图1-31 p.21–22 [核]
所有函数返回 图形；只用 _prim 原语，线型只取 STYLES 名（thick/thin/center）。
"""
import sys
from pathlib import Path
MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path: sys.path.insert(0, str(MDKIT))
from lib.drawing._prim import 图形, 校验图元, 线, 圆, 弧, 矩形, 文, 剖面线, 箭头, 波浪线, 双折线, 尺寸H, 尺寸V, 拼

import math

字高 = 3.5      # 标注字高 h，斜度/锥度符号的基准尺寸都按它算


def _字宽(s, h=字高):
    return sum(h if ord(c) > 0x2E80 else 0.55 * h for c in s)


def _比(值):
    """把比值写成 1:n（能整除就整数，否则小数）。"""
    if 值 <= 0:
        raise ValueError("比值须为正")
    n = 1.0 / 值
    if abs(n - round(n)) < 1e-9:
        return f"1:{int(round(n))}"
    return f"1:{值:g}"


def _角(dx, dy):
    """向量角（度，[0,360)）。"""
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _弧段(cx, cy, r, p1, p2):
    """过 p1→p2 的逆时针短弧（<180°），交给 弧()。"""
    a1 = _角(p1[0] - cx, p1[1] - cy)
    a2 = _角(p2[0] - cx, p2[1] - cy)
    return 弧(cx, cy, r, a1, a1 + ((a2 - a1) % 360.0))


# ---------------------------------------------------------------- 等分 / 正多边形
def 等分圆周(n=6, R=30, cx=100, cy=100, 画多边形=True, 画圆=True):
    """图1-23 p.16（3/6/12 等分）、图1-24 p.17（5 等分）、图1-25 p.17（n 等分）[核]。

    圆 thin、内接多边形 thick、水平/竖直中心线 center（超出圆周 4 mm，同表1-4 的 2~3 mm 量级），
    每个等分点画 r=0.8 小圆作标记。起始点在正上方（90°），逆时针等分。
    画圆=False 供 正多边形() 复用（只要多边形）。
    """
    if n < 3:
        raise ValueError(f"等分圆周需 n≥3，收到 n={n}")
    g = 图形()
    if 画圆:
        g.加(圆(cx, cy, R, "thin"))
    pts = [(cx + R * math.cos(math.pi / 2 + 2 * math.pi * i / n),
            cy + R * math.sin(math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]
    if 画多边形:
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            g.加(线(a[0], a[1], b[0], b[1], "thick"))
    g.加(线(cx - R - 4, cy, cx + R + 4, cy, "center"),
        线(cx, cy - R - 4, cx, cy + R + 4, "center"))
    for p in pts:
        g.加(圆(p[0], p[1], 0.8, "thin"))
    return g.范围(cx - R - 4, cy - R - 4, cx + R + 4, cy + R + 4)


def 正多边形(n=6, R=30, cx=100, cy=100):
    """图1-23 / 图1-24 / 图1-25 [核]：圆内接正 n 边形，转调 等分圆周(画圆=False)。"""
    return 等分圆周(n=n, R=R, cx=cx, cy=cy, 画多边形=True, 画圆=False)


# ---------------------------------------------------------------- 斜度 / 锥度
def 斜度(值=0.2, 长=60, x=0, y=0):
    """图1-26 / 图1-27 p.18 [核]：斜度 = tanα = 升高/水平长，写成 ∠1:n。

    直角三角形：底 长（水平）、高 值×长（竖直）、斜边 thick；直角处细线小方框标记。
    符号：两条细实线夹角 30°，高 = 字高 h；斜线方向与斜度方向一致（向右上升）。
    n=round(1/值) 仅在 值=1/n 时成立，否则比值写小数（∠1:0.3）。
    """
    if 值 <= 0:
        raise ValueError("斜度须为正")
    高 = 值 * 长
    g = 图形().加(线(x, y, x + 长, y, "thick"),          # 底边
                  线(x + 长, y, x + 长, y + 高, "thick"),  # 竖边
                  线(x, y, x + 长, y + 高, "thick"))       # 斜边
    # 直角标记（细实线，边长 3 mm）
    g.加(线(x + 长 - 3, y, x + 长 - 3, y + 3, "thin"),
        线(x + 长 - 3, y + 3, x + 长, y + 3, "thin"))
    # 符号：底边长 h/tan30° = 1.732h，斜线升 h
    sx, sy = x + 长 + 6, y + 高 + 2
    底 = 字高 / math.tan(math.radians(30))
    g.加(线(sx, sy, sx + 底, sy, "thin"), 线(sx, sy, sx + 底, sy + 字高, "thin"))
    标 = f"∠{_比(值)}"
    g.加(文(sx + 底 + 2, sy, 标, 字高, anchor="start"))
    return g.范围(x - 2, y - 3, sx + 底 + 2 + _字宽(标), y + 高 + 6)


def 锥度(值=0.2, 长=60, 大端=30, x=0, y=0):
    """图1-28 / 图1-29 p.19 [核]：锥度 = (D−d)/l = 1:n。

    等腰梯形：大端 D 在左（x 处），小端 d = D − 值×长 在右，四边 thick；轴线 center（两端各出 6）。
    符号：等腰三角形，顶角 30°（左右各 15°），高 1.4h；水平轴线长 2.5h（图标注「1.4h / 2.5h / 15°」）。
    注：顶角 30° 与「高 1.4h」自洽，而底边由 30° 定出为 0.75h≠2.5h，故 2.5h 按符号轴线长度理解。
    """
    if 值 <= 0:
        raise ValueError("锥度须为正")
    d = 大端 - 值 * 长
    if d <= 0:
        raise ValueError(f"小端直径 d={d:g}≤0，长/值过大")
    g = 图形().加(线(x - 6, y, x + 长 + 6, y, "center"))                 # 轴线
    梯 = [(x, y - 大端 / 2), (x + 长, y - d / 2), (x + 长, y + d / 2), (x, y + 大端 / 2)]
    for i in range(4):
        g.加(线(*梯[i], *梯[(i + 1) % 4], "thick"))

    # 符号：顶角 30°、高 1.4h 的等腰三角形 + 长 2.5h 的水平轴线
    高 = 1.4 * 字高
    半 = 高 * math.tan(math.radians(15))
    sx, sy = x + 长 + 14, y + 1.2 * 字高
    顶, 上, 下 = (sx, sy), (sx - 高, sy + 半), (sx - 高, sy - 半)
    g.加(线(*上, *顶, "thin"), 线(*顶, *下, "thin"), 线(*下, *上, "thin"))
    g.加(线(sx, sy, sx - 2.5 * 字高, sy, "thin"))
    标 = _比(值)
    g.加(文(sx + 2, sy + 0.2, 标, 字高, anchor="start"))
    return g.范围(x - 6, y - 大端 / 2 - 2, sx + 2 + _字宽(标), y + 大端 / 2 + 2)


# ---------------------------------------------------------------- 圆弧连接
def 圆弧连接(半径=15, 类型="两直线", 长=60, x=0, y=0):
    """表1-7 第 1 行（连接相交两直线）+ 图1-30a p.20 [核]。

    直角两边 thick（沿 +x、+y，从角点起）；连接弧 thick，圆心 (x+R, y+R)，
    与两边分切于 (x+R, y)、(x, y+R)；圆心与两切点各画 3 mm 细十字。
    其它连接类型（直线+弧、弧+弧，表1-7 其余 6 行）本批未实现 → NotImplementedError。
    """
    if 类型 != "两直线":
        raise NotImplementedError(f"圆弧连接 本批只实现 '两直线'（表1-7 第 1 行），收到 {类型!r}")
    R = 半径
    if 长 <= R:
        raise ValueError("长须大于半径，否则切点落在边外")
    if R <= 0:
        raise ValueError("半径须为正")

    g = 图形().加(线(x, y, x + 长, y, "thick"), 线(x, y, x, y + 长, "thick"))
    g.加(弧(x + R, y + R, R, 180, 270, "thick"))
    for px, py in [(x + R, y + R), (x + R, y), (x, y + R)]:
        g.加(线(px - 1.5, py, px + 1.5, py, "thin"), 线(px, py - 1.5, px, py + 1.5, "thin"))
    return g.范围(x - 2, y - 2, x + 长 + 2, y + 长 + 2)


# ---------------------------------------------------------------- 四心椭圆
def 椭圆(长轴=80, 短轴=50, cx=0, cy=0):
    """图1-31 p.21–22 [核]：四心法（四段圆弧的近似椭圆，非真椭圆）。

    构造（A-sheet 图1-31 步骤 2~6）：E 在短轴延长线上、OE=OA=a，故 CE=a−b；
    以 C 为心、CE 为半径截 CA 得 F；AF 的中垂线交长轴于 O₁、短轴于 O₂，
    对称得 O₃、O₄。小弧圆心 O₁/O₃ 在长轴上（半径 a−x₁），大弧圆心 O₂/O₄ 在短轴上（半径 b+|y₂|）。
    四段弧在连心线处内切，长/短轴端点 A、B、C、D 落在弧上，故 bbox 恰为 长轴×短轴。
    """
    if 长轴 <= 短轴:
        raise ValueError("长轴须大于短轴")
    if 短轴 <= 0:
        raise ValueError("短轴须为正")
    a, b = 长轴 / 2.0, 短轴 / 2.0
    L = math.hypot(a, b)
    k = (a - b) / L
    fx, fy = k * a, b * (1 - k)                 # F 在 CA 上，|CF| = a−b
    x1 = (fx * fx + fy * fy - a * a) / (2 * (fx - a))       # O₁ 在长轴上的 x
    y2 = fy / 2 + ((a + fx) / 2) * (fx - a) / fy            # 中垂线交短轴的 y（负）
    S, B = a - x1, b - y2                                    # 小弧、大弧半径（y2<0）
    d = math.hypot(x1, y2)
    if abs(d - (B - S)) > 1e-6 * max(1.0, B):
        raise ValueError(f"四心法构造不自洽：|O₁O₂|={d:.6f}，B−S={B - S:.6f}")

    O1, O3 = (x1, 0.0), (-x1, 0.0)              # 小弧圆心（长轴）
    O2, O4 = (0.0, y2), (0.0, -y2)              # 大弧圆心（短轴，O₂ 在下、O₄ 在上）
    ux, uy = (x1 - O2[0]) / d, (0.0 - O2[1]) / d
    px, py = O1[0] + S * ux, O1[1] + S * uy     # 右上方切点（小弧与大弧连心线上）

    def P(Ox, Oy):      # 局部坐标 → 图面坐标
        return (Ox + cx, Oy + cy)

    g = 图形()
    g.加(_弧段(*P(*O1), S, P(px, -py), P(px, py)))         # 右小弧：下切点 → A → 上切点
    g.加(_弧段(*P(*O2), B, P(px, py), P(-px, py)))         # 上大弧：右切点 → C → 左切点
    g.加(_弧段(*P(*O3), S, P(-px, py), P(-px, -py)))       # 左小弧：上切点 → B → 下切点
    g.加(_弧段(*P(*O4), B, P(-px, -py), P(px, -py)))       # 下大弧：左切点 → D → 右切点
    g.参数 = dict(a=a, b=b, x1=x1, y2=y2, R小=S, R大=B, 切点=(px, py))
    return g.范围(cx - a, cy - b, cx + a, cy + b)


__all__ = ["等分圆周", "正多边形", "斜度", "锥度", "圆弧连接", "椭圆"]
