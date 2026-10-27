#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gbdraw —— GB/T 4457 图元函数（1 用户单位 = 1 mm，viewBox 直接对应图纸）。

为什么不用 svgwrite：图元层本来就只是 line/circle/rect/text/path 加几个 mm 坐标的小函数，
库只省字符串拼接，省不了文字基线、旋转公差叠排、窄处让位、中文字宽这些真正费时的地方，
还多一层坐标/单位语义。这里 1 单位 = 1 mm，`Sheet(297,210)` 就是 A4 横放。

坐标：默认 y 向上（图纸习惯），输出时翻转；`Sheet(..., y_up=False)` 可切成 SVG 习惯。

用法：
    s = Sheet(297, 210)                       # A4 横放
    s.add(L(20, 20, 120, 20))                 # 粗实线（可见轮廓）
    s.add(L(20, 20, 120, 20, 'thin'))         # 细实线
    s.add(L(20, 20, 120, 20, 'center'))       # 细点画线（中心线）
    s.add(CIRCLE(60, 60, 10))
    s.add(RECT(30, 30, 40, 20, fill='none'))
    s.add(T(60, 65, '腹板式', 3.5))
    s.add(DIM_H(20, 120, 80, 'φ25'))          # y, x1, x2, 文本
    s.add(DIM_V(20, 30, 120, '90'))
    s.add(LEAD(60, 60, 90, 90, 'Ra 3.2'))
    s.add(ROUGH(100, 80, 'Ra3.2'))
    s.add(TOL_FRAME(150, 100, ['⌖', '0.02', 'A']))
    s.add(DATUM(80, 40, 'A'))
    s.add(HATCH([(30,30),(70,30),(70,50),(30,50)], spacing=2.0))   # 剖面线：逐条线段，不用 pattern
    s.write('out.svg')

选型/尺寸/公差/粗糙度取值不在这里管 —— 见 references/gb-gear-drawing.md。
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field

# ---- GB/T 4457.4 线型（线宽按 0.5/0.25 两档，图面文字不随比例缩放）----
STYLES = {
    # name: (宽度 mm, dasharray 或 None)
    "thick":  (0.50, None),           # 粗实线：可见轮廓
    "thin":   (0.25, None),           # 细实线：尺寸线、剖面线、过渡线
    "center": (0.25, "8 2 1 2"),      # 细点画线：轴线、对称线（书 p.12 说 15~30/约3 只是建议值）
    "hidden": (0.25, "4 1.5"),        # 细虚线：不可见轮廓
    "wavy":   (0.25, "6 2"),          # 兼容旧图：假波浪（真波浪用 WAVY）
    "phase":  (0.25, None),           # 兼容旧图：假双折线（真折线用 PHASE）
    "thick-hidden": (0.50, "4 1.5"),          # 粗虚线：允许表面处理的表示线
    "thick-center": (0.50, "18 3 1 3"),       # 粗点画线：限定范围表示线
    "double-dash":  (0.25, "18 5 1 5 1 5"),   # 细双点画线：相邻辅助零件轮廓、极限位置、轨迹
}
TEXT_H = 3.5    # 标准字号
TEXT_S = 2.5    # 小字（剖面、注释）

# 中文字宽 ≈ 1.0 em，数字/字母 ≈ 0.55 em
def text_w(s: str, h: float = TEXT_H) -> float:
    w = 0.0
    for ch in s:
        w += h * (1.0 if ord(ch) > 0x2E80 else 0.55)
    return w


def _n(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


# ============================================================ 图元
def L(x1, y1, x2, y2, style="thick"):
    return ("line", dict(x1=x1, y1=y1, x2=x2, y2=y2, style=style))


def CIRCLE(cx, cy, r, style="thick", fill="none"):
    return ("circle", dict(cx=cx, cy=cy, r=r, style=style, fill=fill))


def RECT(x, y, w, h, style="thick", fill="none"):
    return ("rect", dict(x=x, y=y, w=w, h=h, style=style, fill=fill))


def ARC(cx, cy, r, a1, a2, style="thick"):
    """a1→a2 逆时针，度。"""
    x1 = cx + r * math.cos(math.radians(a1)); y1 = cy + r * math.sin(math.radians(a1))
    x2 = cx + r * math.cos(math.radians(a2)); y2 = cy + r * math.sin(math.radians(a2))
    large = 1 if abs(a2 - a1) > 180 else 0
    sweep = 0 if a2 > a1 else 1      # y 向上 → SVG sweep 反向
    return ("path", dict(d=f"M {_n(x1)} {_n(y1)} A {_n(r)} {_n(r)} 0 {large} {sweep} {_n(x2)} {_n(y2)}",
                         style=style, fill="none"))


def T(x, y, s, h=TEXT_H, anchor="middle", rotate=None, style="text"):
    return ("text", dict(x=x, y=y, s=s, h=h, anchor=anchor, rotate=rotate, style=style))


def ARROW(x1, y1, x2, y2, size=3.0):
    """实心箭头，从 (x1,y1) 指向 (x2,y2)，箭头在 (x2,y2)。"""
    a = math.atan2(y2 - y1, x2 - x1)
    w = size * 0.18
    p1 = (x2, y2)
    p2 = (x2 - size * math.cos(a) + w * math.sin(a), y2 - size * math.sin(a) - w * math.cos(a))
    p3 = (x2 - size * math.cos(a) - w * math.sin(a), y2 - size * math.sin(a) + w * math.cos(a))
    return ("poly", dict(pts=[p1, p2, p3], style="thin", fill="solid"))


def _dash(style):
    return STYLES.get(style, STYLES["thin"])[1]


def DIM_H(y, x1, x2, text, ext_from=(0, 0), h=TEXT_H, above=1.0, tick=None):
    """水平尺寸：尺寸界线（从 ext_from 起）+ 尺寸线 + 两端箭头 + 数字在上方。
    ext_from=(dx1,dy1)：尺寸界线起点相对 (x1,y) 的偏移，默认从尺寸线上起（调用方给对象表面坐标）。"""
    out = []
    dx1, dy1 = ext_from if ext_from != (0, 0) else (0, 0)
    if ext_from != (0, 0):
        out.append(L(x1 + dx1, y + dy1, x1, y + math.copysign(2, y + dy1 - y), "thin"))
        out.append(L(x2 + dx1, y + dy1, x2, y + math.copysign(2, y + dy1 - y), "thin"))
    out.append(L(x1, y, x2, y, "thin"))
    out.append(ARROW(x1 + 3, y, x1, y)); out.append(ARROW(x2 - 3, y, x2, y))
    out.append(T((x1 + x2) / 2, y + above, text, h))
    return ("group", dict(items=out))


def DIM_V(x, y1, y2, text, h=TEXT_H, right=1.0):
    out = [L(x, y1, x, y2, "thin"),
           ARROW(x, y1 + 3, x, y1), ARROW(x, y2 - 3, x, y2),
           T(x + right, (y1 + y2) / 2, text, h, anchor="start", rotate=-90)]
    return ("group", dict(items=out))


def LEAD(x1, y1, x2, y2, text, h=TEXT_H, anchor="start", shelf=4.0):
    """引线：从被标注处 (x1,y1) 到 (x2,y2)，带水平托线写字。"""
    d = 1 if x2 >= x1 else -1
    out = [ARROW(x2, y2, x1, y1), L(x2, y2, x2 + d * shelf, y2, "thin"),
           T(x2 + d * (shelf + 0.8), y2, text, h, anchor=anchor if d > 0 else "end")]
    return ("group", dict(items=out))


def ROUGH(x, y, ra="Ra3.2", h=TEXT_S, flip=False):
    """表面粗糙度：60° 尖角 + 长边 + 数值（GB/T 131）。flip=True 用于下表面。"""
    s = -1 if flip else 1
    p = [(x, y), (x + 1.4 * s, y + 2.4), (x + 2.8 * s, y)]
    out = [("poly", dict(pts=p, style="thin", fill="none")),
           L(x + 1.4 * s, y + 2.4, x + 1.4 * s + 3.2 * s, y + 4.6, "thin"),
           T(x + 1.4 * s + 3.6 * s, y + 4.2, ra, h, anchor="start" if s > 0 else "end")]
    return ("group", dict(items=out))


def TOL_FRAME(x, y, cells, h=TEXT_H, pad=1.6):
    """公差框格：cells 依次为符号/公差值/基准，横向排列，左上角 (x,y)。"""
    widths = [max(text_w(c, h) + 2 * pad, h + 2) for c in cells]
    out, cx = [], x
    H = h + 2.4
    for c, w in zip(cells, widths):
        out.append(("rect", dict(x=cx, y=y, w=w, h=H, style="thin", fill="none")))
        out.append(T(cx + w / 2, y + H / 2, c, h))
        cx += w
    return ("group", dict(items=out))


def DATUM(x, y, label="A", h=TEXT_H, up=True):
    """基准符号：涂黑三角 + 方框字母。"""
    s = 1 if up else -1
    tri = [(x, y), (x - 1.6, y - 2.8 * s), (x + 1.6, y - 2.8 * s)]
    box = ("rect", dict(x=x - 2.2, y=y - 7.4 * s if up else y + 4.6 * abs(s),
                        w=4.4, h=4.4, style="thin", fill="none"))
    out = [("poly", dict(pts=tri, style="thin", fill="solid")),
           L(x, y - 2.8 * s, x, y - 3.0 * s, "thin"), box,
           T(x, y - 7.4 * s + 2.2 if up else y + 6.8, label, h)]
    return ("group", dict(items=out))


def HATCH(poly, spacing=2.0, angle=45.0, style="thin"):
    """剖面线：按 angle 方向的平行线族逐条生成线段（**不用 SVG pattern** ——
    Chrome 打印 PDF 时 pattern 不落地，剖切区整块发白）。poly 为顶点列表（闭合，自动收尾）。"""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    # 旋转到 (u,v)：线族 u = c
    uvs = [(x * ca + y * sa, -x * sa + y * ca) for x, y in poly]
    us = [u for u, _ in uvs]
    umin, umax = min(us), max(us)
    segs = []
    c = umin + spacing * 0.5
    while c < umax:
        pts = []
        n = len(uvs)
        for i in range(n):
            (u1, v1), (u2, v2) = uvs[i], uvs[(i + 1) % n]
            if (u1 - c) * (u2 - c) < 0:
                t = (c - u1) / (u2 - u1)
                pts.append(v1 + t * (v2 - v1))
        pts.sort()
        for j in range(0, len(pts) - 1, 2):
            v1, v2 = pts[j], pts[j + 1]
            # 回到原坐标
            p1 = (c * ca - v1 * sa, c * sa + v1 * ca)
            p2 = (c * ca - v2 * sa, c * sa + v2 * ca)
            segs.append(L(p1[0], p1[1], p2[0], p2[1], style))
        c += spacing
    return ("group", dict(items=segs))


def PATH(d, style="thin", fill="none"):
    return ("path", dict(d=d, style=style, fill=fill))


def PHASE(x1, y1, x2, y2, amp=1.5, period=12.0, style="thin"):
    """双折线：沿 (x1,y1)→(x2,y2) 的**真折线**（每周期两个折角），用于断裂边界。

    旧 `phase` 线型只是细实线，画不出折角；本原语按周期生成
    「基线 → 抬到 +amp → 平移 → 落回基线」的梯形折，符合表1-3 的双折线符号。
    """
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return L(x1, y1, x2, y2, style)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    pts = [(x1, y1)]
    t = 0.0
    while L - t > period * 0.5:
        a, b = t + 0.25 * period, t + 0.75 * period
        pts.append((x1 + ux * a + nx * amp, y1 + uy * a + ny * amp))
        pts.append((x1 + ux * b + nx * amp, y1 + uy * b + ny * amp))
        t += period
        pts.append((x1 + ux * min(t, L), y1 + uy * min(t, L)))   # 回落基线，下一周期重新起折
    pts.append((x2, y2))
    d = "M " + " L ".join(f"{_n(x)} {_n(y)}" for x, y in pts)
    return ("path", dict(d=d, style=style, fill="none"))


def WAVY(x1, y1, x2, y2, amp=1.2, wavelength=6.0, style="thin"):
    """波浪线：沿两点方向的**真波浪**（正弦，端点收在轴线上），用于断裂/局部剖边界。"""
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return L(x1, y1, x2, y2, style)
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    n = max(16, int(L / (wavelength / 10.0)))
    pts = []
    for i in range(n + 1):
        t = L * i / n
        env = math.sin(math.pi * i / n)          # 端点收线
        off = amp * env * math.sin(2 * math.pi * t / wavelength)
        pts.append((x1 + ux * t + nx * off, y1 + uy * t + ny * off))
    d = "M " + " L ".join(f"{_n(x)} {_n(y)}" for x, y in pts)
    return ("path", dict(d=d, style=style, fill="none"))


# ============================================================ Sheet
_PATH_CMD = re.compile(r"([MLA])((?:[^MLA])*)")


def _flip_path(d: str, h: float) -> str:
    """把图纸坐标路径翻成 SVG 坐标：M/L 的每个坐标对、A 的终点都要翻，A 的半径不翻。"""
    def one(m):
        cmd, body = m.group(1), m.group(2)
        nums = re.findall(r"-?\d+(?:\.\d+)?", body)
        if cmd in ("M", "L"):
            for i in range(1, len(nums), 2):
                nums[i] = _n(h - float(nums[i]))
        elif cmd == "A" and len(nums) >= 7:
            nums[-1] = _n(h - float(nums[-1]))
        return cmd + " " + " ".join(nums)

    return _PATH_CMD.sub(one, d)


@dataclass
class Sheet:
    w: float
    h: float
    y_up: bool = True
    items: list = field(default_factory=list)
    title: str = ""

    def add(self, *els):
        for e in els:
            self.items.append(e)
        return self

    def _y(self, y):
        return self.h - y if self.y_up else y

    def _emit(self, e) -> str:
        kind, a = e
        if kind == "line":
            return (f'<line x1="{_n(a["x1"])}" y1="{_n(self._y(a["y1"]))}" '
                    f'x2="{_n(a["x2"])}" y2="{_n(self._y(a["y2"]))}" class="{a["style"]}"/>')
        if kind == "circle":
            return f'<circle cx="{_n(a["cx"])}" cy="{_n(self._y(a["cy"]))}" r="{_n(a["r"])}" class="{a["style"]}" fill="{a["fill"]}"/>'
        if kind == "rect":
            y = a["y"] + a["h"] if self.y_up else a["y"]
            return f'<rect x="{_n(a["x"])}" y="{_n(self._y(y))}" width="{_n(a["w"])}" height="{_n(a["h"])}" class="{a["style"]}" fill="{a["fill"]}"/>'
        if kind == "path":
            d = _flip_path(a["d"], self.h) if self.y_up else a["d"]
            return f'<path d="{d}" class="{a["style"]}" fill="{a["fill"]}"/>'
        if kind == "text":
            rot = f' transform="rotate({a["rotate"]} {_n(a["x"])} {_n(self._y(a["y"]))})"' if a["rotate"] else ""
            return (f'<text x="{_n(a["x"])}" y="{_n(self._y(a["y"]))}" font-size="{_n(a["h"])}" '
                    f'text-anchor="{a["anchor"]}" class="txt"{rot}>{_esc(a["s"])}</text>')
        if kind == "poly":
            pts = " ".join(f"{_n(x)},{_n(self._y(y))}" for x, y in a["pts"])
            fill = "#000" if a["fill"] == "solid" else "none"
            cls = f'{a["style"]} solid' if a["fill"] == "solid" else a["style"]
            return f'<polygon points="{pts}" class="{cls}" fill="{fill}"/>'
        if kind == "group":
            return "\n".join(self._emit(x) for x in a["items"])
        raise ValueError(kind)

    def svg(self) -> str:
        css = []
        for name, (w, dash) in STYLES.items():
            d = f"stroke-dasharray:{dash};" if dash else ""
            css.append(f".{name}{{stroke:#000;stroke-width:{w};fill:none;stroke-linecap:round;{d}}}")
        css.append(".txt{fill:#000;font-family:'PingFang SC','Heiti SC',sans-serif;}"
                   "polygon.solid{fill:#000}")
        body = "\n".join(self._emit(e) for e in self.items)
        return (f'<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(self.w)}mm" height="{_n(self.h)}mm" '
                f'viewBox="0 0 {_n(self.w)} {_n(self.h)}">\n'
                f'<title>{_esc(self.title)}</title>\n<style>{"".join(css)}</style>\n{body}\n</svg>\n')

    def write(self, path) -> str:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.svg())
        return str(path)

    def count(self) -> int:
        def walk(e):
            k, a = e
            if k == "group":
                return sum(walk(x) for x in a["items"])
            return 1
        return sum(walk(e) for e in self.items)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ============================================================ 自检
def selftest() -> int:
    import os
    import tempfile
    s = Sheet(297, 210, title="gbdraw 自检 A4 横放")
    # 图框 + 标题栏占位（GB: 留边 25/5/5/5）
    s.add(RECT(5, 5, 287, 200, "thin"), RECT(25, 5, 267, 200, "thick"))
    s.add(RECT(172, 5, 120, 32, "thick"), L(172, 21, 292, 21, "thin"))
    s.add(T(232, 25, "标题栏 1:2", 4), T(232, 12, "中南林业科技大学", 3.5))
    # 视图：圆 + 中心线 + 剖面
    s.add(CIRCLE(70, 110, 30), CIRCLE(70, 110, 12))
    s.add(L(30, 110, 110, 110, "center"), L(70, 70, 70, 150, "center"))
    s.add(HATCH([(58, 98), (82, 98), (82, 122), (58, 122)], spacing=2.0))
    s.add(L(40, 60, 100, 60, "hidden"))
    # 尺寸与标注
    s.add(DIM_H(45, 40, 100, "60"))
    s.add(DIM_V(120, 80, 140, "60"))
    s.add(LEAD(58, 98, 25, 170, "Ra 3.2"))
    s.add(ROUGH(105, 140, "Ra1.6"))
    s.add(TOL_FRAME(150, 160, ["⌖", "φ0.02", "A"]))
    s.add(DATUM(70, 80, "A", up=False))
    s.add(ARC(200, 110, 25, 0, 120), T(200, 130, "弧 120°", 3))
    s.add(ARROW(150, 60, 180, 60), T(165, 63, "→", 3))
    s.add(RECT(140, 40, 30, 15, "thin", fill="none"))
    s.add(T(155, 47.5, "腹板式 d_a≤160", TEXT_S))

    out = os.path.join(tempfile.gettempdir(), "gbdraw-selftest.svg")
    s.write(out)
    size = os.path.getsize(out)
    n = s.count()
    txt = s.svg()
    checks = [
        ("元素数 > 30", n > 30),
        ("文件非空", size > 2000),
        ("无 <pattern>（打印会丢）", "<pattern" not in txt),
        ("剖面线已生成", txt.count("class=\"thin\"") > 5),
        ("viewBox = 297x210", 'viewBox="0 0 297 210"' in txt),
    ]
    for name, ok in checks:
        print(f"  [{'✓' if ok else '✗'}] {name}")
    print(f"  元素 {n} 个、{size} 字节 → {out}")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    print(__doc__)
