#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零件图画法口径闸 —— 直接量生成的 SVG 几何，不信任脚本注释、也不信任「测试全绿」。

用法：python3 verify_drawing_conventions.py 图1.svg [图2.svg ...]
退出码 0 = 全绿；1 = 有违例（可直接当提交闸 / 交付前最后一关）。

为什么量 SVG 而不是量脚本：脚本注释写着「贯穿全径」、单测只数元素个数时，图上照样可能
只有一半尺寸线、界线停在尺寸线前 2 mm。只有量线段的端点、箭头的顶点、文字的锚点，
才能抓出这类错。

坐标约定（最容易踩）：gbdraw 的 `Sheet` 输出 SVG 时把 y 翻成 `H - y_sheet`。
图上「上方」= SVG 里 y 更小。所以量出来的 y 关系与图纸坐标符号相反，写判据时别再把
方向翻第二次（图元已翻过一次，bbox 再翻就全线误判越界）。

判据（用户逐条纠正过的口径，每条都要能失败）：
  R1 全文仿宋且 STFangsong 在前
  R2 线宽只有 0.5 / 0.25 两档（GB/T 4457.4）
  R3 箭头（实心三角）外接尺寸 1.0~3.6 mm
  R5 每条尺寸线两端，尺寸界线越过尺寸线 ≥1.9 mm
  R6 水平尺寸数字在尺寸线上方 0.6~3.0 mm
  R7 竖直尺寸线贯穿（≥4 mm）
  R8 竖直尺寸数字在尺寸线左侧（SVG x 更小）
  R9 直径 φ 值不落在尺寸线中点（那是中心线高度，会压线）

注意 R9 只对 φ/⌀ 文字生效：长度/深度尺寸（62.5、74.9 这类）的数字**就该**在尺寸线中段，
对它们套用「避开中点」会全部误报。
"""
from __future__ import annotations

import re
import sys

LINE = re.compile(r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)" class="(\w+)"')
TEXT = re.compile(r'<text x="([-\d.]+)" y="([-\d.]+)" font-size="([-\d.]+)"([^>]*)>(.*?)</text>')
POLY = re.compile(r'<polygon points="([^"]+)"')
STYLE = re.compile(r'\.(\w+)\{([^}]*)\}')

失败 = []


def 判(名, 好, 说明=""):
    print("  %s %-34s %s" % ("✓" if 好 else "✗", 名, 说明))
    if not 好:
        失败.append("%s: %s" % (名, 说明))


def 载(path):
    s = open(path, encoding="utf-8").read()
    线 = [(float(a), float(b), float(c), float(d), e) for a, b, c, d, e in LINE.findall(s)]
    字 = [(float(a), float(b), float(c), d, e) for a, b, c, d, e in TEXT.findall(s)]
    三角 = [[tuple(map(float, p.split(","))) for p in q.split()] for q in POLY.findall(s)]
    样式 = dict(STYLE.findall(s))
    return s, 线, 字, 三角, 样式


def 主(path):
    s, 线, 字, 三角, 样式 = 载(path)
    print("\n=== %s" % path.split("/")[-1])

    def 有箭头(x, y):
        return any(abs(p[0] - x) < 0.4 and abs(p[1] - y) < 0.4 for p in 三角)

    判("R1 仿宋 STFangsong", "STFangsong" in s and s.index("STFangsong") < s.index("serif"),
       "字体声明%s" % ("有" if "STFangsong" in s else "缺"))
    宽 = sorted({round(float(re.search(r"stroke-width:([\d.]+)", v).group(1)), 2)
                 for v in 样式.values() if "stroke-width" in v})
    判("R2 线宽只有两档", 宽 == [0.25, 0.5], "实测 %r" % (宽,))

    尺寸 = [max(max(p[0] for p in t) - min(p[0] for p in t),
                max(p[1] for p in t) - min(p[1] for p in t)) for t in 三角]
    坏 = [round(d, 2) for d in 尺寸 if not (1.0 <= d <= 3.6)]
    判("R3 箭头尺寸 1.0~3.6mm", not 坏, "三角 %d 个，越界 %d" % (len(尺寸), len(坏)))

    # 尺寸线 = 两端都有箭头尖的线（只靠「长细线」会把引线尾、表格线一起算进去）
    横 = [l for l in 线 if abs(l[1] - l[3]) < 1e-6 and abs(l[2] - l[0]) >= 8
          and 有箭头(l[0], l[1]) and 有箭头(l[2], l[3])]
    竖 = [l for l in 线 if abs(l[0] - l[2]) < 1e-6 and abs(l[3] - l[1]) >= 4
          and 有箭头(l[0], l[1]) and 有箭头(l[0], l[3])]

    不越 = []
    for l in 横:
        y = l[1]
        for xe in (l[0], l[2]):
            段s = [v for v in 线 if abs(v[0] - xe) < 0.05 and abs(v[2] - xe) < 0.05]
            if not 段s:
                不越.append((round(xe, 1), round(y, 1), "无界线"))
                continue
            越 = max(max(max(v[1], v[3]) - y, y - min(v[1], v[3])) for v in 段s)
            if 越 < 1.9:
                不越.append((round(xe, 1), round(y, 1), round(越, 2)))
    判("R5 界线越过尺寸线 ≥1.9mm", not 不越,
       "尺寸线 %d 条，未越出 %d 端 %r" % (len(横), len(不越), 不越[:3]))

    错 = []
    for x, y, h, attr, txt in 字:
        if "rotate" in attr:
            continue
        上 = [l[1] for l in 横 if min(l[0], l[2]) - 0.5 <= x <= max(l[0], l[2]) + 0.5
              and 0 < y - l[1] <= 3.4]
        if not 上:
            continue
        if not (0.6 <= min(y - d for d in 上) <= 3.0):
            错.append((txt.strip(), round(y - 上[0], 2)))
    判("R6 数字在尺寸线上方", not 错, "违例 %d %r" % (len(错), 错[:3]))

    问题7, 问题8, 问题9 = [], [], []
    for x, y, h, attr, txt in 字:
        if "rotate" not in attr or not re.match(r"^[(（]?[φ⌀]?\d", txt.strip()):
            continue
        near = [v for v in 竖 if abs(v[0] - x) <= 3.0]
        if not near:
            continue
        v = max(near, key=lambda q: abs(q[3] - q[1]))
        长 = abs(v[3] - v[1])
        中 = (v[1] + v[3]) / 2
        if 长 < 4:
            问题7.append((txt.strip(), round(长, 1)))
        if x >= v[0]:                       # 数字必须在尺寸线左侧
            问题9.append((txt.strip(), round(x - v[0], 2)))
        if ("φ" in txt or "⌀" in txt) and abs(y - 中) < 2.0:
            问题8.append((txt.strip(), round(y - 中, 2)))
    判("R7 竖直尺寸线贯穿", not 问题7, "%r" % (问题7[:3],))
    判("R8 竖直数字在尺寸线左侧", not 问题9, "%r" % (问题9[:3],))
    判("R9 φ 值不压中心线", not 问题8, "%r" % (问题8[:3],))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    for p in sys.argv[1:]:
        主(p)
    print("\n%s（失败 %d 条）" % ("全绿" if not 失败 else "有违例", len(失败)))
    for f in 失败:
        print("  -", f)
    sys.exit(1 if 失败 else 0)
