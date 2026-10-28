#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fontcov.py —— 字形覆盖核对（CHARTER 8.9）。

问的问题只有一个：**图上每个字，@font-face 那个字体里到底有没有字形**。
没有字形浏览器就会回退到系统字体，PDF 里字形就换了（齿轮项目 `z₂` 的 U+2082
回退宋体就是这么来的），而检查器的字体栈判据看不出来。

要用装了 fontTools 的解释器跑（charter 自己的 python 不带这个包）：

    ~/.venvs/fonttools/bin/python lib/drawing/charter/fontcov.py 图.svg
    ~/.venvs/fonttools/bin/python lib/drawing/charter/fontcov.py 图.svg --json out.json

退出码：0 全覆盖 / 1 有缺字 / 2 读不到字体或解析失败。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "{http://www.w3.org/2000/svg}"


def text_runs(root):
    """[(内容, data-role, 所在字体族 class)] —— 只取画面上有字的 <text>。"""
    out = []
    for t in root.iter(NS + "text"):
        s = "".join(t.itertext()).strip()
        if not s:
            continue
        out.append((s, t.get("data-role") or "", t.get("class") or ""))
    return out


def font_faces(root, svg_dir):
    """@font-face: {family: (kind, 值)}——kind 是 "file"（相对/绝对路径）或 "data"（内嵌 base64）。"""
    css = "".join((st.text or "") for st in root.iter(NS + "style"))
    out = {}
    for m in re.finditer(r"@font-face\s*\{([^}]*)\}", css):
        body = m.group(1)
        fam = re.search(r"font-family\s*:\s*([^;}]+)", body)
        src = re.search(r"url\(\s*['\"]?([^'\")]+)", body)
        if fam and src:
            raw = src.group(1)
            key = fam.group(1).strip("'\" ").lower()
            if raw.startswith("data:"):
                out[key] = ("data", raw)
            else:
                q = Path(raw)
                out[key] = ("file", q if q.is_absolute() else svg_dir / q)
    return out


def cmap_of(path):
    """path 可以是文件路径，也可以是 data:base64 内嵌字体（样例图把字体整个塞在 CSS 里）。"""
    from fontTools.ttLib import TTFont
    from io import BytesIO
    if isinstance(path, str) and path.startswith("data:"):
        import base64
        head, _, b64 = path.partition(",")
        raw = base64.b64decode(b64, validate=False)
        f = TTFont(BytesIO(raw), fontNumber=0, lazy=True)
        return set().union(*[set(t.cmap.keys()) for t in f["cmap"].tables]), \
            (f["name"].getDebugName(1) or "") + "（内嵌）"
    f = TTFont(str(path), fontNumber=0, lazy=True)
    cov = set()
    for table in f["cmap"].tables:
        cov |= set(table.cmap.keys())
    return cov, (f["name"].getDebugName(1) or "")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--json", help="把结果写成 JSON")
    a = ap.parse_args(argv)
    try:
        import fontTools  # noqa: F401
    except ModuleNotFoundError:
        print("这个解释器没有 fontTools。用装了它的解释器跑：", file=sys.stderr)
        print("  ~/.venvs/fonttools/bin/python %s 图.svg" % Path(__file__).name, file=sys.stderr)
        print("  装：uv pip install --python ~/.venvs/fonttools/bin/python fonttools",
              file=sys.stderr)
        print("  或用 FONTTOOLS_PY 指定解释器（G-13 就是这么调它的）", file=sys.stderr)
        return 2                     # 2 = 跑不了；1 的含义是「有缺字」，别混
    p = Path(a.svg)
    root = ET.parse(p).getroot()
    runs = text_runs(root)
    faces = font_faces(root, p.parent)
    if not faces:
        print("没有 @font-face，判不了字形覆盖（图靠系统字体）")
        return 2
    rec = {"svg": str(p), "faces": {}, "missing": [], "n_text": len(runs)}
    covered = set()
    for fam, (kind, fp) in faces.items():
        if kind == "file" and not fp.exists():
            print("字体文件不存在：%s（%s）" % (fp, fam))
            return 2
        cov, name = cmap_of(fp)
        rec["faces"][fam] = {"file": str(fp), "name": name, "glyphs": len(cov)}
        covered |= cov
    need = {}
    for s, role, cls in runs:
        for ch in s:
            if ch in "\n\t ":
                continue
            need.setdefault(ch, []).append(s)
    missing = sorted(ch for ch in need if ord(ch) not in covered)
    rec["chars"] = len(need)
    rec["missing"] = [{"char": c, "U+": "U+%04X" % ord(c), "示例": need[c][:3]} for c in missing]

    print("\n字形覆盖 — %s" % p.name)
    for fam, info in rec["faces"].items():
        print("  字体 %-10s %-28s %d 个字形" % (fam, Path(info["file"]).name, info["glyphs"]))
    print("  图上用字 %d 个（%d 段文字）" % (len(need), len(runs)))
    if missing:
        print("  缺字形 %d 个：" % len(missing))
        for c in missing:
            print("    %r  U+%04X  出现在 %s" % (c, ord(c), "、".join(need[c][:3])[:60]))
    else:
        print("  全部有字形，不会回退")
    if a.json:
        Path(a.json).write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        print("  结果已落盘：%s" % a.json)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())