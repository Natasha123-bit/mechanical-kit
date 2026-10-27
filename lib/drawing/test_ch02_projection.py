# -*- coding: utf-8 -*-
"""ch02 投影基础与平面体三视图断言（图2-7/2-8/2-12/2-43/2-45）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import projection  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_三视图_三等关系():
    g = projection.三视图(60, 40, 30)
    assert 校验图元(g.elems)[0]
    assert len(矩形(g)) == 3
    主, 俯, 左 = g.视图["主视图"], g.视图["俯视图"], g.视图["左视图"]
    assert 主 == (40, 110, 60, 40)
    assert 俯[0] == 主[0] and 俯[2] == 主[2], "长对正"
    assert 左[1] == 主[1] and 左[3] == 主[3], "高平齐"
    assert 俯[3] == 30 and 左[2] == 30, "宽相等"
    assert 有竖线(g, 40, 95, 110, "thin")
    assert 有横线(g, 110, 100, 115, "thin")


def test_点的三面投影():
    g = projection.点的三面投影(15, 20, 25, ox=60, oy=110, 间距=45)
    assert 校验图元(g.elems)[0]
    assert g.点["a"] == (75, 135)
    assert g.点["a′"] == (75, 45)
    assert g.点["a″"] == (125, 135)
    assert len(圆(g)) == 3
    assert 有竖线(g, 75, 45, 135, "thin")
    assert any(abs(d["x1"] - 75) < 1e-6 and abs(d["y1"] - 45) < 1e-6
               and abs(d["x2"] - 125) < 1e-6 and abs(d["y2"] - 135) < 1e-6
               for d in 线(g)), "a′→a″ 投影连线"


def test_棱柱三视图():
    g = projection.棱柱三视图(6, 25, 45)
    assert 校验图元(g.elems)[0]
    assert g.参数["主"] == (40, 90, 50, 45)
    assert abs(g.参数["深"] - math.sqrt(3) * 25) < 1e-6
    assert 有竖线(g, 52.5, 90, 135, "thick"), "六棱柱内部可见竖棱 x=+R/2"
    assert 有竖线(g, 77.5, 90, 135, "thick"), "六棱柱内部可见竖棱 x=3R/2"
    assert len([d for d in 线(g) if d["style"] == "thick"]) >= 8
    assert len(矩形(g)) == 2


def test_棱锥三视图():
    g = projection.棱锥三视图(5, 25, 45)
    assert 校验图元(g.elems)[0]
    assert g.参数["顶"] == (65, 135)
    assert 有横线(g, 90, 40, 90, "thick")
    thick = [d for d in 线(g) if d["style"] == "thick"]
    assert len(thick) >= 5 + 5 + 5, "五边形 + 5 条顶点连线 + 三角形"
    assert any(abs(d["x1"] - 40) < 1e-6 and abs(d["y1"] - 90) < 1e-6
               and abs(d["x2"] - 65) < 1e-6 and abs(d["y2"] - 135) < 1e-6
               for d in thick), "主视左斜棱 40,90 → 65,135"


def test_非法参数():
    for f, args in ((projection.三视图, (0, 10, 10)),
                    (projection.棱柱三视图, (2, 20, 30)),
                    (projection.棱锥三视图, (5, -1, 30))):
        try:
            f(*args)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{f.__name__}{args} 应抛 ValueError")
