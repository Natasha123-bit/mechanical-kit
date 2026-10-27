# -*- coding: utf-8 -*-
"""batch2_figures.py —— 批2 靶子图（ch1 图线/图幅 + ch6 剖视/断面/放大）

靶子（页码按 E.json 勘误后的实际页）：
  表1-3 图线及应用（9 种）              p.11–12  ★任务书误写“图1-x p.6–8”
  A3 图框 + 标题栏（图1-12/图1-15）      p.8–9
  全剖/半剖/局部剖 + 剖切符号（图6-13/6-15/6-16） p.151–153
  移出/重合断面（图6-38/6-44）           p.161/163
  局部放大（图6-45）                     p.164

用法：/usr/bin/python3 batch2_figures.py [--only fig1-3]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing import sheet, standards, section, thread_left  # noqa: E402
from lib.drawing._prim import 图形, 文, 拼, 落图, 校验图元  # noqa: E402

OUT = Path(__file__).resolve().parent


def fig1_3():
    g = standards.线型表(x=15, y=190, 样长=65, 行距=13)
    g.加(文(148.5, 14, "表1-3 机械制图的图线及应用（9 种；线宽 0.5/0.25 两档）", 4.2))
    return g


def fig1_sheet():
    g = 拼(sheet.图框("A3", 装订边="左", 横放=True),
           sheet.标题栏(件名="主动轴", 材料="45", 比例="1:1", 图号="R01",
                    设计="张三", 审核="李四", 日期="2026-10",
                    单位名称="机械制图标准库"))
    g.加(文(40, 278, "图1-12 留装订边的图框 / 图1-15 标题栏（A3 横放，左装订 a=25、c=5）", 4.2,
            anchor="start"))
    return g


def fig6_section():
    g = 图形()
    g.加(section.剖视(类型="全剖", cx=70, cy=140, 宽=64, 高=44, 孔半径=9),
         文(70, 175, "全剖（图6-13）", 4))
    g.加(section.剖视(类型="半剖", cx=170, cy=140, 宽=64, 高=44, 孔半径=9),
         文(170, 175, "半剖（图6-15；分界为细点画线）", 4))
    g.加(section.剖视(类型="局部剖", cx=70, cy=65, 宽=64, 高=44, 孔半径=9),
         文(70, 100, "局部剖（图6-16；波浪线边界）", 4))
    g.加(section.剖切符号(方向="竖", 长度=44, 字母="A", x=170, y=68, 间隔=4),
         文(170, 100, "剖切符号 A—A（粗短画 + 垂直箭头）", 4))
    return g


def fig6_break():
    g = 图形()
    g.加(section.断面(类型="移出", x=50, y=120, 宽=40, 高=20),
         文(70, 158, "移出断面（粗实线，图6-38）", 4))
    g.加(section.断面(类型="重合", x=190, y=120, 宽=40, 高=20),
         文(200, 158, "重合断面（细实线，视图轮廓连续，图6-44）", 4))
    g.注("移出断面轮廓粗实线；重合断面轮廓细实线且叠在视图内，视图轮廓不断开")
    return g


def fig8_21_left():
    g = thread_left.螺纹连接左视图(d=20.0, x=148.0, y=105.0)
    g.加(文(148.5, 14, "图8-21(a) 左视图（细实线 3/4 圈 = 内螺纹大径；粗实线整圆 = 小径）", 4.2))
    return g


def fig6_detail():
    g = section.局部放大(半径=12, 比例=2.0, 罗马数字="I", x=70, y=110)
    g.加(文(148.5, 14, "图6-45 局部放大图（细实线圈示 + 2:1）", 4.2))
    return g


FIGURES = {
    "fig1-3": fig1_3,
    "fig1-sheet": fig1_sheet,
    "fig6-section": fig6_section,
    "fig6-break": fig6_break,
    "fig6-detail": fig6_detail,
    "fig8-21-left": fig8_21_left,
}
PAGE = {
    "fig1-3": (297, 210),
    "fig1-sheet": (420, 297),
    "fig6-section": (297, 210),
    "fig6-break": (297, 210),
    "fig6-detail": (297, 210),
    "fig8-21-left": (297, 210),
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
        print(f"{name}: {len(g)} 图元  {msg}  bbox={tuple(round(v, 1) for v in g.bbox)}  -> {Path(p).name}")


if __name__ == "__main__":
    main()
