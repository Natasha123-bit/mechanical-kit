# -*- coding: utf-8 -*-
"""manual_ch19_tests.py — manual_ch19.py 的断言测试（批4·ch19 编写设计说明书）

期望值全部来自页图逐格核读的表字典本体（B2 核读 + F 主代理回 p001/p002 页图复核：
「铅垂面/弯矩/扭矩」等确为图××内部标注、不入 data），断言参数不编数。跑法：

    cd .../mdkit/lib/handbook
    python3 manual_ch19_tests.py     # 末行打印「合计：通过 N 项，失败 0 项」
"""
import json
import sys
import traceback
from pathlib import Path

import manual_ch19 as m
from _lookup import 校验


class _跳过(Exception):
    """缺证据文件（books/ 不随公开版分发）时跳过该案例，不算失败。"""


_HO = Path(__file__).resolve().parent.parent.parent / "books" / "handbook" / "handoff-ch19"

t191 = m.表19_1_说明书书写格式

CASES = []


def 案例(名称):
    def 注册(fn):
        CASES.append((名称, fn))
        return fn
    return 注册


def 应抛(异常类, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except 异常类:
        return
    except Exception as e:  # noqa: BLE001
        raise AssertionError(f"应抛 {异常类.__name__}，实抛 {type(e).__name__}: {e}")
    raise AssertionError(f"应抛 {异常类.__name__}，却正常返回")


# ---------------------------------------------------------------- L1 结构

@案例("L1 结构体检：表19-1 一张表，11 行×2 列，页 255")
def _():
    assert t191["表号"] == "表19-1" and t191["页"] == 255
    assert t191["cols"] == ["计算及说明", "结　　果"]
    assert len(t191["rows"]) == 11 and len(t191["data"]) == 11
    bad = 校验(t191)
    assert not bad, bad


@案例("L1 左栏层级照抄：七、→1.→（1）（2）→1）→分式两行→=779 N→……")
def _():
    左 = [r[0] for r in t191["data"]]
    assert 左[0] == "七、轴的设计及核验计算"
    assert 左[1] == "1. 低速轴的计算"
    assert 左[2] == "结构和受力如图××所示。"
    assert 左[3] == "（1）轴上作用载荷" and 左[5] == "（2）计算轴承支反力"
    assert 左[6] == "1）铅垂面内支反力"
    assert 左[7] == "F_By=(79×10^-3·F+55×10^-3·F_1-M_a)/(110×10^-3)"
    assert 左[8] == "=(79×10^-3×760+55×10^-3×665-10.95)/(110×10^-3)"
    assert 左[9] == "=779 N" and 左[10] == "……"


@案例("L1 右栏全书只一个值 F_By=779 N，归属「1）铅垂面内支反力」行")
def _():
    非空 = [(r[0], r[1]) for r in t191["data"] if r[1] is not None]
    assert 非空 == [("1）铅垂面内支反力", "F_By=779 N")]


@案例("L1 图××内部标注不入 data（F 回 p.255 页图裁决）：铅垂面/弯矩/扭矩等不在左栏")
def _():
    全文 = "".join(str(c) for r in t191["data"] for c in r)
    for 图内标注 in ("铅垂面\n", "弯矩M_y", "水平面\n", "弯矩M_x", "扭矩T",
                  "F_Ay=874", "M_Cy左=42.83", "T=49.52"):
        assert 图内标注 not in 全文, 图内标注
    assert "图××" in t191["注"] and "图19-2" in t191["注"] and "图19-3" in t191["注"]


# ---------------------------------------------------------------- L2 判据

@案例("L2 说明书章节：14 项（p.254 页图逐字），首目录、末参考文献")
def _():
    章 = m.说明书章节()
    assert len(章) == 14
    assert 章[0] == "目录（标题及页次）" and 章[1] == "设计任务书"
    assert 章[3] == "动力机选择" and 章[7] == "轴的计算"
    assert 章[8] == "轴承（滚动轴承、滑动轴承）的选择和计算"
    assert 章[12] == "零部件和整机的价格评估" and 章[13] == "参考文献"


@案例("L2 编写注意三点：打印件/列出公式并标单位/大小标题与结论、注明来源")
def _():
    注 = m.说明书编写注意()
    assert len(注) == 3
    assert "不得用铅笔或彩色笔" in 注[0]
    assert "中间运算应省略" in 注[1]
    assert "注明重要公式或数据的来源" in 注[2]


@案例("L2 书写格式行：逐行出 dict，结果列透传")
def _():
    行 = m.书写格式行()
    assert len(行) == 11
    assert 行[6] == {"行": "7", "计算及说明": "1）铅垂面内支反力", "结果": "F_By=779 N"}
    assert 行[0]["结果"] is None


@案例("L2 交付串")
def _():
    assert m.交付串("说明书书写格式", 页码=255) == "说明书书写格式（表19-1，p.255）"
    assert m.交付串("说明书章节目录", "p.254 正文") == "说明书章节目录（p.254 正文）"


@案例("书上未给：封面/折叠/文件袋格式数值 → NotImplementedError")
def _():
    应抛(NotImplementedError, m.封面或折叠格式)
    应抛(NotImplementedError, m.封面或折叠格式, "图19-1")


# ---------------------------------------------------------------- 等值

@案例("与 handoff-ch19/B1.json 逐格等值（表号/表名/页/单位/rows/cols/data/merges/注）")
def _():
    if not _HO.is_dir():
        raise _跳过("缺 books/handbook/handoff-ch19/B1.json")
    jt = json.loads((Path(__file__).resolve().parent.parent.parent
                     / "books/handbook/handoff-ch19/B1.json").read_text(encoding="utf-8"))
    assert t191["表号"] == jt["ref"] and t191["表名"] == jt["title"]
    assert t191["页"] == jt["pages"][0] and t191["单位"] == jt.get("单位", "")
    assert t191["rows"] == jt["rows"] and t191["cols"] == jt["cols"]
    assert t191["data"] == jt["data"] and t191["merges"] == jt["merges"]
    assert t191["注"] == jt["注"] + "同号结论：" + jt["同号结论"] + "。"


@案例("同号结论入注：表体仅 255，254 为正文引用页")
def _():
    assert "正文引用" in t191["注"] and "255" in t191["注"]


# ---------------------------------------------------------------- 运行

def main():
    通过, 失败, 跳过 = 0, [], []
    for 名称, fn in CASES:
        try:
            fn()
            通过 += 1
        except _跳过 as e:
            跳过.append((名称, str(e)))
        except Exception:  # noqa: BLE001
            失败.append((名称, traceback.format_exc()))
    for 名称, tb in 失败:
        print(f"[失败] {名称}\n{tb}")
    for 名称, why in 跳过:
        print(f"[跳过] {名称} —— {why}")
    print(f"合计：通过 {通过} 项，失败 {len(失败)} 项，跳过 {len(跳过)} 项")
    sys.exit(1 if 失败 else 0)


if __name__ == "__main__":
    main()
