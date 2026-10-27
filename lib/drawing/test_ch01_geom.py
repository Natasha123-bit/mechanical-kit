# -*- coding: utf-8 -*-
"""ch01 §1-3 几何作图断言（图1-23/1-24/1-26/1-28/1-31，表1-7）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import geom  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 有横线, 有竖线  # noqa: E402


def test_等分圆周_六等分():
    g = geom.等分圆周(6, 30, 100, 100)
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert any(abs(c["r"] - 30) < 1e-9 and c["style"] == "thin" for c in cs)      # 圆
    assert len([c for c in cs if abs(c["r"] - 0.8) < 1e-9]) == 6                 # 6 个等分点
    assert len(线(g)) == 8, "6 条多边形边 + 2 条中心线"
    # 起始点在正上方
    assert any(abs(c["cx"] - 100) < 1e-6 and abs(c["cy"] - 130) < 1e-6 for c in cs)


def test_正多边形_与非法n():
    g = geom.正多边形(5, 30, 0, 0)
    assert 校验图元(g.elems)[0]
    assert len([d for d in 线(g) if d["style"] == "thick"]) == 5
    assert not [c for c in 圆(g) if abs(c["r"] - 30) < 1e-9], "正多边形不应画外接圆"
    try:
        geom.等分圆周(2)
    except ValueError:
        pass
    else:
        raise AssertionError("n=2 应报错")


def test_斜度_1比5():
    g = geom.斜度(0.2, 60)
    assert 校验图元(g.elems)[0]
    ls = 线(g)
    assert any(abs(d["x1"]) < 1e-9 and abs(d["y1"]) < 1e-9
               and abs(d["x2"] - 60) < 1e-9 and abs(d["y2"] - 12) < 1e-9 for d in ls)
    assert 有横线(g, 0, x1=0, x2=60, style="thick")
    assert 有竖线(g, 60, y1=0, y2=12, style="thick")
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "∠1:5" in texts


def test_锥度_1比5():
    g = geom.锥度(0.2, 60, 30)
    assert 校验图元(g.elems)[0]
    # 小端 d = 30 − 0.2×60 = 18
    assert 有竖线(g, 0, y1=-15, y2=15, style="thick")
    assert 有竖线(g, 60, y1=-9, y2=9, style="thick")
    assert 有横线(g, 0, x1=-6, x2=66, style="center")
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "1:5" in texts


def test_圆弧连接_相切():
    g = geom.圆弧连接(15, "两直线", 60)
    assert 校验图元(g.elems)[0]
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1
    d = paths[0]["d"]
    assert "A 15 15" in d
    for p in ("0 15", "15 0"):
        assert p in d or p.replace(" ", "  ") in d, d
    try:
        geom.圆弧连接(15, "两圆弧")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("未实现的连接类型应报错")


def test_椭圆_四心法():
    g = geom.椭圆(80, 50)
    assert 校验图元(g.elems)[0]
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 4, "四心法应为 4 段弧"
    assert g.bbox == (-40.0, -25.0, 40.0, 25.0)
    p = g.参数
    assert abs(p["R大"] - p["R小"] - math.hypot(p["x1"], p["y2"])) < 1e-6, "内切条件不成立"
    try:
        geom.椭圆(50, 80)
    except ValueError:
        pass
    else:
        raise AssertionError("长轴≤短轴应报错")
