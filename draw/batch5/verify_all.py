# -*- coding: utf-8 -*-
"""verify_all.py —— 批5 五张靶子图像素核对（扫线 + 线宽 + 闭合）"""
import re, subprocess, sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERIFY = ROOT / "check" / "verify_drawing_lines.py"
CLOSED = ROOT / "check" / "check_closed.py"
PY = "/usr/bin/python3"
TOL = 0.45

PAGE = {k: (297, 210) for k in ("fig2-43", "fig3-48", "fig4-11", "fig4-30", "fig5-4")}
# 页面坐标 y = 210 − 图内 y（落图翻 y）
SCANS = {
    "fig2-43": [("y", 90, [105, 117.5, 142.5, 155, 170, 213.3]),
                ("x", 118, [70, 115, 130, 173.3])],
    "fig3-48": [("y", 70, [100, 140, 150, 190]),
                ("x", 125, [65, 75, 105, 115, 130.6, 169.4])],
    "fig4-11": [("y", 100, [90, 120, 150, 165, 185, 205]),
                ("x", 100, [90, 115, 130, 170])],
    "fig4-30": [("y", 100, [78, 90, 150]), ("x", 95, [85, 110, 135, 175])],
    "fig5-4": [("y", 155, [80, 106.3]), ("x", 80, [100, 130, 155])],
}
WIDTHS = {"fig2-43": [("y", 90, 105, 0.50)], "fig3-48": [("y", 70, 100, 0.50)],
          "fig4-11": [("y", 100, 90, 0.50)], "fig4-30": [("y", 100, 90, 0.50)],
          "fig5-4": [("y", 155, 80, 0.50)]}

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
                       f"  实测 {[round(m,1) for m in mids][:16]}")
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
