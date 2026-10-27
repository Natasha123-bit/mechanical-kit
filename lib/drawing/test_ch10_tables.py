# -*- coding: utf-8 -*-
"""ch10 附录（附表1–32）表库断言

依据：books/drawing/handoff-ch10/B1–B5.json 逐格提取，合并为
      lib/drawing/tables/ch10.json；页码为印刷页（282–323）。
断言只抽查可复核的关键格；全表由 `_lookup.校验` 做维度体检。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib.handbook._lookup import 取, 校验, 行号  # noqa: E402

T = json.loads((Path(__file__).resolve().parent / "tables" / "ch10.json")
               .read_text(encoding="utf-8"))
TABLES = [f"附表{i}" for i in range(1, 33)]


def test_附表数量与编号():
    assert T["_meta"]["附表数"] == 32
    assert len(TABLES) == 32
    assert all(k in T for k in TABLES), "附表1–32 必须齐全"
    assert not any(k for k in T if k.startswith("附表") and k not in TABLES), "不许有表号越界"


def test_结构与页码():
    for k in TABLES:
        t = T[k]
        assert 校验(t) == [], f"{k} 结构不合格：{校验(t)}"
    page = {"附表1": 282, "附表2": 283, "附表3": 284, "附表4": 285, "附表5": 286,
            "附表6": 287, "附表7": 288, "附表8": 289, "附表9": 290, "附表10": 291,
            "附表11": 292, "附表12": 293, "附表13": 294, "附表14": 295, "附表15": 295,
            "附表16": 296, "附表17": 296, "附表18": 297, "附表19": 298, "附表20": 300,
            "附表21": 301, "附表22": 302, "附表23": 303, "附表24": "304–307",
            "附表25": "308–310", "附表26": 311, "附表27": 311, "附表28": 312,
            "附表29": 313, "附表30": 313, "附表31": 315, "附表32": 318}
    assert {k: T[k]["页"] for k in TABLES} == page


def test_普通螺纹_M12():
    assert 取(T["附表1"], "12", "螺距 P/粗牙") == "1.75"
    assert "1.5" in 取(T["附表1"], "12", "螺距 P/细牙")
    assert 取(T["附表1"], "10", "螺距 P/粗牙") == "1.5"
    assert 取(T["附表1"], "20", "螺距 P/粗牙") == "2.5"
    assert 取(T["附表1"], "8", "螺距 P/细牙").startswith("1")


def test_梯形与管螺纹():
    assert 取(T["附表2"], "40×7", "螺距 P") == "7"
    assert 取(T["附表2"], "40×7", "中径 d₂=D₂") == "36.50"
    assert 取(T["附表2"], "40×7", "小径 d₃") == "32.00"
    assert 取(T["附表3"], "1/2", "基准平面上的基本直径/大径（基准直径）d=D") == "20.955"
    assert 取(T["附表3"], "1/2", "基准平面上的基本直径/小径 d₁=D₁") == "18.631"
    assert 取(T["附表4"], "1/2", "螺纹直径/大径 D、d") == "20.955"
    assert 取(T["附表4"], "1/2", "螺纹直径/小径 D₁、d₁") == "18.631"


def test_标准结构_M10():
    assert 取(T["附表5"], "中等装配", "10") == "11"
    assert 取(T["附表5"], "精装配", "10") == "10.5"
    assert 取(T["附表5"], "粗装配", "10") == "12"


def test_螺栓_M12():
    t = T["附表6"]
    assert 取(t, "b 参考/l≤125", "M12") == 30
    assert 取(t, "c", "M12") == 0.6
    assert 取(t, "d_w/B", "M12") == 16.4
    assert 取(t, "b 参考/125<l≤200", "M12") == 36


def test_螺母_M12():
    t = T["附表12"]
    assert 取(t, "D×P", "M12") == "M12×1.5"
    assert 取(t, "s_max", "M12") == 18
    assert 取(t, "m_max/A、B 级", "M12") == 10.8


def test_垫圈_10():
    t = T["附表13"]
    assert 取(t, "10", "标准系列/GB/T 97.1（A 级）/d_1min") == 10.5
    assert 取(t, "10", "标准系列/GB/T 97.1（A 级）/d_2max") == 20
    assert 取(t, "10", "标准系列/GB/T 97.1（A 级）/h") == 2
    assert 取(t, "10", "标准系列/GB/T 95（C 级）/d_2max") == 20


def test_弹簧垫圈_10():
    t = T["附表14"]
    assert 取(t, "d", "10") == "10.2"
    assert 取(t, "S(b)", "10") == "2.6"
    assert 取(t, "H", "10") == "5.2"


def test_圆柱销_6():
    t = T["附表16"]
    assert 取(t, "d（公称）", "6") == "6"
    assert 取(t, "c≈", "6") == "0.8"
    assert 取(t, "l 范围", "6") == "22~90"


def test_键槽_φ30():
    t = T["附表18"]
    assert 取(t, "22~30", "键尺寸 b×h") == "8×7"
    assert 取(t, "22~30", "键槽/深度/轴 t₁/公称尺寸") == "4.0"
    assert 取(t, "22~30", "键槽/深度/毂 t₂/公称尺寸") == "3.3"
    assert 取(t, "22~30", "键槽/宽度 b/极限偏差/正常连接/轴 N9").endswith("-0.036")


def test_平键长度范围():
    t = T["附表19"]
    assert t["长度范围"]["8"] == "18~90"
    assert t["长度范围"]["10"] == "22~110"
    assert t["长度范围"]["22"] == "63~250"
    assert "空白＝该 b×L 组合为标准长度" in t["矩阵约定"]
    assert "18~90" in t["注"]


def test_半圆键_6():
    t = T["附表21"]
    assert 取(t, "6×9×22", "高度 h/公称尺寸") == "9"
    assert 取(t, "6×9×22", "直径 D/公称尺寸") == "22"
    assert "6×10×25" in t["注"]


def test_轴承_6206():
    t = T["附表22"]
    assert 取(t, "6206", "深沟球轴承/d") == "30"
    assert 取(t, "6206", "深沟球轴承/D") == "62"
    assert 取(t, "6206", "深沟球轴承/B") == "16"
    assert 取(t, "6206", "圆锥滚子轴承/轴承型号") == "30207"


def test_公差_IT():
    t = T["附表23"]
    assert 取(t, "30~50", "IT7") == "25"
    assert 取(t, "30~50", "IT6") == "16"
    assert 取(t, "18~30", "IT7") == "21"
    assert 取(t, "30~50", "IT12") == "0.25"
    assert "IT12~IT18 以 mm 计" in t["注"]


def test_轴偏差_h6():
    t = T["附表24"]
    assert 取(t, "24~30", "h6/上偏差") == "0"
    assert 取(t, "24~30", "h6/下偏差") == "-13"
    assert 取(t, "30~40", "h6/下偏差") == "-16"
    assert t["完整"] is True, "补页后提取完整"
    assert "不是提取缺口" in t["注"]


def test_孔偏差_H7():
    t = T["附表25"]
    assert 取(t, "24~30", "H7/上偏差") == "+21"
    assert 取(t, "24~30", "H7/下偏差") == "0"
    assert 取(t, "30~40", "H7/上偏差") == "+25"
    assert t["完整"] is True
    assert "不是提取缺口" in t["注"]


def test_配合():
    assert 取(T["附表26"], "H7", "f") == "H7/f6"
    assert 取(T["附表26"], "H7", "k") == "H7/k6"
    assert 取(T["附表27"], "h6", "F") == "F7/h6"
    assert 行号(T["附表28"], "H7/g6") == 3
    assert 取(T["附表28"], "H7/g6", "基轴制") == "G7/h6"


def test_材料():
    assert 取(T["附表29"], "HT200", "牌号") == "HT200\nHT250"
    assert 取(T["附表30"], "45", "名称").startswith("优质碳素结构钢")
    assert "综合力学性能" in 取(T["附表31"], "调质", "目的")


def test_几何公差_32():
    t = T["附表32"]
    assert len(t["data"]) == 14
    assert 取(t, "直线度公差", "公差带定义").startswith("由于公差值前加注了符号")
    assert 取(t, "平面度公差", "公差带定义").startswith("公差带是距离为")
    assert 取(t, "同轴度公差", "公差带定义").count("圆柱面") >= 1
    assert 取(t, "全跳动公差", "标注示例和解释").startswith("当提取")
