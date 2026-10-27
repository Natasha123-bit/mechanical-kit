# -*- coding: utf-8 -*-
"""ch08 §8-2 螺纹紧固件连接断言（依据图8-26~8-31，p.232–235）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import fastener  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 矩形, 有横线, 有竖线  # noqa: E402


def test_螺栓_头螺母垫圈比例():
    d = 20.0
    g = fastener.螺栓连接画法(d=d)
    assert 校验图元(g.elems)[0]
    rs = 矩形(g)
    # 螺栓头 k=0.7d=14、垫圈 h=0.15d=3 外径 2.2d=44、螺母 m=0.8d=16
    assert any(abs(r["x"] + 20) < 1e-6 and abs(r["y"] + 14) < 1e-6
               and abs(r["w"] - 40) < 1e-6 and abs(r["h"] - 14) < 1e-6 for r in rs), rs
    assert any(abs(r["w"] - 44) < 1e-6 and abs(r["h"] - 3) < 1e-6 for r in rs), rs
    assert any(abs(r["w"] - 40) < 1e-6 and abs(r["h"] - 16) < 1e-6 for r in rs), rs


def test_螺栓_光孔与螺纹终止线():
    d = 20.0
    g = fastener.螺栓连接画法(d=d)
    # 光孔 1.1d=22（半值 11），单边间隙 0.05d=1
    assert 有竖线(g, 11.0, 0.0, 45.0, style="thick")
    assert 有竖线(g, -11.0, 0.0, 45.0, style="thick")
    # 大径 20（半值 10）贯穿；小径 17（半值 8.5）自自由端向上 b=2d=40
    assert 有竖线(g, 10.0, 0.0, 70.0, style="thick")
    assert 有竖线(g, 8.5, 30.0, 70.0, style="thin")
    # 螺纹终止线：短段自大径到小径
    assert 有横线(g, 30.0, x1=-10.0, x2=-8.5, style="thick")
    assert 有横线(g, 30.0, x1=8.5, x2=10.0, style="thick")


def test_螺柱_旋入端与钻头角():
    d = 20.0
    g = fastener.螺柱连接画法(d=d)
    assert 校验图元(g.elems)[0]
    # bm=d=20：旋入端终止线与结合面 y=0 重合（此处以 y=-20 为螺纹末端）
    assert 有竖线(g, 8.5, -40.0, -20.0, style="thick")
    # 螺孔深 bm+0.5d=30 -> 孔底 y=-30；孔深 bm+d=40 -> 锥起点 y=-40
    assert 有竖线(g, 8.5, -40.0, -20.0, style="thick") is not None
    h = 8.5 / math.tan(math.radians(60))
    assert any(abs(dd["y2"] + (40.0 + h)) < 1e-6 and abs(dd["x2"]) < 1e-6
               for dd in 线(g)), "120° 锥尖缺失"
    # 弹簧垫圈：厚 0.2d=4、外径 1.35d=27
    assert any(abs(min(dd["y1"], dd["y2"]) - 25.6) < 1e-6
               and abs(max(dd["y1"], dd["y2"]) - 28.4) < 1e-6 for dd in 线(g)), "弹簧垫圈缺失"


def test_螺钉_光孔与旋入深度():
    d = 10.0
    g = fastener.螺钉连接画法(d=d)
    assert 校验图元(g.elems)[0]
    # 上件光孔 1.1d=11（半值 5.5），从 y=0 到 t=20
    assert 有竖线(g, 5.5, 0.0, 20.0, style="thick")
    # 杆 d=10（半值 5）伸到旋入端 bm=10
    assert 有竖线(g, 5.0, -10.0, 20.0, style="thick")
    # 小径 8.5（半值 4.25）在旋入段
    assert 有竖线(g, 4.25, -10.0, 0.0, style="thin")
    # 螺纹终止线在螺孔深 bm+0.5d=15 处
    assert 有横线(g, -15.0, x1=-5.0, x2=-4.25, style="thick")
    # 一字槽：主视在轴线上、俯视 45° 粗线
    assert any(abs(dd["y1"] - 20.0) < 1e-6 and abs(dd["y2"] - 20.0) < 1e-6
               and abs(dd["x1"] + dd["x2"]) < 1e-6 for dd in 线(g)), "一字槽主视缺失"
    assert any(abs(abs(dd["y2"] - dd["y1"]) - abs(dd["x2"] - dd["x1"])) < 1e-6
               and dd["style"] == "thick" for dd in 线(g)), "一字槽俯视 45° 线缺失"


def test_三连接_剖面线两件可区分():
    for fn in (fastener.螺栓连接画法, fastener.螺柱连接画法, fastener.螺钉连接画法):
        g = fn()
        assert 校验图元(g.elems)[0], fn.__name__
        细 = [d for d in 线(g) if d["style"] == "thin"
              and abs(d["y1"] - d["y2"]) > 1e-6 and abs(d["x1"] - d["x2"]) > 1e-6]
        assert len(细) >= 12, f"{fn.__name__} 剖面线太少：{len(细)}"
