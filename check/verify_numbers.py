#!/usr/bin/env python3
"""verify_numbers.py — 把答案里的数字/表号拉回教材原文核一遍。

为什么需要它：解题时"查表取 K_A=1.25"这类取值，一旦表号或数字记错，
后续模数、齿数、图纸参数会跟着一起错，而且算式内部自洽查不出来。
道道都能对上课本 → 取值有据；对不上 → 要么是推导/常数，要么就是记错了，逐条看。

用法:
    python3 verify_numbers.py <答案文件或目录> --corpus <OCR 源目录> [--corpus 另一目录]

例：
    python3 verify_numbers.py ~/Desktop/机械设计作业/<题号>解答/ \
        --corpus ~/Documents/Obsidian/机械知识库/raw/sources

注意：缺口 ≠ 错。下列都是已知误报，逐条看：
  - 页码（p.260 / 表11-2）；课本 PDF 该页若未 OCR，页码自然核不到
  - 自己算出来的中间值（d1t、K_H、σ_H）——它们本来就不在课本里
  - 单位换算常数（60×1000 → 60000）、标准件号（GB/T 1095）
真正可疑的是：查表/查图取来的系数、模数、齿数、公差在课本里找不到。
"""
import argparse
import pathlib
import re
import sys

NUM = re.compile(r"\d+(?:\.\d+)?(?:[\u00b0\u2032\u2033])?")
TAG = re.compile(r"<[^>]+>")


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def read_any(p: pathlib.Path) -> str:
    t = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix.lower() in (".html", ".htm"):
        t = TAG.sub(" ", t)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="答案文件或目录（.md/.html/.txt）")
    ap.add_argument("--corpus", action="append", required=True, help="OCR 源目录，可多次给")
    a = ap.parse_args()

    corpus = norm("".join(read_any(p) for d in a.corpus for p in pathlib.Path(d).expanduser().glob("*.md")))
    if not corpus:
        sys.exit("语料为空：--corpus 指向的目录里没有 md")

    tgt = pathlib.Path(a.target).expanduser()
    files = [tgt] if tgt.is_file() else [p for p in tgt.rglob("*") if p.suffix.lower() in (".md", ".html", ".txt")]
    if not files:
        sys.exit("没找到可检文件")

    total = gaps = 0
    for f in files:
        body = read_any(f)
        nums = {n for n in NUM.findall(body)}
        miss = sorted(n for n in nums if n.rstrip("\u00b0\u2032\u2033") not in corpus)
        total += len(nums)
        gaps += len(miss)
        flag = "  " if not miss else "!!"
        print(f"{flag} {f.name[:46]:48s} 数字 {len(nums):>4}  课本里找不到 {len(miss):>3}")
        if miss:
            for m in miss[:25]:
                pos = body.find(m)
                print(f"      {m:>10}  … {body[max(0,pos-50):pos+30].replace(chr(10),' ')}")
            if len(miss) > 25:
                print(f"      … 还有 {len(miss)-25} 个")

    print(f"\n合计：数字 {total}，课本里找不到 {gaps}")
    print("提醒：页码、自己算出的中间值、单位常数、标准件号都是误报；查表/查图取来的值才是重点。")


if __name__ == "__main__":
    main()
