#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫渲染出的图纸 PNG，按 mm 打印指定行/列上的暗线段位置。

用途：不接受 vision 对图的“读数”，用像素证据核实视图几何 —— 轮廓是否闭合、
齿顶/齿根/孔壁/端面是否在理论位置、剖面线是否只落在轮体内。

用法：
  python3 verify_drawing_lines.py sheet.png --page 297x210 --scan y=85 --scan x=75
  python3 verify_drawing_lines.py sheet.png --page 297x210 --scan y=160 --center 152,180
  python3 verify_drawing_lines.py sheet.png --page 297x210 --scan y=85 --window 40,100

参数：
  --page WxH     图幅（mm），用来把像素换算成 mm
  --scan y=85    水平扫描线（在该 y 上找 x 方向的暗段）；x=75 则竖直扫描
  --center cx,cy 打印每条线相对该中心的偏移（查直径/孔位置时很方便）
  --window a,b   只保留在扫描轴向上落在 [a,b] mm 内的结果（滤掉表格文字等）
  --thr 128      暗像素阈值，线细/发灰时调大
  --minlen 1     最小连续暗像素长度，滤掉孤立噪点
"""
import argparse
import sys

import numpy as np
from PIL import Image


def runs(vals, thr=128, minlen=1):
    idx = np.where(vals < thr)[0]
    out = []
    if len(idx):
        s = p = idx[0]
        for i in idx[1:]:
            if i - p > 1:
                out.append((s, p))
                s = i
            p = i
        out.append((s, p))
    return [r for r in out if r[1] - r[0] + 1 >= minlen]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--page", required=True, help="WxH in mm, e.g. 297x210")
    ap.add_argument("--scan", action="append", required=True, help="y=<mm> or x=<mm>")
    ap.add_argument("--center", help="cx,cy in mm for relative offsets")
    ap.add_argument("--window", help="a,b in mm on the scan axis")
    ap.add_argument("--thr", type=int, default=128)
    ap.add_argument("--minlen", type=int, default=1)
    args = ap.parse_args()

    pw, ph = (float(v) for v in args.page.lower().split("x"))
    im = Image.open(args.image).convert("L")
    a = np.array(im)
    h, w = a.shape
    sx, sy = w / pw, h / ph

    center = None
    if args.center:
        center = tuple(float(v) for v in args.center.split(","))
    window = None
    if args.window:
        window = tuple(float(v) for v in args.window.split(","))

    print(f"image {w}x{h}px  page {pw}x{ph}mm  scale {sx:.2f}px/mm")
    for spec in args.scan:
        key, _, val = spec.partition("=")
        key, val = key.strip().lower(), float(val)
        if key == "y":
            line = a[min(int(round(val * sy)), h - 1), :]
            scale, other = sx, center[0] if center else None
            label = f"y={val:g}mm  (x)"
        elif key == "x":
            line = a[:, min(int(round(val * sx)), w - 1)]
            scale, other = sy, center[1] if center else None
            label = f"x={val:g}mm  (y)"
        else:
            print(f"skip bad scan {spec!r}", file=sys.stderr)
            continue

        found = []
        for s, e in runs(line, args.thr, args.minlen):
            p0, p1 = s / scale, e / scale
            if window and not (window[0] <= p0 <= window[1]):
                continue
            found.append((p0, p1))

        print(f"\n[{label}]  {len(found)} segments")
        for p0, p1 in found:
            mid = (p0 + p1) / 2
            rel = f"  rel {mid - other:+.2f}" if other is not None else ""
            print(f"  {p0:8.2f} .. {p1:8.2f}   mid {mid:8.2f}{rel}")


if __name__ == "__main__":
    main()
