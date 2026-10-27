# -*- coding: utf-8 -*-
"""verify_all.py —— 六张靶子图的像素扫线 + 闭合检查汇总

坐标一律用“页面坐标”（原点左上、y 向下，与 verify_drawing_lines.py 一致）；
画法函数用的是图纸坐标（y 向上），所以扫描位置是 210 − y图纸。

每条关键位置带期望线型：thick=0.50、thin/center/hidden=0.25（GB 两档）。
线宽统计只取这些“已知线”的 run 长度，不把沿线条方向的扫描和斜剖面线混进来。

输出 verify.log；任一关键位置缺失或线宽超差即 exit 1。
"""
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
VERIFY = ROOT / "check" / "verify_drawing_lines.py"
CLOSED = ROOT / "check" / "check_closed.py"
PY = "/usr/bin/python3"
TOL = 0.45

# name: (scans, center, [(scan, 位置, 线型), ...])
SPEC = {
    "fig8-21": (["x=75", "y=65", "y=85"], "75,85", [
        ("x=75", 60.0, "thick"), ("x=75", 69.9, "thin"), ("x=75", 71.5, "thick"),
        ("x=75", 88.5, "thick"), ("x=75", 90.1, "thin"), ("x=75", 100.0, "thick"),
        ("y=65", 50.0, "thick", False), ("y=65", 110.0, "thick", False),
        ("y=85", 85.0, "thick", False), ("y=85", 140.0, "thick", False)]),
    "fig8-23": (["x=55", "y=84"], "55,84", [
        ("x=55", 74.0, "thin"), ("x=55", 75.5, "thick"),
        ("x=55", 92.5, "thick"), ("x=55", 94.0, "thin"),
        ("x=55", 155.0, "thick"), ("x=55", 156.5, "thin"),
        ("x=55", 173.5, "thin"), ("x=55", 175.0, "thick")]),
    "fig8-40": (["x=130", "y=76"], "130,76", [
        ("x=130", 57.07, "thick", False), ("x=130", 71.95, "thick"), ("x=130", 75.16, "thick", False),
        ("x=130", 79.8, "thick"), ("x=130", 104.84, "thick", False), ("x=130", 122.93, "thick", False),
        ("y=76", 128.2, "thick", False), ("y=76", 128.8, "thick", False),
        ("y=76", 135.6, "thick", False), ("y=76", 136.2, "thick", False)]),
    "fig8-54": (["y=70", "x=78", "x=160"], "78,70", [
        ("y=70", 56.3, "thick", False), ("y=70", 62.6, "thin", False),
        ("y=70", 97.4, "thin", False), ("y=70", 101.0, "center", False), ("y=70", 103.7, "thick", False),
        ("y=70", 111.3, "thick", False), ("y=70", 116.2, "thin", False),
        ("y=70", 195.8, "thin", False), ("y=70", 198.5, "center", False), ("y=70", 200.7, "thick", False),
        ("x=78", 155.0, "thick"), ("x=78", 156.5, "thick"), ("x=78", 162.5, "center"),
        ("x=78", 168.5, "hidden"), ("x=78", 170.0, "thick"),
        ("x=160", 41.0, "thick", False), ("x=160", 43.0, "center", False), ("x=160", 45.5, "thin", False)]),
    "fig8-60": (["y=126.75", "y=133.25"], "148,126.75", [
        ("y=126.75", 120.0, "thick"), ("y=126.75", 128.0, "thick"),
        ("y=133.25", 168.0, "thick"), ("y=133.25", 176.0, "thick")]),
    "fig8-64": (["x=142", "x=144", "x=145"], "142,105", [
        ("x=142", 74.0, "thick"), ("x=142", 90.0, "thick"), ("x=142", 120.0, "thick"),
        ("x=142", 136.0, "thick"),
        ("x=144", 79.35, "thick", False), ("x=144", 84.65, "thick", False),
        ("x=145", 128.0, "thick", False)]),
}

SEG = re.compile(r"^\s+(\d+\.\d+)\s+\.\.\s+(\d+\.\d+)\s+mid\s+(\d+\.\d+)")


def run(cmd):
    return subprocess.run(cmd, text=True, capture_output=True)


def main():
    log, ok = [], True
    by_style = {}
    for name, (scans, center, checks) in SPEC.items():
        png = HERE / f"png_{name}" / "p001.png"
        if not png.exists():
            print(f"{name}: 缺 {png}")
            ok = False
            continue
        cmd = [PY, str(VERIFY), str(png), "--page", "297x210", "--center", center]
        for s in scans:
            cmd += ["--scan", s]
        text = run(cmd).stdout
        block = [f"===== {name}  ({png.relative_to(ROOT)})", text.rstrip()]
        segs, cur = {}, None
        for line in text.splitlines():
            m = re.match(r"\[(x|y)=([\d.]+)mm", line)
            if m:
                cur = f"{m.group(1)}={m.group(2)}"
                segs.setdefault(cur, [])
                continue
            m = SEG.match(line)
            if m and cur:
                segs.setdefault(cur, []).append((float(m.group(3)), float(m.group(2)) - float(m.group(1))))
        from PIL import Image
        import numpy as np
        arr = np.array(Image.open(png).convert("L"), dtype=float)
        H, W = arr.shape
        sx, sy = W / 297.0, H / 210.0

        def 覆盖率(scan, mid):
            axis, _, val = scan.partition("=")
            if axis == "x":
                profile = arr[:, int(float(val) * sx)]
                sc = sy
            else:
                profile = arr[int(float(val) * sy), :]
                sc = sx
            a, b = max(0, int((mid - 0.30) * sc)), min(len(profile), int((mid + 0.30) * sc))
            return float(((255.0 - profile[a:b]) / 255.0).sum() / sc)

        miss = []
        for ck in checks:
            scan, want, style = ck[0], ck[1], ck[2]
            measure = ck[3] if len(ck) > 3 else True
            got = segs.get(scan, [])
            hit = min(got, key=lambda t: abs(t[0] - want)) if got else None
            if hit is None or abs(hit[0] - want) > TOL:
                miss.append(f"{scan} 期望 {want:g}（±{TOL}），实测 {[round(g, 2) for g, _ in got]}")
                continue
            if measure:
                others = [g for g, _ in got if abs(g - hit[0]) > 1e-9]
                if any(abs(o - hit[0]) < 0.7 for o in others):
                    continue          # 两线太近（如楔键 0.6mm 间隙），run 已合并，不量线宽
                w = 覆盖率(scan, hit[0])
                by_style.setdefault(style, []).append(w)
                if abs(w - (0.50 if style == "thick" else 0.25)) > 0.05:
                    log.append(f"  ! {name} {scan} {want:g} {style} 实测 {w:.3f}mm")
        if miss:
            block.append("✗ 关键位置缺失:\n  " + "\n  ".join(miss))
            ok = False
        else:
            block.append(f"✓ 关键位置 {len(checks)} 处全部命中（±{TOL}mm）")
        log.append("\n".join(block))

        c = run([PY, str(CLOSED), str(png), "--page", "297x210", "--min-mm2", "300"])
        log.append(c.stdout.strip() or c.stderr.strip())
        if c.returncode != 0:
            ok = False

    log.append("\n===== 线宽（命中关键线处的扫线 run，mm）")
    for style in ("thick", "thin", "center", "hidden"):
        ws = by_style.get(style, [])
        if not ws:
            continue
        target = 0.50 if style == "thick" else 0.25
        med = statistics.median(ws)
        good = all(abs(w - target) <= 0.05 for w in ws)
        log.append(f"{style:6} n={len(ws):2}  中位 {med:.3f}  "
                   f"区间 {min(ws):.3f}..{max(ws):.3f}  目标 {target:.2f}±0.05  "
                   f"{'PASS' if good else 'CHECK'}")
        if not good:
            ok = False
    out = "\n".join(log)
    (HERE / "verify.log").write_text(out + "\n", encoding="utf-8")
    print(out)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
