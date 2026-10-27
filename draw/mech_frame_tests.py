# -*- coding: utf-8 -*-
"""mech_frame.py 的测试：只验几何，不验审美。

判据取「可数、可复算」的东西：多边形顶点数、竖边（台阶）数、尺寸链文字、
件号箭头数、弯矩图顶点与填充条数、外框是否落在图幅内。
运行：  python3 mech_frame_tests.py   全通过则退出码 0。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gbdraw import Sheet, text_w                      # noqa: E402
import mech_frame as mf                               # noqa: E402

失败 = []
通过 = 0


def 检查(名, 条件, 实际=None):
    global 通过
    if 条件:
        通过 += 1
        print("✓ %s" % 名)
    else:
        失败.append((名, 实际))
        print("✗ %s   实际=%r" % (名, 实际))


def 收集(items, kind=None):
    out = []
    for e in items:
        k, a = e
        if k == "group":
            out += 收集(a["items"], kind)
        elif kind is None or k == kind:
            out.append((k, a))
    return out


段表 = [(-12, 12, 60, "cyl", "左轴承"), (12, 97.9, 70, "cyl", ""),
        (97.9, 109.9, 80, "cyl", "轴环"), (109.9, 187.9, 70, "gear", (294.06, 280.56)),
        (187.9, 208.9, 60, "cyl", ""), (208.9, 232.6, 60, "cyl", ""),
        (232.6, 277, 55, "cyl", "密封"), (277, 382, 50, "cyl", "联轴器段")]
k = 0.44
x0, y0 = 14, 128


def 测试轴草图():
    print("\n=== 轴草图 ===")
    s = Sheet(210, 190)
    框 = mf.轴草图(s, 段表, x0=x0, y0=y0, 比例=k, 件号=[(0, "左轴承"), (145.9, "齿轮 4")])

    # 1) 轮廓多边形：n 段 → 4n 个顶点（上沿 2n + 下沿 2n）
    poly = [a for kk, a in 收集(s.items, "poly") if a.get("fill") == "none" and len(a["pts"]) > 4]
    检查("轮廓多边形只有一个", len(poly) == 1, len(poly))
    pts = poly[0]["pts"]
    检查("轮廓顶点数 = 4×段数", len(pts) == 4 * len(段表), len(pts))

    # 2) 每段的上下两条边都要在 ±d/2×比例 处、长度 = 段长×比例（少一段或多一段都会被抓到）
    横边 = []
    for p, q in zip(pts, pts[1:] + pts[:1]):
        if abs(p[1] - q[1]) < 1e-9 and abs(p[0] - q[0]) > 1e-9:
            横边.append((round(abs(p[1] - y0), 6), round(abs(q[0] - p[0]), 6)))
    缺 = []
    for a in 段表:
        want = (round(a[2] / 2 * k, 6), round((a[1] - a[0]) * k, 6))
        if 横边.count(want) < 2:          # 上下各一条
            缺.append((a[2], want, 横边.count(want)))
    检查("每段上下沿都在正确高度与长度", not 缺, 缺)

    # 2b) 台阶面竖线必须**贯穿较大直径全高**（零件图同口径，2026-10-26 被指出两次）
    竖线列表 = [(a["x1"], a["y1"], a["y2"]) for kk, a in 收集(s.items, "line")
              if abs(a["x1"] - a["x2"]) < 1e-9 and a.get("style") == "thick"]
    缺台阶面 = []
    for prev, cur in zip(段表, 段表[1:]):
        if abs(prev[2] - cur[2]) < 1e-9:
            continue
        xb = 14 + (cur[0] + 12) * k
        r_big = max(prev[2], cur[2]) / 2 * k
        有 = any(abs(x - xb) < 1e-6
                and abs(min(y1, y2) - (y0 - r_big)) < 1e-6
                and abs(max(y1, y2) - (y0 + r_big)) < 1e-6
                for x, y1, y2 in 竖线列表)
        if not 有:
            缺台阶面.append((prev[2], cur[2]))
    检查("每个变径处有贯穿较大直径全高的台阶面竖线", not 缺台阶面, 缺台阶面)

    # 2c) 直径尺寸：尺寸线贯穿全径、两端箭头、不越出；φ 值竖排写在尺寸线上（不拉引线）；
    #     同直径的连续段只标一次（⌀60 连两段只出一个）
    细线3 = [(a["x1"], a["y1"], a["y2"]) for kk, a in 收集(s.items, "line")
             if abs(a["x1"] - a["x2"]) < 1e-9 and a.get("style") == "thin"]
    圆字 = [a for kk, a in 收集(s.items, "text") if a.get("rotate") == -90]
    段组 = []
    for s_ in 段表:
        if 段组 and abs(段组[-1][2] - s_[2]) < 1e-9:
            段组[-1][1] = s_[1]
        else:
            段组.append([s_[0], s_[1], s_[2]])
    缺直径尺寸 = []
    for x1, x2, d in 段组:
        xm = 14 + ((x1 + x2) / 2 + 12) * k
        r = d / 2 * k
        有线 = any(abs(x - xm) < 1e-6 and abs(min(y1, y2) - (y0 - r)) < 1e-6
                  and abs(max(y1, y2) - (y0 + r)) < 1e-6 for x, y1, y2 in 细线3)
        不越出 = not any(abs(x - xm) < 1e-6 and abs(min(y1, y2) - (y0 + r)) < 1e-6
                       and abs(max(y1, y2) - (y0 + r + 2)) < 1e-6 for x, y1, y2 in 细线3)
        txt = "⌀%s" % (str(int(d)) if float(d).is_integer() else ("%g" % d))
        有字 = any(abs(a["x"] - (xm - 0.8)) < 1e-6 and a["s"] == txt for a in 圆字)
        if not (有线 and 不越出 and 有字):
            缺直径尺寸.append((d, 有线, 不越出, 有字))
    检查("每个直径组：贯穿全径尺寸线 + φ 竖排贴线（不越出、不拉引线）",
         not 缺直径尺寸, 缺直径尺寸)
    检查("同直径连续段只标一次（8 段 → 7 个尺寸）",
         len([a for a in 圆字 if a["s"].startswith("⌀")]) == len(段组),
         (len([a for a in 圆字 if a["s"].startswith("⌀")]), len(段组)))
    轮廓外圆字 = [a["s"] for kk, a in 收集(s.items, "text")
                if a["s"].startswith("⌀") and a["y"] > y0 + max(s_[2] for s_ in 段表) / 2 * k]
    检查("φ 值不放轮廓外（不拉引线）", not 轮廓外圆字, 轮廓外圆字)
    三角数 = len([1 for kk, a in 收集(s.items, "poly") if len(a["pts"]) == 3])
    检查("直径尺寸两端箭头（总数 ≥ 2×直径组数）", 三角数 >= 2 * len(段组), 三角数)


    # 3) 轮廓 x 跨度与实际轴长×比例一致
    xs = [p[0] for p in pts]
    检查("轮廓 x 跨度", abs((max(xs) - min(xs)) - (382 + 12) * k) < 1e-6,
         (max(xs) - min(xs), (382 + 12) * k))

    # 3b) 尺寸界线必须**越过尺寸线 2 mm**（用户反复强调；旧版恒停在轮廓上）
    横线 = [(a["y1"]) for kk, a in 收集(s.items, "line")
           if abs(a["y1"] - a["y2"]) < 1e-9 and a.get("style") == "thin"]
    尺寸行 = sorted({round(y, 2) for y in 横线 if y < y0 - 10})
    竖线2 = [(a["x1"], a["y1"], a["y2"]) for kk, a in 收集(s.items, "line")
            if abs(a["x1"] - a["x2"]) < 1e-9 and a.get("style") == "thin"]
    缺越过 = []
    for yy in 尺寸行:
        有 = any(abs(min(y1, y2) - (yy - 2.0)) < 1e-6 for _, y1, y2 in 竖线2)
        if not 有:
            缺越过.append(yy)
    检查("每条尺寸线的界线都越过 2 mm", not 缺越过, (尺寸行, 缺越过))

    # 4) 轴线是点画线且两端各出头 4 mm
    center = [a for kk, a in 收集(s.items, "line") if a.get("style") == "center"]
    检查("轴线唯一且为点画线", len(center) == 1, len(center))
    检查("轴线两头各出 4 mm",
         abs((center[0]["x2"] - center[0]["x1"]) - ((382 + 12) * k + 8)) < 1e-6,
         center[0]["x2"] - center[0]["x1"])

    # 5) 尺寸链：每段一个数字 + 总长一个
    txts = [a["s"] for kk, a in 收集(s.items, "text")]
    段长 = [str(int(b - a)) if float(b - a).is_integer() else ("%g" % (b - a))
            for a, b in zip([p[0] for p in 段表], [p[1] for p in 段表])]
    检查("尺寸链每段都有长度文字", all(t in txts for t in 段长), [t for t in 段长 if t not in txts])
    检查("总长文字存在", any(t.startswith("总长") for t in txts), txts[:3])

    # 6) 件号：每条都有引杆（细竖线）+ 箭头，且文字在
    细竖线 = [(a["x1"], a["y1"], a["y2"]) for kk, a in 收集(s.items, "line")
             if abs(a["x1"] - a["x2"]) < 1e-9 and a.get("style") == "thin"]
    缺引线 = []
    for xa, txt_ in [(0, "左轴承"), (145.9, "齿轮 4")]:
        xx = 14 + (xa + 12) * k
        有杆 = any(abs(x - xx) < 1.6 and abs(max(y1, y2) - min(y1, y2)) > 6 for x, y1, y2 in 细竖线)
        有字 = any(a["s"].startswith(txt_) for kk, a in 收集(s.items, "text"))
        if not (有杆 and 有字):
            缺引线.append((txt_, 有杆, 有字))
    检查("件号引杆与文字齐全", not 缺引线, 缺引线)

    # 7) 外框在图纸内，且上边覆盖件号文字
    x_min, y_min, x_max, y_max = 框
    检查("外框在图幅内", 0 <= x_min and 0 <= y_min and x_max <= 210 and y_max <= 190,
         (x_min, y_min, x_max, y_max))
    检查("外框上沿高于轴线", y_max > y0, (y_max, y0))

    # 8) 齿顶圆默认不画；开着才多一个虚线矩形
    s2 = Sheet(210, 400)
    n0 = len(收集(s2.items, "rect"))
    mf.轴草图(s2, 段表, x0=x0, y0=300, 比例=k)
    检查("默认不画齿顶圆", len(收集(s2.items, "rect")) == n0, len(收集(s2.items, "rect")))
    mf.轴草图(s2, 段表, x0=x0, y0=300, 比例=k, 齿顶圆=True)
    检查("齿顶圆=True 多一个虚线矩形", len(收集(s2.items, "rect")) == n0 + 1,
         len(收集(s2.items, "rect")))

    # 9) gear 段缺 (da, df) 要报错
    try:
        mf.轴草图(Sheet(210, 190), [(0, 10, 30, "gear", "")], x0=10, y0=100)
        检查("gear 段缺齿顶圆/齿根圆 → ValueError", False, "未抛错")
    except ValueError:
        检查("gear 段缺齿顶圆/齿根圆 → ValueError", True)


def 测试力学模型():
    print("\n=== 力学模型 ===")
    s = Sheet(210, 120)
    L, a = 220.75, 145.875
    mf.力学模型(s, x0=14, y0=60, 跨度=L, 载荷=[(a, "F_r", 2271.5, "down")],
                反力=[(0, "R_A", 3500.0)], 比例=k)
    线 = [a for kk, a in 收集(s.items, "line")]
    # 梁：跨距×比例
    梁 = [x for x in 线 if abs(x["y1"] - x["y2"]) < 1e-9 and abs((x["x2"] - x["x1"]) - L * k) < 1e-6]
    检查("梁长 = 跨距×比例", len(梁) == 1, len(梁))
    三角 = [a for kk, a in 收集(s.items, "poly") if len(a["pts"]) == 3]
    # 支座三角的底边在梁下方（y < y0），箭头三角的尖端在梁上
    跨度 = lambda a: max(p[0] for p in a["pts"]) - min(p[0] for p in a["pts"])
    支座 = [a for a in 三角 if 跨度(a) > 4 and max(p[1] for p in a["pts"]) < 60]
    箭头 = [a for a in 三角 if 跨度(a) < 1.2]
    检查("两个铰支座三角在梁下", len(支座) == 2, len(支座))
    检查("载荷/反力箭头数 = 1 + 1", len(箭头) == 2, len(箭头))
    # 集中力朝梁：箭头顶点（尖端）落在梁 y 上
    检查("集中力箭头尖端落在梁上",
         any(abs(min(p[1] for p in a["pts"]) - 60) < 1e-6 for a in 箭头), True)
    txts = [a["s"] for kk, a in 收集(s.items, "text")]
    检查("载荷载荷值写成文字", any("2271.5" in t for t in txts), txts)
    检查("支点 A/B 都有", "A" in txts and "B" in txts, txts)


def 测试弯矩图():
    print("\n=== 弯矩图 ===")
    s = Sheet(210, 120)
    L = 220.75
    框 = mf.弯矩图(s, x0=14, y0=40, 位置=[0, 145.875, 220.75], 值=[0, 382059, 0],
                 跨度=L, 比例=k, 高度=16, 标题="M")
    poly = [a for a in (a for kk, a in 收集(s.items, "poly") if kk == "poly") if len(a["pts"]) == 3]
    折线 = [a for kk, a in 收集(s.items, "poly") if len(a["pts"]) == 3 and a["style"] == "thick"]
    检查("弯矩折线 = 3 个顶点", len(折线) == 1 and len(折线[0]["pts"]) == 3,
         len(折线[0]["pts"]) if 折线 else 0)
    # 顶点 x 与跨距对齐
    折x = [p[0] for p in 折线[0]["pts"]]
    检查("首尾顶点落在支点上",
         abs(折x[0] - 14) < 1e-6 and abs(折x[-1] - (14 + L * k)) < 1e-6, 折x)
    # 填充：竖向细线若干条
    填充 = [a for kk, a in 收集(s.items, "line")
            if a.get("style") == "thin" and abs(a["x1"] - a["x2"]) < 1e-9]
    检查("有竖向细线填充", len(填充) > 20, len(填充))
    # 零线
    零线 = [a for kk, a in 收集(s.items, "line")
            if a.get("style") == "thin" and abs(a["y1"] - a["y2"]) < 1e-9
            and abs(a["y1"] - 40) < 1e-9]
    检查("零线在 y0 上", len(零线) == 1, len(零线))
    txts = [a["s"] for kk, a in 收集(s.items, "text")]
    检查("极值标注", any("382059" in t for t in txts), txts)
    # 求拉侧="下"：顶点应在零线下方
    s2 = Sheet(210, 120)
    mf.弯矩图(s2, x0=14, y0=60, 位置=[0, 110, 220], 值=[0, 100, 0], 跨度=220,
             比例=k, 高度=10, 求拉侧="下")
    折2 = [a for kk, a in 收集(s2.items, "poly") if len(a["pts"]) == 3 and a["style"] == "thick"][0]
    检查("求拉侧=下 时顶点在零线下方", all(p[1] <= 60 + 1e-9 for p in 折2["pts"]),
         [p[1] for p in 折2["pts"]])


def 测试转矩图():
    print("\n=== 转矩图 ===")
    s = Sheet(210, 120)
    mf.转矩图(s, x0=14, y0=40, 段值=[(0, 85.9, 130000), (85.9, 394, 0)],
              跨度=394, 比例=k, 高度=12)
    折 = [a for kk, a in 收集(s.items, "poly") if len(a["pts"]) == 4 and a["style"] == "thick"]
    检查("转矩阶梯 = 4 个顶点", len(折) == 1 and len(折[0]["pts"]) == 4, len(折))
    ys = [p[1] for p in 折[0]["pts"]]
    检查("阶梯两档不同高", len(set(round(y, 3) for y in ys)) == 2, ys)
    txts = [a["s"] for kk, a in 收集(s.items, "text")]
    检查("转矩值标注", any("130000" in t for t in txts), txts)


if __name__ == "__main__":
    测试轴草图()
    测试力学模型()
    测试弯矩图()
    测试转矩图()
    print("\n合计：通过 %d 项，失败 %d 项" % (通过, len(失败)))
    for f in 失败:
        print("  ✗", f)
    sys.exit(0 if not 失败 else 1)
