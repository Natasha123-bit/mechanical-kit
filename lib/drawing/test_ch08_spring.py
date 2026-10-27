# -*- coding: utf-8 -*-
"""ch08 §8-5 弹簧断言（依据图8-58~8-60，p.247–248）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import spring  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆  # noqa: E402


def test_弹簧参数():
    p = spring.弹簧参数(8, 48, 96, 13)
    assert p["D"] == 56 and p["D1"] == 40
    # 书公式反推：n=round((96−2d)/13)=6（H0 只按书公式给两端共 2d）
    assert p["n"] == 6 and p["总圈数"] == 8.5
    assert p["有效段高"] == 78
    assert abs(p["端部可用高"] - 9.0) < 1e-9
    # 规定画法每端并紧段占 2d，图8-60 的实际圈数 n=5
    assert spring.弹簧画法().参数["n"] == 5
    assert abs(p["旋绕比"] - 6) < 1e-9


def test_断面圆数与位置():
    g = spring.弹簧画法()
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert len(cs) == 16
    assert {round(c["cx"], 6) for c in cs} == {56.0, 104.0}
    assert {round(c["r"], 6) for c in cs} == {4.0}
    # 有效圈同侧相邻圆心距 = t = 13
    left = sorted(c["cy"] for c in cs if abs(c["cx"] - 56) < 1e-9)
    assert any(abs((b - a) - 13.0) < 1e-9 for a, b in zip(left, left[1:])), left
    # 自由高度 H0=96：上下端面 y=40 / 136
    assert any(abs(dd["y1"] - 40) < 1e-9 and dd["style"] == "thin" for dd in 线(g))
    assert any(abs(dd["y1"] - 136) < 1e-9 and dd["style"] == "thin" for dd in 线(g))


def test_公切线相切():
    g = spring.弹簧画法()
    cs = [(c["cx"], c["cy"], c["r"]) for c in 圆(g)]
    thick = [dd for dd in 线(g) if dd["style"] == "thick"]
    assert len(thick) == 30, f"每对断面圆两条公切线，应 30 条，实为 {len(thick)}"
    for dd in thick:
        for (x, y) in ((dd["x1"], dd["y1"]), (dd["x2"], dd["y2"])):
            ds = [abs(math.hypot(x - cx, y - cy) - r) for cx, cy, r in cs]
            assert min(ds) < 1e-6, f"公切线端点未落在断面圆上：{x},{y} min={min(ds)}"


def test_省略中间圈():
    g = spring.弹簧画法(省略中间圈=True)
    assert 校验图元(g.elems)[0]
    assert g.参数["实绘断面圆数"] == 8
    assert len(圆(g)) == 8
    assert len([d for d in 线(g) if d["style"] == "center"]) >= 6


def test_H0不足报错():
    try:
        spring.弹簧画法(H0=50.0)
    except ValueError:
        pass
    else:
        raise AssertionError("H0=50 容不下 5 圈有效圈，应报错")
