#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教材路径自检：换书根、加书层、挪页图之后跑一次。

查三件事：
  1. 旧形态残留 —— raw/assets/chNN、raw/sources/chNN（缺 <book> 层）
  2. 顶层散落   —— raw/assets、raw/sources 顶层是否只剩 <book> 目录
  3. 引用有效性 —— md 里写的 assets/<book>/chNN/pNNN.png 是否真的存在

用法：
  python3 check_paths.py
  python3 check_paths.py --book design
  python3 check_paths.py --vault ~/Documents/Obsidian/机械知识库 --skills ... --mdkit ...

退出码 0 = 全过，1 = 有问题（非 0 就不要说「搬完了」）。
"""
import argparse
import pathlib
import re
import sys

HOME = pathlib.Path.home()
OLD = re.compile(r'raw/(?:assets|sources)/ch\d')
BOOKDIR = re.compile(r'^[a-z][a-z0-9_-]*$')
REF = re.compile(r'assets/([a-z][a-z0-9_-]*)/ch(\d\d)/p(\d{3})\.png')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vault', default=str(HOME / 'Documents/Obsidian/机械知识库'))
    ap.add_argument('--skills', default=str(HOME / '.hermes/skills/engineering'))
    ap.add_argument('--mdkit', default=str(HOME / '.hermes/lib/mdkit'))
    ap.add_argument('--book', default='', help='只看某本书；留空查全部')
    a = ap.parse_args()

    vault = pathlib.Path(a.vault)
    raw = vault / 'raw'
    bad = 0

    print('== 1) 旧形态残留（缺 <book> 层）==')
    hits = 0
    for root in (pathlib.Path(a.skills), pathlib.Path(a.mdkit), vault):
        if not root.exists():
            continue
        for p in sorted(root.rglob('*.md')):
            try:
                text = p.read_text(errors='ignore')
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if OLD.search(line):
                    hits += 1
                    print('  %s:%d  %s' % (p, i, line.strip()[:110]))
    if hits:
        bad += hits
        print('  → %d 处待改（只该改路径 token，别动 OCR 正文与页标）' % hits)
    else:
        print('  ✓ 无')

    print('== 2) 顶层是否散落 ==')
    for name in ('assets', 'sources'):
        d = raw / name
        if not d.is_dir():
            print('  ✗ %s 不存在' % d)
            bad += 1
            continue
        entries = [x.name for x in d.iterdir() if not x.name.startswith('.')]
        entries = sorted(entries)
        stray = [n for n in entries if not BOOKDIR.match(n) or (d / n).is_file()]
        print('  %s/ -> %s' % (name, ', '.join(entries) or '(空)'))
        if stray:
            print('  → 顶层有非 <book> 项: %s' % ', '.join(stray))
            bad += len(stray)

    print('== 3) 页图引用是否真实存在 ==')
    checked = missing = 0
    for p in sorted(vault.rglob('*.md')):
        try:
            text = p.read_text(errors='ignore')
        except OSError:
            continue
        for book, ch, pg in REF.findall(text):
            if a.book and book != a.book:
                continue
            checked += 1
            f = raw / 'assets' / book / ('ch%s' % ch) / ('p%s.png' % pg)
            if not f.exists():
                missing += 1
                print('  ✗ %s → %s' % (p.name, f))
    print('  引用 %d 处，缺失 %d 处' % (checked, missing))
    bad += missing

    print()
    print('结论：%s' % ('✓ 全过' if bad == 0 else '✗ %d 个问题' % bad))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
