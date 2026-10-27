# -*- coding: utf-8 -*-
"""ch09 装配图断言（图9-2/9-4/9-13/9-14/9-15/9-30）"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import assembly  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_序号_三种终端():
    g = assembly.序号(3, (0, 0), (30, 20), "短线")
    assert 校验图元(g.elems)[0]
    assert len([d for k, d in 展开(g.elems) if k == "poly"]) == 1
    assert 有横线(g, 20, x1=30, x2=38, style="thin")
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "3" in texts
    g2 = assembly.序号(4, (0, 0), (30, 20), "圆")
    assert len([c for c in 圆(g2) if abs(c["r"] - 4) < 1e-9]) == 1
    g3 = assembly.序号(5, (0, 0), (30, 20), "直接")
    assert 校验图元(g3.elems)[0]


def test_明细栏_180宽与列宽():
    rows = [dict(序号=1, 代号="", 名称="轴承座", 数量=1, 材料="HT150", 备注=""),
            dict(序号=2, 代号="", 名称="轴瓦", 数量=2, 材料="ZCuSn10P1", 备注="")]
    g = assembly.明细栏(rows)
    assert 校验图元(g.elems)[0]
    assert g.参数["宽"] == 180
    assert g.参数["列宽"] == [8, 40, 44, 8, 38, 10, 12, 20]
    assert g.参数["高"] == 14 + 7 * 2
    assert any(abs(r["w"] - 180) < 1e-9 and abs(r["h"] - 28) < 1e-9 for r in 矩形(g))
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "轴承座" in texts and "轴瓦" in texts and "材料" in texts
    s = assembly.明细栏(rows, 完整=False)
    assert s.参数["列宽"] == [8, 60, 50, 30, 32]
    assert s.参数["宽"] == 180


def test_装配结构_接触与非接触():
    c = assembly.装配结构("接触面")
    assert 校验图元(c.elems)[0]
    assert 有横线(c, 8, x1=0, x2=50, style="thick"), "结合面只画一条线"
    n = assembly.装配结构("非接触面")
    rs = 矩形(n)
    assert len(rs) == 2 and abs(rs[1]["y"] - (rs[0]["y"] + 17)) < 1e-9
    f = assembly.装配结构("防松", 形式="双螺母")
    assert 校验图元(f.elems)[0]
    d = assembly.装配结构("防漏")
    assert 校验图元(d.elems)[0]


def test_滑动轴承装配图_轴与序号():
    g = assembly.滑动轴承装配图()
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert any(abs(c["r"] - 15) < 1e-9 for c in cs), "轴 φ30"
    assert any(abs(c["r"] - 3) < 1e-9 for c in cs), "油杯"
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    for n in ("1", "2", "3", "4", "5"):
        assert n in texts, n
    # 轴瓦与轴承座剖面线方向应相反（45° 与 -45°）
    hat = [d for d in 线(g) if d["style"] == "thin" and abs(d["y1"] - d["y2"]) > 1e-6]
    assert len(hat) > 30


def test_拆画泵体_轮廓与孔():
    g = assembly.拆画泵体零件图()
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len([d for d in paths if "A 20 20" in d["d"]]) >= 2, "长圆腔左右半圆"
    assert len([c for c in cs if abs(c["r"] - 3.5) < 1e-9]) == 4
    assert len([c for c in cs if abs(c["r"] - 2.5) < 1e-9]) == 2
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert any("技术要求" in s for s in texts)
    assert "A—A" in texts and "B 向" in texts


def test_拆画检查表():
    q = assembly.拆画检查表()
    assert len(q) == 6
    assert any("被遮挡" in s for s in q)
    assert any("配合尺寸" in s for s in q)


# ============================================================ 整页装配图（D2）
def test_装配图一页_版面():
    g = assembly.装配图一页(件名="滑动轴承", 图号="ZQ-01", 比例="1:1")
    assert 校验图元(g.elems)[0]
    p = g.参数
    assert (p["W"], p["H"]) == (420, 297)
    assert p["标题栏"] == (235, 5, 180, 56)                  # 贴图框右下角（A3 左装订）
    assert p["明细栏"]["左下"] == (235, 61)                  # 紧贴标题栏上沿（5+56）
    assert p["明细栏"]["宽"] == 180                          # 与标题栏同宽
    assert abs(p["明细栏"]["左下"][1] - (5 + 56)) < 1e-9


def test_装配图一页_视图在空白区内且居中():
    v = assembly.滑动轴承装配图()
    vb = v.bbox
    g = assembly.装配图一页(视图=v)
    x0, y0, x1, y1 = g.参数["视图区"]
    dx, dy = g.参数["平移"]
    assert abs(((vb[0] + vb[2]) / 2 + dx) - (x0 + x1) / 2) < 1e-6
    assert abs(((vb[1] + vb[3]) / 2 + dy) - (y0 + y1) / 2) < 1e-6
    # 平移后的视图必须整个落在视图区里
    assert vb[0] + dx >= x0 - 1e-6 and vb[2] + dx <= x1 + 1e-6
    assert vb[1] + dy >= y0 - 1e-6 and vb[3] + dy <= y1 + 1e-6


def _应抛ValueError(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


def test_装配图一页_序号与件表必须对得上():
    # 漏标：件表有 2，图上只标了 1
    assert _应抛ValueError(lambda: assembly.装配图一页(
        件表=[dict(序号=1, 名称="a"), dict(序号=2, 名称="b")],
        序号表=[(1, (100, 150), (120, 170))]))
    # 重号
    assert _应抛ValueError(lambda: assembly.装配图一页(
        件表=[dict(序号=1, 名称="a")],
        序号表=[(1, (100, 150), (120, 170)), (1, (140, 150), (160, 170))]))
    # 引线压标题栏（标题栏在 235..415 × 5..61）
    assert _应抛ValueError(lambda: assembly.装配图一页(
        件表=[dict(序号=1, 名称="a")], 序号表=[(1, (300, 30), (330, 30))]))
    # 视图比任何空白区都大 → 拒绝出图（不放半张）
    from lib.drawing._prim import 图形, 矩形
    大视图 = 图形().加(矩形(0, 0, 400, 260, "thick")).范围(0, 0, 400, 260)
    assert _应抛ValueError(lambda: assembly.装配图一页(视图=大视图, 件名="试"))


def test_装配图一页_明细栏行序自下而上():
    from lib.drawing._testutil import 展开
    件 = [dict(序号=1, 名称="底"), dict(序号=2, 名称="中"), dict(序号=3, 名称="顶")]
    g = assembly.装配图一页(件表=件)
    ys = {}
    for k, d in 展开(g.elems):
        if k == "text" and d["s"] in ("底", "中", "顶"):
            ys[d["s"]] = d["y"]
    assert ys["底"] < ys["中"] < ys["顶"]        # y 向上：序号 1 在最下
