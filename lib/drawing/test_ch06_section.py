# -*- coding: utf-8 -*-
"""ch06 §6-2~§6-5 剖视/断面/放大断言（图6-13/6-15/6-16、6-38/6-44、6-45，表6-1）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import section  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_全剖_孔壁与剖面线():
    g = section.剖视(类型="全剖")
    assert 校验图元(g.elems)[0]
    assert 有竖线(g, 68, 85, 135, style="thick"), "孔左壁 cx−r"
    assert 有竖线(g, 92, 85, 135, style="thick"), "孔右壁 cx+r"
    # 剖面线为 45° 细线，孔内（68..92）不得落线
    hatch = [d for d in 线(g) if d["style"] == "thin"
             and abs(d["y1"] - d["y2"]) > 1e-6 and abs(d["x1"] - d["x2"]) > 1e-6]
    assert len(hatch) > 20
    for d in hatch:
        lo, hi = min(d["x1"], d["x2"]), max(d["x1"], d["x2"])
        assert hi <= 68 + 1e-6 or lo >= 92 - 1e-6, f"剖面线进入孔内：{d}"


def test_半剖_分界与单侧():
    g = section.剖视(类型="半剖")
    assert 校验图元(g.elems)[0]
    assert 有竖线(g, 80, 85, 135, style="center"), "分界线必须是细点画线"
    assert 有竖线(g, 68, 85, 135, style="thick")
    assert 有竖线(g, 92, 85, 135, style="thick") is None, "视图半边不应再画孔壁"
    hatch = [d for d in 线(g) if d["style"] == "thin"
             and abs(d["y1"] - d["y2"]) > 1e-6 and abs(d["x1"] - d["x2"]) > 1e-6]
    assert hatch and all(max(d["x1"], d["x2"]) <= 68 + 1e-6 for d in hatch), "只许左半有剖面线"


def test_局部剖_波浪线与范围():
    g = section.剖视(类型="局部剖")
    assert 校验图元(g.elems)[0]
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1
    d = paths[0]["d"]
    assert "M 102 " in d and "102 " in d, "波浪线应在 x=cx+r+10=102"
    hatch = [d for d in 线(g) if d["style"] == "thin"
             and abs(d["y1"] - d["y2"]) > 1e-6 and abs(d["x1"] - d["x2"]) > 1e-6]
    assert hatch and max(max(d["x1"], d["x2"]) for d in hatch) <= 102 + 1e-6


def test_剖切符号_两短画两箭头():
    g = section.剖切符号(方向="竖", 长度=60, 字母="A")
    assert 校验图元(g.elems)[0]
    shorts = [d for d in 线(g) if d["style"] == "thick"
              and abs(d["x1"] - d["x2"]) < 1e-9 and abs(abs(d["y2"] - d["y1"]) - 6) < 1e-9]
    assert len(shorts) == 2
    assert abs(abs(shorts[0]["y1"] - shorts[1]["y1"]) - 60) < 1e-6
    polys = [d for k, d in 展开(g.elems) if k == "poly"]
    assert len(polys) == 2
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert texts.count("A") == 2
    g2 = section.剖切符号(方向="横")
    assert len([d for d in 线(g2) if d["style"] == "thick"]) == 2


def test_断面_移出粗重合细():
    g = section.断面(类型="移出")
    assert 校验图元(g.elems)[0]
    assert any(abs(r["x"] - 80) < 1e-9 and abs(r["w"] - 40) < 1e-9
               and abs(r["h"] - 20) < 1e-9 and r["style"] == "thick" for r in 矩形(g))
    g2 = section.断面(类型="重合")
    assert 校验图元(g2.elems)[0]
    assert any(abs(r["w"] - 40) < 1e-9 and abs(r["h"] - 20) < 1e-9 and r["style"] == "thin" for r in 矩形(g2))
    view = [r for r in 矩形(g2) if r["style"] == "thick"]
    assert len(view) == 1 and view[0]["h"] == 10.0, "视图带高 = 高/2，轮廓连续不断"


def test_局部放大_比例():
    g = section.局部放大(半径=12, 比例=2.0)
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    thin = [c for c in cs if c["style"] == "thin"]
    thick = [c for c in cs if c["style"] == "thick"]
    assert len(thin) == 2 and len(thick) == 2
    assert max(c["r"] for c in thick) / max(c["r"] for c in thin) == 2.0
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert any("2:1" in s for s in texts)


def test_剖面符号_三种材料():
    for 材 in ("金属", "非金属", "线圈"):
        s = section.剖面符号([(0, 0), (20, 0), (20, 10), (0, 10)], 材)
        ok, msg = 校验图元([s])
        assert ok, f"{材}: {msg}"
    try:
        section.剖面符号([(0, 0), (20, 0), (20, 10)], "木材")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("未实现的材料应报 NotImplementedError")
