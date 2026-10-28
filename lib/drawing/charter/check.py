#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check.py —— 一条命令跑完 L0~L3（需要时连 L4 自检一起跑）。

为什么要这个入口：四层是四个脚本，正确顺序是 measure → L0 → L1-L3。
`--bounds` 忘了传，L3 六条会静默变成"未检查"，屏幕上照样飘着二十几个 ✓，
看不出问题。这个入口把顺序固定死，"未检查"也顶到显眼位置。

用法：
    python3 lib/drawing/charter/check.py 图.svg
    python3 lib/drawing/charter/check.py 图.svg --calc calc.json --fig-no SJCS-1
    python3 lib/drawing/charter/check.py 图.svg --selftest      # 顺带跑 L4 变异
    python3 lib/drawing/charter/check.py 图.svg --no-browser    # 跳过量测（L3 全未检查）

退出码：
    0  没有"不通过"（可能带若干"未检查"，范围会在末尾写明）
    1  有规则"不通过"
    2  检查器自身异常，或 L4 自检漏抓

章程依据：CHK-08 要求"检查器只处理部分图元类型时，必须明确写出未自动覆盖的类型"，
所以末尾一定会打印未检查清单，不会让它们混进 ✓ 里。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing.charter.check_contract import audit, load as load_rows   # noqa: E402
from lib.drawing.charter.check_rules import run as run_rules             # noqa: E402

ICON = {"通过": "✓", "不通过": "✗", "警示": "!", "未检查": "?", "不适用": "—"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--calc", help="计算书 JSON（期望值的独立来源）")
    ap.add_argument("--features",
                    help="要素清单 JSON（完备性 L2-10）；不给就找图同目录的 features.json")
    ap.add_argument("--fig-no", help="应出现的图号")
    ap.add_argument("--no-browser", action="store_true", help="不启动 Chromium 量测")
    ap.add_argument("--selftest", action="store_true", help="顺带跑 L4 变异自检")
    ap.add_argument("--part", choices=("shaft", "gear"),
                    help="加载零件类型规则包（common 层总是加载）")
    ap.add_argument("--json", help="把逐条结果写成 JSON（落盘审计：sha256/字节数/证据）")
    a = ap.parse_args()

    path = Path(a.svg)
    if not path.exists():
        print("找不到文件：%s" % path, file=sys.stderr)
        return 2

    print("\n═══ %s ═══" % path.name)

    # ---------- L0 ----------
    l0 = []
    try:
        rows = load_rows(path)
        res, stat = audit(rows)
        print("\nL0 契约（图元有没有身份）")
        print("  图元 %d；role %.1f%%；name %.1f%%"
              % (stat["total"], 100 * stat["role_coverage"], 100 * stat["name_coverage"]))
        for rid, name, sev, st, detail in res:
            print("  %s %-3s %-30s %s" % (ICON.get(st, " "), rid, name, detail))
            l0.append((rid, st, detail))
    except Exception as e:
        print("\nL0 检查器异常：%r" % (e,), file=sys.stderr)
        return 2

    # ---------- 量测（L3 前置） ----------
    bounds = None
    if not a.no_browser:
        try:
            from lib.drawing.charter.measure import measure
            bounds = measure(path)
            print("\n量测（浏览器 getBBox × 根变换矩阵）")
            print("  文字 %d；线段 %d；包围盒 %d"
                  % (len(bounds["texts"]), len(bounds["segments"]), len(bounds["boxes"])))
        except Exception as e:
            print("\n量测失败：%r —— L3 将全部判未检查" % (e,), file=sys.stderr)
    else:
        print("\n量测：跳过（--no-browser），L3 会全部判未检查")

    # ---------- L1~L3 ----------
    fp = a.features
    if not fp:
        guess = path.with_name("features.json")
        if guess.exists():
            fp = str(guess)
            print("\n要素清单：自动找到 %s" % guess.name)
    # 坏输入（JSON 读不了）不是「图不通过」：契约里 2 = 检查器/输入异常。
    # 以前这里直接抛栈 exit 1，与「有规则不通过」同码，CI 分不清是图坏还是输入坏。
    for label, fpath in (("--calc", a.calc), ("--features", fp)):
        if not fpath:
            continue
        try:
            json.loads(Path(fpath).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print("\n输入文件读不了：%s %s —— %r" % (label, fpath, e), file=sys.stderr)
            print("  这是输入错，不是图错（契约：2 = 检查器或输入异常）", file=sys.stderr)
            return 2

    try:
        rows = run_rules(path, a.calc, a.fig_no, bounds, fp)
    except Exception as e:
        print("\nL1~L3 检查器异常：%r" % (e,), file=sys.stderr)
        return 2
    print("\nL1 结构 / L2 几何 / L3 碰撞")
    for rid, name, ch, sev, st, ev in rows:
        print("  %s %-6s %-32s %s" % (ICON.get(st, " "), rid, name, ev))

    # ---------- common / part ----------
    from lib.drawing.charter.check_rules import make_ctx, run_plugins
    try:
        plug = run_plugins(make_ctx(path, a.calc, a.fig_no, bounds, fp), a.part)
    except Exception as e:
        print("\ncommon/part 规则异常：%r" % (e,), file=sys.stderr)
        return 2
    if plug:
        print("\ncommon%s 规则" % ("＋part（%s）" % a.part if a.part else ""))
        for rid, name, ch, sev, st, ev in plug:
            print("  %s %-6s %-32s %s" % (ICON.get(st, " "), rid, name, ev))
        pst = Counter(x[4] for x in plug)
        print("  → %d 通过 / %d 不通过 / %d 警示 / %d 未检查"
              % (pst.get("通过", 0), pst.get("不通过", 0),
                 pst.get("警示", 0), pst.get("未检查", 0)))

    # ---------- L4 ----------
    mut_rc = None
    if a.selftest:
        from lib.drawing.charter import mutants
        print("\nL4 自检（往临时副本里注错，看规则报不报）")
        mut_rc = mutants.run_all()      # 不能调 main()：它会解析 check.py 的 argv

    # ---------- 汇总 ----------
    st_all = Counter(x[1] for x in l0) + Counter(x[4] for x in rows) + Counter(x[4] for x in plug)
    bad = st_all.get("不通过", 0)
    unk = st_all.get("未检查", 0)
    print("\n── 汇总 ──")
    print("  L0 %d 条 + L1~L3 %d 条 + common/part %d 条（合计 %d）：%d 通过 / %d 不通过 / %d 警示 / %d 未检查"
          % (len(l0), len(rows), len(plug), len(l0) + len(rows) + len(plug),
             st_all.get("通过", 0), bad, st_all.get("警示", 0), unk))
    if unk:
        names = ([x[0] for x in l0 if x[1] == "未检查"]
                 + [x[0] for x in rows if x[4] == "未检查"]
                 + [x[0] for x in plug if x[4] == "未检查"])
        print("  未检查：%s" % "、".join(names))
        print("  （未检查 ≠ 通过。CHK-08 要求把没自动覆盖的类型写出来，不能算进绿。）")
    if bad:
        names = ([x[0] for x in l0 if x[1] == "不通过"]
                 + [x[0] for x in rows if x[4] == "不通过"]
                 + [x[0] for x in plug if x[4] == "不通过"])
        print("  不通过：%s" % "、".join(names))

    if a.json:                      # 落盘：图纸哈希绑住这一版证据，事后能对得上
        import datetime
        import hashlib
        raw = Path(a.svg).read_bytes()
        rec = {
            "svg": str(path), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "fig_no": a.fig_no,
            "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            "scale": "见 L0",
            "l0": [{"id": r[0], "status": r[1], "evidence": r[2]} for r in l0],
            "rules": [{"id": r[0], "name": r[1], "chapter": r[2], "severity": r[3],
                       "status": r[4], "evidence": r[5]} for r in rows],
            "summary": {"pass": st_all.get("通过", 0), "fail": bad,
                        "warn": st_all.get("警示", 0), "unknown": unk,
                        "n_l0": len(l0), "n_rules": len(rows),
                        "n_plugin": len(plug)},
            "mutants": None if mut_rc is None else {"rc": mut_rc},
        }
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rec, ensure_ascii=False, indent=1),
                                encoding="utf-8")
        print("\n结果已落盘：%s" % a.json)

    if mut_rc == 2:
        print("\n退出码 2：L4 自检漏抓或注入未生效")
        return 2
    if bad:
        print("\n退出码 1：有规则不通过")
        return 1
    print("\n退出码 0：跑的规则都过了（范围见上）")
    return 0


if __name__ == "__main__":
    sys.exit(main())