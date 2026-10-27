# -*- coding: utf-8 -*-
"""thread_left.py —— 图8-21 的左视图（批2 补做项，不改已验收的 thread.py）

依据：图8-21 p.227 [核]（(a) 内、外螺纹连接时的左视图）
  外圈：被连接件/螺母外轮廓，粗实线；
  大径圆：内螺纹大径 D，细实线，只画约 3/4 圈（缺口在右下）；
  小径圆：旋合后的螺纹小径 D1=0.85D，粗实线整圆；
  中心线：细点画线十字，伸出外圈 4 mm。
说明：外圈半径取 1.6d（页图未给外径数值，示意），docstring 标明。
"""
import sys
from pathlib import Path

MDKIT = Path(__file__).resolve().parents[2]
if str(MDKIT) not in sys.path:
    sys.path.insert(0, str(MDKIT))

from lib.drawing._prim import 图形, 校验图元, 线, 圆, 弧, 文  # noqa: E402

小径系数 = 0.85
外圈系数 = 1.6


def 螺纹连接左视图(d=20.0, x=0.0, y=0.0, 缺口起角=270.0):
    """内、外螺纹旋合后的左视图（轴线垂直纸面）。

    依据：图8-21(a) p.227 [核]。
      粗实线整圆 = 螺纹小径 D1=0.85d；细实线 3/4 圆弧 = 内螺纹大径 D=d；
      粗实线外圆 = 被连接件外轮廓（1.6d，示意）；细点画线十字伸出外圆 4。
    缺口起角=270：大径圆弧从 0° 逆时针画到 270°，缺口落在 270°~360°（右下）。
    """
    if d <= 0:
        raise ValueError("d 必须 > 0")
    if not (0 < 缺口起角 < 360):
        raise ValueError("缺口起角须在 (0,360) 内")
    R外 = 外圈系数 * d
    R = d / 2.0
    R1 = 小径系数 * d / 2.0

    g = 图形()
    g.加(圆(x, y, R外, "thick"))                 # 被连接件外轮廓
    g.加(弧(x, y, R, 0.0, 缺口起角, "thin"))       # 大径：细实线 3/4 圈
    g.加(圆(x, y, R1, "thick"))                  # 小径：粗实线整圆
    引 = R外 + 4
    g.加(线(x - 引, y, x + 引, y, "center"),
         线(x, y - 引, x, y + 引, "center"))
    g.注(f"左视图：细实线 3/4 圈 = 内螺纹大径 d={d:g}；粗实线整圆 = 小径 D1=0.85d={2 * R1:g}",
         f"外圈 1.6d={2 * R外:g} 为被连接件外轮廓（示意，页图未给外径）")
    g.范围(x - 引, y - 引, x + 引, y + 引)
    return g


if __name__ == "__main__":
    g = 螺纹连接左视图()
    ok, msg = 校验图元(g.elems)
    print(msg, len(g), g.bbox)
