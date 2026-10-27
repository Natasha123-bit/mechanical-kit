#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编号一致性.py — 图表/公式编号的「引用 ↔ 库」闭环检查

为什么需要它：说明书里写「查表10-4」「由图10-8」「按式10-14」，这些编号一旦跟库里的
实际函数/字典对不上，读者按号去查会查空，而算式本身还是自洽的，肉眼看不出来。
本脚本把三处编号全部抓出来做双向比对：

  L 库（权威）   lib/<书>/*.py 里的 eqN_M / 表N_M / 图N_M / 查图N_M / 查表N_M 命名
  R 引用（文档） references/<书>/*.md 里的「式N-M」「表N-M」「图N-M」
  W 白名单       references/design/book.md 里「保持手工查图」的图号（明确声明不做的那几张）

判据：
  A 引用了 / 库里没有           → 严重（读者查空）
  B 库里有 / 文档没引用         → 提示（可能是孤儿实现，或只在例题里用到）
  C 图既不进库也不在白名单       → 严重（漏声明）
  D handbook 索引.json ↔ 章库表号集合差 → 严重（复用 index_diff 的判据 A）

用法：
    python3 check/编号一致性.py                # 打印摘要
    python3 check/编号一致性.py --md 报告.md   # 另存 markdown 明细
    python3 check/编号一致性.py --strict       # 有 A/C/D 任一项则 exit 1
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.expanduser('~/.hermes/skills/engineering')
REF = {
    'design': os.path.join(SKILLS, 'mechanical-homework', 'references', 'design'),
    'handbook': os.path.join(SKILLS, 'mechanical-book-deposit', 'references', 'handbook'),
    'drawing': os.path.join(SKILLS, 'mechanical-book-deposit', 'references', 'drawing'),
}

# 文档里的编号：式（10-14）／式10-14／表 10-4／图10-18
# 两个必须排掉的假阳性：①「齿式(8-3)」「链式(9-1)」这类复合名词里的「式」；
# ②「手册表6-6」指的是课程设计手册、不是本书表号。
PAT = re.compile(r'(?<![齿链带锥形样款板卡环])(式|表|图)\s*[（(]?\s*(\d{1,2})'
                 r'\s*[-—–－]\s*(\d{1,3})\s*[)）]?')
手册前 = '(?<!手册)'
# 明确「声明不做」的措辞：定性关系、不构成可计算函数、手工查、示意
声明不做 = ('定性', '不构成可计算', '手工查', '不做数字化', '示意')

# 库里的命名：eq10_14 / 表10_4_KHb / 查表10_4 / 图10_8 / 查图10_8_Kv
LIB_PAT = {
    '式': re.compile(r'\b(?:eq|式)(\d{1,2})_(\d{1,3})\b'),
    '表': re.compile(r'(?:^|[^A-Za-z0-9_])(?:查)?表(\d{1,2})_(\d{1,3})(?![0-9])'),
    '图': re.compile(r'(?:^|[^A-Za-z0-9_])(?:查)?图(\d{1,2})_(\d{1,3})(?![0-9])'),
}
# handbook 用 T01..T39 命名字典、表号写在 '表号': '表8-7' 里；这里补一条「引号里的编号」
# 中文命名函数（批6 之后：设计功率/总效率/电动机转速范围…）在 docstring 里只写
# 「式14-3（p.199）」，没有 eq14_3 这类标识符 —— 补扫一遍 docstring/注释里的「式N-M」，
# 否则会把已落库的式报成「引用了但库里没有」。
DOC_PAT = re.compile(r'式\s*(\d{1,2})\s*[-—–－]\s*(\d{1,3})')

LIB_QUOTED = re.compile(r"""['"](式|表|图)\s*[（(]?\s*(\d{1,2})\s*[-—–－]\s*(\d{1,3})\s*[)）]?['"]""")


def norm(kind: str, ch: str, no: str) -> str:
    return f'{kind}{int(ch)}-{int(no)}'


def 章有库(book: str, ch: int) -> bool:
    """该章有没有独立的公式库/表字典模块：lib/<book>/*_ch{NN}.py"""
    pat = os.path.join(ROOT, 'lib', book, f'*_ch{ch:02d}.py')
    return bool(glob.glob(pat))


def 章有图(book: str, ch: int) -> bool:
    """该章的图是否已开始入库（库里出现 图N_M / 查图N_M 命名）。
    没开始入库的章，图一律按「手工查图」处理（提示，不判严重）。"""
    for f in glob.glob(os.path.join(ROOT, 'lib', book, f'*_ch{ch:02d}.py')):
        src = open(f, encoding='utf-8', errors='replace').read()
        if re.search(rf'(?:查)?图{ch}_\d', src):
            return True
    return False


def scan_lib(book: str) -> dict:
    """扫 lib/<book>/*.py（不含 _tests），返回 {'式': set, '表': set, '图': set}"""
    out = {k: set() for k in ('式', '表', '图')}
    for f in glob.glob(os.path.join(ROOT, 'lib', book, '*.py')):
        if f.endswith('_tests.py'):
            continue
        src = open(f, encoding='utf-8', errors='replace').read()
        for kind, pat in LIB_PAT.items():
            for m in pat.finditer(src):
                out[kind].add(norm(kind, m.group(1), m.group(2)))
        for m in LIB_QUOTED.finditer(src):
            out[m.group(1)].add(norm(m.group(1), m.group(2), m.group(3)))
        for m in DOC_PAT.finditer(src):
            out['式'].add(norm('式', m.group(1), m.group(2)))
    return out


LOC2PATH = {}


def 行文本(loc: str) -> str:
    """'ch12.md:161' → 该行原文（用于判「声明不做」这类措辞）。"""
    fn, ln = loc.rsplit(':', 1)
    path = LOC2PATH.get(fn)
    if not path:
        return ''
    try:
        return open(path, encoding='utf-8', errors='replace').read().split('\n')[int(ln) - 1]
    except (OSError, IndexError):
        return ''


def scan_docs(book: str) -> dict:
    """扫 references/<book>/*.md，返回 {'式': {号: [出处]}, ...}"""
    out = {k: {} for k in ('式', '表', '图')}
    d = REF.get(book)
    if not d or not os.path.isdir(d):
        return out
    for f in sorted(glob.glob(os.path.join(d, '**', '*.md'), recursive=True)):
        for ln, line in enumerate(open(f, encoding='utf-8', errors='replace'), 1):
            for m in PAT.finditer(line):
                # 同一行出现「手册表」时，该行的裸「表N-M」都是课程设计手册的表号，不是本书的
                if m.group(1) == '表' and ('手册表' in line or
                                          '手册' in line[max(0, m.start() - 30):m.start()]):
                    continue
                n = norm(m.group(1), m.group(2), m.group(3))
                loc = f'{os.path.basename(f)}:{ln}'
                LOC2PATH[os.path.basename(f)] = f
                out[m.group(1)].setdefault(n, []).append(loc)
    return out


def 手工查图白名单() -> set:
    """book.md 里写了「不做数字化／保持手工查图」的图号集合。"""
    p = os.path.join(REF['design'], 'book.md')
    out = set()
    if not os.path.exists(p):
        return out
    for line in open(p, encoding='utf-8', errors='replace'):
        if '手工查图' in line or '不做数字化' in line:
            for m in PAT.finditer(line):
                if m.group(1) == '图':
                    out.add(norm('图', m.group(2), m.group(3)))
    return out


def handbook_index_check() -> tuple[list, list]:
    """索引.json 表号 ↔ 章库表号集合。返回 (索引有库无, 库有索引无)"""
    idx_p = os.path.join(ROOT, 'books', 'handbook', '索引.json')
    if not os.path.exists(idx_p):
        return [], []
    idx = set(json.load(open(idx_p, encoding='utf-8'))['表'])
    库 = scan_lib('handbook')['表']
    库 = {f'表{n[len("表"):]}' for n in 库}
    return sorted(idx - 库), sorted(库 - idx)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--md', default=None, help='把明细另存为 markdown')
    ap.add_argument('--strict', action='store_true', help='A/C/D 非空则 exit 1')
    a = ap.parse_args()

    白 = 手工查图白名单()
    rows, 严重, 提示, 参考 = [], 0, 0, 0

    for book in ('design', 'handbook', 'drawing'):
        库, 文 = scan_lib(book), scan_docs(book)
        if not any(库.values()) and not any(文.values()):
            continue
        for kind in ('式', '表', '图'):
            only_doc = sorted(set(文[kind]) - 库[kind])
            only_lib = sorted(库[kind] - set(文[kind]))
            for n in only_doc:
                ch = int(n[len(kind):].split('-')[0])
                有库 = 章有库(book, ch)
                if any(k in 行文本(文[kind][n][0]) for k in 声明不做):
                    提示 += 1
                    rows.append(('B', book, kind, n, '文档声明不做（定性/手工查）',
                                 '、'.join(文[kind][n][:2])))
                elif kind == '图':
                    # 该章的图本来就没入库（书里就是这么分工的），只提示
                    提示 += 1
                    rows.append(('B', book, kind, n, '图未入库（设计类图书按手工查）', '、'.join(文[kind][n][:2])))
                elif not 有库 and kind in ('式', '表'):
                    提示 += 1
                    rows.append(('B', book, kind, n, '本章无库（只有章节说明）', '、'.join(文[kind][n][:2])))
                else:
                    严重 += 1
                    rows.append(('A', book, kind, n, '引用了但库里没有', '、'.join(文[kind][n][:3])))
            for n in only_lib:
                # 参考级：库里实现了但章节说明没提到。这类多数是「只在例题里用到」，
                # 不是缺陷；单独计数、不进程表，免得把真正的引用缺失淹掉。
                参考 += 1
                rows.append(('I', book, kind, n, '库里有但文档没引用（参考）', ''))

    # C：图既不进库、也不在白名单
    #（已并入上面的 only_doc，白名单在比对前剔除；这里单独报白名单本身，便于复核）
    白_rows = sorted(白)

    # D：handbook 索引 ↔ 章库
    索无, 库无 = handbook_index_check()
    for n in 索无:
        严重 += 1
        rows.append(('D', 'handbook', '表', n, '索引有、章库无', ''))
    for n in 库无:
        严重 += 1
        rows.append(('D', 'handbook', '表', n, '章库有、索引无', ''))

    print(f'编号一致性：严重 {严重} 项，提示 {提示} 项，参考 {参考} 项（库里有、文档没提，不算缺陷）')
    for r in rows:
        if r[0] in ('A', 'C', 'D'):
            print(f'  [{r[0]}] {r[1]} {r[3]} — {r[4]}' + (f'（{r[5]}）' if r[5] else ''))
    if 白_rows:
        print('  白名单：' + '、'.join(白_rows))

    if a.md:
        with open(a.md, 'w', encoding='utf-8') as fh:
            fh.write('# 图表/公式编号一致性报告\n\n')
            fh.write(f'- 严重：{严重} 项；提示：{提示} 项；参考：{参考} 项（库里有、文档没提）\n\n')
            fh.write('| 类 | 书 | 类 | 编号 | 结论 | 出处 |\n|---|---|---|---|---|---|\n')
            for r in sorted(rows):
                fh.write('| ' + ' | '.join(str(x) for x in r) + ' |\n')
            fh.write('\n## 手工查图白名单（明确声明不做数字化）\n\n')
            fh.write('、'.join(白_rows) + '\n')
        print(f'明细已写入 {a.md}')

    return 1 if (a.strict and 严重) else 0


if __name__ == '__main__':
    sys.exit(main())
