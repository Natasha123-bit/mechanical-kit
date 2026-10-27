#!/usr/bin/env python3
"""逐格核对「库内表值」与「页图上的表值」——验收用，不走 vision、不靠自述。

做法：ocrbox 把页图 OCR 成 (x,y,文本)，按 y 聚成行；每行取「行标签」与「数字流」，
与库内 data 行按顺序对齐（标签相同即配对），逐格比数值。
只比对 OCR 成功成行的行，所以结论是「比过的格没错」；覆盖行数会打印，别当全表覆盖。

用法：
  python3 verify_table_cells.py belt_ch08 表8_4_单根基本额定功率P0 ch08/p009.png ch08/p010.png
  python3 verify_table_cells.py chain_ch09 表9_1_滚子链规格 ch09/p003.png --label-idx 0
  # --label-idx：行标签在 data 行里的下标（默认 1；链号/带型/材料类表用 0）
  # --min-nums ：一行至少几个数字才当作数据行（默认 6，小表调小）

输出：`覆盖 k/N 行，比对 m 格，不一致 0`；有错时逐条打印 `OCR=… 库=…` 并返回退出码 1。

已知局限：① 窄列（如链表的 d1 列）全页 OCR 常整列漏识，此时工具会报"库值在页图上找不到"，
用 sips 裁出该列放大 2 倍再 ocrbox 复核即可（实测 d1 列 10.16/11.91/12.07 都能出来）；
② 行标签是中文短语的表（材料、工况）与 OCR token 对不上，覆盖会是 0，需人工看图。
"""
import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
OCRBOX = SCRIPTS / "ocrbox"
if not OCRBOX.exists():                    # check/ 里不再放软链，直接用 bin/
    OCRBOX = SCRIPTS.parent / "bin" / "ocrbox"
ASSETS = Path(os.path.expanduser("~/Documents/Obsidian/机械知识库/raw/assets"))
NUM = re.compile(r"\d+(?:\.\d+)?")


LIB = SCRIPTS.parent / "lib"


def load(mod):
    """接受两种写法：`belt_ch08`（自动去 lib/<书>/ 找）或 `../lib/design/belt_ch08`。"""
    path = SCRIPTS / f"{mod}.py"
    if not path.exists():
        hits = sorted(LIB.glob(f"*/{mod}.py"))
        if len(hits) == 1:
            path = hits[0]
        elif len(hits) > 1:
            raise SystemExit(f"{mod} 在多本书里都有："
                             + "、".join(h.parent.name for h in hits)
                             + "，请写成 <书>/" + mod)
        else:
            raise SystemExit(f"找不到 {mod}.py（找过 {SCRIPTS} 与 {LIB}/*/）")
    spec = importlib.util.spec_from_file_location(mod, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[mod] = m
    spec.loader.exec_module(m)
    return m


def page_rows(png, min_nums):
    out = subprocess.run([str(OCRBOX), str(png)], capture_output=True, text=True).stdout
    items = []
    for line in out.splitlines():
        p = line.split(None, 4)
        if len(p) < 5:
            continue
        items.append((float(p[1]), float(p[0]), p[4]))
    items.sort()
    clusters, cur = [], None
    for y, x, t in items:
        if cur and abs(y - cur[0]) < 12:
            cur[1].append((x, t))
        else:
            cur = [y, [(x, t)]]
            clusters.append(cur)
    rows = []
    for _, its in clusters:
        its.sort()
        toks = [re.sub(r"\s+", "", t) for _, t in its]
        nums = [t for t in toks if NUM.fullmatch(t)]
        if len(nums) >= min_nums:
            rows.append((toks, nums))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mod")
    ap.add_argument("table")
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--label-idx", type=int, default=1)
    ap.add_argument("--min-nums", type=int, default=6)
    ap.add_argument("--assets", default=str(ASSETS),
                    help="页图根目录（默认 ~/Documents/Obsidian/机械知识库/raw/assets）")
    a = ap.parse_args()

    lib = getattr(load(a.mod), a.table)["data"]
    labels = [str(r[a.label_idx]) for r in lib]
    ptr = cells = hit = 0
    bad = []
    shifted = []
    for rel in a.pages:
        页行 = page_rows(Path(a.assets) / rel, a.min_nums)
        页全部 = {t for toks, _ in 页行 for t in toks}
        for toks, nums in 页行:
            if nums[:3] == ["400", "700", "800"]:      # 表8-4 转速表头
                continue
            j = None
            for k in range(ptr, len(lib)):
                if labels[k] in toks:                   # 标签可以是数字也可以是字母/中文
                    j = k
                    break
            if j is None:
                continue
            ptr = j + 1
            hit += 1
            vals = list(lib[j][a.label_idx + 1:])
            lab = labels[j]
            seq = [t for t in nums if t != lab]         # 去掉标签本身
            # 用贪心对齐：逐个数在库行里往后找同值，允许中间某列 OCR 没识出（跳过）。
            # 这样漏识只记"跳过一列"，不会把后面所有列判成错。
            跳过, 坏 = [], []
            k = 0
            for v in seq:
                while k < len(vals) and (vals[k] is None or abs(float(v) - float(vals[k])) > 1e-9):
                    if vals[k] is not None:
                        跳过.append(k)
                    k += 1
                if k >= len(vals):
                    bad.append(f"{rel} 行{lab} OCR 多出一个 {v}（库里已无数可对）")
                    break
                cells += 1
                k += 1
            for k2 in 跳过:
                库值 = str(vals[k2])
                if 库值 in 页全部:
                    shifted.append(f"{rel} 行{lab} 第{k2 + 1}列 OCR 顺序错位（库值 {库值} 在页面上存在）")
                else:
                    bad.append(f"{rel} 行{lab} 第{k2 + 1}列 库={库值} 在页图上找不到该数字")

    print(f"{a.mod}/{a.table}: 覆盖 {hit}/{len(lib)} 行，比对 {cells} 格，不一致 {len(bad)}"
          + (f"；另有 {len(shifted)} 处列序错位（库值均在页面上存在）" if shifted else ""))
    for s in shifted[:5]:
        print("  ~ " + s)
    for b in bad[:20]:
        print("  " + b)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
