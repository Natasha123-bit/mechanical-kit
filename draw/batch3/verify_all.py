# -*- coding: utf-8 -*-
"""verify_all.py —— 批3 六张靶子图像素核对（扫线 + 线宽 + 闭合）"""
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

PAGE = {
    "fig7-1": (420, 297), "fig7-15": (297, 210), "fig7-20": (297, 210),
    "fig7-49": (420, 297), "fig9-2": (420, 297), "fig9-25": (420, 297),
}
SCANS = {
    "fig7-1": [("x", 50, [110, 124]), ("x", 95, [104.5, 129.5]),
               ("x", 213, [105.8, 129.5]), ("y", 110, [43.9, 153.9]),
               ("y", 270, [245])],
    "fig7-15": [("y", 65, [65, 135, 180, 250]), ("y", 115, [65, 135]),
                ("y", 65, [260, 290])],
    "fig7-20": [("y", 75, [90, 170]), ("y", 75, [180, 220]), ("y", 30, [180, 220])],
    "fig7-49": [("y", 102, [40, 100]), ("y", 102, [150, 210]), ("y", 102, [242.7, 277.3])],
    "fig9-2": [("x", 145, [113, 141]), ("y", 127, [95, 185]), ("x", 140, [86, 92]),
               ("y", 220, [235, 243, 283, 327, 335, 373, 383, 395, 415])],
    "fig9-25": [("y", 107, [75, 77.7, 162.3, 165]), ("x", 220, [77, 157])],
}
# (axis, coord, center, target)
WIDTHS = {
    "fig7-1": [("x", 50, 110, 0.50), ("y", 270, 245, 0.25)],
    "fig7-15": [("y", 65, 65, 0.50)],
    "fig7-20": [("y", 75, 90, 0.50)],
    "fig7-49": [("y", 102, 40, 0.50)],
    "fig9-2": [("y", 127, 95, 0.50)],
    "fig9-25": [("x", 120, 162, 0.50)],
}

SEG = re.compile(r"^\s+(\d+\.\d+)\s+\.\.\s+(\d+\.\d+)\s+mid\s+(\d+\.\d+)")


def runs(profile, thr=128):
    idx = np.where(profile < thr)[0]
    out = []
    if len(idx):
        s = p = idx[0]
        for i in idx[1:]:
            if i - p > 1:
                out.append((s, p)); s = i
            p = i
        out.append((s, p))
    return out


def cov(a, sx, sy, axis, coord, center, half=0.30):
    prof, sc = (a[:, int(coord * sx)], sy) if axis == "x" else (a[int(coord * sy), :], sx)
    lo, hi = max(0, int((center - half) * sc)), min(len(prof), int((center + half) * sc))
    return float(((255.0 - prof[lo:hi]) / 255.0).sum() / sc)


def main():
    log, ok = [], True
    for name, scans in SCANS.items():
        png = HERE / f"png_{name}" / "p001.png"
        if not png.exists():
            log.append(f"{name}: 缺 {png}"); ok = False; continue
        pw, ph = PAGE[name]
        a = np.array(Image.open(png).convert("L"), dtype=float)
        h, w = a.shape
        sx, sy = w / pw, h / ph
        log.append(f"===== {name}  ({pw}×{ph})")
        for axis, coord, wants in scans:
            prof = a[:, int(coord * sx)] if axis == "x" else a[int(coord * sy), :]
            sc = sy if axis == "x" else sx
            mids = [(s + e) / 2 / sc for s, e in runs(prof)]
            miss = [str(x) for x in wants if not any(abs(m - x) <= TOL for m in mids)]
            log.append(f"  [{axis}={coord:g}] {'✓' if not miss else '✗ 缺 ' + '、'.join(miss)}"
                       f"  实测 {[round(m,1) for m in mids][:14]}")
            if miss:
                ok = False
        for axis, coord, center, target in WIDTHS[name]:
            got = cov(a, sx, sy, axis, coord, center)
            good = abs(got - target) <= 0.05
            log.append(f"  线宽 {axis}={coord:g} 实测 {got:.3f} 目标 {target:.2f} {'PASS' if good else 'FAIL'}")
            if not good:
                ok = False
        c = subprocess.run([PY, str(CLOSED), str(png), "--page", f"{pw}x{ph}", "--min-mm2", "300"],
                           text=True, capture_output=True)
        log.append("  " + (c.stdout.strip() or c.stderr.strip()))
        if c.returncode != 0:
            ok = False
    out = "\n".join(log)
    (HERE / "verify.log").write_text(out + "\n", encoding="utf-8")
    print(out)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
