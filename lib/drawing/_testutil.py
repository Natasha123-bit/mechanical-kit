# -*- coding: utf-8 -*-
"""_testutil.py —— 章库测试的图元展开小工具（只读，不改图形）。"""
from __future__ import annotations

import math


def 展开(nodes):
    """把 group 递归摊平成 (kind, dict) 序列。"""
    for k, d in nodes:
        if k == "group":
            yield from 展开(d["items"])
        else:
            yield k, d


def 线(g):
    return [d for k, d in 展开(g.elems) if k == "line"]


def 圆(g):
    return [d for k, d in 展开(g.elems) if k == "circle"]


def 矩形(g):
    return [d for k, d in 展开(g.elems) if k == "rect"]


def 竖线(g, x, tol=1e-6, style=None):
    return [d for d in 线(g)
            if abs(d["x1"] - x) < tol and abs(d["x2"] - x) < tol
            and (style is None or d["style"] == style)]


def 横线(g, y, tol=1e-6, style=None):
    return [d for d in 线(g)
            if abs(d["y1"] - y) < tol and abs(d["y2"] - y) < tol
            and (style is None or d["style"] == style)]


def 有横线(g, y, x1=None, x2=None, style=None, tol=1e-6):
    for d in 横线(g, y, tol, style):
        if x1 is not None and abs(d["x1"] - x1) > 1e-3:
            continue
        if x2 is not None and abs(d["x2"] - x2) > 1e-3:
            continue
        return d
    return None


def 有竖线(g, x, y1=None, y2=None, style=None, tol=1e-6):
    for d in 竖线(g, x, tol, style):
        if y1 is not None and abs(min(d["y1"], d["y2"]) - y1) > 1e-3:
            continue
        if y2 is not None and abs(max(d["y1"], d["y2"]) - y2) > 1e-3:
            continue
        return d
    return None


def 切线长(d):
    return math.hypot(d["x2"] - d["x1"], d["y2"] - d["y1"])


def 到圆心的距(p, c):
    return math.hypot(p[0] - c[0], p[1] - c[1])
