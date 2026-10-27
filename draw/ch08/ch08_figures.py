# -*- coding: utf-8 -*-
"""ch08_figures.py —— 批1 靶子图反演（一张图一页 A3，供 Chrome→PDF→PNG 链）

靶子（任务书第 5 节，页码按 E.json 勘误后的实际页）：
  图8-21 内、外螺纹连接时的画法（主视图）      p.227  ★任务书靶子
  图8-23 螺纹结构的正确标注                    p.230  ★任务书靶子
  图8-40 钩头楔键连接图                        p.239  ★任务书靶子
  图8-54 齿轮啮合的画法一（剖视 + 五线放大）    p.245  ★任务书误写为图8-51
  图8-60 圆柱螺旋压缩弹簧的画法                p.248  ★任务书靶子
  表8-9 6206 深沟球轴承（上半规定 + 下半通用） p.253  轴承优先项

用法：/usr/bin/python3 ch08_figures.py [--only fig8-21]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing import thread, key, gear, spring, bearing  # noqa: E402
from lib.drawing._prim import 图形, 文, 平移, 落图, 校验图元  # noqa: E402

OUT = Path(__file__).resolve().parent


def fig8_21():
    g = thread.螺纹连接画法(d=20.0, P=2.5, 旋合长度=25.0, 板长=60.0, 板厚=40.0,
                        x0=50.0, y轴=130.0)
    g.加(文(148.5, 14, "图8-21 内、外螺纹连接时的画法（主视图；旋合段按外螺纹绘制）", 4.2))
    return g


def fig8_23():
    g = 图形()
    g.加(thread.内螺纹画法(d=20.0, P=2.0, 螺纹长=30.0, 孔深=40.0, x0=40.0, y轴=126.0))
    g.加(thread.螺纹标注(d=20.0, P=2.0, 类型="内", 公差带="6H", x=68.0, y=126.0))
    g.加(thread.外螺纹画法(d=20.0, P=2.0, 螺纹长=30.0, 杆长=45.0, x0=40.0, y轴=45.0))
    g.加(thread.螺纹标注(d=20.0, P=2.0, 类型="外", 公差带="6h", x=92.0, y=45.0))
    g.加(文(148.5, 14, "图8-23 螺纹结构的正确标注（标记落在大径尺寸线上）", 4.2))
    return g


def fig8_40():
    g = 平移(key.钩头楔键连接画法(d=30.0, b=8.0, h=8.0, L=30.0), 40.0, 120.0)
    g.加(文(148.5, 14, "图8-40 钩头楔键连接图（两侧面有间隙：每侧两条线；顶面楔紧贴合）", 4.2))
    return g


def fig8_54():
    g = gear.齿轮啮合画法(m=2.0, z1=29, z2=47, 齿宽=20.0, 剖视=True, cx1=80.0, cy=120.0, 放大=3.0)
    g.加(文(148.5, 14, "图8-54 齿轮啮合的画法一（五线：2 齿根粗 + 2 齿顶一粗一虚 + 1 节线）", 4.2))
    return g


def fig8_60():
    g = spring.弹簧画法(d=8.0, D2=48.0, H0=96.0, t=13.0, n=5, 支承圈=2.5, 剖视=True,
                     cx=148.0, y0=45.0)
    g.加(文(148.5, 14, "图8-60 圆柱螺旋压缩弹簧的画法（支承圈 2.5；断面圆 + 相切公切线）", 4.2))
    return g


def fig8_64():
    g = bearing.轴承画法(d=30.0, D=62.0, B=16.0, 类型="深沟球", 画法="规定", 半剖=True,
                     cx=148.0, cy=105.0)
    g.加(文(148.5, 14, "表8-9 / 图8-64c 6206 深沟球轴承（上半规定画法，下半通用画法）", 4.2))
    return g


FIGURES = {
    "fig8-21": fig8_21,
    "fig8-23": fig8_23,
    "fig8-40": fig8_40,
    "fig8-54": fig8_54,
    "fig8-60": fig8_60,
    "fig8-64": fig8_64,
}


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name, fn in FIGURES.items():
        if only and name != only:
            continue
        g = fn()
        ok, msg = 校验图元(g.elems)
        assert ok, f"{name}: {msg}"
        p = 落图(g, OUT / f"{name}.svg")
        print(f"{name}: {len(g)} 图元  {msg}  bbox={tuple(round(v, 1) for v in g.bbox)}  -> {Path(p).name}")


if __name__ == "__main__":
    main()
