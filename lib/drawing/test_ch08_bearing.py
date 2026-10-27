# -*- coding: utf-8 -*-
"""ch08 §8-6 滚动轴承断言（依据图8-64、表8-9，p.252–253）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import bearing  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_6206_尺寸():
    q = bearing.轴承代号("6206")
    assert (q["d"], q["D"], q["B"]) == (30.0, 62.0, 16.0)
    g = bearing.轴承画法()
    p = g.参数
    assert p["A"] == 16.0 and p["A半"] == 8.0
    assert p["D0"] == 46.0
    assert abs(p["球半径"] - 4.8) < 1e-9


def test_规定画法_环带与球():
    g = bearing.轴承画法(半剖=False)
    assert 校验图元(g.elems)[0]
    # 外圈/内圈各厚 A/2=8：上 115..131、下 69..85；球心在 123/77，共边在球径内断开
    assert 有横线(g, 131.0, 72.0, 88.0)
    assert 有横线(g, 115.0, 72.0, 88.0)
    assert 有横线(g, 85.0, 72.0, 88.0)
    assert 有横线(g, 69.0, 72.0, 88.0)
    assert 有横线(g, 123.0, 72.0, 75.2), "球心处共边应断开（左段）"
    assert 有横线(g, 123.0, 84.8, 88.0), "球心处共边应断开（右段）"
    assert 有横线(g, 123.0, 72.0, 88.0) is None, "球心处不应有整条横线穿过钢球"
    assert 有竖线(g, 72.0, 115.0, 123.0) and 有竖线(g, 72.0, 123.0, 131.0)
    assert 有竖线(g, 88.0, 115.0, 123.0) and 有竖线(g, 88.0, 123.0, 131.0)
    cs = 圆(g)
    assert len(cs) == 2
    assert {round(c["cy"], 1) for c in cs} == {77.0, 123.0}
    assert {round(c["r"], 2) for c in cs} == {4.8}


def test_半剖_上半规定下半通用():
    g = bearing.轴承画法()
    assert len(圆(g)) == 1
    assert round(圆(g)[0]["cy"], 1) == 123.0
    # 剖面线（细线）只应出现在上半（y>100）
    剖 = [dd for dd in 线(g) if dd["style"] == "thin"
          and abs(dd["y1"] - dd["y2"]) > 1e-6 and abs(dd["x1"] - dd["x2"]) > 1e-6]
    assert len(剖) > 5
    assert all(min(dd["y1"], dd["y2"]) > 100.0 for dd in 剖), "下半通用画法不应有剖面线"
    # 下半是 B×D/2 矩形 + 十字（不画球）
    assert any(abs(r["y"] - 69.0) < 1e-6 and abs(r["h"] - 16.0) < 1e-6 for r in 矩形(g))


def test_通用与特征画法():
    g = bearing.轴承画法(画法="通用")
    assert 校验图元(g.elems)[0]
    assert len(圆(g)) == 0
    assert any(abs(r["x"] - 72.0) < 1e-6 and abs(r["w"] - 16.0) < 1e-6
               and abs(r["y"] - 69.0) < 1e-6 and abs(r["h"] - 62.0) < 1e-6 for r in 矩形(g))
    # 角部台阶 2B/3 × 2A/3
    assert any(abs(r["w"] - 32.0 / 3) < 1e-6 and abs(r["h"] - 32.0 / 3) < 1e-6
               for r in 矩形(g)), 矩形(g)
    g2 = bearing.轴承画法(画法="特征")
    assert len(圆(g2)) == 0
    斜 = [dd for dd in 线(g2) if abs(dd["x1"] - dd["x2"]) > 1e-6 and abs(dd["y1"] - dd["y2"]) > 1e-6
          and abs(math.degrees(math.atan2(abs(dd["y2"] - dd["y1"]),
                                          abs(dd["x2"] - dd["x1"]))) - 30.0) < 1e-6]
    assert 斜, "特征画法 30° 粗斜线缺失"


def test_未收录代号与类型报错():
    for bad in ("6209", "9999"):
        try:
            bearing.轴承代号(bad)
        except NotImplementedError:
            pass
        else:
            raise AssertionError(f"{bad} 应报 NotImplementedError")
    try:
        bearing.轴承画法(类型="圆锥滚子")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("圆锥滚子尚未实现，应报 NotImplementedError")
