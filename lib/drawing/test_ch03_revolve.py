# -*- coding: utf-8 -*-
"""ch03 回转体三视图、截交线与相贯线断言（图3-17/3-21/3-25、表3-1、图3-48）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import revolve  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_圆柱三视图():
    g = revolve.圆柱三视图(40, 50)
    assert 校验图元(g.elems)[0]
    assert g.参数["主"] == (40, 90, 40, 50)
    assert g.参数["左"] == (95, 90, 40, 50)
    assert len(圆(g)) == 1 and abs(圆(g)[0]["r"] - 20) < 1e-9
    r = 矩形(g)[0]
    assert len(矩形(g)) == 2 and (r["x"], r["y"], r["w"], r["h"]) == (40, 90, 40, 50)
    assert 有横线(g, 115, 37, 83, "center") and 有横线(g, 115, 92, 138, "center")


def test_圆锥三视图():
    g = revolve.圆锥三视图(40, 50)
    assert 校验图元(g.elems)[0]
    assert g.参数["顶"] == (60, 140)
    assert 有横线(g, 90, 40, 80, "thick")
    assert 有横线(g, 90, 95, 135, "thick")
    assert len(圆(g)) == 1 and abs(圆(g)[0]["r"] - 20) < 1e-9
    thick = [d for d in 线(g) if d["style"] == "thick"]
    assert any(abs(d["x1"] - 40) < 1e-6 and abs(d["y1"] - 90) < 1e-6
               and abs(d["x2"] - 60) < 1e-6 and abs(d["y2"] - 140) < 1e-6 for d in thick)


def test_球三视图():
    g = revolve.球三视图(40)
    assert 校验图元(g.elems)[0]
    assert len(圆(g)) == 3
    assert all(abs(d["r"] - 20) < 1e-9 for d in 圆(g))
    assert len([d for d in 线(g) if d["style"] == "center"]) == 6
    assert g.参数["主中"] == (60, 110)


def test_圆柱截交线():
    g = revolve.圆柱截交线(40, 50, 30)
    assert 校验图元(g.elems)[0]
    assert g.参数["主"] == (40, 90, 40, 30)
    assert 有横线(g, 120, 40, 80, "thick"), "截交线=主视顶边 y=90+30"
    assert 有横线(g, 120, 95, 135, "thick")
    try:
        revolve.圆柱截交线(40, 50, 30, 类型="倾斜")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("倾斜截切本批未实现，应抛 NotImplementedError")


def test_相贯线():
    g = revolve.相贯线(20, 15, 50, 60, 采样=12)
    assert 校验图元(g.elems)[0]
    assert abs(g.参数["xmin"] - math.sqrt(400 - 225)) < 1e-9
    thick = [d for d in 线(g) if d["style"] == "thick"]
    # 每条相贯线在 x=主x+R1±R1 处到达 z0±R2
    def 有点(x, y):
        return any((abs(d["x1"] - x) < 1e-6 and abs(d["y1"] - y) < 1e-6) or
                   (abs(d["x2"] - x) < 1e-6 and abs(d["y2"] - y) < 1e-6) for d in thick)
    assert 有点(40, 100), "左侧下支端点 (40, z0−R2)"
    assert 有点(80, 130), "右侧上支端点 (80, z0+R2)"
    try:
        revolve.相贯线(15, 20, 50, 60)
    except ValueError:
        pass
    else:
        raise AssertionError("R2≥R1 应抛 ValueError")
