#!/usr/bin/env python3
"""book_prepare.py — 整本书按章拆分：章节地图 → 单章 PDF → 页图 → OCR 源

章节边界来自教材目录（book_toc.json），不靠页眉猜；
页眉（chmap.jsonl）只用来标定「印刷页 ↔ 书内 PDF 页」的偏移，并在边界页复核章号。
偏移不是全书常数（本扫描件前段 4、后段 3），所以逐章标定。

用法：
  python3 book_prepare.py --book X.pdf --chmap chmap.jsonl --report-only
  python3 book_prepare.py --book X.pdf --chmap chmap.jsonl [--only 8,9] [--skip-existing] [--no-ocr]
"""
import argparse
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
BIN = SCRIPTS.parent / "bin"   # Swift 小工具在 mdkit/bin/，不在 book/

ERRATA = """
## 勘误与说明（本书扫描件实测）

**两把可信的尺子**：书内 201–254 是第10章 54 页、255–286 是第11章 32 页，
与当年手工拆的单章 PDF 逐页一致 → 「目录页码 + 页眉偏移插值」这套边界是可靠的。

**扫描件缺陷（不是拆分错）**：
1. 第11章缺印刷页 **p.280**（279 后直接跳 281）：32 页 = 33 个页码 − 1；章内换算 k≤28 时 `印刷页 = 252+(k−1)`，k≥29 起再加 1。
2. 书内 **287–292 是错位块**：第四篇篇首页、第12章章首页、p.290 正文各重复一次，中间夹第11章习题页(p.285)。处理：第11章截到 286，习题页单独抽成 `_split/ch11-补页-习题p285.pdf` + `assets/<book>/ch11/p033.png`。
3. 第12章章 PDF 从正文 p.290 开始（章首页是重复件，未收），`p001 ↔ 印刷 290`，不缺页。
4. 第15章「轴」止于印刷 403，404–406 不在文件里。
5. 第16–18章（弹簧/机座/减速器）属第五篇，本书 PDF 未包含（`book_toc.json` 标 `in_scan:false`）。
6. **第13/14章边界错位（沉淀第13章时实测）**：第13章真正止于印刷 **p.358**（习题13-1~13-7），不是 p.360。`assets/<book>/ch13/` 的 **p038 是第14章章首页（无页码）、p039 是 p.360（14-1 节正文）**；`assets/<book>/ch14/p001` 从 p.361 起，因此第14章缺自己的章首页与 p.360。做第14章时须用 `ch13/p038.png + ch13/p039.png` 补齐，再从 `ch14/p001.png` 接 p.361。
7. **第7/8章边界错位（沉淀第7章时实测）**：第7章真正止于印刷 **p.147**（习题7-1~7-5、图7-28/29，`assets/<book>/ch07/p022.png`）。`ch07/p023` 是「第三篇 机械传动」篇首页（无页码），`p024–p028` 是第三篇概述（p.150–154，表1~表4 各类传动对比），**不属第7章**。第7章实际 126–147（22 页），章节地图原记 126–154/28 页有误。
8. **第4/5章边界错位（沉淀第4章时实测）**：第4章真正止于印刷 **p.64**（`assets/<book>/ch04/p015.png`，弹性流体动力润滑/流体静力润滑收尾）。`ch04/p016` 是「第二篇 连接」篇首页（无页码），`p017–p018` 是第二篇概述（p.66–67），不属第4章。第4章实际 50–64（15 页），章节地图原记 50–67/18 页有误。

**偏移不是全书常数**：第 1–7 章 +4，第 8 章起 +3（扫描件在第7、8章之间少一页）。`book_prepare.py` 按页眉锚点逐页插值，别拿一个偏移算到底。

**命名约定**：章 PDF 只在 `_split/chNN-章名.pdf` 临时存在（可删，`--split-only` 随时重建）；页图 `raw/assets/<book>/chNN/p{k:03d}.png`（= 章内第 k 页）；OCR 源 `raw/sources/<book>/chNN-全章OCR.md`（每页 `## p.印刷页`）。OCR 里公式体和表体必坏（残迹如 `dm'z3`），一律回页图核。
"""



HANDBOOK_ERRATA = """
## 勘误与说明（本书扫描件实测）

**页码只有页脚一种来源**：本书没有「第N章」页眉，页脚页码形如 `•56•`。`chmap` 的章号与页码正则都读不出（要求数字结尾），
所以先用整本逐页 OCR + `parse_footer_pages.py` 抠页脚数字造伪 chmap（`书内页 = 印刷页 + 12`，全书恒定），
再 `assemble_sources.py` 组装全章 OCR 源；不要按章重复 OCR 一遍。

**目录勘误**：目录写第15章起于 p.207，实测章首页在 **p.208**（p.207 是第14章表14-5/14-6 的续表）。

**无缺页、无重复块**：330 页逐页页码连续，不像教材类扫描件那样有偏移跳变与错位块。

**形态**：全书 270 个表号、只有 7 条编号式（14-1~14-5、15-1、15-2）——沉淀主体是表字典，不是公式库。
"""


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  !! {' '.join(map(str, cmd))[:120]} → {r.stderr.strip()[:200]}")
    return r


def load(chmap):
    return {r["pdf"]: r for r in (json.loads(l) for l in Path(chmap).read_text().splitlines() if l.strip())}


def calibrate(ch, printed_start, pages):
    """用页眉里同章的 (pdf, printed) 对求偏移众数；找不到就返回 None"""
    offs = []
    for pdf, r in pages.items():
        if r.get("ch") == ch and r.get("printed") and abs(r["printed"] - printed_start) < 40:
            h = r.get("head", "")
            if re.search(rf"第\s*{ch}\s*[\.．。]?\s*章", h):
                offs.append(pdf - r["printed"])
    return Counter(offs).most_common(1)[0][0] if offs else None


_CN = "零一二三四五六七八九十"


def _cn_num(n):
    """阿拉伯数字 → 汉字数字（0–99），用于匹配「第一章」这种页眉。"""
    if n <= 10:
        return _CN[n]
    if n < 20:
        return "十" + _CN[n - 10]
    return _CN[n // 10] + "十" + (_CN[n % 10] if n % 10 else "")


def _ch_alt(ch):
    """章号的正则分支：同时接受「第3章」与「第三章」（教材类页眉常用汉字数字）。"""
    alt = re.escape(str(ch))
    try:
        alt += "|" + _cn_num(int(ch))
    except (TypeError, ValueError):
        pass
    return alt


def build(book_toc, pages):
    """章节边界：先用页眉的 (pdf, 印刷页) 锚点插值出逐页印刷号，再按目录把页归章。
    偏移不是常数（本扫描件前段 4、后段 3），插值能自动吃掉这个跳变。"""
    toc = book_toc["chapters"]
    last_printed = book_toc.get("printed_end_last", 10 ** 6)

    def ch_of(pr):
        for i, c in enumerate(toc):
            end = toc[i + 1]["printed_start"] - 1 if i + 1 < len(toc) else last_printed
            if c["printed_start"] <= pr <= end:
                return c
        return None

    # 1) 锚点：页眉里的印刷号，过滤掉离谱值（偏移须落在全书偏移众数 ±1）并保序
    #    偏移不是全书常数，但也不会离众数太远；手册类书页脚页码偏移 12 也要能用，
    #    所以不能写死 2~5（那是《机械设计》教材的偏移），改为按众数自适应。
    offs_all = Counter(pdf - pages[pdf]["printed"] for pdf in sorted(pages)
                       if pages[pdf].get("printed"))
    mode_off = offs_all.most_common(1)[0][0] if offs_all else 4
    anchors, last = [], -1
    for pdf in sorted(pages):
        pr = pages[pdf].get("printed")
        if not pr or abs((pdf - pr) - mode_off) > 2 or pr <= last:
            continue
        anchors.append((pdf, pr)); last = pr
    # 2) 锚点间线性插值 → 每页的印刷号 → 章号
    label = {}
    for (p1, a), (p2, b) in zip(anchors, anchors[1:]):
        for pdf in range(p1, p2):
            label[pdf] = round(a + (pdf - p1) * (b - a) / max(1, p2 - p1))
    for pdf, pr in anchors:
        label[pdf] = pr
    # 首尾锚点之外：按最近锚点的偏移外推（封面/目录页因此会落到第1章之前，被过滤）
    if anchors:
        p0, a0 = anchors[0]
        for pdf in range(1, p0):
            label[pdf] = pdf - (p0 - a0)
        pn, an = anchors[-1]
        for pdf in range(pn + 1, max(pages) + 1):
            label[pdf] = an + (pdf - pn)
    chapters = []
    for pdf in sorted(label):
        c = ch_of(label[pdf])
        if not c:
            continue
        if chapters and chapters[-1]["ch"] == c["ch"]:
            chapters[-1]["end"] = pdf
        else:
            chapters.append({"ch": c["ch"], "name": c["name"], "start": pdf, "end": pdf})
    # 2.5) 剔除扫描错位页（章末被夹进下一章块的情况）
    toc_by_ch = {c["ch"]: c for c in toc}
    for c in chapters:
        skip = set(toc_by_ch.get(c["ch"], {}).get("exclude_pdf", []))
        while c["end"] in skip:
            c["end"] -= 1
    # 3) 补元数据
    for c in chapters:
        c["pages"] = c["end"] - c["start"] + 1
        ps = [label[p] for p in range(c["start"], c["end"] + 1) if p in label]
        c["printed_start"], c["printed_end"] = (min(ps), max(ps)) if ps else (None, None)
        offs = [p - label[p] for p in range(c["start"], c["end"] + 1) if p in label]
        c["offset"] = Counter(offs).most_common(1)[0][0] if offs else None
        h = pages.get(c["start"], {}).get("head", "") or pages.get(c["start"] + 1, {}).get("head", "")
        c["check"] = "起始页有页眉" if re.search(rf"第\s*(?:{_ch_alt(c['ch'])})\s*[\.．。]?\s*章", h) else "起始页为章首页（无页眉），需读页图确认"
    return chapters


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", required=True)
    ap.add_argument("--chmap", required=True)
    ap.add_argument("--toc", default="",
                    help="目录页码 json；缺省用 books/<slug>/book_toc.json（工具目录不放某本书的数据）")
    ap.add_argument("--workdir", default="",
                    help="默认 ~/.hermes/lib/mdkit/books/<slug>；换书时只传 --slug 即可")
    ap.add_argument("--assets", default=os.path.expanduser("~/Documents/Obsidian/机械知识库/raw/assets"))
    ap.add_argument("--sources", default=os.path.expanduser("~/Documents/Obsidian/机械知识库/raw/sources"))
    ap.add_argument("--slug", default="",
                    help="书短代号，决定 assets/<slug>/chNN/ 与 sources/<slug>/ 落点")
    ap.add_argument("--book-title", default="", help="章节地图标题里的书名")
    ap.add_argument("--only", default="")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    ap.add_argument("--split-only", action="store_true", help="只拆章 PDF，不渲图不 OCR")
    ap.add_argument("--scale", default="4")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if not a.slug:
        m = re.search(r"books/([^/]+)/book_toc\.json$", a.toc or "")
        if not m:
            ap.error("请给 --slug（书短代号），或让 --toc 指向 books/<slug>/book_toc.json")
        a.slug = m.group(1)
    if not a.toc:
        cand = SCRIPTS.parent / "books" / a.slug / "book_toc.json"
        if not cand.exists():
            ap.error(f"缺目录文件：{cand}（用 --toc 指定）")
        a.toc = str(cand)
    if not a.workdir:
        a.workdir = os.path.expanduser(f"~/.hermes/lib/mdkit/books/{a.slug}")

    pages = load(a.chmap)
    chapters = build(json.loads(Path(a.toc).read_text()), pages)
    work = Path(a.workdir); work.mkdir(parents=True, exist_ok=True)
    (work / "章节地图.json").write_text(json.dumps(chapters, ensure_ascii=False, indent=2))

    title = a.book_title or f"{a.slug} · 章节地图"
    md = [f"# {title}", "",
          "边界取自教材目录（`book_toc.json`）；偏移由页眉标定，逐章不同。", "",
          "| 章 | 章名 | 书内页 | 印刷页 | 页数 | 偏移 | 边界复核 |", "|---|---|---|---|---|---|---|"]
    for c in chapters:
        md.append(f"| {c['ch']} | {c['name']} | {c.get('start','?')}–{c.get('end','?')} | "
                  f"{c['printed_start']}–{c['printed_end']} | {c['pages']} | {c['offset']} | {c.get('check','')} |")
    errata = {"design": ERRATA, "handbook": HANDBOOK_ERRATA}.get(a.slug, "")
    (work / "章节地图.md").write_text("\n".join(md) + "\n" + errata + "\n")
    print("\n".join(md[4:]))
    if a.report_only:
        print(f"\n地图：{work/'章节地图.md'}")
        return

    only = {int(x) for x in a.only.split(",") if x.strip()} if a.only else None
    for c in chapters:
        if c.get("in_scan") is False:
            continue
        if only and c["ch"] not in only:
            continue
        tag = f"ch{c['ch']:02d}"
        print(f"\n=== {tag} {c['name']} 书内 {c['start']}–{c['end']}（{c['pages']} 页）")
        pdf = work / "_split" / f"{tag}-{c['name']}.pdf"
        if not (a.skip_existing and pdf.exists()):
            one = work / "_one.json"
            one.write_text(json.dumps([c], ensure_ascii=False))
            run([BIN / "pdfsplit", a.book, one, work / "_split"])
            one.unlink(missing_ok=True)
        else:
            print("  章 PDF 已存在")

        if a.split_only:
            continue
        adir = Path(a.assets) / a.slug / tag
        have = len(list(adir.glob("p*.png"))) if adir.exists() else 0
        if a.skip_existing and have >= c["pages"]:
            print(f"  页图已存在（{have}）")
        else:
            adir.mkdir(parents=True, exist_ok=True)
            run([BIN / "renderall", pdf, adir, a.scale])

        if a.no_ocr:
            continue
        sdir = Path(a.sources) / a.slug
        sdir.mkdir(parents=True, exist_ok=True)
        sfile = sdir / f"{tag}-全章OCR.md"
        if a.skip_existing and sfile.exists():
            print("  OCR 源已存在")
            continue
        tmp = Path("/tmp") / f"ocr_{tag}"
        run([BIN / "ocrpdf", pdf, "1", c["pages"], tmp])
        parts = [f"# 第{c['ch']}章 {c['name']}（{tag}）· 全章 OCR\n",
                 f"> 教材第 {c['ch']} 章，印刷页 p.{c['printed_start']}–{c['printed_end']}（共 {c['pages']} 页）。\n"
                 f"> 页图 `{adir}/p{{k:03d}}.png`；**章内第 k 页 ↔ 印刷页 = {c['printed_start']} + (k−1)**。\n"
                 f"> 源 PDF `{pdf}`。公式与表值在 OCR 中必坏，一律回页图核。\n"]
        for k in range(1, c["pages"] + 1):
            f = tmp / f"p{k:03d}.txt"
            body = f.read_text(errors="ignore").strip() if f.exists() else "（本页无文字层，按页图读）"
            printed = c["printed_start"] + k - 1
            parts.append(f"\n## p.{printed}（章内第 {k} 页，`{adir.name}/p{k:03d}.png`）\n\n{body}\n")
        sfile.write_text("".join(parts))
        print(f"  OCR → {sfile.name}（{c['pages']} 页）")

    print(f"\n完成。地图：{work/'章节地图.md'}")


if __name__ == "__main__":
    main()
