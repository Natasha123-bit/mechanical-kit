#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_charter.py —— 章程正文与条款表的一致性校验。

为什么需要它：章程一旦能漂移，它就不再是章程，只是一篇散文。
本脚本保证 `CHARTER.md` 与 `charter/rules.json` 的条款 id、状态、等级、正文四项完全对齐。

用法：
    python3 lib/drawing/charter/check_charter.py
    python3 lib/drawing/charter/check_charter.py --quiet

退出码：0 一致；1 有漂移；2 读文件出错。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHARTER = HERE.parent / "CHARTER.md"
RULES = HERE / "rules.json"

# - **GEN-01** `X` 必　用程序化矢量绘图…
LINE = re.compile(r"^- \*\*([A-Z]+-\d{2})\*\* `([AMX])` (必|应|宜)　(.+)$")


def load():
    doc = json.loads(RULES.read_text(encoding="utf-8"))
    md = CHARTER.read_text(encoding="utf-8")
    got = {}
    for ln in md.splitlines():
        m = LINE.match(ln.strip())
        if m:
            rid, st, sev, req = m.groups()
            got[rid] = {"st": st, "sev": sev, "req": req.strip()}
    return doc["rules"], got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    try:
        rules, got = load()
    except Exception as e:
        print("读文件失败：%r" % (e,), file=sys.stderr)
        return 2

    want = {r["id"]: r for r in rules}
    miss = sorted(set(want) - set(got))          # 条款表有、正文没写
    extra = sorted(set(got) - set(want))         # 正文有、条款表没有
    diffs = []
    for rid in sorted(set(want) & set(got)):
        w, g = want[rid], got[rid]
        if w["st"] != g["st"]:
            diffs.append("%s 状态：正文 %s / 表 %s" % (rid, g["st"], w["st"]))
        if w["sev"] != g["sev"]:
            diffs.append("%s 等级：正文 %s / 表 %s" % (rid, g["sev"], w["sev"]))
        if w["req"].strip() != g["req"].strip():
            diffs.append("%s 正文不一致：\n    表  ：%s\n    章程：%s" % (rid, w["req"], g["req"]))

    c = collections.Counter(r["st"] for r in rules)
    n = len(rules)
    if not a.quiet:
        print("章程一致性检查")
        print("  条款 %d 条（表）／ %d 条（正文）" % (n, len(got)))
        print("  状态 A %d / M %d / X %d；自动覆盖率 %.1f%%" % (
            c["A"], c["M"], c["X"], 100 * c["A"] / n))
        ch = collections.OrderedDict()
        for r in rules:
            k = r["id"].split("-")[0]
            ch.setdefault(k, [0, 0, 0])
            ch[k]["AMX".index(r["st"])] += 1
        print("  按章（A/M/X）：" + "、".join(
            "%s %d/%d/%d" % (k, v[0], v[1], v[2]) for k, v in ch.items()))

    bad = bool(miss or extra or diffs)
    if miss:
        print("\n  ✗ 条款表有、正文缺失 %d 条：%s" % (len(miss), ", ".join(miss[:12])))
    if extra:
        print("\n  ✗ 正文有、条款表缺失 %d 条：%s" % (len(extra), ", ".join(extra[:12])))
    if diffs:
        print("\n  ✗ 内容不一致 %d 处：" % len(diffs))
        for d in diffs[:10]:
            print("    " + d)
    if not bad:
        print("\n  ✓ 正文与条款表完全一致")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())