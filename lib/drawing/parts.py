# -*- coding: utf-8 -*-
"""parts.py —— 零件工艺结构与技术要求模板（《机械制图》ch7 §7-2/§7-5）

依据：图7-6 p.177（倒角/倒圆）、图7-7 p.177（退刀槽）、图7-8 p.178（砂轮越程槽）、
      表7-1 p.193–196（中心孔/锥轴/滚花等尺寸注法）、图7-68/7-69 p.218/220（技术要求写法）。
只走 _prim 原语；线型只用 thick/thin/center。
书未给 mm 的（槽的 a/s/R、滚花间距等）一律参数化，docstring 标明“示意”。
"""
import math
import sys
from pathlib import Path

MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path:
    sys.path.insert(0, str(MDKIT))

from lib.drawing._prim import 图形, 校验图元, 线, 圆, 弧, 矩形, 文, 尺寸H, 尺寸V  # noqa: E402


def 倒角(d=20.0, c=2.0, 角度=45.0, 类型="外", x0=0.0, y=0.0, 长=None):
    """轴端/孔口倒角。依据：图7-6 p.177 [核]；表7-1 p.193 [核]（C 表示 45°）。

    外倒角：大径线画到倒角起点，45° 斜线，端面只画到倒角根部；内倒角镜像。
    角度 30/60 时径向进深 = c·tan(角度)，45° 时 = c。
    """
    if d <= 0 or c <= 0:
        raise ValueError("d、c 必须 > 0")
    if 类型 not in ("外", "内"):
        raise ValueError('类型 只能是 "外"/"内"')
    r = d / 2.0
    t = c if abs(角度 - 45.0) < 1e-9 else c * math.tan(math.radians(角度))
    L = 长 if 长 is not None else max(4 * c, 8.0)
    g = 图形()
    if 类型 == "外":
        g.加(线(x0 + t, y + r, x0 + L, y + r),
             线(x0 + t, y - r, x0 + L, y - r),
             线(x0, y + r - t, x0 + t, y + r),
             线(x0, y - r + t, x0 + t, y - r),
             线(x0, y - r + t, x0, y + r - t),
             线(x0 - 4, y, x0 + L + 4, y, "center"))
    else:
        r1 = r
        g.加(线(x0 + t, y + r1, x0 + L, y + r1),
             线(x0 + t, y - r1, x0 + L, y - r1),
             线(x0, y + r1 + t, x0 + t, y + r1),
             线(x0, y - r1 - t, x0 + t, y - r1),
             线(x0, y - r1 - t, x0, y + r1 + t),
             线(x0 - 4, y, x0 + L + 4, y, "center"))
    g.加(文(x0 + L / 2, y + r + 4, f"C{c:g}", 3.5))
    g.参数 = dict(d=d, c=c, t=t, 角度=角度, 类型=类型)
    g.范围(x0 - 4, y - r - 4, x0 + L + 4, y + r + 6)
    return g


def 圆角(半径=5.0, 长=40.0, 高=25.0, x=0.0, y=0.0):
    """轴肩/铸件转角圆角。依据：图7-6 p.177 [核]（R 标注）。

    内角圆角：水平边画到切点、竖边画到切点，中间 R 圆弧；圆心 (x+长−R, y+高−R)。
    """
    R = 半径
    if R <= 0 or 长 <= R or 高 <= R:
        raise ValueError("需 长>R、高>R、R>0")
    cx, cy = x + 长 - R, y + 高 - R
    g = 图形().加(线(x, y, cx, y, "thick"), 线(x + 长, y, x + 长, cy, "thick"))
    g.加(弧(cx, cy, R, 0, 90, "thick"))
    for px, py in ((cx, y), (x + 长, cy), (cx, cy)):
        g.加(线(px - 1.5, py, px + 1.5, py, "thin"), 线(px, py - 1.5, px, py + 1.5, "thin"))
    g.加(文(cx + R / 2, cy + R / 2, f"R{R:g}", 3.5))
    g.参数 = dict(R=R, 圆心=(cx, cy), 切点=((cx, y), (x + 长, cy)))
    g.范围(x - 2, y - 2, x + 长 + 2, y + 高 + 2)
    return g


def 退刀槽(轴径=30.0, 槽宽=4.0, 槽深=2.0, 类型="外", x0=0.0, y=0.0, 长=40.0):
    """螺纹退刀槽。依据：图7-7 p.177 [核]；表7-1 p.193 [核]（注 b×d）。

    外槽：大径线在槽处下降 槽深，两侧直壁；槽径 d−2×槽深。内槽镜像（孔壁小径）。
    """
    if not (0 < 槽深 < 轴径 / 2) or 槽宽 <= 0:
        raise ValueError("槽深须在 (0, 轴径/2)，槽宽 > 0")
    if 类型 not in ("外", "内"):
        raise ValueError('类型 只能是 "外"/"内"')
    r = 轴径 / 2.0
    r槽 = r - 槽深
    x1 = x0 + (长 - 槽宽) / 2.0
    x2 = x1 + 槽宽
    g = 图形()
    for s in (1, -1):
        g.加(线(x0, y + s * r, x1, y + s * r),
             线(x1, y + s * r, x1, y + s * r槽),
             线(x1, y + s * r槽, x2, y + s * r槽),
             线(x2, y + s * r槽, x2, y + s * r),
             线(x2, y + s * r, x0 + 长, y + s * r))
    g.加(线(x0, y - r, x0, y + r), 线(x0 + 长, y - r, x0 + 长, y + r),
         线(x0 - 4, y, x0 + 长 + 4, y, "center"))
    g.加(文(x0 + 长 / 2, y + r + 5, f"{槽宽:g}×{2 * r槽:g}", 3.5))
    g.参数 = dict(r=r, r槽=r槽, x1=x1, x2=x2, 槽径=2 * r槽)
    g.范围(x0 - 4, y - r - 4, x0 + 长 + 4, y + r + 7)
    return g


def 越程槽(轴径=30.0, 槽宽=3.0, 槽深=1.5, 类型="轴向", x0=0.0, y=0.0, 长=40.0):
    """砂轮越程槽。依据：图7-8 p.178 [核]。

    轴向槽：两侧 45° 斜壁 + 槽底；端面槽：端面上一圈矩形槽（用轴向剖面示意）。
    """
    if not (0 < 槽深 < 轴径 / 2) or 槽宽 <= 0:
        raise ValueError("槽深须在 (0, 轴径/2)，槽宽 > 0")
    if 类型 not in ("轴向", "端面"):
        raise ValueError('类型 只能是 "轴向"/"端面"')
    r = 轴径 / 2.0
    r槽 = r - 槽深
    x1 = x0 + (长 - 槽宽) / 2.0
    x2 = x1 + 槽宽
    g = 图形()
    for s in (1, -1):
        g.加(线(x0, y + s * r, x1, y + s * r),
             线(x1, y + s * r, x1 + 槽深, y + s * r槽),
             线(x1 + 槽深, y + s * r槽, x2 - 槽深, y + s * r槽),
             线(x2 - 槽深, y + s * r槽, x2, y + s * r),
             线(x2, y + s * r, x0 + 长, y + s * r))
    g.加(线(x0, y - r, x0, y + r), 线(x0 + 长, y - r, x0 + 长, y + r),
         线(x0 - 4, y, x0 + 长 + 4, y, "center"))
    g.加(文(x0 + 长 / 2, y + r + 5, f"{槽宽:g}×{槽深:g}", 3.5))
    g.参数 = dict(r=r, r槽=r槽, 槽宽=槽宽, 槽深=槽深)
    g.范围(x0 - 4, y - r - 4, x0 + 长 + 4, y + r + 7)
    return g


def 中心孔(直径=3.15, 类型="A", x=0.0, y=0.0):
    """中心孔（A 型不带护锥 / B 型带 120° 护锥）。依据：表7-1 p.193–196 [核]。

    A 型：圆柱孔 + 60° 锥面；B 型在孔口再加 120° 护锥。
    """
    if 直径 <= 0:
        raise ValueError("直径必须 > 0")
    if 类型 not in ("A", "B"):
        raise ValueError('类型 只能是 "A"/"B"')
    r = 直径 / 2.0
    深 = 3 * 直径
    锥 = r / math.tan(math.radians(30))       # 60° 锥面（半角 30°）
    g = 图形()
    g.加(线(x, y + r, x + 深, y + r), 线(x, y - r, x + 深, y - r))
    g.加(线(x + 深, y + r, x + 深 + 锥, y), 线(x + 深, y - r, x + 深 + 锥, y))
    g.加(线(x, y - 2 * r, x, y + 2 * r, "thick"))
    if 类型 == "B":
        g.加(线(x, y + 2 * r, x + 0.6 * 直径, y + r),
             线(x, y - 2 * r, x + 0.6 * 直径, y - r))
    g.加(线(x - 4, y, x + 深 + 锥 + 4, y, "center"))
    g.加(文(x + 深 / 2, y + r + 4, f"{类型}{直径:g}", 3.5))
    g.参数 = dict(r=r, 深=深, 锥=锥, 类型=类型)
    g.范围(x - 4, y - 2 * r - 4, x + 深 + 锥 + 4, y + 2 * r + 6)
    return g


def 锥轴端(大端=20.0, 小端=16.0, 长=20.0, x=0.0, y=0.0):
    """锥轴端（圆锥台）。依据：表7-1 p.195 [核]；锥度 = (D−d)/l。

    左大右小，四边 thick，轴线 center；标注锥度 1:n（n=l/(D−d)）。
    """
    if 大端 <= 小端 or 小端 <= 0 or 长 <= 0:
        raise ValueError("需 大端>小端>0、长>0")
    R, r = 大端 / 2.0, 小端 / 2.0
    锥 = 大端 - 小端
    n = 长 / 锥
    g = 图形().加(
        线(x, y - R, x + 长, y - r, "thick"),
        线(x, y + R, x + 长, y + r, "thick"),
        线(x, y - R, x, y + R, "thick"),
        线(x + 长, y - r, x + 长, y + r, "thick"),
        线(x - 4, y, x + 长 + 4, y, "center"))
    g.加(文(x + 长 / 2, y + R + 6, f"1:{n:g}", 3.5))
    g.参数 = dict(R=R, r=r, 锥度=锥 / 长)
    g.范围(x - 4, y - R - 4, x + 长 + 4, y + R + 9)
    return g


def 滚花(直径=30.0, 长度=20.0, 类型="网纹", x=0.0, y=0.0):
    """滚花（直纹/网纹）。依据：表7-1 p.193 [核]（m=0.8 的标注）。

    圆柱轮廓 thick，表面花纹用细实线：直纹画竖线，网纹画 ±45° 交叉线，间距 2。
    """
    if 直径 <= 0 or 长度 <= 0:
        raise ValueError("直径、长度必须 > 0")
    if 类型 not in ("直纹", "网纹"):
        raise ValueError('类型 只能是 "直纹"/"网纹"')
    r = 直径 / 2.0
    g = 图形().加(矩形(x, y - r, 长度, 直径, "thick"),
                 线(x - 4, y, x + 长度 + 4, y, "center"))
    步 = 2.0
    if 类型 == "直纹":
        k = 步
        while k < 长度 - 1e-9:
            g.加(线(x + k, y - r, x + k, y + r, "thin"))
            k += 步
    else:
        k = 步
        while k < 长度 - 1e-9:
            g.加(线(x + k, y - r, min(x + 长度, x + k + 2 * r), y + r, "thin"))
            g.加(线(x + k, y + r, min(x + 长度, x + k + 2 * r), y - r, "thin"))
            k += 步
    g.加(文(x + 长度 / 2, y + r + 5, f"{类型} m0.8", 3.5))
    g.参数 = dict(r=r, 长度=长度, 类型=类型)
    g.范围(x - 4, y - r - 4, x + 长度 + 4, y + r + 7)
    return g


def 技术要求模板(材料="45", 热处理="调质 220~250HB", 未注圆角="R2", 未注倒角="C1",
             未注粗糙度="Ra6.3", 其他=None, x=10.0, y=60.0):
    """零件图技术要求（文字模板）。依据：图7-68/7-69 p.218/220 [核]；p.216 [核]。

    书内技术要求通常 4~6 条：未注圆角/倒角、未注表面结构、热处理、材料（材料也可只写标题栏）。
    本函数把条目逐行写成 3.5 号字；`其他` 逐条追加。返回 图形（纯文字，无图线）。
    """
    条 = [f"1. 未注圆角 {未注圆角}。",
          f"2. 未注倒角 {未注倒角}。",
          f"3. 未注表面结构 {未注粗糙度}。",
          f"4. 热处理：{热处理}。",
          f"5. 材料：{材料}。"]
    for i, s in enumerate(其他 or [], 6):
        条.append(f"{i}. {s}")
    g = 图形()
    for i, s in enumerate(条):
        g.加(文(x, y - i * 6, s, 3.5, anchor="start"))
    g.参数 = dict(条=条, 材料=材料, 热处理=热处理)
    g.范围(x, y - 6 * len(条), x + 90, y + 3)
    return g


__all__ = ["倒角", "圆角", "退刀槽", "越程槽", "中心孔", "锥轴端", "滚花", "技术要求模板"]
