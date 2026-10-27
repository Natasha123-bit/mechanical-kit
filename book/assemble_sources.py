#!/usr/bin/env python3
"""assemble_sources.py — 把「整本逐页 OCR」组装成每章一份 OCR 源（与 book_prepare 同格式）

用途：没有「第N章」页眉的书（例如手册类，只有页脚页码）用不上 chmap 的章号字段，
      但整本逐页 OCR 仍然要跑一遍。本工具复用那份逐页文本，避免按章再 OCR 一遍
      （330 页 ≈ 20 分钟）。页图仍由 book_prepare --no-ocr 渲。

用法：
  assemble_sources.py 章节地图.json _full_ocr 输出目录 [--assets 页图根] [--slug handbook] [--chmap 页脚.jsonl]

- 每页印刷页码：优先取 --chmap 里同 pdf 页的 printed（页脚 OCR 得），否则退回 printed_start + k − 1
- 输出 {输出目录}/chNN-全章OCR.md，文件头与 book_prepare.py 生成的一致
"""
import argparse
import json
import re
from pathlib import Path


def load_chmap(p):
    out = {}
    if not p:
        return out
    for l in Path(p).read_text().splitlines():
        if not l.strip():
            continue
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        if r.get("printed"):
            out[int(r["pdf"])] = int(r["printed"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("map_json")
    ap.add_argument("ocr_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--assets", default="")
    ap.add_argument("--slug", default="handbook")
    ap.add_argument("--chmap", default="")
    a = ap.parse_args()

    chapters = json.loads(Path(a.map_json).read_text())
    ocr = Path(a.ocr_dir)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    printed_of = load_chmap(a.chmap)
    assets = Path(a.assets) if a.assets else None

    for c in chapters:
        tag = f"ch{c['ch']:02d}"
        adir = (assets / a.slug / tag) if assets else Path(f"{a.slug}/{tag}")
        parts = [f"# 第{c['ch']}章 {c['name']}（{tag}）· 全章 OCR\n",
                 f"> 教材第 {c['ch']} 章，印刷页 p.{c['printed_start']}–{c['printed_end']}"
                 f"（共 {c['pages']} 页）。\n"
                 f"> 页图 `{adir}/p{{k:03d}}.png`；**章内第 k 页 ↔ 印刷页见各页标题（页脚页码）**。\n"
                 f"> 源 PDF 章节地图 start/end；公式与表值在 OCR 中必坏，一律回页图核。\n"]
        miss = 0
        for k in range(1, c["pages"] + 1):
            pdf = c["start"] + k - 1
            f = ocr / f"p{pdf:03d}.txt"
            if f.exists():
                body = f.read_text(errors="ignore").strip()
            else:
                body = "（本页无文字层，按页图读）"
                miss += 1
            printed = printed_of.get(pdf, c["printed_start"] + k - 1)
            parts.append(f"\n## p.{printed}（章内第 {k} 页，`{adir.name}/p{k:03d}.png`）\n\n{body}\n")
        sfile = out / f"{tag}-全章OCR.md"
        sfile.write_text("".join(parts))
        print(f"{sfile.name}  {c['pages']} 页" + (f"  （缺 {miss} 页）" if miss else ""))


if __name__ == "__main__":
    main()
