#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""索引对账：表清单 ↔ 章库 ↔ 索引.json 三方比对，输出差异报告。

用法（在 mdkit 根或任意目录）：
    python3 check/index_diff.py            # 打印到 stdout
    python3 check/index_diff.py --md out.md # 另存 markdown

判据：
  A. 清单有/库无、库有/清单无、索引有/库无（三处集合差）
  B. 页不一致：库 dict 的「页」不在清单 pages 里（清单 pages 可能是跨页列表）
  C. 表题缺失：索引里 表题 为空
  D. 跨页候选：清单 pages 有 ≥2 页 或 continuous 非空
"""
from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import re
import sys

MDKIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LH = os.path.join(MDKIT, "lib", "handbook")
BOOKS = os.path.join(MDKIT, "books", "handbook")
sys.path.insert(0, LH)


def 载入库():
    """返回 {表号: [(模块名, 字典名, dict)]}"""
    out: dict[str, list[tuple[str, str, dict]]] = {}
    for p in sorted(glob.glob(os.path.join(LH, "*_ch*.py"))):
        if p.endswith("_tests.py"):
            continue
        modname = os.path.basename(p)[:-3]
        try:
            mod = importlib.import_module(modname)
        except Exception as exc:  # noqa: BLE001
            print(f"[警告] 模块导入失败 {modname}: {exc}", file=sys.stderr)
            continue
        for attr, obj in vars(mod).items():
            if isinstance(obj, dict) and "表号" in obj and "data" in obj:
                out.setdefault(obj["表号"], []).append((modname, attr, obj))
    return out


def 章号(表号: str) -> int:
    m = re.match(r"表(\d+)-", 表号)
    return int(m.group(1)) if m else -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=None, help="同时写一份 markdown 报告到这里")
    a = ap.parse_args()

    清单 = json.load(open(os.path.join(BOOKS, "表清单.json"), encoding="utf-8"))
    索引 = json.load(open(os.path.join(BOOKS, "索引.json"), encoding="utf-8"))
    库 = 载入库()

    清单表: dict[str, dict] = {}
    for ch, v in 清单.items():
        for t, meta in v.get("tables", {}).items():
            清单表[t] = {"章": ch, **meta}

    L = []
    def w(s=""):
        L.append(s)

    w("# 索引对账单（表清单 ↔ 章库 ↔ 索引.json）")
    w()
    w(f"- 生成时间：{__import__('datetime').datetime.now():%Y-%m-%d %H:%M}")
    w(f"- 表清单：{len(清单表)} 个表号（{len(清单)} 章）")
    w(f"- 章库：{len(库)} 个表号 / {sum(len(v) for v in 库.values())} 个字典")
    w(f"- 索引.json：{索引['统计']['表号总数']} 个表号，入库 {索引['统计']['已入库']}")
    w()

    # ---------- A 集合差 ----------
    只清单 = sorted(set(清单表) - set(库))
    只库 = sorted(set(库) - set(清单表))
    只索引 = sorted(set(索引["表"]) - set(库))
    w("## A. 集合差")
    w()
    w(f"| 类别 | 数 | 明细 |")
    w("|---|---|---|")
    w(f"| 清单有、库无 | {len(只清单)} | {'、'.join(只清单) or '—'} |")
    w(f"| 库有、清单无 | {len(只库)} | {'、'.join(只库) or '—'} |")
    w(f"| 索引有、库无 | {len(只索引)} | {'、'.join(只索引) or '—'} |")
    w()

    # ---------- B 页不一致 ----------
    页差 = []
    for t, metas in 库.items():
        if t not in 清单表:
            continue
        pages = set(清单表[t].get("pages") or [])
        if not pages:
            页差.append((t, "清单页为空", metas[0][2].get("页"), "清单未记页"))
            continue
        库页 = metas[0][2].get("页")
        if 库页 not in pages:
            页差.append((t, f"清单 {sorted(pages)}", 库页, "库页不在清单页里"))
    w("## B. 页不一致（库页 ∉ 清单 pages）")
    w()
    w(f"共 **{len(页差)}** 处。")
    w()
    if 页差:
        w("| 表号 | 清单 | 库 | 说明 |")
        w("|---|---|---|---|")
        for t, c, k, note in sorted(页差, key=lambda x: 章号(x[0])):
            w(f"| {t} | {c} | {k} | {note} |")
    w()

    # ---------- C 缺表题 ----------
    缺题 = sorted(索引["统计"]["无表题"], key=章号)
    w("## C. 缺表题")
    w()
    w(f"共 **{len(缺题)}** 个表号：{'、'.join(缺题) if 缺题 else '—'}")
    w()

    # ---------- D 跨页候选 ----------
    跨页 = [(t, 清单表[t].get("pages"), 清单表[t].get("continuous"))
            for t in 清单表
            if len(清单表[t].get("pages") or []) >= 2 or 清单表[t].get("continuous")]
    w("## D. 清单标记的跨页候选（需回页图按「续表」裁决）")
    w()
    w(f"共 **{len(跨页)}** 个。已验收各章的裁决结论见 `*-验收.md`；清单 pages 只管「这页出现过表号」，"
      "注文交叉引用会造成假跨页。")
    w()

    # ---------- 汇总 ----------
    w("## 汇总")
    w()
    w(f"- 覆盖：{len(库)}/{len(清单表)} 表号在库（{(len(库)/max(len(清单表),1)):.1%}）")
    w(f"- 页面待核：{len(页差)} 处；缺表题：{len(缺题)} 个；跨页候选：{len(跨页)} 个")
    w(f"- 结论：{'结构上无缺口' if not (只清单 or 只库 or 只索引) else '存在集合差，见 A'}")

    text = "\n".join(L) + "\n"
    print(text)
    if a.md:
        open(a.md, "w", encoding="utf-8").write(text)
        print(f"[已写] {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
