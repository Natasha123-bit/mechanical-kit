# -*- coding: utf-8 -*-
"""shaft.py —— 阶梯轴零件图与几何公差标注（《机械制图》ch7 §7-1/§7-5）

依据：图7-1 主动轴零件图 p.174 [核]（主视图 + A—A 断面 + 局部放大 + 尺寸 + 技术要求）；
      图7-45~7-49 p.205–207 [核]（公差框格/基准/被测导出要素）。
结构参数化：段长组合是示意（图7-1 的结构），不是抄图上每一个尺寸值。
"""
import math
import sys
from pathlib import Path

MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path:
    sys.path.insert(0, str(MDKIT))

from lib.drawing._prim import (图形, 校验图元, 线, 圆, 弧, 矩形, 文, 剖面线,  # noqa: E402
                               尺寸H, 尺寸V, 公差框, 基准, 粗糙度)
from lib.drawing import parts  # noqa: E402


def _键槽断面(g, cx, cy, d, 槽宽, 槽深):
    """A—A 键槽断面：主圆弧 + 键槽缺口 + 下方剖面线（键槽内不画剖面线）。"""
    r = d / 2.0
    half = 槽宽 / 2.0
    if half >= r:
        raise ValueError("键槽宽须小于轴径")
    y0 = math.sqrt(r * r - half * half)          # 槽侧壁与圆的交点高度
    sb = r - 槽深                                 # 槽底高度（从圆顶向内量槽深）
    a0 = math.degrees(math.atan2(y0, -half))      # 左交点角（约 99°）
    a1 = math.degrees(math.atan2(y0, half))       # 右交点角（约 81°）
    # 主圆弧：从左交点经左/下/右到右交点（顶弧被键槽切掉）
    g.加(弧(cx, cy, r, a0, a1 + 360, "thick"))
    g.加(线(cx + half, cy + y0, cx + half, cy + sb, "thick"),
         线(cx + half, cy + sb, cx - half, cy + sb, "thick"),
         线(cx - half, cy + sb, cx - half, cy + y0, "thick"))
    # 剖面线：材料 = 圆 − 顶部键槽；取“槽底→右壁→主圆弧→左壁”的闭合域
    n = 24
    arc = [(cx + r * math.cos(math.radians(a1 + 360 - (a1 + 360 - a0) * i / n)),
            cy + r * math.sin(math.radians(a1 + 360 - (a1 + 360 - a0) * i / n))) for i in range(n + 1)]
    点 = [(cx - half, cy + sb), (cx + half, cy + sb)] + arc + [(cx - half, cy + sb)]
    g.加(剖面线(点, spacing=2.0, angle=45.0))
    g.加(线(cx - r - 4, cy, cx + r + 4, cy, "center"),
         线(cx, cy - r - 4, cx, cy + r + 4, "center"))


def 阶梯轴零件图(段=((14.0, 30.0), (20.0, 20.0), (25.0, 40.0), (20.0, 20.0), (14.0, 30.0)),
            键槽=(4.0, 25.0, 2.5), 倒角=2.0, 退刀槽=(4.0, 2.0), 材料="45",
            比例="1:1", 中心孔="A3.15"):
    """阶梯轴零件图（主视图 + A—A 键槽断面 + 局部放大 I + 尺寸/粗糙度/公差/技术要求）。

    依据：图7-1 p.174 [核]。
      主视图：各段圆柱 thick、轴肩竖线 thick、两端 45° 倒角、第一段右端退刀槽；
      A—A：键槽断面（圆弧 + 矩形缺口，缺口内不画剖面线）；
      局部放大 I：退刀槽 2:1；
      尺寸：总长、各段直径、键槽宽/深；粗糙度 3 处；同轴度公差框 1 处 + 基准 A；
      技术要求：parts.技术要求模板（未注圆角/倒角/粗糙度/热处理/材料）。
      `段` 的段长组合为示意；`键槽`=(宽, 所在段直径, 深)。
    """
    if len(段) < 2:
        raise ValueError("至少两段")
    长 = [L for _, L in 段]
    直 = [d for d, _ in 段]
    总长 = sum(长)
    xs = [0.0]
    for L in 长:
        xs.append(xs[-1] + L)
    maxr = max(直) / 2.0
    g = 图形()

    for i, (d, L) in enumerate(段):
        x0, x1, r = xs[i], xs[i + 1], d / 2.0
        if i == 0:
            xe = x1 - (退刀槽[0] if 退刀槽 else 0.0)
            g.加(线(x0 + 倒角, 0 + r, xe, 0 + r), 线(x0 + 倒角, 0 - r, xe, 0 - r),
                 线(x0, 0 + r - 倒角, x0 + 倒角, 0 + r),
                 线(x0, 0 - r + 倒角, x0 + 倒角, 0 - r),
                 线(x0, 0 - r + 倒角, x0, 0 + r - 倒角))
        elif i == len(段) - 1:
            g.加(线(x0, 0 + r, x1 - 倒角, 0 + r), 线(x0, 0 - r, x1 - 倒角, 0 - r),
                 线(x1 - 倒角, 0 + r, x1, 0 + r - 倒角),
                 线(x1 - 倒角, 0 - r, x1, 0 - r + 倒角),
                 线(x1, 0 - r + 倒角, x1, 0 + r - 倒角))
        else:
            g.加(线(x0, 0 + r, x1, 0 + r), 线(x0, 0 - r, x1, 0 - r))
        if i > 0:
            rp = 段[i - 1][0] / 2.0
            g.加(线(x0, rp, x0, r), 线(x0, -rp, x0, -r))

    # 退刀槽：第一段右端
    if len(段) >= 2 and 退刀槽:
        b, dep = 退刀槽
        x1 = xs[1]
        xg = x1 - b
        r1 = 段[0][0] / 2.0
        r2 = 段[1][0] / 2.0
        r槽 = r1 - dep
        # 覆盖原第一段两端的直线：先画槽形（后画覆盖前画，视觉上以槽为准）
        for s in (1, -1):
            g.加(线(xg, 0 + s * r1, xg, 0 + s * r槽),
                 线(xg, 0 + s * r槽, x1, 0 + s * r槽),
                 线(x1, 0 + s * r槽, x1, 0 + s * r2))
        g.加(文(xg + b / 2, r1 + 5, f"{b:g}×{2 * r槽:g}", 3.2))

    # 中心孔（两端，细线）
    if 中心孔:
        for x0, s in ((0.0, 1), (总长, -1)):
            r = 1.5
            g.加(线(x0, 1.5, x0 + s * 4, 1.5, "thin"),
                 线(x0, -1.5, x0 + s * 4, -1.5, "thin"),
                 线(x0 + s * 4, 1.5, x0 + s * 6.5, 0, "thin"),
                 线(x0 + s * 4, -1.5, x0 + s * 6.5, 0, "thin"))

    g.加(线(-5, 0, 总长 + 5, 0, "center"))

    # A—A 键槽断面（放在主视图右侧）
    kx = 总长 + 45
    _键槽断面(g, kx, 0, 键槽[1], 键槽[0], 键槽[2])
    g.加(文(kx, -maxr - 14, "A—A", 3.5),
         文(kx, -maxr - 22, f"键槽 {键槽[0]:g}×{键槽[2]:g}", 3.2))

    # 局部放大 I：退刀槽 2:1
    dx, dy = 5, -maxr - 35
    b, dep = 退刀槽 if 退刀槽 else (4, 2)
    sc = 2.0
    g.加(线(dx, dy, dx + b * sc, dy), 线(dx, dy - dep * sc, dx + b * sc, dy - dep * sc),
         线(dx, dy, dx, dy - dep * sc), 线(dx + b * sc, dy, dx + b * sc, dy - dep * sc))
    g.加(文(dx + b * sc + 3, dy - dep * sc / 2, "I  2:1", 3.5, anchor="start"))

    # 尺寸
    g.加(尺寸H(-maxr - 16, 0, 总长, f"{总长:g}"))
    for i, (d, L) in enumerate(段):
        g.加(尺寸V(xs[i] + L / 2, -d / 2, d / 2, f"φ{d:g}", right=2.2))
    g.加(尺寸H(-maxr - 26, xs[2], xs[3], f"{长[2]:g}"))

    # 粗糙度 / 公差 / 基准
    g.加(粗糙度(8, maxr + 8, "Ra3.2"), 粗糙度(xs[2] + 5, maxr + 8, "Ra6.3"),
         粗糙度(总长 - 12, maxr + 8, "Ra3.2"))
    g.加(公差框(5, maxr + 22, ["◎", "φ0.02", "A"]),
         基准(0, -maxr - 36, "A", up=True))
    g.加(parts.技术要求模板(材料=材料, x=5, y=-maxr - 45))

    g.参数 = dict(段=段, 总长=总长, 最大直径=max(直), 段数=len(段), 键槽=键槽)
    g.范围(-8, -maxr - 90, max(总长 + 70, kx + 25), maxr + 32)
    return g


def 几何公差示例(x=20.0, y=110.0):
    """图7-49 被测导出要素三例：(a) 轴线同轴度、(b) 中心平面对称度、(c) 球心位置度。

    依据：图7-45~7-49 p.205–207 [核]。框格高 2h、基准三角形与尺寸线对齐。
    """
    g = 图形()
    # (a) 阶梯轴：大圆柱轴线同轴度
    ax = x
    g.加(线(ax, y + 10, ax + 60, y + 10, "thick"), 线(ax, y - 10, ax + 60, y - 10, "thick"),
         线(ax + 60, y - 10, ax + 60, y + 10, "thick"),
         线(ax + 60, y + 7, ax + 90, y + 7, "thick"), 线(ax + 60, y - 7, ax + 90, y - 7, "thick"),
         线(ax, y - 10, ax, y + 10, "thick"), 线(ax + 90, y - 7, ax + 90, y + 7, "thick"),
         线(ax - 4, y, ax + 95, y, "center"),
         公差框(ax + 10, y + 18, ["◎", "φ0.02", "A"]),
         基准(ax + 70, y - 10, "A", up=True),
         文(ax + 40, y - 48, "(a) 被测圆柱轴线", 3.5))
    # (b) 带槽板：槽中心平面对称度
    bx = x + 110
    g.加(线(bx, y - 20, bx + 60, y - 20, "thick"), 线(bx, y + 20, bx + 60, y + 20, "thick"),
         线(bx, y - 20, bx, y + 20, "thick"), 线(bx + 60, y - 20, bx + 60, y + 20, "thick"),
         线(bx + 25, y + 20, bx + 25, y + 8, "thick"),
         线(bx + 35, y + 20, bx + 35, y + 8, "thick"),
         线(bx + 30, y + 20, bx + 30, y - 20, "center"),
         公差框(bx + 5, y + 26, ["≡", "0.05", "A"]),
         基准(bx + 30, y + 20, "A", up=False),
         文(bx + 30, y - 48, "(b) 被测中心平面", 3.5))
    # (c) 球心位置度
    cx = x + 220
    g.加(圆(cx, y, 18, "thick"),
         线(cx - 24, y, cx + 24, y, "center"),
         线(cx, y - 24, cx, y + 24, "center"),
         公差框(cx - 30, y + 26, ["◆", "Sφ0.05", "A", "B"]),
         基准(cx - 10, y - 18, "A", up=True),
         基准(cx + 10, y - 18, "B", up=True),
         文(cx, y - 50, "(c) 被测球心", 3.5))
    g.参数 = dict(框格数=3)
    g.范围(x - 30, y - 56, x + 280, y + 45)
    return g


__all__ = ["阶梯轴零件图", "几何公差示例"]
