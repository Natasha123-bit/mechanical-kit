#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L0 契约检查 —— 章程 §12：每个图元保留可检查的身份。

只做"图元能不能被机器认出来"这一层，不判画法对错（那是 L1/L2）。
为什么先做这层：role/name/feature 缺一个，后面所有规则都只能靠几何猜，
而"靠猜"的检查在历史上从未抓住过真正的错（画反的圆角、缺名的键槽、夹带的图号）。

用法：
    python3 lib/drawing/charter/check_contract.py 图.svg
    python3 lib/drawing/charter/check_contract.py 图.svg --json
    python3 lib/drawing/charter/check_contract.py 图.svg --min-named 0.9

退出码：0 全部必检项通过；1 有违规；2 检查器自身异常。
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]        # mdkit 根
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing.sem import ROLES, ROLE_TAGS, MULTI_OK  # noqa: E402

SKIP_TAGS = {"svg", "style", "title", "desc", "defs", "metadata", "g"}
IDENT = ("data-role", "data-name", "data-feature", "data-view", "data-src")


def load(path):
    """读 SVG，返回 [(tag, {属性})]，跳过容器与样式。"""
    root = ET.parse(path).getroot()
    rows = []
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in SKIP_TAGS:
            continue
        rows.append((tag, dict(e.attrib)))
    return rows


def audit(rows, min_named=0.6):
    """七条规则；返回 (结果列表, 统计字典)。"""
    res = []
    n = len(rows)
    role_of = Counter(a.get("data-role") for _, a in rows if a.get("data-role"))
    unnamed = Counter()
    unrole = Counter()
    bad_role, bad_tag = [], []
    per_role_tag = defaultdict(Counter)
    named_by_role = Counter()
    for tag, a in rows:
        role = a.get("data-role")
        if not role:
            unrole[tag] += 1
            continue
        per_role_tag[role][tag] += 1
        if role not in ROLES:
            bad_role.append((tag, role))
            continue
        if tag not in ROLE_TAGS.get(role, set()):
            bad_tag.append((tag, role, sorted(ROLE_TAGS.get(role, set()))))
        if not (a.get("data-name") or a.get("data-feature")):
            unnamed[role] += 1
        else:
            named_by_role[role] += 1

    # C1 每个图元有 role
    if not unrole:
        res.append(("C1", "每个图元有 data-role", "必", "通过", "%d/%d" % (n, n)))
    else:
        detail = "%d/%d 缺 role（%.1f%%）：%s" % (
            sum(unrole.values()), n, 100 * sum(unrole.values()) / max(n, 1),
            ", ".join("%s×%d" % (k, v) for k, v in unrole.most_common(6)))
        res.append(("C1", "每个图元有 data-role", "必", "不通过", detail))

    # C2 role 已登记
    res.append(("C2", "role 在章程登记表内", "必",
                "通过" if not bad_role else "不通过",
                "无未登记角色" if not bad_role
                else "未登记 %d 处：%s" % (len(bad_role), bad_role[:4])))

    # C3 role 与元素类型匹配
    res.append(("C3", "role 与元素类型匹配", "必",
                "通过" if not bad_tag else "不通过",
                "无越界组合" if not bad_tag
                else "%d 处越界：%s" % (len(bad_tag), bad_tag[:4])))

    # C4 必须有 outline
    n_out = role_of.get("outline", 0)
    res.append(("C4", "存在 outline（可见轮廓）", "必",
                "通过" if n_out else "不通过",
                "outline %d 个" % n_out if n_out
                else "outline 为 0：轮廓线没打角色，任何“按角色找轮廓”的规则都会空转"))

    # C5 非多实例角色不得整组缺 name/feature
    dead = []
    for role, cnt in role_of.items():
        if not role or role in MULTI_OK:
            continue
        if cnt and named_by_role.get(role, 0) == 0:
            dead.append("%s(%d)" % (role, cnt))
    res.append(("C5", "非多实例角色不得整组缺 name/feature", "必",
                "通过" if not dead else "不通过",
                "无整组缺名" if not dead else "整组缺名：" + ", ".join(sorted(dead))))

    # C6 尺寸必须有箭头（粗查，警示）
    n_dim, n_arr = role_of.get("dimension", 0), role_of.get("arrow", 0)
    ok6 = n_dim == 0 or n_arr >= 2
    res.append(("C6", "尺寸线配到箭头", "警",
                "通过" if ok6 else "警示",
                "dimension %d / arrow %d" % (n_dim, n_arr)))

    # C7 命名覆盖率。分母排除 MULTI_OK：C5 已经明确"剖面线/表格网格这类不要求逐个命名"，
    # 再让它们进 C7 的分母，等于同一条规则在一个地方放宽、在另一个地方扣分。
    tot = sum(c for r, c in role_of.items() if r not in MULTI_OK)
    named = sum(c for r, c in named_by_role.items() if r not in MULTI_OK)
    cov = named / tot if tot else 0.0
    res.append(("C7", "非多实例组命名覆盖率 ≥ %.0f%%" % (min_named * 100), "警",
                "通过" if cov >= min_named else "警示",
                "%d/%d = %.1f%%" % (named, tot, 100 * cov)))

    # C8 语义可疑：同一 role+name 组内碎线过多（折线冒充曲线/轮廓）
    sus = []
    for role, tags in per_role_tag.items():
        if role in MULTI_OK or role in ("section-outline", "key-outline"):
            if tags.get("line", 0) > 60 and not tags.get("path") and not tags.get("circle"):
                sus.append("%s: line×%d（疑为折线拼轮廓）" % (role, tags["line"]))
    res.append(("C8", "轮廓类不该由碎线段堆成", "警",
                "通过" if not sus else "警示",
                "无需解释的碎线" if not sus else "；".join(sus)))

    stat = {
        "total": n,
        "with_role": tot,
        "named": named,
        "role_coverage": round(tot / n, 4) if n else 0,
        "name_coverage": round(cov, 4),
        "name_coverage_all": round(sum(named_by_role.values()) / max(sum(role_of.values()), 1), 4),
        "by_role": dict(role_of),
        "by_tag_missing_role": dict(unrole),
        "by_role_tag": {k: dict(v) for k, v in per_role_tag.items()},
    }
    return res, stat


def report(path, res, stat):
    print("\nL0 契约检查 — %s" % Path(path).name)
    print("  图元 %d 个；role %d（%.1f%%）；name/feature %d（%.1f%%）" % (
        stat["total"], stat["with_role"], 100 * stat["role_coverage"],
        stat["named"], 100 * stat["name_coverage"]))
    print()
    icon = {"通过": "✓", "不通过": "✗", "警示": "!"}
    for rid, name, sev, st, detail in res:
        print("  %s %-3s %-32s %s" % (icon.get(st, " "), rid, name, detail))
    hard = [r for r in res if r[2] == "必"]
    bad = [r for r in hard if r[3] == "不通过"]
    warn = [r for r in res if r[3] == "警示"]
    print("\n  %d/%d 必检通过；%d 警示" % (len(hard) - len(bad), len(hard), len(warn)))
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-named", type=float, default=0.6)
    a = ap.parse_args()
    try:
        rows = load(a.svg)
        res, stat = audit(rows, a.min_named)
    except Exception as e:                       # 检查器自身炸了 ≠ 图合格
        print("检查器异常：%r" % (e,), file=sys.stderr)
        return 2
    ok = report(a.svg, res, stat)
    if a.json:
        print(json.dumps({"ok": ok, "rules": [
            {"id": i, "name": n, "severity": s, "status": st, "evidence": d}
            for i, n, s, st, d in res], "stats": stat}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())