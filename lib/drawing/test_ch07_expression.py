# -*- coding: utf-8 -*-
"""ch07 表达方案与尺寸基准断言（图7-15/7-16~7-24、图7-25/7-26）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import expression  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 矩形  # noqa: E402


def test_叉架_两方案():
    a = expression.表达方案("叉架", "a")
    b = expression.表达方案("叉架", "b")
    assert 校验图元(a.elems)[0] and 校验图元(b.elems)[0]
    assert len(a.参数["视图"]) == 3 and len(b.参数["视图"]) == 3
    assert "俯视图" in a.参数["视图"]
    assert "左视图（全剖）" in b.参数["视图"]
    assert "A—A 剖视" in a.参数["视图"] and "A—A 剖视" in b.参数["视图"]


def test_箱体与轴套_视图数():
    x = expression.表达方案("箱体")
    z = expression.表达方案("轴套")
    assert len(x.参数["视图"]) == 4
    assert "主视图 A—A" in x.参数["视图"] and "C 向视图" in x.参数["视图"]
    assert len(z.参数["视图"]) == 5
    assert any("断面" in k for k in z.参数["视图"])
    assert len(矩形(x)) == 4 and len(矩形(z)) == 5


def test_尺寸基准_轴与板():
    a = expression.尺寸基准("轴")
    b = expression.尺寸基准("板")
    assert 校验图元(a.elems)[0] and 校验图元(b.elems)[0]
    ta = [d["s"] for k, d in 展开(a.elems) if k == "text"]
    assert "A" in ta and "B" in ta
    assert any(d["s"] == "80" for k, d in 展开(a.elems) if k == "text")
    try:
        expression.表达方案("蜗轮")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("未收录类型应报错")
