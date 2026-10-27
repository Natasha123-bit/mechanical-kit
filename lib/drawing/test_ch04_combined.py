# -*- coding: utf-8 -*-
"""ch04 组合体三视图、尺寸与邻接表面断言（图4-5/4-8/4-11/4-30）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import combined  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 线, 圆, 矩形, 有横线, 有竖线, 展开  # noqa: E402


def test_组合体三视图():
    g = combined.组合体三视图(60, 40, 25, 24, 12)
    assert 校验图元(g.elems)[0]
    assert g.参数["主"] == (40, 90, 60, 25)
    assert g.参数["俯"] == (40, 35, 60, 40)
    assert g.参数["左"] == (115, 90, 40, 25)
    assert len(圆(g)) == 1 and abs(圆(g)[0]["r"] - 12) < 1e-9
    assert 有横线(g, 115, 40, 58, "thick"), "底板顶面左段"
    assert 有横线(g, 115, 82, 100, "thick"), "底板顶面右段"
    assert not 有横线(g, 115, 40, 100, "thick"), "顶面线不应穿过凸台"


def test_组合体尺寸():
    g = combined.组合体尺寸(60, 40, 25, 24, 12)
    assert 校验图元(g.elems)[0]
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    for s in ("60", "25", "12", "φ24", "40"):
        assert s in texts, f"缺尺寸 {s}"
    assert sum(1 for k, _ in g.elems if k == "group") == 5
    assert 有横线(g, 78, 40, 100, "thin"), "总体长尺寸线 y=90-12"


def test_邻接表面_平齐():
    g = combined.邻接表面("平齐", 30, 20)
    assert 校验图元(g.elems)[0]
    assert 有横线(g, 110, 40, 100, "thick")
    assert not 有竖线(g, 70, 90, 110, "thick"), "平齐接缝不画竖线"
    assert len(线(g)) == 4


def test_邻接表面_不平齐():
    g = combined.邻接表面("不平齐", 30, 20, 错位=8)
    assert 校验图元(g.elems)[0]
    assert 有竖线(g, 70, 90, 102, "thick"), "台阶面竖线 y=90..102"
    assert 有横线(g, 102, 70, 100, "thick"), "台阶面横线"
    assert len(线(g)) == 6


def test_邻接表面_相切与相交():
    a = combined.邻接表面("相切", 30, 20, 半径=8)
    assert 校验图元(a.elems)[0]
    assert len(圆(a)) == 1 and abs(圆(a)[0]["r"] - 8) < 1e-9
    assert not 有竖线(a, 70, 90, 110, "thick"), "相切处不画交线"
    b = combined.邻接表面("相交", 30, 20, 错位=8)
    assert 校验图元(b.elems)[0]
    assert len(矩形(b)) == 2
    r = 矩形(b)[1]
    assert (r["x"], r["y"], r["w"], r["h"]) == (70, 86, 30, 20), "右块位置形成相交竖边"


def test_非法关系():
    try:
        combined.邻接表面("焊接")
    except ValueError:
        pass
    else:
        raise AssertionError("未知关系应抛 ValueError")
