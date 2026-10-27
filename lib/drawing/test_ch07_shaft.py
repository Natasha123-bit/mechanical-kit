# -*- coding: utf-8 -*-
"""ch07 阶梯轴零件图与几何公差断言（图7-1、图7-49）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import shaft  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 有横线, 有竖线  # noqa: E402


def test_阶梯轴_段与总长():
    g = shaft.阶梯轴零件图()
    assert 校验图元(g.elems)[0]
    assert g.参数["总长"] == 140 and g.参数["段数"] == 5
    assert g.参数["最大直径"] == 25
    # 各段顶母线（粗实线）在 y=7/10/12.5
    for y in (7, 10, 12.5):
        assert 有横线(g, y, style="thick"), y
        assert 有横线(g, -y, style="thick"), -y
    # 轴肩竖线：x=30 从 7 到 10，x=50 从 10 到 12.5
    assert 有竖线(g, 30, 7, 10, style="thick")
    assert 有竖线(g, 50, 10, 12.5, style="thick")


def test_阶梯轴_键槽断面与退刀槽():
    g = shaft.阶梯轴零件图()
    # A—A 在 x=185；圆弧 R12.5；键槽侧壁 x=183/187，y=10..12.34
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert any("A 12.5 12.5" in d["d"] for d in paths), "A—A 圆弧缺失"
    assert 有竖线(g, 183, 10, 12.339, style="thick")
    assert 有竖线(g, 187, 10, 12.339, style="thick")
    # 退刀槽：第一段右端 x=26..30，槽底 y=±5
    assert 有横线(g, 5, x1=26, x2=30, style="thick")
    assert 有横线(g, -5, x1=26, x2=30, style="thick")


def test_阶梯轴_标注与技术要求():
    g = shaft.阶梯轴零件图()
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "140" in texts
    assert "φ14" in texts and "φ25" in texts
    assert texts.count("Ra3.2") == 2 and "Ra6.3" in texts
    assert "◎" in texts and "φ0.02" in texts and "A" in texts
    assert any("未注圆角" in s for s in texts)
    assert any("热处理" in s for s in texts)


def test_几何公差_三例():
    g = shaft.几何公差示例()
    assert 校验图元(g.elems)[0]
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "◎" in texts and "≡" in texts and "◆" in texts
    assert "(a) 被测圆柱轴线" in texts and "(b) 被测中心平面" in texts and "(c) 被测球心" in texts
    assert g.参数["框格数"] == 3
