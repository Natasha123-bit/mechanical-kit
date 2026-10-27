# -*- coding: utf-8 -*-
"""ch08 §8-1 螺纹画法断言（依据图8-16~8-23，p.226–230）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import thread  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 有横线, 有竖线  # noqa: E402


def test_外螺纹_大径小径与倒角():
    g = thread.外螺纹画法()
    assert 校验图元(g.elems)[0]
    assert 有横线(g, 6.0, x1=2.0, x2=45.0, style="thick")
    assert 有横线(g, -6.0, x1=2.0, x2=45.0, style="thick")
    # 小径 d1=0.85d=10.2，半值 5.1；画入倒角（起点 x=1.1）
    assert 有横线(g, 5.1, x1=1.1, x2=30.0, style="thin")
    assert 有横线(g, -5.1, x1=1.1, x2=30.0, style="thin")
    assert len(g) == 9


def test_外螺纹_终止线与轴线():
    g = thread.外螺纹画法()
    assert 有竖线(g, 30.0, -6.0, 6.0, style="thick")
    assert 有横线(g, 0.0, x1=-4.0, x2=49.0, style="center")
    # 倒角 45°：上侧 (0,4)->(2,6)
    assert any(abs(d["x1"]) < 1e-9 and abs(d["y1"] - 4) < 1e-9
               and abs(d["x2"] - 2) < 1e-9 and abs(d["y2"] - 6) < 1e-9 for d in 线(g))
    g2 = thread.外螺纹画法(终止线=False)
    assert 有竖线(g2, 30.0, -6.0, 6.0) is None
    assert len(g2) == 8


def test_内螺纹_大小径线型():
    g = thread.内螺纹画法()
    # 小径 D1=0.85D=17，半值 8.5 -> 孔壁粗实线；大径 D=20，半值 10 -> 细实线
    assert 有横线(g, 8.5, x1=0.0, x2=40.0, style="thick")
    assert 有横线(g, -8.5, x1=0.0, x2=40.0, style="thick")
    assert 有横线(g, 10.0, x1=2.0, x2=30.0, style="thin")
    # 大径细线不进入倒角区（起点 x=倒角=2）
    assert 有横线(g, 10.0, x1=2.0, x2=30.0, style="thin")
    assert 有竖线(g, 30.0, -8.5, 8.5, style="thick")
    assert 有竖线(g, 30.0, -10.0, 10.0) is None


def test_内螺纹_剖面线止于小径():
    g = thread.内螺纹画法()
    from lib.drawing._testutil import 线 as 取线
    细 = [d for d in 取线(g) if d["style"] == "thin"]
    assert len(细) > 10, "剖面线未生成"
    for d in 细:
        # 剖面线只允许在 |y|>=8.5 的实体区（大径细线、端面线除外）
        if abs(d["y1"] - d["y2"]) < 1e-9:
            continue
        assert min(abs(d["y1"]), abs(d["y2"])) >= 8.5 - 1e-6, d


def test_内螺纹不通孔_120度与两段终止线():
    g = thread.内螺纹不通孔画法()
    r1 = 8.5
    h = r1 / math.tan(math.radians(60))
    assert abs(h - 4.907) < 1e-3
    # 锥尖在轴线上，x=钻孔深(40)+锥深
    尖 = 40.0 + h
    assert any(abs(d["x2"] - 尖) < 1e-6 and abs(d["y2"]) < 1e-9 for d in 线(g))
    # 120°：两条斜线与轴线的夹角都是 60°
    for d in 线(g):
        if abs(d["x1"] - 40.0) < 1e-9 and abs(abs(d["y1"]) - 8.5) < 1e-9:
            ang = math.degrees(math.atan2(abs(d["y1"] - d["y2"]), abs(d["x2"] - d["x1"])))
            assert abs(ang - 60.0) < 1e-6, ang
    # 终止线两小段：8.5..10 与 -10..-8.5
    assert 有竖线(g, 30.0, 8.5, 10.0, style="thick")
    assert 有竖线(g, 30.0, -10.0, -8.5, style="thick")


def test_螺纹连接_旋合段按外螺纹():
    g = thread.螺纹连接画法()
    # 板长 60、旋合 25 -> 分界 x=35；杆端 60+1.5d=90，倒角 2 -> 大径线到 88
    assert 有横线(g, 10.0, x1=35.0, x2=88.0, style="thick")
    assert 有横线(g, 8.5, x1=35.0, x2=88.0, style="thin")
    # 未旋合段：内螺纹小径粗、大径细
    assert 有横线(g, 8.5, x1=0.0, x2=35.0, style="thick")
    assert 有横线(g, 10.0, x1=2.0, x2=35.0, style="thin")
    # 终止线（旋合分界）跨小径
    assert 有竖线(g, 35.0, -8.5, 8.5, style="thick")
    # 板外轮廓
    assert 有横线(g, 20.0, x1=0.0, x2=60.0, style="thick")


def test_螺纹标注_落在大径尺寸线():
    g = thread.螺纹标注()
    assert 有竖线(g, 0.0, -10.0, 10.0, style="thin")
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "M20×2-6H" in texts
    g2 = thread.螺纹标注(类型="外")
    texts2 = [d["s"] for k, d in 展开(g2.elems) if k == "text"]
    assert "M20×2-6h" in texts2, texts2
    g3 = thread.螺纹标注(旋合长度代号="L", 旋向="LH")
    texts3 = [d["s"] for k, d in 展开(g3.elems) if k == "text"]
    assert texts3[-1].endswith("-L"), texts3
    assert "LH" in texts3[-1]
