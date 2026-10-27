# -*- coding: utf-8 -*-
"""ch08 补做：图8-21 左视图（批2 验收记录第 3 项）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import thread_left  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆  # noqa: E402


def test_左视图_三圆与三四圈():
    g = thread_left.螺纹连接左视图(d=20.0)
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert {round(c["r"], 3) for c in cs} == {32.0, 8.5}
    assert all(c["style"] == "thick" for c in cs)
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1
    d = paths[0]["d"]
    assert "A 10 10" in d, d
    # 0° → 270°：起点 (10,0)，终点 (0,-10)
    assert "M 10 0" in d and "0 -10" in d, d
    assert paths[0]["style"] == "thin"


def test_左视图_中心线与边界():
    g = thread_left.螺纹连接左视图(d=20.0)
    assert len([x for x in 线(g) if x["style"] == "center"]) == 2
    assert g.bbox == (-36.0, -36.0, 36.0, 36.0)
    try:
        thread_left.螺纹连接左视图(d=0)
    except ValueError:
        pass
    else:
        raise AssertionError("d=0 应报错")
