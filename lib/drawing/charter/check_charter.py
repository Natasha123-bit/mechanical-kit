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


def load_rules_registry():
    """把检查器实际注册的规则读出来（L1~L3 + common + part）。

    为什么必须做这一步：正文↔条款表一致只证明「文档内部自洽」。规则引用哪个条款、
    那个条款在表里存不存在、状态是不是 A，此前没有任何程序校验——实测有 14 条规则
    引用了不存在的条款号，章程却一直显示「正文与条款表完全一致」。
    """
    import importlib
    root = HERE.parents[2]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    mods = ["lib.drawing.charter.check_rules"]
    mods += ["lib.drawing.charter." + m for m in
             ("common.gdt", "common.font", "common.lw", "common.table",
              "part.shaft", "part.gear")]
    out = []
    for name in mods:
        mod = importlib.import_module(name)
        for r in mod.RULES:
            out.append((r[0], r[2], name.rsplit(".", 1)[-1]))     # (规则号, 条款号, 模块)
    return out


def check_rule_map(want):
    """每条规则引用的条款必须存在且状态为 A（有自动检查）。"""
    rows = load_rules_registry()
    missing, not_a, dup = [], [], {}
    for rid, cid, mod in rows:
        dup.setdefault(rid, []).append(mod)
        if cid not in want:
            missing.append("%s → %s（%s）" % (rid, cid, mod))
        elif want[cid]["st"] != "A":
            not_a.append("%s → %s 状态 %s（%s）" % (rid, cid, want[cid]["st"], mod))
    twice = [r for r, ms in dup.items() if len(ms) > 1]
    return rows, missing, not_a, twice


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

    try:
        rows, rmiss, rnot_a, rdup = check_rule_map(want)
    except Exception as e:                       # 规则注册表读不出来也算不一致
        print("读规则注册表失败：%r" % (e,), file=sys.stderr)
        return 2
    refs = sorted({cid for _, cid, _ in rows})
    if not a.quiet:
        print("  规则 %d 条，引用条款 %d 个（%s）" % (
            len(rows), len(refs),
            "、".join(sorted({cid for cid in refs if cid}), )[:96]))

    bad = bool(miss or extra or diffs or rmiss or rnot_a or rdup)
    if rmiss:
        print("\n  ✗ 规则引用了不存在的条款 %d 条：%s" % (len(rmiss), "；".join(rmiss[:8])))
    if rnot_a:
        print("\n  ✗ 规则引用的条款状态不是 A %d 条：%s" % (len(rnot_a), "；".join(rnot_a[:8])))
    if rdup:
        print("\n  ✗ 规则号重复注册：%s" % "、".join(rdup[:8]))
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