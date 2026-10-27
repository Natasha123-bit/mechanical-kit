#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_api.py —— 从代码反射生成 charter/api.md（接口表的唯一真源）。

为什么不用手写接口表：原始规程 §9 的接口表把 `_prim` 里的函数名写错了（那里没有
线/圆/弧，它们在 draw/gbdraw.py 且叫 L/CIRCLE/ARC），照抄就 ImportError。
接口表必须由代码生成，否则一定会随实现漂移。

用法：
    python3 lib/drawing/charter/gen_api.py            # 写 charter/api.md
    python3 lib/drawing/charter/gen_api.py --stdout
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in (str(ROOT), str(ROOT / "draw")):
    if p not in sys.path:
        sys.path.insert(0, p)

from lib.drawing import _prim, sem, sheet  # noqa: E402
from draw import gbdraw  # noqa: E402

OUT = Path(__file__).resolve().parent / "api.md"

GROUPS = [
    ("lib/drawing/_prim.py", "图元层（中文名，画法函数只依赖这一层）", _prim,
     ["图形", "线", "圆", "矩形", "弧", "文", "剖面线", "箭头", "校验图元", "平移", "拼", "落图"]),
    ("lib/drawing/sheet.py", "幅面、图框、标题栏", sheet,
     ["幅面尺寸", "图框", "标题栏"]),
    ("lib/drawing/sem.py", "语义身份（章程 §12）", sem,
     ["R", "G", "SemSheet", "ROLES", "ROLE_TAGS", "MULTI_OK"]),
    ("draw/gbdraw.py", "底层原语与输出器（英文名）", gbdraw,
     ["L", "CIRCLE", "RECT", "ARC", "T", "HATCH", "ARROW", "PATH", "PHASE", "WAVY",
      "DIM_H", "DIM_V", "LEAD", "ROUGH", "TOL_FRAME", "DATUM", "iter_path_commands",
      "STYLES", "TEXT_H", "TEXT_S", "Sheet"]),
]


def sig(fn):
    try:
        return str(inspect.signature(fn))
    except (ValueError, TypeError):
        return ""


def first_doc(fn):
    d = inspect.getdoc(fn) or ""
    return d.splitlines()[0].strip() if d else ""


def render():
    L = []
    A = L.append
    A("# drawing 模块接口表")
    A("")
    A("> 本文件由 `charter/gen_api.py` 从代码反射生成，**不要手改**。")
    A("> 接口以本文件为准；`CHARTER.md` 第 9 章不抄签名。")
    A("")
    for path, title, mod, names in GROUPS:
        A("## %s" % title)
        A("")
        A("`%s`" % path)
        A("")
        A("| 接口 | 签名 | 说明 |")
        A("|---|---|---|")
        for n in names:
            if not hasattr(mod, n):
                A("| `%s` | — | **不存在**（接口表过期，需修正 gen_api.py） |" % n)
                continue
            obj = getattr(mod, n)
            if inspect.isclass(obj):
                A("| `%s` | `class` | %s |" % (n, first_doc(obj)))
                for m, mv in sorted(vars(obj).items()):
                    if m.startswith("_") or not callable(mv):
                        continue
                    A("| `%s.%s` | `%s` | %s |" % (n, m, sig(mv), first_doc(mv)))
            elif inspect.isfunction(obj):
                A("| `%s` | `%s` | %s |" % (n, sig(obj), first_doc(obj)))
            elif isinstance(obj, (set, frozenset)):
                vals = sorted(obj)
                A("| `%s` | `{%s}` | 共 %d 项 |" % (
                    n, ", ".join(vals[:8]) + ("…" if len(vals) > 8 else ""), len(vals)))
            elif isinstance(obj, dict):
                A("| `%s` | `dict`，%d 项 | 键：%s |" % (
                    n, len(obj), ", ".join(map(str, list(obj)[:8]))))
            else:
                A("| `%s` | `%r` | 常量 |" % (n, obj))
        A("")
    A("## 已知输出层约束")
    A("")
    A("- 路径翻转只认 SVG 1.1 的 `M/L/H/V/C/S/Q/T/A/Z`（大小写均可）。")
    A("  `C/S/Q/T` 保留为原生曲线；相对命令（小写）的 dy 取反而不是 `h − y`。")
    A("- 命令元数不合法、出现未识别字符时抛 `ValueError`，不静默降级。")
    A("- 需要更复杂的路径特性（`A` 多组参数、弧的 sweep 语义）时先用最小样例验证，")
    A("  不能假定全部原语都自动适配 `y_up`。")
    A("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdout", action="store_true")
    a = ap.parse_args()
    md = render()
    if a.stdout:
        print(md)
    else:
        OUT.write_text(md, encoding="utf-8")
        print("wrote %s（%d 行）" % (OUT, md.count("\n") + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())