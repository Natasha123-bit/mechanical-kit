#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫渲染出的 PNG，把检出的线位/墨量跟参数算出的理论值逐条对。

用途：SVG 是矢量，几何对不对在 SVG 里能查；但"到底有没有画出来、打印有没有被裁、
剖面线是不是真的落在剖切区内"只有扫像素才能确认（字库缺失、pattern 被裁、
打印缩放错都会在这一步暴露）。

用法：
    python3 verify_raster.py png/p1.png [--params params.json]

坐标按 A4 横放 297×210mm 全幅映射：px/mm = 图宽 / 297。
"""
from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
from PIL import Image

import gear_draw as G


def _groups(idx, s, tol=1):
    out = []
    for i in idx:
        if out and i - out[-1][-1] <= tol:
            out[-1].append(i)
        else:
            out.append([i])
    return [(sum(g) / len(g) / s, len(g)) for g in out]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("png")
    ap.add_argument("--params", default="")
    ap.add_argument("--tol", type=float, default=0.45, help="线位允许偏差 mm")
    args = ap.parse_args(argv)

    p = G.default_params()
    if args.params:
        p = json.load(open(args.params, encoding="utf-8"))
    g, sh = p["geometry"], p["sheet"]
    s_mm = G._scale_factor(sh["scale"])
    W_mm, H_mm = G.SHEET_SIZES[sh["size"]]
    mg = sh["margins"]
    cy = mg["top"] + (H_mm - mg["top"] - mg["bottom"]) / 2.0
    x0 = sh["layout"]["main_x0"]
    x1 = x0 + g["b"] * s_mm
    lcx = sh["layout"]["left_cx"]
    ra, rr, rf, rb = (g["d_a"] / 2 * s_mm, g["d"] / 2 * s_mm,
                      g["d_f"] / 2 * s_mm, g["bore_d"] / 2 * s_mm)
    t2s = g["keyway"]["t2"] * s_mm            # 键槽深（图纸长度）

    a = np.array(Image.open(args.png).convert("L"))
    H, W = a.shape
    s = W / W_mm
    ink = a < 160
    fails = []

    def report(name, expected, got, tol=None):
        tol = args.tol if tol is None else tol
        ok = got is not None and abs(got - expected) <= tol
        print("  %-28s 期望 %7.2f  实测 %s  %s"
              % (name, expected, ("%7.2f" % got) if got is not None else "  --  ",
                 "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    print("图 %s  %dx%d px  %.3f px/mm" % (args.png, W, H, s))
    if abs(H / W - H_mm / W_mm) > 0.01:
        print("  ! 长宽比 %.4f 与 A4 %.4f 不符，可能被裁或比例错" % (H / W, H_mm / W_mm))
        fails.append("长宽比")

    # 1. 主视图：竖扫列（取齿宽中线）
    print("[主视图] 竖扫 x=%.2f mm" % ((x0 + x1) / 2))
    col = ink[:, int((x0 + x1) / 2 * s)]
    hits = _groups([i for i in range(int((cy - ra - 3) * s), int((cy + ra + 8) * s)) if col[i]], s)
    hs = [h[0] for h in hits]
    for name, y in (("齿顶线(上)", cy - ra), ("分度线(上)", cy - rr), ("齿根线(上)", cy - rf),
                    ("键槽槽底(上)", cy - rb - t2s), ("孔壁(上)", cy - rb),
                    ("轴线", cy), ("孔壁(下)", cy + rb),
                    ("齿根线(下)", cy + rf), ("分度线(下)", cy + rr), ("齿顶线(下)", cy + ra)):
        near = min(hs, key=lambda v: abs(v - y)) if hs else None
        report(name, y, near)

    # 2. 端面竖线
    print("[主视图] 横扫 y=%.2f mm" % (cy - ra / 2))
    row = ink[int((cy - ra / 2) * s), :]
    hs = [h[0] for h in _groups([i for i in range(int((x0 - 3) * s), int((x1 + 3) * s)) if row[i]], s)]
    for name, x in (("左端面", x0), ("右端面", x1)):
        near = min(hs, key=lambda v: abs(v - x)) if hs else None
        report(name, x, near)

    # 3. 端面图三个圆（在 y = cy + 0.6ra 处横扫，避开中心线与键槽）
    dy = 0.6 * ra
    print("[端面图] 横扫 y=%.2f mm（偏离圆心 %.2f）" % (cy + dy, dy))
    row = ink[int((cy + dy) * s), :]
    hs = [h[0] for h in _groups([i for i in range(int((lcx - ra - 4) * s), int((lcx + ra + 4) * s)) if row[i]], s)]
    for name, r in (("齿顶圆(左)", ra), ("分度圆(左)", rr), ("齿根圆(左)", rf)):
        exp = lcx - math.sqrt(max(r * r - dy * dy, 0))
        near = min(hs, key=lambda v: abs(v - exp)) if hs else None
        report(name, exp, near)
    # 键槽（y = cy - rb - 0.5 处横扫，槽壁在圆心两侧 8/2×s）
    print("[端面图] 键槽 横扫 y=%.2f mm" % (cy - rb - 0.4))
    row = ink[int((cy - rb - 0.4) * s), :]
    kw = g["keyway"]["width"] / 2 * s_mm
    hs = [h[0] for h in _groups([i for i in range(int((lcx - kw - 3) * s), int((lcx + kw + 3) * s)) if row[i]], s)]
    for name, x in (("键槽左壁", lcx - kw), ("键槽右壁", lcx + kw)):
        near = min(hs, key=lambda v: abs(v - x)) if hs else None
        report(name, x, near)
    # 键槽顶边：取样列取在槽内、避开竖直中心线（中心线正好穿过槽口中线）
    xs_probe = lcx + 0.6 * kw
    print("[端面图] 键槽顶边 竖扫 x=%.2f mm" % xs_probe)
    col = ink[:, int(xs_probe * s)]
    slot_top = cy + rb - (g["bore_d"] + g["keyway"]["t2"]) * s_mm
    hs = [h[0] for h in _groups([i for i in range(int((slot_top - 4) * s), int((slot_top + 4) * s)) if col[i]], s)]
    near = min(hs, key=lambda v: abs(v - slot_top)) if hs else None
    report("键槽顶边", slot_top, near)
    # 槽口处孔的轮廓必须断开：x=lcx+1.5 处（槽内、避开中心线）不应有孔圆墨迹
    xp = lcx + 1.5
    col = ink[:, int(xp * s)]
    # 取样带避开槽顶边线（97.1±0.25）本身
    band = [i for i in range(int((cy - rb - 0.6) * s), int((cy - rb + 1.2) * s)) if col[i]]
    print("  %-28s 孔圆墨点 %d  %s" % ("槽口处孔轮廓断开", len(band), "OK" if not band else "FAIL"))
    if band:
        fails.append("槽口处孔轮廓未断开")

    # 4. 剖面线：剖切区内应有墨，齿区与孔内应留白
    def ratio(y0, y1, xa, xb):
        sub = ink[int(y0 * s):int(y1 * s), int(xa * s):int(xb * s)]
        return sub.mean() * 100

    xm0, xm1 = x0 + 0.6, x1 - 0.6
    r_hatch = ratio(cy - rf + 1.2, cy - rb - 1.2, xm0, xm1)
    # 齿区取样要避开齿顶线/分度线/齿根线本身（各占 0.25~0.5mm）
    r_tooth = max(ratio(cy - ra + 0.45, cy - rr - 0.4, xm0, xm1),
                  ratio(cy - rr + 0.4, cy - rf - 0.45, xm0, xm1))
    # 孔内取样避开轴线（点画线）
    r_bore = max(ratio(cy - rb + 1.2, cy - 1.2, xm0, xm1),
                 ratio(cy + 1.2, cy + rb - 1.2, xm0, xm1))
    print("[剖面] 剖切区墨量 %.2f%%  齿区 %.2f%%  孔内 %.2f%%" % (r_hatch, r_tooth, r_bore))
    for name, val, lo, hi in (("剖面线存在", r_hatch, 0.8, 12.0),
                              ("齿区留白", r_tooth, 0.0, 0.8),
                              ("孔内留白", r_bore, 0.0, 0.5)):
        ok = lo <= val <= hi
        print("  %-28s 实测 %6.2f%%  %s" % (name, val, "OK" if ok else "FAIL"))
        if not ok:
            fails.append(name)

    # 5. 图框与越界
    frame_hits = [h[0] for h in _groups([i for i in range(W) if ink[:, i].sum() > 0.25 * H], s)]
    print("[图框] 竖线 x=%s" % ", ".join("%.1f" % v for v in frame_hits))
    for name, x in (("图框左线", mg["left"]), ("图框右线", W_mm - mg["right"])):
        near = min(frame_hits, key=lambda v: abs(v - x)) if frame_hits else None
        report(name, x, near)
    outside = ink[:int((mg["top"] - 0.6) * s), :].sum() + ink[int((H_mm - mg["bottom"] + 0.6) * s):, :].sum()
    print("  %-28s 图框外墨点数 %d  %s" % ("图框外无内容", outside, "OK" if outside == 0 else "FAIL"))
    if outside:
        fails.append("图框外有内容")

    print("\n%s" % ("像素校验全部通过" if not fails else "像素校验 %d 项不通过：%s"
                    % (len(fails), "、".join(fails))))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
