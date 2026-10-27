# -*- coding: utf-8 -*-
"""batch5_figures.py —— 批5 靶子图（ch2/ch3/ch4/ch5）

图2-43 正六棱柱三视图（p.57）
图3-48 圆柱与圆柱相贯（p.100）
图4-11 叠加型组合体三视图（p.113）
图4-30 组合体尺寸标注（p.129）
图5-4  长方体正等轴测 + 轴测轴（p.136）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing import projection, revolve, combined, axonometric  # noqa: E402
from lib.drawing._prim import 图形, 文, 拼, 落图, 校验图元  # noqa: E402

OUT = Path(__file__).resolve().parent


def fig2_43():
    g = projection.棱柱三视图(6, 25, 45, x=105, y=95)
    g.加(文(148.5, 18, "图2-43 正六棱柱的三面投影（p.57）", 4.2))
    return g


def fig3_48():
    g = revolve.相贯线(20, 15, 50, 60, x=100, y=95)
    g.加(文(148.5, 18, "图3-48 圆柱与圆柱相贯（p.100）", 4.2))
    return g


def fig4_11():
    g = combined.组合体三视图(60, 40, 25, 24, 12, x=90, y=95)
    g.加(文(148.5, 18, "图4-11 叠加型组合体的三视图（p.113）", 4.2))
    return g


def fig4_30():
    g = combined.组合体尺寸(60, 40, 25, 24, 12, x=90, y=100)
    g.加(文(148.5, 18, "图4-30 组合体的尺寸标注（p.129）", 4.2))
    return g


def fig5_4():
    g = 拼(axonometric.正等轴测(60, 40, 30, x=80, y=40),
           axonometric.轴测轴("正等测", 40, x=220, y=40))
    g.加(文(148.5, 18, "图5-4 长方体正等轴测与轴测轴（p.136）", 4.2))
    return g


FIGURES = {"fig2-43": fig2_43, "fig3-48": fig3_48, "fig4-11": fig4_11,
           "fig4-30": fig4_30, "fig5-4": fig5_4}
PAGE = {k: (297, 210) for k in FIGURES}


def main():
    for name, fn in FIGURES.items():
        g = fn()
        ok, msg = 校验图元(g.elems)
        assert ok, f"{name}: {msg}"
        w, h = PAGE[name]
        p = 落图(g, OUT / f"{name}.svg", w=w, h=h)
        print(f"{name}: {len(g)} 图元  {msg}  bbox={tuple(round(v,1) for v in g.bbox)} -> {Path(p).name}")


if __name__ == "__main__":
    main()
