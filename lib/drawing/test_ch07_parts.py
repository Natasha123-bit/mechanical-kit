# -*- coding: utf-8 -*-
"""ch07 工艺结构与技术要求断言（图7-6~7-8、表7-1）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import parts  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 矩形, 有横线, 有竖线  # noqa: E402


def test_倒角_45度与C标注():
    g = parts.倒角(20, 2, 45, "外")
    assert 校验图元(g.elems)[0]
    assert 有横线(g, 10, x1=2, x2=8, style="thick")
    assert any(abs(d["x1"]) < 1e-9 and abs(d["y1"] - 8) < 1e-9
               and abs(d["x2"] - 2) < 1e-9 and abs(d["y2"] - 10) < 1e-9 for d in 线(g))
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "C2" in texts
    assert abs(g.参数["t"] - 2) < 1e-9


def test_倒角_轴端带起点可见轮廓线():
    """端点线=True：倒角起点 x0+t 处画满 ±r 的竖线（圆柱面与锥面交线，GEO-03）。"""
    g = parts.倒角(20, 2, 45, "外", 端点线=True)
    assert 校验图元(g.elems)[0]
    assert 有竖线(g, 2, y1=-10, y2=10, style="thick")
    assert 有竖线(g, 0, y1=-8, y2=8, style="thick")      # 端面仍只到 r−c
    g0 = parts.倒角(20, 2, 45, "外")                      # 默认不画，孔口倒角用
    assert not 有竖线(g0, 2, y1=-10, y2=10, style="thick")


def test_圆角_相切():
    g = parts.圆角(5, 40, 25)
    assert 校验图元(g.elems)[0]
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) == 1 and "A 5 5" in paths[0]["d"]
    assert g.参数["圆心"] == (35.0, 20.0)
    assert 有横线(g, 0, x1=0, x2=35, style="thick")
    assert 有竖线(g, 40, y1=0, y2=20, style="thick")


def test_退刀槽_槽径():
    g = parts.退刀槽(30, 4, 2)
    assert 校验图元(g.elems)[0]
    assert abs(g.参数["槽径"] - 26) < 1e-9
    assert 有横线(g, 13, x1=18, x2=22, style="thick"), "槽底应在 y=13"
    assert 有竖线(g, 18, y1=13, y2=15, style="thick")
    assert 有竖线(g, 22, y1=13, y2=15, style="thick")
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "4×26" in texts


def test_越程槽_45度斜壁():
    g = parts.越程槽(30, 3, 1.5)
    assert 校验图元(g.elems)[0]
    assert abs(g.参数["r槽"] - 13.5) < 1e-9
    斜 = [d for d in 线(g) if abs(d["x2"] - d["x1"]) > 1e-6 and abs(d["y2"] - d["y1"]) > 1e-6]
    assert len(斜) >= 4, "两侧各两段 45° 斜壁"
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "3×1.5" in texts


def test_中心孔_A型B型():
    a = parts.中心孔(3.15, "A")
    b = parts.中心孔(3.15, "B")
    assert 校验图元(a.elems)[0] and 校验图元(b.elems)[0]
    assert len(b) == len(a) + 2, "B 型多两条 120° 护锥线"
    assert abs(a.参数["锥"] - 1.575 * math.tan(math.radians(60))) < 1e-6
    assert 有竖线(a, 0, y1=-3.15, y2=3.15, style="thick")


def test_锥轴端_锥度():
    g = parts.锥轴端(20, 16, 20)
    assert 校验图元(g.elems)[0]
    assert abs(g.参数["锥度"] - 0.2) < 1e-9
    assert any(abs(d["x1"]) < 1e-9 and abs(d["y1"] + 10) < 1e-9
               and abs(d["x2"] - 20) < 1e-9 and abs(d["y2"] + 8) < 1e-9 for d in 线(g))
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "1:5" in texts


def test_滚花_直纹网纹():
    z = parts.滚花(30, 20, "直纹")
    w = parts.滚花(30, 20, "网纹")
    assert 校验图元(z.elems)[0] and 校验图元(w.elems)[0]
    assert len([d for d in 线(z) if d["style"] == "thin"]) == 9
    assert len([d for d in 线(w) if d["style"] == "thin"]) == 18, "网纹每处两条斜线"
    assert any(abs(r["x"]) < 1e-9 and abs(r["y"] + 15) < 1e-9 and abs(r["w"] - 20) < 1e-9 and abs(r["h"] - 30) < 1e-9 for r in 矩形(z))


def test_技术要求模板_条目():
    g = parts.技术要求模板(材料="HT150", 热处理="正火", 其他=["未注壁厚 5"])
    assert 校验图元(g.elems)[0]
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert len(texts) == 6
    assert any("未注圆角" in s for s in texts)
    assert any("HT150" in s for s in texts)
    assert any("未注壁厚 5" in s for s in texts)
