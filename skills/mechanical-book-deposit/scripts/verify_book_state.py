#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_book_state.py —— 文档与磁盘对账（用户问「现在到底做到哪了 / 和记录有没有出入」时跑这个）

只报事实，不改任何文件。查五件事：
  1. 快照：books/<book>/批*-快照.sha256 里的每个文件是否仍在、字节是否仍相同
  2. 断言：实跑 lib 下每个 *_tests.py（两个解释器），与进度表「断言」列比对
  3. 状态行：沉淀进度.md 每章的 状态 / 库文件 / 断言
  4. 契约：_lookup.py / _anno.py 的 sha256（若该批快照里录了，就与快照比）
  5. 证据面：raw 源与页图今天有没有被改（沉淀只许读 raw，不许写）

用法：
  python3 verify_book_state.py <book> <lib_dir> [--raw <raw_root>] [--since YYYY-MM-DD]
  例：python3 verify_book_state.py handbook ~/.hermes/lib/mdkit/lib/handbook \\
        --raw ~/Documents/Obsidian/机械知识库/raw --since 2026-10-22

判据：快照「已变 / 缺」必须为 0；断言实测 == 进度表；进度表状态只能是四态之一；
      契约文件若与快照不一致，说明有人在你验收后又动过它，先把差异查清再签。
"""
import argparse
import glob
import hashlib
import os
import re
import subprocess
import sys

STATES = ("未开始", "进行中", "待验收（自检已过）", "已验收（抽查过）")
PY = [os.path.expanduser("~/.local/bin/python3.12"), "/usr/bin/python3"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def parse_progress(book_dir):
    """返回 {章号: {name,status,lib,asserts}}；表格列序：章|章名|篇|印刷页|页数|表号|类型|状态|库文件|断言|完成时间"""
    out = {}
    p = os.path.join(book_dir, "沉淀进度.md")
    if not os.path.exists(p):
        return out
    for line in open(p, encoding="utf-8"):
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) < 10:
            continue
        out[c[0]] = {"name": c[1], "status": c[7], "lib": c[8], "asserts": c[9]}
    return out


def verify_snapshots(book_dir, mdkit_root, lib_dir):
    print("\n== 1. 快照 sha256 ==")
    snaps = sorted(glob.glob(os.path.join(book_dir, "批*-快照.sha256")))
    if not snaps:
        print("  （没有快照文件）")
        return {}
    recorded = {}
    for snap in snaps:
        ok = bad = miss = 0
        for line in open(snap, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            h, rel = line.split(None, 1)
            rel = rel.strip()
            cands = [os.path.join(mdkit_root, rel), os.path.join(lib_dir, os.path.basename(rel)),
                     os.path.join(book_dir, rel), os.path.join(book_dir, os.path.basename(rel))]
            f = next((c for c in cands if os.path.exists(c)), None)
            if f is None:
                miss += 1
                print(f"  ! 缺 {rel}")
                continue
            recorded.setdefault(rel, h)
            if sha(f) == h:
                ok += 1
            else:
                bad += 1
                print(f"  ! 已变 {rel}")
        print(f"  {os.path.basename(snap)}: 一致 {ok} · 已变 {bad} · 缺 {miss}")
    return recorded


def run_tests(lib_dir):
    print("\n== 2. 断言（实跑）==")
    res = {}
    for f in sorted(glob.glob(os.path.join(lib_dir, "*_tests.py"))):
        name = os.path.basename(f)[:-3]
        counts = []
        rcs = []
        for py in PY:
            if not os.path.exists(py):
                continue
            r = subprocess.run([py, f], capture_output=True, text=True, cwd=lib_dir)
            tail = (r.stdout or r.stderr).strip().splitlines()[-1:] or [""]
            m = re.search(r"通过 (\d+) 项", tail[0])
            counts.append(int(m.group(1)) if m else -1)
            rcs.append(r.returncode)
        res[name] = (max(counts) if counts else -1, rcs)
        print(f"  {name:26s} 断言={res[name][0]:>4d}  rc={rcs}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("book", help="短代号，如 handbook")
    ap.add_argument("lib_dir", help="章库目录，如 ~/.hermes/lib/mdkit/lib/handbook")
    ap.add_argument("--raw", default=None, help="raw 根目录（可选，查今日是否有写入）")
    ap.add_argument("--since", default=None, help="查 raw 改动的起始日期，默认今天")
    a = ap.parse_args()

    lib_dir = os.path.expanduser(a.lib_dir)
    mdkit_root = os.path.dirname(os.path.dirname(lib_dir.rstrip("/")))
    book_dir = os.path.join(mdkit_root, "books", a.book)
    if not os.path.isdir(book_dir):
        sys.exit(f"找不到书目录：{book_dir}")
    print(f"book={book_dir}\nlib={lib_dir}\nmdkit_root={mdkit_root}")

    recorded = verify_snapshots(book_dir, mdkit_root, lib_dir)
    tests = run_tests(lib_dir)

    print("\n== 3. 进度表 vs 实测断言 ==")
    prog = parse_progress(book_dir)
    for ch, row in prog.items():
        if row["status"] not in STATES:
            print(f"  第{ch}章 状态不在四态内：{row['status']!r}")
            continue
        if row["status"] == "未开始":
            continue
        libname = row["lib"].strip("` ")
        stem = os.path.splitext(libname)[0] if libname and libname != "—" else ""
        got = tests.get(stem + "_tests", (None, []))[0]
        flag = "OK" if str(got) == row["asserts"] else "不一致"
        print(f"  第{ch:>2s}章 {row['name'][:16]:16s} {row['status']:12s} 库={libname:22s} "
              f"断言表={row['asserts']:>4s} 实测={got} {flag}")

    print("\n== 4. 契约文件 ==")
    for f in ("_lookup.py", "_anno.py", "_prim.py"):
        p = os.path.join(lib_dir, f)
        if not os.path.exists(p):
            continue
        rel = os.path.relpath(p, mdkit_root)
        now = sha(p)
        rec = recorded.get(rel)
        print(f"  {f:12s} {now[:16]}  快照={'一致' if rec in (None, now) else '已变 ' + rec[:16]}")

    if a.raw:
        print("\n== 5. raw 是否被写 ==")
        since = a.since or subprocess.run(["date", "+%Y-%m-%d"], capture_output=True, text=True).stdout.strip()
        out = subprocess.run(["find", os.path.expanduser(a.raw), "-newermt", since + " 00:00", "-type", "f"],
                             capture_output=True, text=True).stdout.splitlines()
        print(f"  {since} 起被改文件：{len(out)} 个", "（沉淀只许读 raw）" if out else "")
        for x in out[:5]:
            print("   ", x)

    print("\n说明：快照只覆盖产物文件，不覆盖验收记录与进度表本身——快照全绿不等于文档全对，"
          "状态行与累计数还要按「签字一次落四处」逐处看。")


if __name__ == "__main__":
    main()
