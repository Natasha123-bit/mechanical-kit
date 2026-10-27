# -*- coding: utf-8 -*-
"""ch05 轴测图断言（图5-2/5-4/5-7/5-12）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import axonometric  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 线, 圆, 展开  # noqa: E402


def test_轴测变换():
    X, Y = axonometric.轴测变换(1, 0, 0, "正等测")
    assert abs(X - math.cos(math.radians(30))) < 1e-9
    assert abs(Y - 0.5) < 1e-9
    X, Y = axonometric.轴测变换(0, 1, 0, "正等测")
    assert abs(X + math.cos(math.radians(30))) < 1e-9
    assert abs(Y - 0.5) < 1e-9
    assert axonometric.轴测变换(0, 0, 1, "正等测") == (0, 1)
    X, Y = axonometric.轴测变换(0, 1, 0, "斜二测")
    assert abs(X - 0.5 * math.cos(math.radians(45))) < 1e-9
    assert abs(Y - 0.5 * math.sin(math.radians(45))) < 1e-9
    assert axonometric.轴测变换(1, 0, 0, "斜二测") == (1, 0)


def test_轴测轴():
    g = axonometric.轴测轴("正等测", 40)
    assert 校验图元(g.elems)[0]
    assert g.参数["轴间角"] == 120
    assert len(线(g)) == 3
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert set(texts) >= {"X", "Y", "Z"}
    dx, dy = g.参数["方向"]["X"]
    assert abs(math.degrees(math.atan2(dy, dx)) - 30) < 1e-6


def test_正等轴测():
    g = axonometric.正等轴测(60, 40, 30)
    assert 校验图元(g.elems)[0]
    assert len(线(g)) == 13
    assert len([d for d in 线(g) if d["style"] == "thick"]) == 10
    assert len([d for d in 线(g) if d["style"] == "hidden"]) == 3
    p = g.参数["顶点"]
    assert abs(p[1][0] - (60 * math.cos(math.radians(30)))) < 1e-9
    assert abs(p[1][1] - 30) < 1e-9
    assert abs(p[5][1] - 60) < 1e-9


def test_斜二测():
    g = axonometric.斜二测(60, 40, 30)
    assert 校验图元(g.elems)[0]
    p = g.参数["顶点"]
    assert p[1] == (60, 0), "前面 X 向反映实形"
    assert p[4] == (0, 30), "前面 Z 向反映实形"
    assert abs(p[2][0] - 60 - 0.5 * 40 * math.cos(math.radians(45))) < 1e-9
    assert abs(p[2][1] - 0.5 * 40 * math.sin(math.radians(45))) < 1e-9


def test_圆柱正等轴测():
    g = axonometric.圆柱正等轴测(30, 40)
    assert 校验图元(g.elems)[0]
    assert abs(g.参数["长轴"] - 1.22 * 30) < 1e-9
    assert abs(g.参数["短轴"] - 0.70 * 30) < 1e-9
    assert g.参数["顶"][1] - g.参数["底"][1] == 40
    assert len([d for d in 线(g) if d["style"] == "thick"]) == 2 + 72, "两条转向线 + 顶椭圆 72 段（中心线为 center）"
    try:
        axonometric.轴测变换(0, 0, 0, "正三测")
    except ValueError:
        pass
    else:
        raise AssertionError("未知类型应抛 ValueError")
