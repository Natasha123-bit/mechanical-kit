#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_handoff_vs_lib.py —— 验收第二关：handoff JSON ↔ 章库 逐格对账

用法（在 lib/<book>/ 下跑，两个解释器都行）：
    python3 <此脚本> handoff-ch04 key_ch04 handoff-ch06 bearing_r_ch06 ...
参数成对：<books/<book>/ 下的 handoff 目录名> <lib/<book>/ 下的模块名>。

为什么不能只靠“抽查几格”：表型手册一章几千格，抽 5 格过了不代表其余一致；
这个脚本把 handoff 里核过的每一格与库里落的值逐格比，26k 格只要几秒，
“值不一致 0” 才是「库没有凭空造值」的硬证据（页图抽核另行做，见 SKILL.md）。

三个必须处理的假阳性（不处理会报出一堆红字，白花一小时）：
  ① 一个表号 → 库里多个字典：手工书常把 表4-6 拆成「圆柱销/圆锥销」、表6-5 拆成 49/69、
     表10-6 拆成 T05..T12。所以配对键是「表号 + rows/cols 完全相同」，不是表号。
  ② 重复行标签：表9-8 有 7 行都叫「—」。按 rows.index(标签) 找行会把后面的行全对齐到第一行，
     报出「库值=Ⓜ、handoff=Ⓛ」这种假差异。rows 列表完全相等时一律按下标比。
  ③ 轻量 schema：有的 handoff 只写 rows/cols 的**数量**（int）+ cols_desc，没有行标签。
     这种按数据块尺寸（行数×列数）配对后逐格比，别丢下不比。

输出：每章一行摘要（handoff 表段数 / 配上几段 / 比了几格 / 值不一致几格）+ 前 20 条差异。
退出码恒 0；判据看摘要里的「不一致 0」和「配上/表段」比例。
"""
import importlib
import json
import os
import sys

BOOK = os.path.expanduser("~/.hermes/lib/mdkit/books")
LIB = os.path.expanduser("~/.hermes/lib/mdkit/lib")
BOOK_SLUG = os.environ.get("BOOK_SLUG", "handbook")


def norm(x):
    if x is None:
        return None
    return str(x).strip().replace(" ", "").replace("\u3000", "")


def lib_tables(mod_dir, modname):
    sys.path.insert(0, mod_dir)
    mod = importlib.import_module(modname)
    out = []
    for name in dir(mod):
        o = getattr(mod, name)
        if isinstance(o, dict) and "rows" in o and "data" in o and "\u8868\u53f7" in o:
            out.append((name, o))
    return out


def handoff_tables(book_dir):
    """读一个 handoff 目录里的表段。兼容两种键名：
       · `tables` + `表号`（表值型章节）
       · `表` + `ref`（流程型/图例型章节，如 ch17/ch18；这类 handoff 常是「先入库后导出」的镜像，
         能查到漂移但不构成独立证据——摘要会单独提示）
    """
    out = []
    for f in sorted(os.listdir(book_dir)):
        if not f.endswith(".json") or f.startswith("00-"):
            continue
        try:
            d = json.load(open(os.path.join(book_dir, f), encoding="utf-8"))
        except Exception:
            continue
        for t in (d.get("tables") or d.get("\u8868") or []):
            if not isinstance(t, dict):
                continue
            tn = t.get("\u8868\u53f7") or t.get("ref")
            if tn:
                t = dict(t)
                t["\u8868\u53f7"] = tn
                out.append((f, t))
    return out


def cmp_light(tn, fname, H, cand, detail):
    """轻量 schema（rows/cols 是数量）：按数据块尺寸配对后逐格比。返回 (配上?, 格数, 不一致数)"""
    hd = H["data"]
    for vname, L in cand:
        if len(L["data"]) == len(hd) and (not hd or len(L["data"][0]) == len(hd[0])):
            cells = bad = 0
            for r in range(len(hd)):
                for c in range(len(hd[r])):
                    cells += 1
                    if norm(hd[r][c]) != norm(L["data"][r][c]):
                        bad += 1
                        if len(detail) < 20:
                            detail.append(f"{tn}[{vname}] 第{r+1}行第{c+1}列: handoff={norm(hd[r][c])!r} lib={norm(L['data'][r][c])!r}")
            return True, cells, bad
    detail.append(f"{tn} [{fname}] 轻量表：库内无同尺寸字典（候补：{[v for v, _ in cand] or '无'}）")
    return False, 0, 0


def main(pairs):
    for chdir, modname in pairs:
        book_dir = os.path.join(BOOK, BOOK_SLUG, chdir)
        libs = lib_tables(os.path.join(LIB, BOOK_SLUG), modname)
        hos = handoff_tables(book_dir)
        used = set()
        matched = cells = bad = 0
        detail = []
        for fname, H in hos:
            tn = str(H["\u8868\u53f7"])
            if isinstance(H.get("rows"), int) and isinstance(H.get("data"), (list, tuple)):
                cand = [(v, L) for v, L in libs if str(L["\u8868\u53f7"]) == tn]
                ok, c2, b2 = cmp_light(tn, fname, H, cand, detail)
                if ok:
                    matched += 1
                    cells += c2
                    bad += b2
                continue
            if not isinstance(H.get("rows"), (list, tuple)) or not isinstance(H.get("data"), (list, tuple)):
                detail.append(f"{tn} [{fname}] rows/data 不是列表，跳过")
                continue
            hr = [norm(x) for x in H["rows"]]
            hc = [norm(x) for x in H.get("cols") or []]
            hit = None
            for i, (vname, L) in enumerate(libs):
                if str(L["\u8868\u53f7"]) != tn or i in used:
                    continue
                if [norm(x) for x in L["rows"]] == hr and [norm(x) for x in L.get("cols") or []] == hc:
                    hit = (i, vname, L)
                    break
            if hit is None:
                same = [v for i, (v, L) in enumerate(libs) if str(L["\u8868\u53f7"]) == tn]
                detail.append(f"{tn} [{fname}] 库里没有同结构字典（同表号的库字典：{same or '无'}）")
                continue
            i, vname, L = hit
            used.add(i)
            matched += 1
            for r in range(min(len(hr), len(L["data"]))):
                for c in range(min(len(H["data"][r]), len(L["data"][r]))):
                    cells += 1
                    a, b = norm(H["data"][r][c]), norm(L["data"][r][c])
                    if a != b:
                        bad += 1
                        if len(detail) < 20:
                            detail.append(f"{tn}[{vname}] 行{hr[r]} 列{(L.get('cols') or [])[c]}: handoff={a!r} lib={b!r}")
        unused = [v for i, (v, L) in enumerate(libs) if i not in used]
        print(f"\n=== {chdir} \u2194 {modname} ===")
        print(f"handoff \u8868\u6bb5 {len(hos)} \u00b7 \u914d\u4e0a {matched} \u00b7 \u5e93\u5185\u5b57\u5178 {len(libs)} \u00b7 \u5e93\u5185\u672a\u914d\u5bf9 {unused or '\u65e0'}")
        print(f"\u683c\uff1a\u6bd4\u5bf9 {cells} \u00b7 \u4e0d\u4e00\u81f4 {bad}")
        if matched == 0 and libs:
            print("   \u26a0\ufe0f WARN \u914d\u4e0a 0 \u6bb5 \u4f46\u5e93\u91cc\u6709\u5b57\u5178\uff1a\u8fd9\u4e0d\u662f\u300c\u96f6\u5dee\u5f02\u300d\uff0c\u662f\u4e00\u683c\u6ca1\u9a8c\u3002\u5e38\u89c1\u4e8e\u955c\u50cf handoff\uff08\u5148\u5165\u5e93\u540e\u5bfc\u51fa\uff09\u6216\u952e\u540d\u4e0d\u540c\uff1b\u672c\u7ae0\u5fc5\u987b\u6539\u8d70\u9875\u56fe\u62bd\u6838\uff0c\u5e76\u5728\u9a8c\u6536\u8bb0\u5f55\u91cc\u5199\u660e\u300c\u65e0\u72ec\u7acb\u8bc1\u636e\u300d")
        for d in detail[:20]:
            print("   ", d)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    main([(a[i], a[i + 1]) for i in range(0, len(a), 2)])
