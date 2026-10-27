# -*- coding: utf-8 -*-
"""ch06 §6-1 视图断言（图6-2/6-3/6-4/6-7，p.144–147）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import views  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 矩形  # noqa: E402


def test_六视图_配置():
    g = views.视图配置()
    assert 校验图元(g.elems)[0]
    assert len(矩形(g)) == 6
    v = g.视图
    assert set(v) == {"主视图", "俯视图", "仰视图", "左视图", "右视图", "后视图"}
    主, 俯, 仰 = v["主视图"], v["俯视图"], v["仰视图"]
    右, 左, 后 = v["右视图"], v["左视图"], v["后视图"]
    assert 主[0] == 俯[0] == 仰[0], "长对正"
    assert 主[1] == 右[1] == 左[1] == 后[1], "高平齐"
    assert 俯[3] == 仰[3] == 右[2] == 左[2] == 25, "宽相等 = 深"
    assert 仰[1] > 主[1] > 俯[1], "第一角：仰在上、俯在下"
    assert 右[0] < 主[0] < 左[0] < 后[0], "右在左、左在右、后在左再右"


def test_向视图_标注():
    g = views.向视图(宽=50, 高=30, 字母="A", 箭头方向="右")
    assert 校验图元(g.elems)[0]
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert texts.count("A") >= 2, "视图上方与箭头旁各一个 A"
    polys = [d for k, d in 展开(g.elems) if k == "poly"]
    assert len(polys) == 1 and polys[0]["fill"] == "solid"
    try:
        views.向视图(箭头方向="斜")
    except ValueError:
        pass
    else:
        raise AssertionError("非法箭头方向应报错")


def test_局部视图_断裂边界():
    g = views.局部视图(断裂边="波浪", 字母="B")
    assert 校验图元(g.elems)[0]
    assert len([d for d in 线(g) if d["style"] == "thick"]) == 3
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1 and "L" in paths[0]["d"]
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "B向" in texts
    g2 = views.局部视图(断裂边="双折线")
    assert 校验图元(g2.elems)[0]
    assert len([d for k, d in 展开(g2.elems) if k == "path"]) == 1


def test_斜视图_旋转符号():
    g = views.斜视图(旋转=True, 字母="A")
    assert 校验图元(g.elems)[0]
    assert len([d for d in 线(g) if d["style"] == "thick"]) == 4, "旋转矩形四条边"
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1 and "A 3.5 3.5" in paths[0]["d"], "旋转符号半圆弧 R=3.5"
    polys = [d for k, d in 展开(g.elems) if k == "poly"]
    assert len(polys) == 1
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "A" in texts


def test_斜视图_斜放():
    g = views.斜视图(倾角=30, 旋转=False)
    assert 校验图元(g.elems)[0]
    assert not [d for k, d in 展开(g.elems) if k == "path"], "斜放不画旋转符号"
    # 四条边都不水平/不竖直（30° 旋转）
    for d in 线(g):
        assert abs(d["y1"] - d["y2"]) > 1e-6 and abs(d["x1"] - d["x2"]) > 1e-6
