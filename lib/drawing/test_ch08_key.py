# -*- coding: utf-8 -*-
"""ch08 §8-3 键、销连接断言（依据图8-37~8-44、表8-4，p.238–241）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import key, pin  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402


def test_平键_顶面两条线与键不剖():
    d, b, h, L = 30.0, 8.0, 7.0, 25.0
    g = key.平键连接画法(d=d, b=b, h=h, L=L)
    assert 校验图元(g.elems)[0]
    键顶 = 15.0 - 0.6 * h + h          # r - t1 + h = 15 - 4.2 + 7 = 17.8
    槽顶 = 键顶 + 0.02 * d
    # 键是矩形：顶边（键顶 17.8）是矩形上边，轮毂槽顶另画一条线（18.4）
    assert any(abs(r["x"] - 8.0) < 1e-6 and abs(r["y"] - 10.8) < 1e-6
               and abs(r["w"] - 25.0) < 1e-6 and abs(r["h"] - h) < 1e-6 for r in 矩形(g)), 矩形(g)
    assert 有横线(g, 槽顶, x1=8.0, x2=33.0, style="thick"), "轮毂槽顶线（第二条）缺失"
    assert abs((槽顶 - 键顶) - 0.6) < 1e-6
    # 键体内不得有剖面线（主视图 x<41）
    细 = [dd for dd in 线(g) if dd["style"] == "thin" and max(dd["x1"], dd["x2"]) < 41.0]
    assert not 细, f"键/轴被剖了：{细[:2]}"


def test_平键_槽深与断面():
    d, b, h = 30.0, 8.0, 7.0
    g = key.平键连接画法(d=d, b=b, h=h)
    t1 = 0.6 * h
    assert abs((15.0 - t1) - 10.8) < 1e-6
    assert 有横线(g, 10.8, x1=8.0, x2=33.0, style="thick"), "轴槽底线缺失"
    cs = 圆(g)
    assert len(cs) == 2
    assert any(abs(c["r"] - 15.0) < 1e-9 for c in cs)      # 轴断面
    assert any(abs(c["r"] - 33.0) < 1e-9 for c in cs)      # 轮毂外圆 1.1d


def test_半圆键_月牙与顶部间隙():
    g = key.半圆键连接画法()
    assert 校验图元(g.elems)[0]
    横 = [dd for dd in 线(g) if abs(dd["y1"] - dd["y2"]) < 1e-9
          and 15.0 < dd["y1"] < 20.0 and dd["style"] == "thick"]
    ys = sorted({round(dd["y1"], 3) for dd in 横})
    assert len(ys) >= 2, ys
    assert any(abs(a - b) - 0.6 < 1e-6 for a, b in zip(ys, ys[1:])), f"顶部两条线间距不是 0.6：{ys}"
    assert any(k == "arc" or k == "path" for k, _ in 展开(g.elems)), "半圆槽/月牙弧缺失"


def test_楔键_顶面贴合侧面双线():
    d = 30.0
    g = key.钩头楔键连接画法(d=d)
    assert 校验图元(g.elems)[0]
    # A—A 断面中心 x=92.2：槽壁 ±4，键侧 ±3.4 -> 每侧两条线
    assert 有竖线(g, 88.2, 10.2, 15.0, style="thick"), "轴槽壁线缺失"
    assert 有竖线(g, 88.8, 10.2, 18.05, style="thick"), "键侧面线缺失（应每侧两条）"
    assert 有竖线(g, 95.6, 10.2, 18.05, style="thick")
    assert 有竖线(g, 96.2, 10.2, 15.0, style="thick")
    # 顶面贴合：A—A 区域内 y=18.05 只有一条横线（不是两条）
    顶 = [dd for dd in 线(g) if abs(dd["y1"] - 18.05) < 1e-6
          and abs(dd["y2"] - 18.05) < 1e-6 and min(dd["x1"], dd["x2"]) > 85.0]
    assert len(顶) == 1, f"顶面应贴合只画一条，实为 {len(顶)}"
    # 主视图顶面是斜面（楔紧面），不是两条平行线
    斜面 = [dd for dd in 线(g) if abs(dd["y1"] - 18.2) < 1e-6 and abs(dd["y2"] - 17.9) < 1e-6]
    assert len(斜面) == 1, "楔键顶面斜线缺失"


def test_花键_外内线型():
    g外 = key.花键画法(类型="外")
    assert 校验图元(g外.elems)[0]
    assert 有横线(g外, 20.0, style="thick"), "外花键大径应为粗实线"
    assert 有横线(g外, 16.0, style="thin"), "外花键小径应为细实线"
    g内 = key.花键画法(类型="内")
    assert 校验图元(g内.elems)[0]
    assert 有横线(g内, 20.0, style="thick")
    assert 有横线(g内, 16.0, style="thick"), "内花键小径也应为粗实线"


def test_花键_尾部30度():
    g = key.花键画法(类型="外")
    斜 = [dd for dd in 线(g) if dd["style"] == "thin"
          and abs(dd["x1"] - dd["x2"]) > 1e-6 and abs(dd["y1"] - dd["y2"]) > 1e-6
          and abs(math.degrees(math.atan2(abs(dd["y2"] - dd["y1"]),
                                          abs(dd["x2"] - dd["x1"]))) - 30.0) < 1e-6]
    assert 斜, "尾部 30° 斜细实线缺失"


def test_销_三种类型():
    g圆 = pin.销连接画法(d=8, l=30)
    assert 校验图元(g圆.elems)[0]
    assert 有竖线(g圆, 4.0, -0.3, 27.3, style="thick")
    g锥 = pin.销连接画法(d=8, l=30, 类型="圆锥")
    # 锥度 1:50：全长 30 半径共收缩 0.3；锥面线自 y=-0.3 的 3.988 收到 y=27.3 的 3.712
    assert any(abs(dd["x1"] - 3.988) < 1e-3 and abs(dd["y1"] + 0.3) < 1e-6
               and abs(dd["x2"] - 3.712) < 1e-3 and abs(dd["y2"] - 27.3) < 1e-6
               for dd in 线(g锥)), "圆锥销锥面线缺失"
    细 = [dd for dd in 线(g圆) if dd["style"] == "thin"
          and abs(dd["y1"] - dd["y2"]) > 1e-6]
    assert len(细) > 8, "被连接件剖面线缺失"
    g开 = pin.销连接画法(d=8, l=30, 类型="开口")
    assert 校验图元(g开.elems)[0]
    扳 = [dd for dd in 线(g开) if abs(dd["x1"] - dd["x2"]) > 1e-6
          and abs(dd["y1"] - dd["y2"]) > 1e-6]
    assert len(扳) >= 2, "开口销两腿扳开线缺失"
