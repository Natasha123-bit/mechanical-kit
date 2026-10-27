# -*- coding: utf-8 -*-
"""batch3_figures.py —— 批3 靶子图（ch7 零件图 + ch9 装配图）

图7-1  主动轴零件图（主视图 + A—A 键槽断面 + 局部放大 I + 尺寸/粗糙度/公差/技术要求）
图7-15 轴承架两种表达方案（a 主+俯+A—A；b 主+全剖左+A—A）
图7-20 减速箱盖视图（主 A—A + 俯 B—B + 左 + C 向；表达方案骨架）
图7-49 被测导出要素的标注示例（a 轴线/b 中心平面/c 球心）
图9-2  滑动轴承装配图（序号 + 明细栏 + 标题栏）
图9-25 齿轮泵泵体拆画（图9-30 的表达方案 + 尺寸/技术要求）

页码按 E.json 勘误：图7-15 p.182、图7-20 p.184、图7-49 p.207、图9-2 p.255、图9-25 p.276。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing import sheet, shaft, expression, assembly  # noqa: E402
from lib.drawing._prim import 图形, 文, 拼, 平移, 落图, 校验图元  # noqa: E402

OUT = Path(__file__).resolve().parent


def fig7_1():
    g = 拼(sheet.图框("A3"),
           sheet.标题栏(件名="主动轴", 材料="45", 比例="1:1", 图号="R01",
                    设计="张三", 审核="李四", 日期="2026-10"),
           平移(shaft.阶梯轴零件图(), 30.0, 180.0))
    g.加(文(40, 280, "图7-1 主动轴零件图（A—A 键槽断面 + 局部放大 I；尺寸为结构示意）", 4.2, anchor="start"))
    return g


def fig7_15():
    a = expression.表达方案("叉架", "a", cx=65.0, cy=125.0)
    b = expression.表达方案("叉架", "b", cx=180.0, cy=125.0)
    g = 拼(a, b)
    g.加(文(148.5, 195, "图7-15 轴承架的两种表达方案（p.182）", 4.2))
    return g


def fig7_20():
    g = expression.表达方案("箱体", "a", cx=90.0, cy=110.0)
    g.加(文(148.5, 200, "图7-20 减速箱盖视图（主 A—A + 俯 B—B + 左 + C 向，p.184）", 4.0))
    return g


def fig7_49():
    g = 平移(shaft.几何公差示例(), 20.0, 90.0)
    g.加(文(40, 280, "图7-49 被测导出要素的标注示例（a 圆柱轴线 / b 中心平面 / c 球心，p.207）",
             4.2, anchor="start"))
    return g


def fig9_2():
    g = 拼(sheet.图框("A3"),
           sheet.标题栏(件名="滑动轴承", 材料="—", 比例="1:1", 图号="Z01",
                    设计="张三", 审核="李四", 日期="2026-10", 单位名称="机械制图标准库"),
           assembly.明细栏(),
           平移(assembly.滑动轴承装配图(), 140.0, 170.0))
    g.加(文(40, 280, "图9-2 滑动轴承装配图（序号 1~5；明细栏；接触面一条线、相邻件剖面线相反）",
             4.2, anchor="start"))
    return g


def fig9_25():
    g = 拼(sheet.图框("A3"),
           sheet.标题栏(件名="泵体", 材料="HT150", 比例="1:1", 图号="B01",
                    设计="张三", 审核="李四", 日期="2026-10"),
           平移(assembly.拆画泵体零件图(), 120.0, 180.0))
    g.加(文(40, 280, "图9-25→9-30 齿轮泵泵体拆画（主视图 + A—A 全剖左视图 + B 向；尺寸示意）",
             4.2, anchor="start"))
    return g


FIGURES = {
    "fig7-1": fig7_1,
    "fig7-15": fig7_15,
    "fig7-20": fig7_20,
    "fig7-49": fig7_49,
    "fig9-2": fig9_2,
    "fig9-25": fig9_25,
}
PAGE = {
    "fig7-1": (420, 297),
    "fig7-15": (297, 210),
    "fig7-20": (297, 210),
    "fig7-49": (420, 297),
    "fig9-2": (420, 297),
    "fig9-25": (420, 297),
}


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name, fn in FIGURES.items():
        if only and name != only:
            continue
        g = fn()
        ok, msg = 校验图元(g.elems)
        assert ok, f"{name}: {msg}"
        w, h = PAGE[name]
        p = 落图(g, OUT / f"{name}.svg", w=w, h=h)
        print(f"{name}: {len(g)} 图元  {msg}  bbox={tuple(round(v,1) for v in g.bbox)}  -> {Path(p).name}")


if __name__ == "__main__":
    main()
