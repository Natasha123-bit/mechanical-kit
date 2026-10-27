# -*- coding: utf-8 -*-
"""ch08 §8-4 齿轮断言（依据图8-52/8-54/8-55，p.244–246）"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import gear  # noqa: E402
from lib.drawing._prim import 校验图元  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线  # noqa: E402


def test_derive_几何():
    p = gear.derive(2, 29, 47)
    assert p["d1"] == 58 and p["da1"] == 62 and p["df1"] == 53
    assert p["d2"] == 94 and p["da2"] == 98 and p["df2"] == 89
    assert p["a"] == 76
    assert abs(p["p"] - 2 * math.pi) < 1e-12
    assert abs(p["i"] - 47 / 29) < 1e-12
    assert abs(p["间隙"] - 0.5) < 1e-12


def test_五线_五条线型():
    五 = gear.五线(2.0)
    assert len(五) == 5
    assert [it["偏移"] for it in 五] == [-2.5, -2.0, 0.0, 2.0, 2.5]
    assert [it["线型"] for it in 五] == ["thick", "hidden", "center", "thick", "thick"]
    # 相邻 ±m 与 ∓1.25m 之间恰好 0.25m
    assert 2.0 - 1.25 * 2.0 == -0.5
    assert abs((五[1]["偏移"] - 五[0]["偏移"]) - 0.5) < 1e-12
    assert abs((五[4]["偏移"] - 五[3]["偏移"]) - 0.5) < 1e-12


def test_齿轮画法_圆线型():
    g = gear.齿轮画法()
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert len(cs) == 4
    径 = {round(c["r"], 3): c["style"] for c in cs}
    assert 径[31.0] == "thick"      # da=m(z+2)=62
    assert 径[29.0] == "center"     # d=mz=58
    assert 径[26.5] == "thin"       # df=m(z−2.5)=53
    assert 径[10.0] == "thick"      # 孔 φ20
    # 键槽缺口：两条竖线自孔壁 + 一条顶线
    assert any(abs(dd["x1"] - 76.0) < 1e-6 and abs(dd["x2"] - 76.0) < 1e-6 for dd in 线(g))
    assert any(abs(dd["x1"] - 84.0) < 1e-6 and abs(dd["x2"] - 84.0) < 1e-6 for dd in 线(g))
    assert 有横线(g, 124.0, x1=76.0, x2=84.0)


def test_齿轮画法_轴向视图():
    g = gear.齿轮画法()
    rs = 矩形(g)
    assert any(abs(r["x"] - 129.0) < 1e-6 and abs(r["y"] - 79.0) < 1e-6
               and abs(r["w"] - 20.0) < 1e-6 and abs(r["h"] - 62.0) < 1e-6 for r in rs), rs
    assert 有横线(g, 139.0, style="center")     # 分度线 +29
    assert 有横线(g, 81.0, style="center")      # 分度线 −29
    assert 有横线(g, 136.5, style="thin")       # 齿根线 +26.5
    assert 有横线(g, 83.5, style="thin")        # 齿根线 −26.5


def test_啮合_中心距与相切():
    g = gear.齿轮啮合画法()
    assert 校验图元(g.elems)[0]
    cs = 圆(g)
    assert len(cs) == 6
    c1 = [c for c in cs if abs(c["cx"] - 80.0) < 1e-9]
    c2 = [c for c in cs if abs(c["cx"] - 156.0) < 1e-9]
    assert len(c1) == 3 and len(c2) == 3
    assert {round(c["r"], 1) for c in c1} == {31.0, 29.0, 26.5}
    assert {round(c["r"], 1) for c in c2} == {49.0, 47.0, 44.5}
    # 两分度圆在节点相切：中心距 76 = 29 + 47
    assert abs((156.0 - 80.0) - (29.0 + 47.0)) < 1e-9
    p = g.参数
    assert p["a"] == 76 and p["间隙"] == 0.5


def test_啮合_五线画出():
    g = gear.齿轮啮合画法()
    # 放大 3×：节线 y=37.5、齿顶线 43.5/31、齿根线 45/30
    assert 有横线(g, 37.5, x1=70.0, x2=90.0, style="center")
    assert 有横线(g, 43.5, x1=70.0, x2=90.0, style="thick")
    assert 有横线(g, 31.5, x1=70.0, x2=90.0, style="hidden")
    assert 有横线(g, 45.0, x1=70.0, x2=90.0, style="thick")
    assert 有横线(g, 30.0, x1=70.0, x2=90.0, style="thick")
    g2 = gear.齿轮啮合画法(剖视=False)
    assert 校验图元(g2.elems)[0]
    assert 有横线(g2, 37.5, style="center") is None


def test_非法参数():
    for bad in (dict(m=0, z=20), dict(m=2, z=2)):
        try:
            gear.单轮(bad["m"], bad["z"])
        except ValueError:
            pass
        else:
            raise AssertionError(f"应报错：{bad}")
