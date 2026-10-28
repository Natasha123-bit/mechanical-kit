#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mutants.py —— 给检查器喂错误，看它报不报（CHARTER §15 MUT-01~03）。

为什么要有这一层：L0/L1/L2/L3 说"通过"只证明"跑过的都没问题"，不证明检查器
看得见问题。一个永远返回"通过"的检查器也能让四层全绿。这里往图里注错，
看对应的规则会不会红。

三种结果要分清，退出码也不同：
    抓到              期望的规则变成"不通过"          exit 0 累计
    漏抓              规则没红 —— 检查器有盲区        exit 2
    注入未生效        改完图跟原图一样 —— 用例本身坏了  exit 2

第三种最坑：正则没匹配上、属性名记错，edit 静默返回原文，跑出来"漏抓"，
实际是根本没注进去。所以每次注入后先比哈希，没变就直接判失败，不往下跑。

MUT-01 点名的六类错误（错向槽口/穿字/删箭头/残留整圆/错值文字/不可成形圆角）
每类至少一个用例；其余用例覆盖各层判据。

用法：
    python3 lib/drawing/charter/mutants.py             # 跑全部
    python3 lib/drawing/charter/mutants.py -k L2       # 只跑几何层（MUT-02）
    python3 lib/drawing/charter/mutants.py --list      # 列用例
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing.charter.check_rules import run as check_run   # noqa: E402
from lib.drawing.charter.measure import measure               # noqa: E402

SVG = ROOT / "draw/gear_pipeline/样例-输出轴零件图.svg"
CALC = Path.home() / "Documents/Hermes/机械设计作业/设计测试/calc/s3_shaft.json"
FIG_NO = "SJCS-1"
FEATURES = ROOT / "draw/gear_pipeline/证据/features_shaft.json"


def tag_with(text: str, needle: str) -> str:
    """取包含 needle 的整个标签。找不到就抛，不静默返回原文。"""
    i = text.index(needle)
    a = text.rindex("<", 0, i)
    b = text.index(">", i) + 1
    if text[a:b].endswith("/>"):
        b = text.index("/>", i) + 2
    return text[a:b]


def swap(text: str, needle: str, old: str, new: str) -> str:
    """在 needle 所在的标签内替换一个属性片段。找不到就抛。"""
    t = tag_with(text, needle)
    if old not in t:
        raise KeyError("%r 里没有 %r" % (needle, old))
    return text.replace(t, t.replace(old, new), 1)


@dataclass
class Case:
    name: str
    layer: str            # L1 / L2 / L3，-k 按这个筛（MUT-02）
    expect: str           # 期望变红的规则 id
    kind: str             # MUT-01 的六类之一，或"其它"
    desc: str
    edit: Callable[[str], str]
    bounds: bool = False   # L3 需要重新量测（慢，只有 L3 用例开）
    known_gap: bool = False  # 已登记盲区：漏抓只提示、不判失败（MUT-03）


CASES = [
    # ---------------- L1 结构 ----------------
    Case("dim_value", "L1", "L1-02", "错值文字",
         "尺寸数字 41 改成 40", lambda s: s.replace(">41<", ">40<", 1)),
    Case("no_arrow", "L1", "L1-01", "删箭头",
         "删掉 41 左端的箭头",
         lambda s: s.replace(tag_with(s, 'points="65,47'), "", 1)),
    Case("cut_letter", "L1", "L1-06", "其它",
         "剖切字母 A 改成 Z（与断面名对不上）",
         lambda s: s.replace('>A</text>', '>Z</text>', 1)),
    Case("ext_overshoot", "L1", "L1-04", "其它",
         "共用界线外端 26 拉到 6（超出尺寸线 21mm）",
         lambda s: swap(s, 'y1="97.2" x2="65"', 'y2="26"', 'y2="6"')),

    # ---------------- L2 几何 ----------------
    Case("arc_impossible", "L2", "L2-02", "不可成形圆角",
         "圆角 R2 改成 R0.5（弦长 2.83，画不出来）",
         lambda s: s.replace("M 104 97A 2 2 0 0 0 106 95", "M 104 97A 0.5 0.5 0 0 0 106 95", 1)),
    Case("arc_full_circle", "L2", "L2-05", "残留整圆",
         "断面大半圆弧改成起终点重合的整圆",
         lambda s: s.replace("M 129.383 202A 22.5 22.5 0 1 0 129.383 216",
                             "M 129.383 202A 22.5 22.5 0 1 0 129.384 202", 1)),
    Case("hatch_outside", "L2", "L2-06", "其它",
         "一条剖面线整体移出轮廓 40mm",
         lambda s: swap(swap(s, 'y1="229.253"', 'x1="98.202"', 'x1="58.202"'),
                        'x1="58.202"', 'x2="87.745"', 'x2="47.745"')),
    Case("hatch_angle", "L2", "L2-07", "其它",
         "一条剖面线歪 4°（角度不再一致）",
         lambda s: swap(s, 'y1="229.253"', 'y2="218.796"', 'y2="220.5"')),
    Case("dup_line", "L2", "L2-08", "其它",
         "复制一条轮廓线（完全重合）",
         lambda s: s.replace(tag_with(s, 'y1="97" x2="104"'),
                             tag_with(s, 'y1="97" x2="104"') * 2, 1)),
    Case("out_of_frame", "L2", "L2-09", "其它",
         "加一条 x=450 的线（跑到图框外）",
         lambda s: s.replace("</svg>", '<line x1="450" y1="60" x2="470" y2="60" class="thick" '
                                       'data-role="outline" data-name="mut"/></svg>', 1)),
    Case("seam", "L2", "L2-01", "其它",
         "圆角终点拉开 0.3mm（轮廓留缝）",
         lambda s: s.replace("M 104 97A 2 2 0 0 0 106 95", "M 104 97A 2 2 0 0 0 106 95.3", 1)),

    Case("keyway_flip", "L1", "L1-11", "错向槽口",
         "断面 A 的键槽开到轴线另一侧（x 125 → 91，关于圆心镜像）",
         lambda s: s.replace('<line x1="125" y1="215.7" x2="125" y2="202.3"',
                             '<line x1="91" y1="215.7" x2="91" y2="202.3"', 1), known_gap=True),

    Case("feat_missing", "L2", "L2-10", "其它",
         "删掉清单里的一条轮廓线（完备性：该画的没画）",
         lambda s: __import__("re").sub(
             r'<line[^>]*x1="197"[^>]*y1="97"[^>]*x2="280"[^>]*y2="97"[^>]*/>\s*',
             "", s, count=1)),

    # ---------------- L3 碰撞（要重新量测） ----------------
    Case("text_text", "L3", "L3-01", "穿字",
         "数字 41 挪到 68 的位置（两字重叠）",
         lambda s: swap(s, ">41<", 'x="85.5"', 'x="140"'), bounds=True),
    Case("text_outline", "L3", "L3-02", "穿字",
         "技术要求挪到轴上母线（字压轮廓）",
         lambda s: swap(swap(s, ">技术要求<", 'x="35"', 'x="60"'), ">技术要求<", 'y="243"', 'y="97"'),
         bounds=True),
    Case("text_dim", "L3", "L3-03", "穿字",
         "数字 41 的 y 45.5→47（压到尺寸线上）",
         lambda s: swap(s, ">41<", 'y="45.5"', 'y="47"'), bounds=True),
    Case("dim_cross", "L3", "L3-04", "其它",
         "加一条竖直尺寸线穿过横向尺寸线",
         lambda s: s.replace("</svg>", '<line x1="90" y1="20" x2="90" y2="80" class="thin" '
                                       'data-role="dimension" data-name="mut"/></svg>', 1),
         bounds=True),
    Case("fill_text", "L3", "L3-05", "穿字",
         "数字挪到箭头尖上（压住实心符号）",
         lambda s: swap(swap(s, ">41<", 'x="85.5"', 'x="147"'), ">41<", 'y="45.5"', 'y="90.5"'),
         bounds=True),
]


def sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def run_case(c: Case, src: str, tmp: Path) -> tuple[str, str]:
    """返回 (结果, 说明)。结果 ∈ 抓到 / 漏抓 / 注入未生效。"""
    try:
        new = c.edit(src)
    except Exception as e:
        return "注入未生效", "改法报错：%r" % (e,)
    if new == src or sha(new) == sha(src):
        return "注入未生效", "改完哈希没变——用例本身坏了，不算检查器漏抓"
    f = tmp / ("mut_%s.svg" % c.name)
    f.write_text(new, encoding="utf-8")
    bp = None
    if c.bounds:
        bp = tmp / ("mut_%s.json" % c.name)
        bp.write_text(json.dumps(measure(f), ensure_ascii=False), encoding="utf-8")
    rows = check_run(f, str(CALC), FIG_NO, str(bp) if bp else None,
                     str(FEATURES) if FEATURES.exists() else None)
    st = {r[0]: (r[4], r[5]) for r in rows}
    got = st.get(c.expect)
    if got is None:
        return "漏抓", "检查器里没有 %s 这条规则" % c.expect
    if got[0] == "不通过":
        return "抓到", got[1][:110]
    return "漏抓", "%s 判成 %s：%s" % (c.expect, got[0], got[1][:90])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-k", help="只跑某一层（L1/L2/L3），MUT-02 要求别重复跑无关用例")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    cases = [c for c in CASES if not a.k or c.layer == a.k]
    if a.list:
        for c in cases:
            print("%-16s %s  %-10s %-14s %s" % (c.name, c.layer, c.expect, c.kind, c.desc))
        return 0

    return _run_cases(cases)


def run_all(layer=None, quiet=False):
    """跑全部（或某一层）。供 check.py 直接调用，不碰 sys.argv。"""
    cases = [c for c in CASES if not layer or c.layer == layer]
    return _run_cases(cases, verbose=not quiet)


def _run_cases(cases, verbose=True):
    src = SVG.read_text(encoding="utf-8")
    ok, miss, bad, gap = [], [], [], []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for c in cases:
            res, why = run_case(c, src, tmp)
            if res == "漏抓" and c.known_gap:
                icon = "?"                      # 已登记盲区，不算失败但要看得见
            else:
                icon = {"抓到": "✓", "漏抓": "✗", "注入未生效": "!"}[res]
            if verbose:
                print("  %s %-16s %-3s %-10s %s" % (icon, c.name, c.layer, c.expect, why))
            if res == "抓到":
                ok.append(c.name)
            elif res == "漏抓":
                (gap if c.known_gap else miss).append(c.name)
            else:
                bad.append(c.name)

    print("\n  注入 %d 个：抓到 %d / 漏抓 %d / 已登记盲区 %d / 注入未生效 %d"
          % (len(cases), len(ok), len(miss), len(gap), len(bad)))
    if gap:
        print("  已登记盲区（检查器确实看不见，需要补规则）：%s" % "、".join(gap))
    if bad:
        print("  注入未生效（用例坏了，先修用例）：%s" % "、".join(bad))
    if miss:
        print("  漏抓（检查器有盲区）：%s" % "、".join(miss))
    if miss or bad:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())