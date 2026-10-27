# -*- coding: utf-8 -*-
"""ch01 §1-2 图线与图幅断言（表1-3 p.11–12、表1-4 p.12、图1-11/1-12、图1-15）"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing import sheet, standards  # noqa: E402
from lib.drawing._prim import 校验图元, STYLES  # noqa: E402
from lib.drawing._testutil import 展开, 线, 圆, 矩形, 有横线, 有竖线  # noqa: E402

RULES = Path(__file__).resolve().parents[0] / "rules" / "line_types.json"


def test_图线库_九种两档():
    d = json.loads(RULES.read_text(encoding="utf-8"))
    assert len(d["线型"]) == 9
    names = [x["线型"] for x in d["线型"]]
    assert names[0] == "细实线" and names[-1] == "细双点画线"
    for x in d["线型"]:
        assert x["线宽mm"] in (0.25, 0.50), x
        assert x["样式"] in STYLES, x
    assert {x["线宽mm"] for x in d["线型"]} == {0.25, 0.50}
    # 细点画线/细双点画线有书给的画长/间距
    by = {x["线型"]: x for x in d["线型"]}
    assert by["细点画线"]["画长"] == "15~30" and by["细点画线"]["间距"] == "约3"
    assert by["细双点画线"]["画长"] == "15~20" and by["细双点画线"]["间距"] == "约5"
    assert by["细虚线"]["画长"] is None, "书未给细虚线画长，应为 null"


def test_新增线型_STYLES():
    assert STYLES["thick-hidden"][0] == 0.5 and STYLES["thick-hidden"][1]
    assert STYLES["thick-center"][0] == 0.5 and STYLES["thick-center"][1]
    assert STYLES["double-dash"][0] == 0.25 and STYLES["double-dash"][1]
    # 粗细两档不许被改动
    assert STYLES["thick"][0] == 0.5 and STYLES["thin"][0] == 0.25


def test_线型表_九条样线():
    g = standards.线型表()
    assert 校验图元(g.elems)[0]
    ls = 线(g)
    styles = [d["style"] for d in ls]
    assert styles.count("thin") >= 1
    assert styles.count("thick") >= 1
    assert styles.count("hidden") >= 1
    assert styles.count("thick-hidden") >= 1
    assert styles.count("center") >= 1
    assert styles.count("thick-center") >= 1
    assert styles.count("double-dash") >= 1
    paths = [d for k, d in 展开(g.elems) if k == "path"]
    assert len(paths) >= 2, "波浪线/双折线应各有 path"
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert any("9 种" in s for s in texts)


def test_双折线与波浪线_真形状():
    from lib.drawing._prim import 双折线, 波浪线
    p = 双折线(0, 0, 48, 0)
    assert p[0] == "path" and "L" in p[1]["d"]
    pts = [tuple(map(float, x.split())) for x in p[1]["d"].replace("M", "").replace("L", "|").split("|") if x.strip()]
    assert len(pts) >= 8
    assert max(abs(y) for _, y in pts) <= 1.5 + 1e-9
    assert pts[0] == (0.0, 0.0) and pts[-1] == (48.0, 0.0)
    # 每个周期回到基线
    assert sum(1 for _, y in pts if abs(y) < 1e-9) >= 4
    w = 波浪线(0, 0, 40, 0)
    assert w[0] == "path"
    wp = [tuple(map(float, x.split())) for x in w[1]["d"].replace("M", "").replace("L", "|").split("|") if x.strip()]
    assert len(wp) >= 20 and max(abs(y) for _, y in wp) <= 1.2 + 1e-9


def test_图框_A3左装订():
    g = sheet.图框("A3", 装订边="左", 横放=True)
    assert 校验图元(g.elems)[0]
    rs = 矩形(g)
    assert any(abs(r["w"] - 420) < 1e-9 and abs(r["h"] - 297) < 1e-9 and r["style"] == "thin" for r in rs)
    assert any(abs(r["x"] - 25) < 1e-9 and abs(r["y"] - 5) < 1e-9
               and abs(r["w"] - 390) < 1e-9 and abs(r["h"] - 287) < 1e-9 and r["style"] == "thick" for r in rs)
    # 四边中点的对中符号（5mm）
    assert 有横线(g, 148.5, x1=0, x2=5, style="thick")
    assert 有竖线(g, 210, y1=0, y2=5, style="thick")


def test_图框_无装订边与幅面表():
    g = sheet.图框("A3", 装订边="无")
    assert any(abs(r["x"] - 10) < 1e-9 and abs(r["y"] - 10) < 1e-9
               and abs(r["w"] - 400) < 1e-9 and abs(r["h"] - 277) < 1e-9 for r in 矩形(g))
    assert sheet.幅面尺寸("A0")["c"] == 10 and sheet.幅面尺寸("A0")["e"] == 20
    assert sheet.幅面尺寸("A4")["c"] == 5 and sheet.幅面尺寸("A4")["e"] == 10
    try:
        sheet.幅面尺寸("A5")
    except NotImplementedError:
        pass
    else:
        raise AssertionError("A5 应报 NotImplementedError")


def test_标题栏_180x56格位():
    g = sheet.标题栏(件名="主动轴", 材料="45", 比例="1:1", 图号="R01", 设计="张三", 日期="2026-10")
    assert 校验图元(g.elems)[0]
    assert any(abs(r["x"] - 235) < 1e-9 and abs(r["y"] - 5) < 1e-9
               and abs(r["w"] - 180) < 1e-9 and abs(r["h"] - 56) < 1e-9 for r in 矩形(g))
    for k in range(1, 8):
        assert 有横线(g, 5 + 7 * k, x1=235, x2=415)
    for dx in (10, 20, 36, 52, 64, 80, 106, 118, 130):
        assert 有竖线(g, 235 + dx, y1=5, y2=61), dx
    texts = [d["s"] for k, d in 展开(g.elems) if k == "text"]
    assert "主动轴" in texts and "45" in texts and "1:1" in texts
    assert "材料标记" in texts and "比例" in texts


def test_标准表_比例字体幅面():
    for g in (standards.比例表(), standards.字体表(), standards.幅面表()):
        assert 校验图元(g.elems)[0]
    t = [d["s"] for k, d in 展开(standards.比例表().elems) if k == "text"]
    assert any("1:1" in s for s in t)
    f = [d["s"] for k, d in 展开(standards.字体表().elems) if k == "text"]
    assert any("h/√2" in s or "√2" in s for s in f)
    a = [d["s"] for k, d in 展开(standards.幅面表().elems) if k == "text"]
    assert any("A3" in s for s in a) and any("297×420" in s for s in a)
