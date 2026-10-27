#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_lookup_ranges.py —— 表型章库「按输入值查得到吗」探针

单元测试全绿不等于查得到：断言用的是**已经解析出来的**行键，
而做题时是拿数值去查（`区间取(表, 35, "…")`）。两回事。

用法：
    cd ~/.hermes/lib/mdkit/lib/<book>
    python3.12 <skill>/scripts/check_lookup_ranges.py .            # 扫全部 *_chNN.py
    python3.12 <skill>/scripts/check_lookup_ranges.py . key_ch04   # 只扫指定模块

做四件事：
  1) 枚举每个 `rows`/`data` 字典（表），统计表数、格子数；
  2) 逐行标签喂 `_lookup._区间()`，列出「看着是区间却解析不出来」的行
     （`自 6~8`、`a≤150`、`—~18`、`50~120（推力球轴承）` 这类）——
     这些行 `区间取()` 永远 KeyError，而 tests 覆盖不到；
  3) 再拿该行自己的下限+0.5 实调一次 `区间取()`，把真查不到的证据打出来；
  4) 基准 `取()` / `行()` 的 µs/次，回答「表大了查表会不会慢」。

退出码：0 = 无缺口；1 = 有查不到的区间行；2 = 用法/导入错误。
"""
import glob
import importlib
import os
import re
import sys
import timeit


def load_modules(lib_dir, prefixes):
    sys.path.insert(0, os.path.abspath(lib_dir))
    mods = []
    if prefixes:
        names = prefixes
    else:
        names = []
        for f in sorted(glob.glob(os.path.join(lib_dir, "*_ch??.py"))):
            m = os.path.basename(f)[:-3]
            if "_tests" in m:
                continue
            names.append(m)
    for n in names:
        try:
            mods.append(importlib.import_module(n))
        except Exception as e:  # noqa: BLE001
            print("! 导入 %s 失败：%s" % (n, e))
    return mods


def tables_of(mod):
    out = []
    for name in dir(mod):
        if name.startswith("_"):
            continue
        obj = getattr(mod, name)
        if isinstance(obj, dict) and "rows" in obj and "data" in obj:
            out.append((name, obj))
    return out


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    lib_dir = sys.argv[1]
    prefixes = sys.argv[2:]
    mods = load_modules(lib_dir, prefixes)
    if not mods:
        print("没有可导入的模块")
        return 2
    try:
        import _lookup as L
    except Exception as e:  # noqa: BLE001
        print("! 无法导入 _lookup：%s" % e)
        return 2
    区间 = getattr(L, "_区间", None)
    区间取 = getattr(L, "区间取", None)

    total_tables = 0
    total_cells = 0
    gaps = []

    for mod in mods:
        tabs = tables_of(mod)
        if tabs:
            print("== %s：%d 个表字典" % (mod.__name__, len(tabs)))
        for tname, t in tabs:
            total_tables += 1
            total_cells += len(t.get("rows") or []) * len(t.get("cols") or [])
            ref = t.get("表号", tname)
            for lab in t.get("rows") or []:
                s = str(lab)
                rangeish = any(ch in s for ch in "~～≤≥<>") and any(c.isdigit() for c in s)
                if not rangeish:
                    continue
                iv = 区间(lab) if 区间 else None
                if iv is not None:
                    continue
                gaps.append((mod.__name__, ref, s, "_区间 解析不了"))
                continue
            # 区间行实调一次
            if 区间取 and t.get("cols"):
                col = t["cols"][-1]
                for lab in t.get("rows") or []:
                    iv = 区间(lab) if 区间 else None
                    if iv is None:
                        continue
                    lo = iv[0]
                    probe = float(lo) + 0.5
                    try:
                        区间取(t, probe, col)
                    except Exception as e:  # noqa: BLE001
                        gaps.append((mod.__name__, ref, "%s (试 %s)" % (lab, probe),
                                     "%s: %s" % (type(e).__name__, str(e)[:70])))

    print("\n表数 %d · 格子 ≈ %s" % (total_tables, format(total_cells, ",")))

    # 基准
    sample = None
    for mod in mods:
        for tname, t in tables_of(mod):
            if t.get("rows") and t.get("cols"):
                sample = t
                break
        if sample:
            break
    if sample:
        n = 20000
        try:
            us = timeit.timeit(lambda: L.取(sample, sample["rows"][0], sample["cols"][-1]),
                               number=n) / n * 1e6
            print("基准 取()：%.1f µs/次" % us)
        except Exception:  # noqa: BLE001
            pass
        try:
            us2 = timeit.timeit(lambda: L.行(sample, sample["rows"][0]), number=n) / n * 1e6
            print("基准 行()：%.1f µs/次" % us2)
        except Exception:  # noqa: BLE001
            pass

    if gaps:
        print("\n!! %d 处查不到（区间行解析/实查失败）：" % len(gaps))
        for m, ref, lab, why in gaps:
            print("   %-20s %-8s %-24s %s" % (m, ref, repr(lab), why))
        print("\n修法：_lookup._区间() 补 `自 a~b` / `a≤x` / `—~b` / `a~b（说明）` 四类形态，"
              "改完跑各章 *_tests.py 必须仍全绿，再复跑本探针。")
        return 1

    print("\nOK：没有查不到的区间行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
