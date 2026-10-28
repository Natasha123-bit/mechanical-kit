#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inkbox.py —— 量 SVG 里每个 <text> 的**真实墨迹框**，供碰撞/净距判据用。

为什么要有它：字宽估算（font-size 乘平均字宽）对仿宋窄字形算不准，而且只回答「碰没碰」、
回答不了「净距几毫米」。实测「18 N9」估算 3.5×11 mm、真墨迹 2.6×8.9 mm。

做法：把每个文字原样（同字体、同 font-size、同 text-anchor、同 rotate）搬到探针页上
逐行排开，用同一台 Chromium 渲染，逐行量墨迹包围盒，换算成「相对锚点的偏移」
（SVG 坐标、y 向下、mm）写进 inkbox.json。旋转已在探针里烘进去，检查端不用再算旋转。

用法（需要 PIL 的解释器；macOS 上常是 /usr/bin/python3）：
    env -u PYTHONPATH /usr/bin/python3 inkbox.py 图.svg
    env -u PYTHONPATH /usr/bin/python3 inkbox.py 图.svg --scale 8 --out 我的墨迹.json

前置：图所在目录要有 fonts/ 里的仿宋 TTF（与出图脚本一致）。
检查端换算（y 向上的图纸坐标）：box = (x+dx0, y−dy1, x+dx1, y−dy0)。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

CHROME_CANDIDATES = [
    "~/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "~/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
]
ROW_DY = 24.0      # 行距 mm：rotate(-90) 的文字纵向跨度≈字串长，留足
PER_PAGE = 10
PAGE_W = 220.0
GUTTER = 20.0
FONT_CSS = ("@font-face{font-family:'GBFang';src:url('fonts/STFANGSO.ttf') format('truetype');}"
            ".txt{fill:#000;font-family:'FangSong','STFangsong','GBFang','华文仿宋',serif}")

TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
ATTR = re.compile(r'([\w:-]+)="([^"]*)"')


def find_chrome(explicit=None):
    for c in ([explicit] if explicit else []) + [str(Path(c).expanduser()) for c in CHROME_CANDIDATES]:
        if c and Path(c).exists():
            return c
    sys.exit("找不到 Chromium：用 --chrome <路径> 指定")


def parse(svg_text):
    out = []
    for m in TEXT.finditer(svg_text):
        a = dict(ATTR.findall(m.group(1)))
        mr = re.search(r"rotate\(\s*(-?[\d.]+)", a.get("transform", ""))
        out.append(dict(
            id=a.get("id", ""), x=float(a["x"]), y=float(a["y"]),
            fs=float(a.get("font-size", 3.5)),
            anchor=a.get("text-anchor", "start"),
            rot=float(mr.group(1)) if mr else None,
            text=re.sub(r"<[^>]+>", "", m.group(2)).strip()))
    return out


def probe_html(items):
    rows = []
    for i, it in enumerate(items):
        ay = 30.0 + i * ROW_DY
        tr = ' transform="rotate(%g %g %g)"' % (it["rot"], 30.0, ay) if it["rot"] else ""
        esc = it["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        rows.append('<text x="30" y="%g" font-size="%g" text-anchor="%s"%s>%s</text>'
                    % (ay, it["fs"], it["anchor"], tr, esc))
    h = 30.0 + len(items) * ROW_DY + GUTTER
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
           'viewBox="0 0 %g %g"><style>%s</style>%s</svg>'
           % (PAGE_W, h, PAGE_W, h, FONT_CSS, "".join(rows)))
    html = ("<!doctype html><meta charset='utf-8'><style>@page{size:%gmm %gmm;margin:0}"
            "html,body{margin:0;padding:0;background:#fff}svg{display:block;width:%gmm;"
            "height:%gmm}</style>%s" % (PAGE_W, h, PAGE_W, h, svg))
    return html, h


def ink_of_row(im, k, ay, half):
    """[ay−half, ay+half] 这一行的墨迹 bbox（mm，SVG 坐标）。"""
    H = im.size[1]
    y0 = max(0, int((ay - half) * k))
    y1 = min(H, int((ay + half) * k))
    px = im.load()
    xs, ys = [], []
    for y in range(y0, y1):
        for x in range(im.size[0]):
            if px[x, y] < 128:
                xs.append(x)
                ys.append(y)
                break
        else:
            continue
        for x in range(im.size[0] - 1, -1, -1):
            if px[x, y] < 128:
                xs.append(x)
                break
    if not xs:
        return None
    return (min(xs) / k, max(xs) / k, min(ys) / k, max(ys) / k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--out", default=None)
    ap.add_argument("--scale", type=float, default=4.0, help="deviceScaleFactor，默认 4（≈15.1 px/mm）")
    ap.add_argument("--chrome", default=None)
    a = ap.parse_args()

    svg = Path(a.svg).resolve()
    here = svg.parent
    out = Path(a.out) if a.out else here / "inkbox.json"
    chrome = find_chrome(a.chrome)
    items = parse(svg.read_text(encoding="utf-8"))
    if not items:
        sys.exit("SVG 里没有 <text>")

    boxes = {}
    for p0 in range(0, len(items), PER_PAGE):
        chunk = items[p0:p0 + PER_PAGE]
        html, h = probe_html(chunk)
        tag = "%02d" % (p0 // PER_PAGE)
        p_html, p_png = here / ("_ink_%s.html" % tag), here / ("_ink_%s.png" % tag)
        p_html.write_text(html, encoding="utf-8")
        subprocess.run([chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=%g" % a.scale,
                        "--window-size=%d,%d" % (int(PAGE_W * 96 / 25.4) + 1,
                                                 int(math.ceil(h * 96 / 25.4)) + 1),
                        "--screenshot=%s" % p_png, "file://%s" % p_html],
                       check=True, capture_output=True)
        im = Image.open(p_png).convert("L")
        k = im.size[0] / PAGE_W
        for i, it in enumerate(chunk):
            ay = 30.0 + i * ROW_DY
            bb = ink_of_row(im, k, ay, ROW_DY / 2 - 1.0)
            if bb is None:
                boxes[it["id"]] = [0.0, 0.0, 0.0, 0.0]
                continue
            xa, xb, ya, yb = bb
            boxes[it["id"]] = [round(xa - 30.0, 3), round(xb - 30.0, 3),
                               round(ya - ay, 3), round(yb - ay, 3)]
        p_html.unlink(missing_ok=True)
        p_png.unlink(missing_ok=True)
        print("  探针页 %s：%d 个文字" % (tag, len(chunk)))

    out.write_text(json.dumps({"_说明": "相对锚点的墨迹偏移（SVG 坐标，y 向下，mm）",
                               "src": svg.name, "scale_px_per_mm": round(a.scale * 96 / 25.4, 3),
                               "boxes": boxes}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("→ %s（%d 个文字，%.2f px/mm）" % (out.name, len(boxes), a.scale * 96 / 25.4))


if __name__ == "__main__":
    main()
