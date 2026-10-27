#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure.py —— 用 Chromium 量真实包围盒，导出给碰撞检查用。

为什么非得开浏览器：CHK-06 要求"文字包围盒必须乘根变换矩阵，只读 getBBox 的
x/y/w/h 会漏掉旋转与分组变换"。本图里竖排尺寸文字全在 <g transform="rotate(...)">
里，按属性算出来的框是横的、位置也是错的——拿那种框判碰撞，报的全是假。

做法：
  1. 把 SVG 原样内联进一个临时 HTML
  2. 页面里跑脚本：逐元素 getBBox() → 累加祖先矩阵 → 四点变换 → 取轴对齐包围盒
  3. 结果塞进 <pre id="hermes-out">，用 chrome --dump-dom 取回来
  4. 存成 JSON：{"texts":[...], "segments":[...], "boxes":[...], "meta":{...}}

坐标一律是**图面毫米**（SVG 用户单位），不是像素：累乘的都是元素自身到根 <svg>
的变换，不含 viewBox→viewport 的那层缩放。

用法：
    python3 lib/drawing/charter/measure.py 图.svg -o 证据/bounds.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# 浏览器路径可用 CHROME 环境变量覆盖；默认取本机 headless Chromium 那一份
CHROME = Path(os.environ.get("CHROME") or (
    Path.home() / ".hermes/tools/chromium-1208/chrome-mac-arm64/"
                   "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"))

JS = r"""
(function () {
  var svg = document.querySelector('svg');
  if (!svg) { document.title = 'NO_SVG'; return; }

  function rootMatrix(el) {
    var m = svg.createSVGMatrix();
    var node = el;
    while (node && node !== svg) {
      if (node.transform && node.transform.baseVal && node.transform.baseVal.numberOfItems) {
        var c = node.transform.baseVal.consolidate();
        if (c) { m = c.matrix.multiply(m); }
      }
      node = node.parentNode;
    }
    return m;
  }

  function apply(m, x, y) {
    return [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f];
  }

  var out = {texts: [], segments: [], boxes: [], skipped: {}};
  var skipTags = {style: 1, title: 1, desc: 1, defs: 1, metadata: 1, g: 1, svg: 1};

  var els = svg.querySelectorAll('*');
  for (var i = 0; i < els.length; i++) {
    var el = els[i];
    var tag = el.tagName.toLowerCase();
    if (skipTags[tag]) { continue; }
    var bb;
    try { bb = el.getBBox(); } catch (e) { out.skipped[tag] = (out.skipped[tag] || 0) + 1; continue; }
    var m = rootMatrix(el);
    var xs = [], ys = [], pts = [[bb.x, bb.y], [bb.x + bb.width, bb.y],
                                 [bb.x, bb.y + bb.height], [bb.x + bb.width, bb.y + bb.height]];
    for (var k = 0; k < 4; k++) {
      var q = apply(m, pts[k][0], pts[k][1]);
      xs.push(q[0]); ys.push(q[1]);
    }
    var rec = {
      tag: tag,
      id: el.getAttribute('id') || '',
      role: el.getAttribute('data-role') || '',
      name: el.getAttribute('data-name') || '',
      xmin: Math.min.apply(null, xs), xmax: Math.max.apply(null, xs),
      ymin: Math.min.apply(null, ys), ymax: Math.max.apply(null, ys)
    };
    if (tag === 'text') {
      rec.t = (el.textContent || '').trim();
      out.texts.push(rec);
    } else {
      if (tag === 'line') {
        var a = apply(m, +el.getAttribute('x1'), +el.getAttribute('y1'));
        var b = apply(m, +el.getAttribute('x2'), +el.getAttribute('y2'));
        out.segments.push({x1: a[0], y1: a[1], x2: b[0], y2: b[1],
                           role: rec.role, name: rec.name, id: rec.id});
      }
      out.boxes.push(rec);
    }
  }
  var pre = document.createElement('pre');
  pre.id = 'hermes-out';
  pre.textContent = JSON.stringify(out);
  document.body.appendChild(pre);
})();
"""


def measure(svg_path: Path, chrome: Path = CHROME, timeout=90) -> dict:
    svg = svg_path.read_text(encoding="utf-8")
    # 去掉 XML 声明，内联进 HTML
    svg_inline = svg.split("?>", 1)[-1] if svg.lstrip().startswith("<?xml") else svg
    html = ("<!doctype html><meta charset='utf-8'>"
            "<style>html,body{margin:0;background:#fff}</style>"
            + svg_inline + "<script>" + JS + "</script>")
    with tempfile.TemporaryDirectory() as td:
        pg = Path(td) / "page.html"
        pg.write_text(html, encoding="utf-8")
        p = subprocess.run([str(chrome), "--headless=new", "--disable-gpu",
                            "--virtual-time-budget=4000", "--no-sandbox",
                            "--dump-dom", pg.as_uri()],
                           capture_output=True, text=True, timeout=timeout)
    dom = p.stdout
    key = '<pre id="hermes-out">'
    i = dom.find(key)
    if i < 0:
        raise RuntimeError("页面没吐出结果（Chrome 输出 %d 字节，stderr: %s）"
                           % (len(dom), (p.stderr or "")[-300:]))
    j = dom.find("</pre>", i)
    raw = dom[i + len(key):j]
    data = json.loads(raw.replace("&amp;", "&").replace("&lt;", "<")
                      .replace("&gt;", ">").replace("&quot;", '"'))
    data["meta"] = {"svg": svg_path.name, "chrome": chrome.name}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("-o", "--out")
    ap.add_argument("--chrome", default=str(CHROME))
    a = ap.parse_args()
    data = measure(Path(a.svg), Path(a.chrome))
    print("\n量测 — %s" % Path(a.svg).name)
    print("  文字 %d 个；线段 %d 条；包围盒 %d 个"
          % (len(data["texts"]), len(data["segments"]), len(data["boxes"])))
    if data.get("skipped"):
        print("  取不到几何的元素：%s" % data["skipped"])
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print("  已写 %s" % a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())