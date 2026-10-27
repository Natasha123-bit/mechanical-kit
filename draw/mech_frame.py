#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mech_frame —— 轴系“非零件图”三件套：轴草图 / 力学模型图 / 弯矩图 / 转矩图。

为什么单开一层：`gbdraw.py` 只有零件图图元（轮廓、尺寸、公差、剖面线），
而说明书里的轴草图、简化力学模型、弯矩/转矩图以前是逐题手写 SVG，每换一道题
重写一遍坐标与标注链。这一层只做「排布 + 标注链」，图元、线型、字高仍走 gbdraw，
**1 用户单位 = 1 mm**（与 gbdraw 相同）。

坐标：y 向上（图纸习惯）。四个函数都在给定 `Sheet` 上以 (x0, y0) 为锚点画，
并返回本次占用的外框 (x_min, y_min, x_max, y_max)，方便上下叠放：
    外框 = 轴草图(...)          # 画在上面
    力学模型(sheet, x0, 外框[3] + 8, ...)

画法口径清单（每条都有出处，出图前逐条对，别靠记忆）：
  1. 台阶面竖线**贯穿较大直径全高** —— 源：设计测试/图纸/输出轴零件图.py:91
  2. 直径尺寸：尺寸线**贯穿整个直径**、上下两端箭头朝外顶轮廓、不越出轮廓；
     φ 值竖排在尺寸线左侧；**连续同径段只标一次**；**不许用引线拉出去标**
  3. 长度尺寸界线：起于轮廓外 0.5 mm，**越过尺寸线再出 2 mm** —— 用户 2026-10-26 反复强调
  4. 长度箭头两端都画，窄段箭头外置 —— 源：同文件长度尺寸链
  5. 件号：引杆（细竖线）+ 箭头指轮廓 + 文字，引线落点避让 ⌀ 文字
  6. 轴线（细点画线）两端各出 4 mm
  7. 一切元素落在图幅内；外框由函数返回给调用方叠放
  以上 7 条在 draw/mech_frame_tests.py 里都是断言，改图先跑测试。

不做什么：
  * 不算支座反力、不算弯矩值 —— 那是 `lib/design/` 的活，这里只画。
  * 不选比例规则 —— 比例（mm图上/mm实际）由调用方按图幅给。
  * 不改 gbdraw 的线型表与字高。

用法（`python3 draw/mech_frame.py` 会画一张自检图到 scratch）：

    from gbdraw import Sheet
    from mech_frame import 轴草图, 力学模型, 弯矩图, 转矩图

    s = Sheet(210, 120, title="图2 高速轴结构草图")
    轴草图(s, [(0, 48, 25, "cyl", "带轮"), (48, 93, 30, "cyl", "密封"), ...],
          x0=20, y0=80, 比例=0.45, 件号=[(102.1, "左轴承 30207")])
    力学模型(s, 20, 40, 跨度=215.25, 载荷点=158.7, 载荷=[(158.7, "F_t", 6109.6, "down")])
    弯矩图(s, 20, 25, 位置=[0, 158.7, 215.25], 值=[0, 382059, 0], 跨度=215.25)
    s.write("fig.svg")
"""
from __future__ import annotations

import math

try:                                   # 作为 draw 包的一部分导入
    from .gbdraw import (Sheet, L, RECT, T, ARROW, PATH, text_w, TEXT_H, TEXT_S, _n)
except ImportError:                    # 直接跑脚本 / 在 draw/ 里 import
    from gbdraw import (Sheet, L, RECT, T, ARROW, PATH, text_w, TEXT_H, TEXT_S, _n)


# ============================================================ 小工具
def _poly(pts, style="thick", fill="none"):
    """折线/多边形（poly 图元；fill="solid" 是实心黑，其它给 none）。"""
    return ("poly", dict(pts=pts, style=style, fill=fill))


def _虚线填充(折线, 轴y, 间距=1.6, 高=1.0):
    """弯矩/转矩图的竖向细线填充：沿折线每 间距 一根，从轴画到曲线。

    不用 fill：gbdraw 的 CSS 里 .thin{fill:none} 会盖掉元素的 fill 属性，
    所以实心填充只能走 polygon.solid（纯黑），这里改用细线填充，浅且能印。
    """
    out = []
    if len(折线) < 2:
        return out
    xs = [p[0] for p in 折线]
    x = min(xs)
    while x <= max(xs) + 1e-9:
        y = _插值(折线, x)
        if abs(y - 轴y) > 0.25:
            out.append(L(x, 轴y, x, y, "thin"))
        x += 间距
    return out


def _插值(折线, x):
    """折线（按 x 升序）在 x 处的 y。"""
    if x <= 折线[0][0]:
        return 折线[0][1]
    for (x1, y1), (x2, y2) in zip(折线, 折线[1:]):
        if x1 <= x <= x2:
            if abs(x2 - x1) < 1e-9:
                return y2
            t = (x - x1) / (x2 - x1)
            return y1 + t * (y2 - y1)
    return 折线[-1][1]


# ============================================================ 轴草图
def 轴草图(sheet, 段表, x0, y0, 比例=0.45, 件号=(), 尺寸链=True,
           直径标注=True, 字高=TEXT_H, 标注字号=TEXT_S, 齿顶圆=False):
    """阶梯轴草图（工序图，不画倒角/圆角，按说明书“结构草图”惯例）。

    参数
    ----
    段表 : [(x起, x止, 直径, 类型, 说明), ...]   x、直径单位 mm
           类型 "cyl"  → 说明是件名文字（可空）
           类型 "gear" → 说明 = (齿顶圆直径, 齿根圆直径)；轮廓按**齿根圆**画，
                        齿顶圆用细虚线矩形表示（与说明书惯例一致）
    x0, y0 : 锚点。y0 是**轴线**的 y 坐标（不是外框底边）
    比例   : 图上 mm / 实际 mm，常见 0.4~0.6
    件号   : [(x实际, "左轴承 30207"), ...]，引线指向该 x 处轮廓顶边
    齿顶圆 : **默认不开**。只有齿轮轴（齿轮与轴一体）才开——那时 d_a 与轴径同量级。
             轴上另装的大齿轮 d_a 常是轴径的 3~4 倍（如 ⌀294 装在 ⌀70 上），
             照实画会把整幅草图撑爆；按说明书惯例只在件号里写「齿轮 4（d_a=294 见零件图）」。
    返回   : (x_min, y_min, x_max, y_max) 外框
    """
    xs = [s[0] for s in 段表] + [s[1] for s in 段表]
    x_lo, x_hi = min(xs), max(xs)
    dmax = max(s[2] for s in 段表)
    for s in 段表:
        if s[3] == "gear":
            if len(s) < 5 or not isinstance(s[4], (tuple, list)) or len(s[4]) != 2:
                raise ValueError("gear 段的说明要给 (齿顶圆, 齿根圆)：%r" % (s,))
    k = float(比例)
    r_max = dmax / 2 * k

    def PX(x):                        # 实际 x → 图上 x
        return x0 + (x - x_lo) * k

    cy = y0
    # 轴线：两端各出 4 mm
    sheet.add(L(PX(x_lo) - 4, cy, PX(x_hi) + 4, cy, "center"))

    # 轮廓：上沿正向 + 下沿反向，闭合成多边形（台阶竖线由折点自动生成）
    top, bot = [], []
    for s in 段表:
        a, b, d = s[0], s[1], s[2]
        r = d / 2 * k
        top += [(PX(a), cy + r), (PX(b), cy + r)]
        bot += [(PX(a), cy - r), (PX(b), cy - r)]
    sheet.add(_poly(top + bot[::-1], "thick"))

    # 台阶面竖线：**贯穿较大直径全高**（不是只连两个半径差）。
    # 这条口径来自 输出轴零件图.py:91「台阶面竖线贯穿较大直径全高」，
    # 之前只靠多边形的短竖边，视觉上等于没有封闭 —— 已被用户当面指出两次。
    for i in range(1, len(段表)):
        d_prev, d_cur = 段表[i - 1][2], 段表[i][2]
        if abs(d_prev - d_cur) < 1e-9:
            continue
        xb = PX(段表[i][0])
        r_big = max(d_prev, d_cur) / 2 * k
        sheet.add(L(xb, cy - r_big, xb, cy + r_big, "thick"))

    # 齿轮段：齿顶圆（细虚线）+ 齿根圆（细实线，与轮廓重合处不重复画）
    if 齿顶圆:
        for s in 段表:
            if s[3] != "gear":
                continue
            da, df = s[4]
            w = (s[1] - s[0]) * k
            sheet.add(RECT(PX(s[0]), cy - da / 2 * k, w, da * k, "hidden"))
            if abs(df - s[2]) > 1e-9:  # 齿根圆与轮廓不同径时才补线
                for sgn in (+1, -1):
                    sheet.add(L(PX(s[0]), cy + sgn * df / 2 * k, PX(s[1]), cy + sgn * df / 2 * k, "thin"))

    # ---- 直径尺寸线：尺寸线**贯穿整个直径**，两端箭头朝外顶住轮廓，
    # φ 值**写在尺寸线上**（竖排、紧贴尺寸线左侧，不从轮廓拉引线出去）。
    # 同一直径的连续段只标一次（⌀60 连着两段只出一个 ⌀60）。
    直径文字 = {}
    if 直径标注:
        段组 = []
        for i, seg in enumerate(段表):
            if 段组 and abs(段组[-1]["d"] - seg[2]) < 1e-9:
                段组[-1]["x2"] = seg[1]
                段组[-1]["idx"].append(i)
            else:
                段组.append({"x1": seg[0], "x2": seg[1], "d": seg[2], "idx": [i]})
        for g in 段组:
            xm = PX((g["x1"] + g["x2"]) / 2)
            r = g["d"] / 2 * k
            txt = "⌀%s" % _n(g["d"])
            ad = min(3.0, r * 0.5)
            sheet.add(L(xm, cy - r, xm, cy + r, "thin"))
            sheet.add(ARROW(xm, cy + r - ad, xm, cy + r))
            sheet.add(ARROW(xm, cy - r + ad, xm, cy - r))
            # 数字紧贴尺寸线左侧、上半区（避开中心线）
            sheet.add(T(xm - 0.8, cy + r * 0.40, txt, 标注字号, rotate=-90))
            for i in g["idx"]:
                直径文字[i] = (xm, text_w(txt, 标注字号) / 2)
    # ---- 件号：引线自上方指到轮廓顶边
    for j, item in enumerate(件号):
        xa, txt = item[0], item[1]
        # 找该 x 所在段，取其顶边 y
        d_here, idx = None, None
        for i, s in enumerate(段表):
            if s[0] - 1e-9 <= xa <= s[1] + 1e-9:
                d_here, idx = s[2], i
                break
        if d_here is None:
            continue
        # 落点若正压在 ⌀ 文字上，改指到该段的台阶处（左端优先）
        落点 = xa
        if idx in 直径文字:
            中心, 半宽 = 直径文字[idx]
            if abs(PX(xa) - 中心) <= 半宽 + 1.5:
                seg = 段表[idx]
                落点 = seg[0] + 0.6 if abs(xa - seg[0]) <= abs(xa - seg[1]) else seg[1] - 0.6
        y_top = cy + d_here / 2 * k
        y_lbl = cy + r_max + 9 + (j % 2) * (字高 * 1.9)
        y_tip = y_top + 0.8
        sheet.add(ARROW(PX(落点), y_tip + 3.0, PX(落点), y_tip))      # 箭头朝轮廓
        sheet.add(L(PX(落点), y_tip + 3.0, PX(落点), y_lbl, "thin"))  # 引杆（原来漏了，只剩箭头悬空）
        sheet.add(T(PX(xa), y_lbl + 2.6, txt, 标注字号))

    # ---- 尺寸链：轴线下方，长度分两档，最后一行总长
    y_min = cy - r_max
    if 尺寸链:
        row = y_min - 7.0
        窄 = [(s[1] - s[0]) * k < 12 for s in 段表]
        for i, s in enumerate(段表):
            a, b = s[0], s[1]
            yy = row - (字高 * 1.9 if 窄[i] and i % 2 else 0)
            sheet.add(L(PX(a), yy, PX(b), yy, "thin"))
            # 箭头朝外顶尺寸界线；段太窄时箭头画在外侧
            if (b - a) * k >= 8:
                sheet.add(ARROW(PX(a) + 2.6, yy, PX(a), yy))
                sheet.add(ARROW(PX(b) - 2.6, yy, PX(b), yy))
            else:
                sheet.add(ARROW(PX(a) - 1.2, yy, PX(a) - 5.0, yy))
                sheet.add(ARROW(PX(b) + 1.2, yy, PX(b) + 5.0, yy))
            # 尺寸界线：起于轮廓外 0.5 mm，**越过尺寸线再伸出 2 mm**（用户反复强调的口径）。
            # 旧写法 max(y_edge-0.5, yy-2.0) 恒等于 y_edge-0.5，等于界线只到轮廓、不越过尺寸线。
            y_edge = cy - s[2] / 2 * k
            for xx in (PX(a), PX(b)):
                sheet.add(L(xx, y_edge - 0.5, xx, yy - 2.0, "thin"))
            # 数字写在尺寸线**上方**（GB：字头向上、距线约 1 mm）
            sheet.add(T((PX(a) + PX(b)) / 2, yy + 1.2, _n(b - a), 标注字号))
            y_min = min(y_min, yy - 3.0)
        y_total = y_min - 6.0
        sheet.add(L(PX(x_lo), y_total, PX(x_hi), y_total, "thin"))
        sheet.add(ARROW(PX(x_lo) + 2.6, y_total, PX(x_lo), y_total))
        sheet.add(ARROW(PX(x_hi) - 2.6, y_total, PX(x_hi), y_total))
        for xx in (PX(x_lo), PX(x_hi)):
            sheet.add(L(xx, y_total + 3.0, xx, y_total - 2.0, "thin"))
        sheet.add(T((PX(x_lo) + PX(x_hi)) / 2, y_total + 1.2,
                    "总长 %s" % _n(x_hi - x_lo), 标注字号))
        y_min = y_total - 3.0

    return (PX(x_lo) - 5, y_min, PX(x_hi) + 5, cy + r_max + 9 + 字高 * 1.9 + 4)


# ============================================================ 力学模型
def 力学模型(sheet, x0, y0, 跨度, 载荷点=None, 载荷=(), 反力=(),
             比例=0.45, 支点=("A", "B"), 字号=TEXT_S, 力臂=26.0):
    """简支梁（轴系）简化力学模型：梁 + 铰支座 + 集中力/力偶。

    载荷 : [(x, "F_t", 6109.6, "down"), ...]  x 为距左支点 mm；"down"/"up"
    反力 : [(x, "R_A", 3500.0), ...]          画成向上的箭头，标在下侧
    返回 : 外框
    """
    k = float(比例)
    L_ = float(跨度)

    def PX(x):
        return x0 + x * k

    sheet.add(L(PX(0), y0, PX(L_), y0, "thick"))
    # 铰支座：三角 + 底线
    for x, nm in ((0.0, 支点[0]), (L_, 支点[1])):
        xx = PX(x)
        sheet.add(_poly([(xx, y0 - 0.6), (xx - 3.2, y0 - 6.0), (xx + 3.2, y0 - 6.0)], "thin"))
        sheet.add(L(xx - 5.0, y0 - 6.0, xx + 5.0, y0 - 6.0, "thin"))
        sheet.add(T(xx, y0 - 9.2, nm, 字号))
    # 集中力
    for item in 载荷:
        x, nm, val, sgn = item[0], item[1], item[2], item[3]
        xx = PX(x)
        if sgn == "down":
            sheet.add(ARROW(xx, y0 + 力臂, xx, y0))
            sheet.add(T(xx + 2.2, y0 + 力臂 - 1.2, "%s = %s N" % (nm, _n(val)), 字号, anchor="start"))
        else:
            sheet.add(ARROW(xx, y0, xx, y0 - 力臂))
            sheet.add(T(xx, y0 - 力臂 - 4.0, "%s = %s N" % (nm, _n(val)), 字号))
    # 反力
    for item in 反力:
        x, nm, val = item[0], item[1], item[2]
        xx = PX(x)
        sheet.add(ARROW(xx, y0 - 8.6, xx, y0 - 8.6 - 力臂 * 0.55))
        sheet.add(T(xx, y0 - 8.6 - 力臂 * 0.55 - 3.2, "%s = %s N" % (nm, _n(val)), 字号))
    return (PX(0) - 8, y0 - 8.6 - 力臂 * 0.55 - 8, PX(L_) + 8, y0 + 力臂 + 6)


# ============================================================ 弯矩图 / 转矩图
def 弯矩图(sheet, x0, y0, 位置, 值, 跨度, 比例=0.45, 高度=22.0,
           标题="", 求拉侧=None, 单位="N·mm", 字号=TEXT_S):
    """弯矩图：折线 + 竖向细线填充 + 极值标注。零线横穿。

    位置 : 距左支点 mm 的采样点（升序）
    值   : 同长度的弯矩值（正负号保留；正=画在零线上方）
    高度 : 最大值画到多少 mm（图上）
    求拉侧 : None=按值符号画；"上"/"下"=把图翻到该侧（画弯矩图的工程习惯）
    返回 : 外框
    """
    k = float(比例)
    L_ = float(跨度)

    def PX(x):
        return x0 + x * k

    最大值 = max(abs(v) for v in 值) or 1.0
    比例v = 高度 / 最大值
    折线 = [(PX(x), y0 + v * 比例v) for x, v in zip(位置, 值)]
    if 求拉侧 == "上":
        折线 = [(x, y0 + abs(y0 - y)) for x, y in 折线]
    elif 求拉侧 == "下":
        折线 = [(x, y0 - abs(y0 - y)) for x, y in 折线]

    sheet.add(L(PX(0), y0, PX(L_), y0, "thin"))
    sheet.add(_poly(折线, "thick"))
    for e in _虚线填充(折线, y0):
        sheet.add(e)
    # 极值标注：找 |值| 最大点
    imax = max(range(len(值)), key=lambda i: abs(值[i]))
    xm, ym = 折线[imax]
    sheet.add(T(xm, ym + (2.6 if ym >= y0 else -4.2),
                "%s %s" % (_n(abs(值[imax])), 单位), 字号))
    if 标题:
        sheet.add(T(PX(0) - 3, y0 + 1.6, 标题, 字号, anchor="end"))
    ys = [y for _, y in 折线]
    return (PX(0) - 8, min(min(ys), y0) - 6, PX(L_) + 8, max(max(ys), y0) + 6)


def 转矩图(sheet, x0, y0, 段值, 跨度, 比例=0.45, 高度=18.0,
           标题="T", 单位="N·mm", 字号=TEXT_S):
    """转矩图：分段常值的阶梯图。

    段值 : [(x起, x止, T值), ...]（距左支点 mm）
    返回 : 外框
    """
    k = float(比例)
    L_ = float(跨度)
    PX = lambda x: x0 + x * k
    最大值 = max(abs(t) for _, _, t in 段值) or 1.0
    sv = 高度 / 最大值
    折线 = []
    for a, b, t in 段值:
        折线 += [(PX(a), y0 + t * sv), (PX(b), y0 + t * sv)]
    sheet.add(L(PX(0), y0, PX(L_), y0, "thin"))
    sheet.add(_poly(折线, "thick"))
    for e in _虚线填充(折线, y0, 间距=2.0):
        sheet.add(e)
    for a, b, t in 段值:
        sheet.add(T((PX(a) + PX(b)) / 2, y0 + t * sv + (2.4 if t >= 0 else -4.0),
                    "%s %s" % (_n(abs(t)), 单位), 字号))
    if 标题:
        sheet.add(T(PX(0) - 2, y0 + 3, 标题, 字号, anchor="end"))
    ys = [y for _, y in 折线]
    return (PX(0) - 8, min(min(ys), y0) - 6, PX(L_) + 8, max(max(ys), y0) + 6)


# ============================================================ 自检
def _demo(path):
    """自检图：低速轴草图 + 力学模型 + 弯矩图，数据取设计测试的低速轴。"""
    s = Sheet(210, 172, title="mech_frame 自检")
    段表 = [(-12, 12, 60, "cyl", "左轴承 30212"), (12, 97.9, 70, "cyl", ""),
            (97.9, 109.9, 80, "cyl", "轴环"), (109.9, 187.9, 70, "gear", (294.06, 280.56)),
            (187.9, 208.9, 60, "cyl", ""), (208.9, 232.6, 60, "cyl", "右轴承 30212"),
            (232.6, 277, 55, "cyl", "密封"), (277, 382, 50, "cyl", "联轴器段")]
    s.add(T(105, 5, "图 3　低速轴结构草图（mech_frame 生成）", 5.0))
    框 = 轴草图(s, 段表, x0=14, y0=128, 比例=0.44,
                件号=[(0, "左轴承 30212"), (145.9, "齿轮 4（d_a=294 见零件图）"),
                      (330, "联轴器 LX4")])
    y2 = 框[1] - 26
    力学模型(s, 14, y2, 跨度=220.75, 载荷点=145.875,
             载荷=[(145.875, "F_r", 2271.5, "down")], 比例=0.44, 力臂=14)
    弯矩图(s, 14, y2 - 28, 位置=[0, 145.875, 220.75], 值=[0, 382059, 0],
          跨度=220.75, 比例=0.44, 高度=14, 标题="M", 求拉侧="下")
    s.write(path)
    return path


if __name__ == "__main__":
    import os
    import tempfile
    out = os.path.join(tempfile.mkdtemp(), "mech_frame_demo.svg")
    print(_demo(out))
