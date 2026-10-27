# -*- coding: utf-8 -*-
"""verify_all.py —— 批2 五张靶子图的像素核对（扫线 + 线宽 + 闭合）

坐标用页面坐标（左上、y 向下）；画法函数用图纸坐标（y 向上），扫描位置 = 页高 − y图纸。
图线表另做逐行分析：实线 1 段、虚线 ≥3 段、波浪/双折 ≥3 段，证明 9 种线型确实不同。
"""
import re
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERIFY = ROOT / "check" / "verify_drawing_lines.py"
CLOSED = ROOT / "check" / "check_closed.py"
PY = "/usr/bin/python3"
TOL = 0.45


def load(png):
    a = np.array(Image.open(png).convert("L"), dtype=float)
    h, w = a.shape
    return a, w, h


def runs(profile, thr=128, minlen=1):
    idx = np.where(profile < thr)[0]
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


def cov(a, sx, sy, axis, coord, center, half=0.30):
    if axis == "x":
        prof, sc = a[:, int(coord * sx)], sy
    else:
        prof, sc = a[int(coord * sy), :], sx
    lo, hi = max(0, int((center - half) * sc)), min(len(prof), int((center + half) * sc))
    return float(((255.0 - prof[lo:hi]) / 255.0).sum() / sc)


def hit(segs, want, tol=TOL):
    return [g for g in segs if abs(g - want) <= tol]


def check_positions(name, png, checks):
    """checks: [(axis, coord, positions, style)]，逐条命中即记录线宽。"""
    a, w, h = load(png)
    sx, sy = w / 297.0, h / 210.0 if "sheet" not in name else h / 297.0
    lines, widths = [], {k: [] for k in ("thick", "thin", "center")}
    ok = True
    for axis, coord, positions, style in checks:
        if axis == "x":
            prof = a[:, int(coord * sx)]
            sc = sy
        else:
            prof = a[int(coord * sy), :]
            sc = sx
        segs = [(s / sc, e / sc) for s, e in runs(prof, minlen=1)]
        mids = [(s + e) / 2 for s, e in segs]
        lines.append(f"[{axis}={coord:g}] {len(segs)} 段")
        miss = []
        for want in positions:
            m = hit(mids, want)
            if not m:
                miss.append(f"{want:g}")
            else:
                widths[style].append(cov(a, sx, sy, axis, coord, m[0]))
        if miss:
            lines.append("  ✗ 缺 " + "、".join(miss) + f"；实测 {[round(x,2) for x in mids]}")
            ok = False
        else:
            lines.append(f"  ✓ {len(positions)} 处命中")
    return ok, lines, widths


def check_line_table(png):
    a, w, h = load(png)
    sx, sy = w / 297.0, h / 210.0
    rows = [180 - 13 * i for i in range(9)]
    expect = [1, 3, 3, 1, 4, 4, 3, 3, 4]
    kinds = ["细实线", "波浪线", "双折线", "粗实线", "细虚线", "粗虚线", "点画线", "粗点画线", "细双点画线"]
    ok, lines, widths = True, [], {}
    for i, (y, n, kind) in enumerate(zip(rows, expect, kinds)):
        y = 210.0 - y
        row = a[int(y * sy), int(62 * sx):int(128 * sx)]
        rr = runs(row)
        lines.append(f"{kind:6} y={y:g}: {len(rr)} 段（要求 ≥{n}）")
        if len(rr) < n:
            ok = False
        # 线宽只量两条实线样线，避免斜段/短划把 run 拉宽
        if kind in ("细实线", "粗实线"):
            style = "thick" if kind == "粗实线" else "thin"
            widths.setdefault(style, []).append(cov(a, sx, sy, "x", 95.0, y))
    return ok, lines, widths


def main():
    log, ok = [], True
    # ---------------- 图1-3 图线表 ----------------
    p = HERE / "png_fig1-3" / "p001.png"
    good, ls, ws = check_line_table(p)
    ok &= good
    log.append("===== fig1-3 表1-3 图线（9 种）")
    log += ["  " + x for x in ls]
    for k, v in ws.items():
        if v:
            log.append(f"  {k} 线宽中位 {statistics.median(v):.3f}（{min(v):.3f}..{max(v):.3f}）")

    # ---------------- 其余图 ----------------
    SPEC = {
        "fig1-sheet": ("420x297", [
            ("y", 160, [0, 25, 415, 420], "thick"),
            ("x", 220, [0, 5, 292], "thick"),
            ("y", 267, [235, 245, 255, 271, 287, 299, 315, 341, 353, 365, 415], "thin"),
            ("x", 300, [236, 243, 250, 257, 264, 271, 278, 285, 292], "thin"),
        ]),
        "fig6-section": ("297x210", [
            ("y", 70, [38, 61, 79, 102], "thick"),
            ("x", 70, [48, 92], "thick"),
            ("y", 73, [138, 161, 170, 202], "thick"),
            ("y", 145, [38, 61, 79, 102], "thick"),
            ("x", 170, [120, 164], "thick"),
        ]),
        "fig6-break": ("297x210", [
            ("y", 80, [50, 90], "thick"),
            ("x", 200, [70, 90], "thin"),
            ("x", 200, [75, 85], "thick"),
        ]),
        "fig6-detail": ("297x210", [
            ("y", 100, [58, 82], "thin"),
            ("y", 100, [106, 154], "thick"),
        ]),
        "fig8-21-left": ("297x210", [
            ("y", 101, [116.25, 138.83, 140.5, 155.5, 157.17, 179.75], "thick"),
        ]),
    }
    for name, (page, checks) in SPEC.items():
        png = HERE / f"png_{name}" / "p001.png"
        if not png.exists():
            log.append(f"{name}: 缺 {png}")
            ok = False
            continue
        pw, ph = (float(v) for v in page.split("x"))
        # check_positions 内部按 297x210 换算；A3 图框单独按 420x297
        if name == "fig1-sheet":
            a, w, h = load(png)
            sx, sy = w / pw, h / ph
            lines, widths = [], {"thick": [], "thin": [], "center": []}
            gok = True
            for axis, coord, positions, style in checks:
                prof = a[:, int(coord * sx)] if axis == "x" else a[int(coord * sy), :]
                sc = sy if axis == "x" else sx
                mids = [(s + e) / 2 / sc for s, e in runs(prof)]
                miss = [str(want) for want in positions if not hit(mids, want)]
                lines.append(f"[{axis}={coord:g}] {'✗ 缺 ' + '、'.join(miss) if miss else '✓'}")
                if miss:
                    gok = False
                for want in positions:
                    m = hit(mids, want)
                    if m:
                        widths[style].append(cov(a, sx, sy, axis, coord, m[0]))
            log.append(f"===== {name}  ({pw:g}×{ph:g})")
            log += ["  " + x for x in lines]
            ok &= gok
            for k, v in widths.items():
                if v:
                    log.append(f"  {k} 线宽中位 {statistics.median(v):.3f}（{min(v):.3f}..{max(v):.3f}）")
        else:
            gok, lines, widths = check_positions(name, png, checks)
            log.append(f"===== {name}")
            log += ["  " + x for x in lines]
            ok &= gok
            for k, v in widths.items():
                if v:
                    log.append(f"  {k} 线宽中位 {statistics.median(v):.3f}（{min(v):.3f}..{max(v):.3f}）")

        # 闭合检查（图线表是表格，不做）
        if name != "fig1-3":
            c = subprocess.run([PY, str(CLOSED), str(png), "--page", page, "--min-mm2", "200"],
                               text=True, capture_output=True)
            log.append("  " + (c.stdout.strip() or c.stderr.strip()))
            if c.returncode != 0:
                ok = False

    # 孤立线线宽（避免合并线/斜线把 run 拉宽）
    WIDTHS = {
        "fig1-3": [("x", 95, 30, "thin", 0.25), ("x", 95, 69, "thick", 0.50)],
        "fig1-sheet": [("y", 160, 25, "thick", 0.50), ("y", 267, 245, "thin", 0.25)],
        "fig6-section": [("y", 70, 61, "thick", 0.50), ("y", 73, 170, "center", 0.25)],
        "fig6-break": [("y", 80, 50, "thick", 0.50), ("x", 195, 70, "thin", 0.25)],
        "fig6-detail": [("y", 100, 58, "thin", 0.25), ("y", 100, 106, "thick", 0.50)],
        "fig8-21-left": [("x", 150, 73.06, "thick", 0.50), ("x", 150, 95.2, "thin", 0.25),
                         ("x", 150, 96.74, "thick", 0.50)],
    }
    log.append("\n===== 孤立线线宽（覆盖率积分，mm）")
    for name, items in WIDTHS.items():
        png = HERE / f"png_{name}" / "p001.png"
        pw, ph = (420, 297) if name == "fig1-sheet" else (297, 210)
        a, w, h = load(png)
        sx, sy = w / pw, h / ph
        for axis, coord, center, style, target in items:
            got = cov(a, sx, sy, axis, coord, center)
            good = abs(got - target) <= 0.05
            log.append(f"{name:13} {style:6} {axis}={coord:g} 实测 {got:.3f} 目标 {target:.2f}  {'PASS' if good else 'FAIL'}")
            if not good:
                ok = False

    # 图8-21 左视图：大径 3/4 圈——45° 有弧、315° 缺口无弧
    p = HERE / "png_fig8-21-left" / "p001.png"
    a, w, h = load(p)
    sx, sy = w / 297.0, h / 210.0
    def 暗(x, y):
        return min(int(a[int((y + dy) * sy), int((x + dx) * sx)])
                   for dx in (-0.3, 0, 0.3) for dy in (-0.3, 0, 0.3)) < 128
    gap_ok = 暗(155.071, 97.929) and not 暗(155.071, 112.071)
    log.append(f"fig8-21-left  3/4 圈：45° 有弧={暗(155.071, 97.929)}，315° 缺口无弧={not 暗(155.071, 112.071)}  {'PASS' if gap_ok else 'FAIL'}")
    ok &= gap_ok

    out = "\n".join(log)
    (HERE / "verify.log").write_text(out + "\n", encoding="utf-8")
    print(out)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
