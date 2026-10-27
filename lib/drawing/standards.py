# -*- coding: utf-8 -*-
"""standards.py —— 一页 A3 上的四张规范表：线型、比例、字体、幅面

依据：表1-3 p.11（续表 p.12）[核]；表1-2 p.10 [核]；§1-2 四.字体 p.10 [核]；表1-1 p.7 [核]
表值读 lib/drawing/tables/ch01.json；线宽读 lib/drawing/rules/line_types.json。
每个函数返回一个 图形（自带 bbox），拼图方可用 平移() 摆位——各函数默认 y 是为单页排版
给的独立位置，四张表同时摆在一页 A3 上时默认位置彼此重叠，需按需传 y 挪开。
"""
import sys
from pathlib import Path
MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path: sys.path.insert(0, str(MDKIT))
from lib.drawing._prim import 图形, 校验图元, 线, 圆, 弧, 矩形, 文, 剖面线, 箭头, 波浪线, 双折线, 尺寸H, 尺寸V, 拼

import json
import math

_DRAWING = Path(__file__).resolve().parent
_TABLES = _DRAWING / "tables" / "ch01.json"
_RULES = _DRAWING / "rules" / "line_types.json"


def _表(名):
    data = json.loads(_TABLES.read_text(encoding="utf-8"))
    if 名 not in data:
        raise NotImplementedError(f"{_TABLES} 无 {名}")
    return data[名]


def _格(表):
    """按 merges 展开 data（三元组纵向合并 / 四元组横向合并），被合并格取首格值。"""
    rows = [list(r) for r in 表["data"]]
    for m in 表.get("merges", []):
        if len(m) == 3:
            r0, r1, c0 = m
            c1 = c0
        else:
            r0, r1, c0, c1 = m
        v = rows[r0][c0]
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                if r < len(rows) and c < len(rows[r]):
                    rows[r][c] = v
    return rows


def _字宽(s, h):
    return sum(h if ord(c) > 0x2E80 else 0.55 * h for c in s)


class _范围:
    """累计文字/图线的实际包围盒，末尾交给 图形.范围()。"""

    def __init__(self, x, y):
        self.x0, self.y0, self.x1, self.y1 = x, y, x, y

    def 加(self, x0, y0, x1, y1):
        self.x0, self.y0 = min(self.x0, x0), min(self.y0, y0)
        self.x1, self.y1 = max(self.x1, x1), max(self.y1, y1)
        return self

    def 文本(self, x, y, s, h):
        return self.加(x, y - 0.25 * h, x + _字宽(s, h), y + 0.8 * h)


# ---------------------------------------------------------------- 表1-3 线型
def 线型表(x=15, y=190, 样长=55, 行距=13):
    """表1-3 p.11（续表 p.12）[核]：9 种图线，逐行「序号+名称+线宽 / 样线 / 主要用途」。

    样线：细实线、粗实线用 线()；细虚线 hidden、粗虚线 thick-hidden、细点画线 center、
    粗点画线 thick-center、细双点画线 double-dash；波浪线用 波浪线()、双折线用 双折线()
    （真波形/真折角，不用 STYLES 里的 wavy/phase 近似线型）。
    """
    t = _表("表1-3")
    grid = _格(t)
    meta = json.loads(_RULES.read_text(encoding="utf-8"))["线型"]
    宽 = {d["线型"]: d["线宽mm"] for d in meta}
    样 = {d["线型"]: d["样式"] for d in meta}

    r = _范围(x, y)
    g = 图形().加(文(x, y, "表1-3 机械制图的图线及应用（9 种）", 5, anchor="start"))
    r.文本(x, y, "表1-3 机械制图的图线及应用（9 种）", 5)
    g.加(线(x, y - 5, x + 230, y - 5, "thin"))
    r.加(x, y - 5, x + 230, y - 5)

    for i, row in enumerate(grid):
        yb = y - 10 - i * 行距
        名, 用 = row[2], row[3]
        g.加(文(x, yb, str(row[0]), 3.5, anchor="start"))
        r.文本(x, yb, str(row[0]), 3.5)
        标 = f"{名} {宽[名]:.2f}"
        g.加(文(x + 8, yb, 标, 3.5, anchor="start"))
        r.文本(x + 8, yb, 标, 3.5)
        x1, x2 = x + 46, x + 46 + 样长
        if 名 == "波浪线":
            g.加(波浪线(x1, yb, x2, yb))
        elif 名 == "双折线":
            # 逐周期调用：PHASE 一次多周期时只在开头起折、不回基线；每周期单独调才画得出反复折角
            n = max(1, int(round(样长 / 12.0)))
            段 = 样长 / n
            for i in range(n):
                g.加(双折线(x1 + i * 段, yb, x1 + (i + 1) * 段, yb))
        else:
            g.加(线(x1, yb, x2, yb, 样[名]))
        r.加(x1, yb - 2, x2, yb + 2)
        g.加(文(x2 + 5, yb, 用, 3.5, anchor="start"))
        r.文本(x2 + 5, yb, 用, 3.5)

    注 = "注① 一张图样上一般采用一种线型，即采用波浪线或双折线。"
    yn = y - 10 - 9 * 行距 - 2
    g.加(文(x, yn, 注, 3.5, anchor="start"))
    r.文本(x, yn, 注, 3.5)
    return g.范围(r.x0, r.y0, r.x1, r.y1)


# ---------------------------------------------------------------- 表1-2 比例
def 比例表(x=15, y=150):
    """表1-2 p.10 [核]：原值 / 放大 / 缩小三行，照原文（括号保留），×10ⁿ 写作 ×10^n。"""
    t = _表("表1-2")
    r = _范围(x, y)
    标题 = "表1-2 比例的类型（GB/T 14690）"
    g = 图形().加(文(x, y, 标题, 5, anchor="start"))
    r.文本(x, y, 标题, 5)
    g.加(线(x, y - 5, x + 165, y - 5, "thin"))
    r.加(x, y - 5, x + 165, y - 5)

    yb = y - 13
    for 类型, 值 in zip(t["rows"], [row[1] for row in t["data"]]):
        行 = str(值).replace("ⁿ", "^n").split("\n")
        g.加(文(x, yb, 类型, 3.5, anchor="start"))
        r.文本(x, yb, 类型, 3.5)
        for k, ln in enumerate(行):
            g.加(文(x + 30, yb - k * 6, ln, 3.5, anchor="start"))
            r.文本(x + 30, yb - k * 6, ln, 3.5)
        yb -= 8 + 6 * (len(行) - 1)

    注 = "注：n 为正整数；括号内为优先选用以外的值。"
    g.加(文(x, yb - 1, 注, 3.5, anchor="start"))
    r.文本(x, yb - 1, 注, 3.5)
    return g.范围(r.x0, r.y0, r.x1, r.y1)


# ---------------------------------------------------------------- 字体
def 字体表(x=15, y=110):
    """§1-2 四 p.10 [核]：高度系列 1.8…20；汉字长仿宋 h≥3.5、字宽 h/√2；
    A 型笔画宽 d=h/14、B 型 d=h/10；斜体字头右倾 75°；同一图样只用一种类型。"""
    高 = [1.8, 2.5, 3.5, 5, 7, 10, 14, 20]
    r = _范围(x, y)
    标题 = "字体（GB/T 14691—1993，高度 h 单位 mm）"
    g = 图形().加(文(x, y, 标题, 5, anchor="start"))
    r.文本(x, y, 标题, 5)
    g.加(线(x, y - 5, x + 175, y - 5, "thin"))
    r.加(x, y - 5, x + 175, y - 5)

    表头 = [(0, "h"), (18, "汉字字宽 h/√2"), (62, "A 型 d=h/14"), (110, "B 型 d=h/10")]
    yh = y - 13
    for dx, s in 表头:
        g.加(文(x + dx, yh, s, 3.5, anchor="start"))
        r.文本(x + dx, yh, s, 3.5)

    for i, h in enumerate(高):
        yb = yh - 7 - i * 6.5
        单元 = [(0, f"{h:g}"), (18, f"{h / math.sqrt(2):.2f}"),
                (62, f"{h / 14:.3f}"), (110, f"{h / 10:.2f}")]
        for dx, s in 单元:
            g.加(文(x + dx, yb, s, 3.5, anchor="start"))
            r.文本(x + dx, yb, s, 3.5)

    yb = yh - 7 - 8 * 6.5 - 3
    for s in ["汉字用长仿宋体、简化字，h≥3.5 mm；字宽 = h/√2。",
              "斜体字头向右倾斜，与水平基准线成 75°；同一图样只允许选用一种类型（A 型或 B 型）。"]:
        g.加(文(x, yb, s, 3.5, anchor="start"))
        r.文本(x, yb, s, 3.5)
        yb -= 7
    return g.范围(r.x0, r.y0, r.x1, r.y1)


# ---------------------------------------------------------------- 表1-1 幅面
def 幅面表(x=15, y=60):
    """表1-1 p.7 [核]：A0–A4 的 B×L、a、c、e，逐格读表（合并格已展开，B×L 千位空格照原表）。"""
    t = _表("表1-1")
    grid = _格(t)
    r = _范围(x, y)
    标题 = "表1-1 图纸幅面（GB/T 14689—2008，mm）"
    g = 图形().加(文(x, y, 标题, 5, anchor="start"))
    r.文本(x, y, 标题, 5)
    g.加(线(x, y - 5, x + 170, y - 5, "thin"))
    r.加(x, y - 5, x + 170, y - 5)

    yh = y - 13
    for dx, s in [(0, "幅面代号"), (26, "B×L"), (95, "a"), (120, "c"), (145, "e")]:
        g.加(文(x + dx, yh, s, 3.5, anchor="start"))
        r.文本(x + dx, yh, s, 3.5)

    for j, code in enumerate(t["cols"][1:], start=1):
        yb = yh - 7 - (j - 1) * 7
        单元 = [(0, code), (26, str(grid[0][j])), (95, str(grid[3][j])),
                (120, str(grid[2][j])), (145, str(grid[1][j]))]
        for dx, s in 单元:
            g.加(文(x + dx, yb, s, 3.5, anchor="start"))
            r.文本(x + dx, yb, s, 3.5)
    return g.范围(r.x0, r.y0, r.x1, r.y1)


__all__ = ["线型表", "比例表", "字体表", "幅面表"]
