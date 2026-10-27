#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_closed.py —— 轮廓闭合的像素证据（不做 vision 判读）

做法：把页面外的白色区域用 floodfill 标掉，剩下的白像素就是被图线围住的区域。
轮廓有断口时，内部白区与页面外连通，剩下白面积会塌到只剩文字笔画里的孔。

用法：
  /usr/bin/python3 check/check_closed.py 图.png --page 297x210 [--min-mm2 500]
输出：enclosed_mm2=…；exit 0/1
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--page", default="297x210")
    ap.add_argument("--min-mm2", type=float, default=500.0)
    a = ap.parse_args()

    pw, ph = (float(v) for v in a.page.lower().split("x"))
    im = Image.open(a.image).convert("RGB")
    w, h = im.size
    ImageDraw.floodfill(im, (0, 0), (255, 0, 255), thresh=180)
    arr = np.array(im)
    white = (arr[:, :, 0] > 240) & (arr[:, :, 1] > 240) & (arr[:, :, 2] > 240)
    px = int(white.sum())
    mm2 = px / (w / pw) / (h / ph)
    print(f"{a.image}: enclosed_white={px}px  enclosed_mm2={mm2:.1f}  min={a.min_mm2:g}")
    return 0 if mm2 >= a.min_mm2 else 1


if __name__ == "__main__":
    sys.exit(main())
