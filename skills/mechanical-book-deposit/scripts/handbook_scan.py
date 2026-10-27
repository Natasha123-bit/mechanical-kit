#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""handbook_scan.py —— 手册/标准汇编类扫描件（没有「第N章」页眉）的两件预处理

这类书 `chmap` 读不出章号与页码（页脚形如 `•56•`，正则要求数字结尾会全灭），
跑 6 分钟后拿到全 null。改用「整本逐页 OCR + 页脚页码」这条链，本脚本做其中两步。

前置（只跑一次，约 0.6 s/页）：
    ~/.hermes/lib/mdkit/bin/ocrpdf <整本.pdf> 1 <总页> _full_ocr

用法：
    handbook_scan.py footer  _full_ocr -o books/<book>/页脚扫描.jsonl
    handbook_scan.py tables  books/<book>/章节地图.json _full_ocr books/<book>/页脚扫描.jsonl \\
                             -o books/<book>/表清单.json

footer：每页末尾两行抓 `[•·]\s*(\d{1,3})` → `{pdf, printed, head, flag}`，
        并打印偏移众数与异常页；产物可直接当 `--chmap` 喂 `book_prepare.py`
        （它只读 `pdf` / `printed` 两个字段，`ch` 留空即可）。
        flag：no-footer（章首页/整页图常见，不是缺页）、back-jump、gap(+n)。

tables：每页正文抓 `表N-x`，按章节地图归章 → `{表号: {pages, continuous}}`。
        **`pages` 是「该表号出现过的页」，正文引用页也会被收进来，不是起始页**；
        起始页必须在页图上核，别拿它当表头位置。
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

NUM = re.compile(r"[•·]\s*(\d{1,3})")
TBL = re.compile(r"表\s*(\d{1,2})\s*[-－–—]\s*(\d{1,3})")
SKIP = "仅供个人科研教学使用"


def footer_page(text):
    """末尾两行里的页脚页码 → (int|None, 该行原文)"""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None, ""
    for l in lines[-2:][::-1]:
        if SKIP in l and not NUM.search(l):
            continue
        m = NUM.search(l)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 999:
                return v, l
    for l in lines[-2:][::-1]:          # 无圆点装饰的纯数字页码行
        if re.fullmatch(r"\d{1,3}", l):
            return int(l), l
    return None, lines[-1]


def cmd_footer(args):
    d = Path(args.ocr_dir)
    files = sorted(d.glob("p*.txt"))
    if not files:
        sys.exit(f"{d} 里没有 pNNN.txt，先跑 bin/ocrpdf")
    rows, prev = [], 0
    for f in files:
        try:
            pdf = int(f.stem[1:])
        except ValueError:
            continue
        pr, tail = footer_page(f.read_text(errors="ignore"))
        flag = ""
        if pr is None:
            flag = "no-footer"
        elif prev and pr < prev:
            flag = "back-jump"
        elif prev and pr > prev + 1:
            flag = f"gap(+{pr - prev})"
        if pr:
            prev = pr
        rows.append({"pdf": pdf, "printed": pr, "head": tail[:60], "flag": flag})

    out = args.out or str(d.parent / "页脚扫描.jsonl")
    with open(out, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")

    ok = [r for r in rows if r["printed"]]
    offs = Counter(r["pdf"] - r["printed"] for r in ok)
    print(f"{len(rows)} 页，读到页脚页码 {len(ok)} 页，未读到 {len(rows) - len(ok)} 页")
    print("偏移众数：" + "，".join(f"+{o}（{n} 页）" for o, n in offs.most_common(4)))
    if offs:
        mode = offs.most_common(1)[0][0]
        odd = [(r["pdf"], r["printed"]) for r in ok if r["pdf"] - r["printed"] != mode]
        print(f"偏离众数的页 {len(odd)} 个（多数是 OCR 误读，逐页核对后再决定是否改）：{odd[:12]}")
    bad = [r for r in rows if r["flag"] in ("back-jump",) or r["flag"].startswith("gap(")]
    for r in bad[:20]:
        print(f"  ⚠ pdf{r['pdf']} printed={r['printed']} {r['flag']}  {r['head']}")
    print(f"→ {out}")
    return 0


def cmd_tables(args):
    chapters = json.loads(Path(args.map_json).read_text())
    ocr = Path(args.ocr_dir)
    printed = {}
    for line in Path(args.footer_jsonl).read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("printed"):
            printed[int(r["pdf"])] = int(r["printed"])

    res = {}
    for c in chapters:
        tag = f"ch{c['ch']:02d}"
        tables = {}
        for k in range(c["pages"]):
            pdf = c["start"] + k
            f = ocr / f"p{pdf:03d}.txt"
            if not f.exists():
                continue
            text = f.read_text(errors="ignore")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            cont = bool(lines) and lines[0].startswith("续表")
            page = printed.get(pdf)
            for m in TBL.finditer(text):
                key = f"表{int(m.group(1))}-{int(m.group(2))}"
                if not key.startswith(f"表{c['ch']}-"):
                    continue
                e = tables.setdefault(key, {"pages": [], "continuous": []})
                if page and page not in e["pages"]:
                    e["pages"].append(page)
                if cont and page and page not in e["continuous"]:
                    e["continuous"].append(page)
        res[tag] = {"ch": c["ch"], "name": c["name"],
                    "printed": f"{c['printed_start']}-{c['printed_end']}",
                    "pages": c["pages"], "table_count": len(tables), "tables": tables}

    out = args.out or "表清单.json"
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    total = sum(v["table_count"] for v in res.values())
    for tag, v in res.items():
        nopage = sum(1 for t in v["tables"].values() if not t["pages"])
        print(f"{tag} p.{v['printed']:>7} {v['pages']:>3} 页  表 {v['table_count']:>3}"
              + (f"  无页 {nopage}" if nopage else ""))
    print(f"合计表号 {total}（表号数 ≠ 表个数：跨页续表同一表号，正文引用页也会被算进来）")
    print(f"→ {out}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="手册类扫描件预处理：页脚页码 → 伪 chmap；表号 → 出现页清单")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("footer", help="逐页 OCR → 页脚页码 jsonl（可当 --chmap）")
    f.add_argument("ocr_dir")
    f.add_argument("-o", "--out", default="")
    f.set_defaults(func=cmd_footer)
    t = sub.add_parser("tables", help="章节地图 + 逐页 OCR → 表号出现页清单")
    t.add_argument("map_json")
    t.add_argument("ocr_dir")
    t.add_argument("footer_jsonl")
    t.add_argument("-o", "--out", default="")
    t.set_defaults(func=cmd_tables)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
