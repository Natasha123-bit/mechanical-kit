#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""devloop_crop.py —— 按 data-view 锚点把整页截图切成每块一张。

裁剪区域不靠猜：只认图上的 data-view（ID-02 禁止按 bbox 聚类猜视图归属）。
图上没有 data-view 时只出整页，并提示去补锚点——宁可少给一张，也不给一张
"不知道是哪块"的图。

用法：
    python3 devloop_crop.py 图.svg 整页.png --outdir 预览
    python3 devloop_crop.py 图.svg 整页.png --pad 3 --max 6 --min-side 900

输出（打印绝对路径，给 agent 直接喂 vision）：
    整页 297×210mm → 预览/整页.png
    视图 main  (x 25..120, y 62..165) → 预览/局部_main.png
    ...
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # charter→drawing→lib→mdkit
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing.charter.measure import measure       # noqa: E402

# 判"这是视图"的词。注记块（title/table/tech/note/proj）不在此列。
VIEW_WORDS = ("main", "view", "front", "left", "right", "top", "bottom",
              "end", "section", "iso", "detail", "剖", "视图", "断面", "向")


def svg_size(svg: Path):
    """从 <svg width="297mm" height="210mm"> 取图幅，单位 mm。"""
    head = svg.read_text(encoding="utf-8")[:800]
    w = re.search(r'width="([\d.]+)mm"', head)
    h = re.search(r'height="([\d.]+)mm"', head)
    if w and h:
        return float(w.group(1)), float(h.group(1))
    vb = re.search(r'viewBox="([-\d.\s]+)"', head)
    if vb:
        p = [float(x) for x in vb.group(1).split()]
        return p[2] - p[0], p[3] - p[1]
    return None


def group_bboxes(m: dict) -> dict:
    """按 data-view 归组，每组取并集 bbox（图面毫米，y 向下）。"""
    g = defaultdict(list)
    for coll in ("boxes", "texts"):
        for r in m.get(coll, []):
            v = r.get("view") or ""
            if v:
                g[v].append((r["xmin"], r["ymin"], r["xmax"], r["ymax"]))
    for s in m.get("segments", []):
        v = s.get("view") or ""
        if v:
            g[v].append((min(s["x1"], s["x2"]), min(s["y1"], s["y2"]),
                         max(s["x1"], s["x2"]), max(s["y1"], s["y2"])))
    return {v: (min(b[0] for b in bs), min(b[1] for b in bs),
                max(b[2] for b in bs), max(b[3] for b in bs))
            for v, bs in g.items() if bs}


def is_view(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in VIEW_WORDS)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("png")
    ap.add_argument("--outdir", default="")
    ap.add_argument("--pad", type=float, default=3.0, help="四周留白（mm），默认 2")
    ap.add_argument("--max", type=int, default=5, help="最多出几张局部图，默认 5")
    ap.add_argument("--min-side", type=int, default=900, help="局部图短边像素下限")
    a = ap.parse_args()

    from PIL import Image
    # Pillow 10 把 LANCZOS 挪到 Image.Resampling，两种写法都认
    RESAMPLE = getattr(getattr(Image, "Resampling", Image), "LANCZOS")

    svg, png = Path(a.svg), Path(a.png)
    outdir = Path(a.outdir) if a.outdir else png.parent
    outdir.mkdir(parents=True, exist_ok=True)

    img = Image.open(png).convert("RGB")
    size = svg_size(svg)
    if not size:
        print("读不到图幅尺寸，只出整页", file=sys.stderr)
        print(png)
        return 0
    sw, sh = size
    k = img.width / sw

    m = measure(svg)
    views = group_bboxes(m)
    if not views:
        print("  ! 图上没有 data-view，只出整页。给图元加 data-view 可自动裁出各视图")
        print(png)
        return 0

    # 视图排前，注记排后；注记按面积降序，只取够填 --max 的几张
    vs = sorted([v for v in views if is_view(v)], key=lambda v: -(
        (views[v][2] - views[v][0]) * (views[v][3] - views[v][1])))
    ns = sorted([v for v in views if not is_view(v)], key=lambda v: -(
        (views[v][2] - views[v][0]) * (views[v][3] - views[v][1])))
    picked = (vs + ns)[:a.max]

    print("  整页 %g×%gmm → %s" % (sw, sh, png))
    for v in picked:
        x0, y0, x1, y1 = views[v]
        # measure 给的是屏幕坐标（y 向下），截图像素同样向下，直接乘比例，不翻转
        bx0 = max(0, int((x0 - a.pad) * k))
        by0 = max(0, int((y0 - a.pad) * k))
        bx1 = min(img.width, int((x1 + a.pad) * k))
        by1 = min(img.height, int((y1 + a.pad) * k))
        c = img.crop((bx0, by0, bx1, by1))
        if min(c.width, c.height) < a.min_side:
            # 放大倍数封顶：短边够看、长边不超 2000px、最多 3 倍。
            # 只按短边算会把 134×32mm 的标题栏拉成 3408×900，喂 vision 反而糊
            f = min(a.min_side / max(1, min(c.width, c.height)),
                    2000 / max(1, max(c.width, c.height)),
                    3.0)
            if f > 1.0:
                c = c.resize((int(c.width * f), int(c.height * f)), RESAMPLE)
        out = outdir / ("局部_%s.png" % v)
        c.save(out)
        print("  %-10s (x %g..%g, y %g..%g) → %s  %d×%d"
              % (v, x0, x1, y0, y1, out, c.width, c.height))
    if len(views) > len(picked):
        rest = sorted(set(views) - set(picked))
        print("  （另有 %d 块没裁：%s）" % (len(rest), "、".join(rest)))
    return 0


if __name__ == "__main__":
    sys.exit(main())