#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫「空值且无合盖」的格 —— 验收第二关的同源盲区探针。

为什么需要它：handoff 与章库往往是**同一路读出**（子代理读图 → 主代理原样入库），
逐格比对 0 差异只证明「两边一致」，不证明「与书一致」。实测表12-2 的 132M 行 B 列
（书上 178）在 handoff 与库里同时缺，5842 格比对全过，是靠回页图才抓到。
本脚本把「缺格」全部列出来，再拿去逐处回页图定性：书空 / 合并 / 漏读。

用法（在 lib/<book>/ 下）：
    python3 scan_missing_cells.py motor_ch12 gear_tol_ch10 ...
    python3 scan_missing_cells.py --all          # 扫目录下所有 *_ch*.py（跳过 *_tests.py）

输出：每表「空值且无合盖」格数 + 前几处 (行标签, 列名)，末行给总数。
判据：不是「必须为 0」——书上的空栏本来就该空；要的是**逐处有结论**。
"""
from __future__ import annotations

import glob
import importlib
import os
import sys


def covered(merges, r: int, c: int) -> bool:
    """merges 3 元是 [首行,末行,列]（纵向），4 元是 [首行,末行,首列,末列]（矩形）。"""
    for mg in merges:
        if len(mg) == 3 and mg[2] == c and mg[0] <= r <= mg[1]:
            return True
        if len(mg) == 4 and mg[0] <= r <= mg[1] and mg[2] <= c <= mg[3]:
            return True
    return False


def scan(mod_name: str) -> list[tuple[int, str, str, list[tuple[str, str]]]]:
    mod = importlib.import_module(mod_name)
    out = []
    for attr, d in vars(mod).items():
        if not isinstance(d, dict) or "表号" not in d:
            continue
        rows, cols = d.get("rows") or [], d.get("cols") or []
        data, merges = d.get("data") or [], d.get("merges") or []
        holes, samples = 0, []
        for r, row in enumerate(data):
            for c in range(1, len(cols)):          # 第 0 列是行标签，不查
                if c >= len(row):
                    continue
                v = row[c]
                if v in (None, "") and not covered(merges, r, c):
                    holes += 1
                    if len(samples) < 6:
                        samples.append((str(rows[r]) if r < len(rows) else f"#{r}", str(cols[c])))
        out.append((holes, d["表号"], attr, samples))
    return sorted(out, key=lambda x: (-x[0], x[1], x[2]))


def main() -> int:
    sys.path.insert(0, os.getcwd())        # 在 lib/<book>/ 下跑时按 cwd 找章库
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv or not args:
        args = [os.path.basename(p)[:-3] for p in sorted(glob.glob("*_ch*.py"))
                if not p.endswith("_tests.py")]
    total = 0
    for m in args:
        try:
            res = scan(m)
        except Exception as exc:                   # noqa: BLE001
            print(f"[{m}] 跳过：{exc}")
            continue
        print(f"== {m}")
        for holes, no, attr, samples in res:
            total += holes
            if holes:
                print(f"  {no:8s} {attr[:28]:28s} {holes:3d} 处  {samples}")
        if not any(h for h, *_ in res):
            print("  （无空值且无合盖的格）")
    print(f"\n合计 {total} 处待定性（书空 / 合并 / 漏读，逐处回页图）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
