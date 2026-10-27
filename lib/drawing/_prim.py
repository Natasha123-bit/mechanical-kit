# -*- coding: utf-8 -*-
"""_prim.py —— 画法层与 gbdraw 之间的唯一接缝（图元契约 + 来源校验）

为什么要有这层：画法函数（螺纹、齿轮、轴承…）一旦手写 `<path d="...">`，就再也核不出来——
既不知道那是哪根线，也不知道线宽是不是 GB 的 0.5/0.25 两档。
gbdraw 的原语返回的是 **AST 元组** `("line", {...})`，由 `Sheet` 统一转 SVG。所以这里不拼字符串，
只做三件事：
  1. 把 gbdraw 原语按中文名重新导出（画法函数只依赖本模块，不直接 import gbdraw）；
  2. `图形` 类：收集元素 + 注记 + 包围盒，支持 `拼()`；
  3. `校验图元()`：拒收非 AST 元素、未知图元种类、STYLES 之外的线型名、手写 SVG 字符串。

用法：
    from lib.drawing._prim import 线, 圆, 文, 图形, 校验图元, 落图
    g = 图形().加(线(0, 10, 60, 10, "thick"), 线(0, 12, 60, 12, "thin"))
    print(校验图元(g.elems))        # → (True, 'OK 2 个图元，线型 {thick, thin}')
    ......
    落图(g, "/tmp/x.svg")
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path:
    sys.path.insert(0, str(MDKIT))

from draw import gbdraw  # noqa: E402
from draw.gbdraw import STYLES, TEXT_H, TEXT_S  # noqa: E402,F401

允许种类 = {"line", "circle", "rect", "arc", "text", "group", "path", "polygon", "poly", "polyline", "ellipse"}


# ---------------- gbdraw 原语的中文别名（画法函数只认这些） ----------------
线 = gbdraw.L
圆 = gbdraw.CIRCLE
矩形 = gbdraw.RECT
弧 = gbdraw.ARC
文 = gbdraw.T
剖面线 = gbdraw.HATCH
尺寸H = gbdraw.DIM_H
尺寸V = gbdraw.DIM_V
引出线 = gbdraw.LEAD
公差框 = gbdraw.TOL_FRAME
基准 = gbdraw.DATUM
粗糙度 = gbdraw.ROUGH
箭头 = gbdraw.ARROW
波浪线 = gbdraw.WAVY
双折线 = gbdraw.PHASE
分组 = lambda *items: ("group", dict(items=list(items)))  # noqa: E731


@dataclass
class 图形:
    """一个画法的产出：AST 元素 + 注记（技术要求条目）+ 包围盒(mm)。"""
    elems: list = field(default_factory=list)
    注记: list = field(default_factory=list)
    bbox: tuple | None = None

    def 加(self, *els) -> "图形":
        for e in els:
            if isinstance(e, 图形):
                self.elems.extend(e.elems)
                self.注记.extend(e.注记)
                self.bbox = _并(self.bbox, e.bbox)
            elif isinstance(e, tuple) and len(e) == 2 and isinstance(e[0], str):
                self.elems.append(e)
            elif isinstance(e, str):
                raise TypeError("图形.加() 不接受 SVG 字符串——必须用 线/圆/弧/矩形 等原语")
            else:
                raise TypeError(f"不能加 {type(e)}")
        return self

    def 注(self, *条目) -> "图形":
        self.注记.extend(条目)
        return self

    def 范围(self, x0, y0, x1, y1) -> "图形":
        self.bbox = (x0, y0, x1, y1) if self.bbox is None else _并(self.bbox, (x0, y0, x1, y1))
        return self

    def __len__(self):
        return _计数(self.elems)


def _并(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def 拼(*图形s) -> 图形:
    out = 图形()
    for g in gs if (gs := 图形s) else []:
        out.加(g)
    return out


def _移path(d: str, dx: float, dy: float) -> str:
    """搬路径：按命令元数平移每个坐标；A 只搬终点，相对命令（小写）不受平移影响。

    解析用 gbdraw.iter_path_commands（与输出层共用一份，避免两处各写一套再分叉）。
    """
    parts = []
    for cmd, args in gbdraw.iter_path_commands(d):
        up, rel = cmd.upper(), cmd.islower()
        if rel or up == "Z":                       # 相对量在平移下不变
            parts.append(cmd if not args else cmd + " " + " ".join(args))
            continue
        vals = []
        for i, v in enumerate(args):
            if up == "H":
                vals.append(_n3(float(v) + dx))
            elif up == "V":
                vals.append(_n3(float(v) + dy))
            elif up == "A":
                vals.append(_n3(float(v) + dx) if i == 5 else
                            _n3(float(v) + dy) if i == 6 else v)
            else:
                vals.append(_n3(float(v) + dx) if i % 2 == 0 else _n3(float(v) + dy))
        parts.append(cmd + " " + " ".join(vals))
    return " ".join(parts)


def _n3(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def 平移(g: 图形, dx: float = 0.0, dy: float = 0.0) -> 图形:
    """整图平移（mm），供出图时把轴线在图幅里摆位；不动线型、不改图元种类。"""
    def sh(e):
        k, d = e
        if k == "group":
            return ("group", dict(items=[sh(x) for x in d["items"]]))
        if k == "line":
            return ("line", dict(d, x1=d["x1"] + dx, y1=d["y1"] + dy,
                                 x2=d["x2"] + dx, y2=d["y2"] + dy))
        if k == "circle":
            return ("circle", dict(d, cx=d["cx"] + dx, cy=d["cy"] + dy))
        if k == "rect":
            return ("rect", dict(d, x=d["x"] + dx, y=d["y"] + dy))
        if k == "text":
            return ("text", dict(d, x=d["x"] + dx, y=d["y"] + dy))
        if k == "poly":
            return ("poly", dict(d, pts=[(x + dx, y + dy) for x, y in d["pts"]]))
        if k == "path":
            return ("path", dict(d, d=_移path(d["d"], dx, dy)))
        return e

    out = 图形(elems=[sh(e) for e in g.elems], 注记=list(g.注记))
    if g.bbox is not None:
        x0, y0, x1, y1 = g.bbox
        out.bbox = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
    for k in ("参数",):
        if hasattr(g, k):
            setattr(out, k, getattr(g, k))
    return out


def _计数(nodes):
    n = 0
    for kind, d in nodes:
        if kind == "group":
            n += _计数(d["items"])
        else:
            n += 1
    return n


def 校验图元(nodes, strict: bool = True):
    """校验元素来源与线型。返回 (ok, msg)；strict 时不合格抛 ValueError。"""
    bad, kinds, styles = [], set(), set()

    def walk(ns):
        for kind, d in ns:
            if kind not in 允许种类:
                bad.append(f"未知图元种类 {kind!r}（手写 SVG？）")
                continue
            kinds.add(kind)
            if kind == "group":
                walk(d["items"])
                continue
            if kind == "text":
                continue          # 文字用 style="text"，不是线型，不查 STYLES
            st = d.get("style")
            if st is not None:
                styles.add(st)
                if st not in STYLES:
                    bad.append(f"线型 {st!r} 不在 STYLES（{sorted(STYLES)}）")

    try:
        walk(nodes)
    except (TypeError, ValueError, AttributeError) as e:
        bad.append(f"元素不是合法 AST 元组：{e}")

    if not kinds:
        bad.append("没有任何图形元素")
    msg = f"{'OK' if not bad else 'FAIL'} {_计数(nodes)} 个图元，线型 {sorted(styles) or '无'}"
    if bad:
        msg += "；" + "；".join(bad[:6])
        if strict:
            raise ValueError(msg)
    return (not bad, msg)


def 落图(g: 图形, path, w=297.0, h=210.0) -> str:
    """把图形写成一页 SVG（A3 横放默认），供 gear_pipeline/build.sh 那条 Chrome→PDF→PNG 链使用。"""
    校验图元(g.elems)
    sh = gbdraw.Sheet(w, h)
    sh.add(*g.elems)
    if g.注记:
        sh.add(gbdraw.T(12, h - 10, "技术要求：", h=TEXT_H, anchor="start"))
        for i, t in enumerate(g.注记, 1):
            sh.add(gbdraw.T(12, h - 10 - i * 5, f"{i}. {t}", h=TEXT_S, anchor="start"))
    p = Path(path)
    p.write_text(sh.svg())
    return str(p)


if __name__ == "__main__":
    g = 图形().加(线(10, 10, 60, 10, "thick"), 线(10, 12, 60, 12, "thin"), 圆(35, 30, 5), 文(35, 40, "M12"))
    ok, msg = 校验图元(g.elems)
    print(msg, "| 围:", g.范围(10, 10, 60, 40).bbox, "| 元素:", len(g))
    # 反例：手写 SVG 必须被拒
    try:
        校验图元([("path", dict(d="M0 0 L10 10", style="hairline"))])
    except ValueError as e:
        print("反例被拒：", str(e)[:80])
