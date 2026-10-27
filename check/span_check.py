#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨页普查：全书 274 张表，逐张看「起始页的下一页」有没有接续，给出 单页/跨页 裁决。

为什么不用清单的 pages：它只记「这页出现过这个表号」，正文里一句「见表10-30」也算，
而且**漏续表页**（表14-3 的 204 是引用、真正的续表 202 没记）。所以本脚本不看清单，
只看章库 dict 里的起始页 `页`，再回逐页 OCR 看下一页。

裁决规则（按证据强度排序）：
  1. 起始页 +1（或 +2）的 OCR 里有「续表」           → 跨页
  2. 起始页 +1 的 OCR 里重印了本表表题（前 8 字）     → 跨页（手册有些续表不写「续表」只重印表题）
  3. 否则                                             → 单页

已知边界：竖排表题、整页扫描糊、以及「续表」出现在起始页 +3 及以后的表（本脚本不追那么远）。

用法：
    python3 check/span_check.py                 # 打印汇总 + 跨页清单
    python3 check/span_check.py --md out.md     # 写完整报告
    python3 check/span_check.py --check         # 只校验已知的 6 条仲裁案例
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

MDKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = os.path.join(MDKIT, "books", "handbook")
OCR = os.path.join(BOOKS, "_full_ocr")
OFFSET = 12  # PDF 页序号 = 印刷页 + 12（表10-5 在印刷 133/134、OCR 落 p145/p146，已实核）

# 各章验收时按页图人工核过的跨页结论（用来校验本脚本，冲突以这些为准）
已知 = {
    "表1-25": "单页", "表1-39": "跨页", "表1-40": "单页",
    "表3-9": "单页",
    "表14-3": "跨页", "表14-4": "单页", "表14-5": "跨页", "表14-6": "跨页",
}


def _ocr(印刷页: int) -> str:
    p = os.path.join(OCR, f"p{印刷页 + OFFSET:03d}.txt")
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def 裁决(no: str, 库页, 表题: str):
    if not isinstance(库页, int):
        return "待核", "章库没有页码"
    题芯 = _norm(表题)[:8]
    for 跳 in (1, 2):
        页 = 库页 + 跳
        txt = _ocr(页)
        if not txt:
            continue
        nt = _norm(txt)
        if "续表" in nt:
            return "跨页", f"起始页 {库页} 之后 {跳} 页（印刷 {页}）有「续表」"
        if len(题芯) >= 4 and 题芯 in nt:
            return "跨页", f"印刷 {页} 重印了表题（手册用重印表题当续表）"
    return "单页", f"印刷 {库页 + 1} 未接续（无「续表」、无重印表题）"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=None)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    索引 = json.load(open(os.path.join(BOOKS, "索引.json"), encoding="utf-8"))["表"]
    清单 = json.load(open(os.path.join(BOOKS, "表清单.json"), encoding="utf-8"))
    清单页 = {}
    for ch, v in 清单.items():
        for no, meta in v.get("tables", {}).items():
            清单页[no] = sorted(set(meta.get("pages") or []) | set(meta.get("continuous") or []))

    rows = []
    for no, meta in sorted(索引.items(), key=lambda kv: (int(re.match(r"表(\d+)-", kv[0]).group(1)), int(re.match(r"表\d+-(\d+)", kv[0]).group(1)))):
        结论, 证据 = 裁决(no, meta.get("页"), meta.get("表题"))
        rows.append({
            "表号": no, "章": meta.get("章"), "库页": meta.get("页"),
            "清单页": 清单页.get(no, []), "结论": 结论, "证据": 证据,
            "表题": (meta.get("表题") or "")[:40],
        })

    跨页 = [r for r in rows if r["结论"] == "跨页"]
    单页 = [r for r in rows if r["结论"] == "单页"]
    待核 = [r for r in rows if r["结论"] == "待核"]

    # 与人工裁决对照
    冲突 = [(no, v, next((r["结论"] for r in rows if r["表号"] == no), "—")) for no, v in 已知.items()
            if next((r["结论"] for r in rows if r["表号"] == no), "—") != v]

    if a.check:
        print(f"人工裁决 {len(已知)} 条，脚本与之一致 {len(已知) - len(冲突)} 条")
        for no, want, got in 冲突:
            print(f"  冲突 {no}: 人工={want} 脚本={got}")
        return 0 if not 冲突 else 1

    L = []
    def w(s=""):
        L.append(s)
    w("# 跨页普查报告（全书 274 表）")
    w()
    w(f"- **跨页**：{len(跨页)} 张")
    w(f"- **单页**：{len(单页)} 张")
    w(f"- 待核：{len(待核)} 张")
    w(f"- 与各章验收页图裁决对照：{len(已知)} 条中**一致 {len(已知) - len(冲突)}**，冲突 {len(冲突)}")
    if 冲突:
        w("  - " + "；".join(f"{no}（人工 {want} / 脚本 {got}）" for no, want, got in 冲突))
    w()
    w("## 跨页表清单")
    w()
    w("| 表号 | 表题 | 起始页 | 证据 |")
    w("|---|---|---|---|")
    for r in 跨页:
        w(f"| {r['表号']} | {r['表题']} | {r['库页']} | {r['证据']} |")
    w()
    w("## 待核")
    w()
    for r in 待核:
        w(f"- {r['表号']}：{r['证据']}")
    if not 待核:
        w("（无）")
    w()
    w("## 单页表清单")
    w()
    w("| 表号 | 起始页 | 清单页 | 说明 |")
    w("|---|---|---|---|")
    for r in 单页:
        extra = [p for p in r["清单页"] if p not in (r["库页"], (r["库页"] or 0) + 1)]
        note = f"清单多记 {extra}（正文引用）" if extra else ""
        w(f"| {r['表号']} | {r['库页']} | {r['清单页'] or '—'} | {note} |")

    text = "\n".join(L) + "\n"
    print("\n".join(L[:12]))
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text)
        print(f"[已写] {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
