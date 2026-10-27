#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""索引薄层：表号 → 表题/页/章/是否入库/库内字典名，用途 → 判据函数（`_index.py`）。

为什么：`取(表, 行, 列)` 要求调用方先知道表号与列名；270 张表靠猜就是做题时的真实耗时
（见 skill mechanical-book-deposit 的「查询层坍陷」节末段）。查表本身是微秒级，缺的是**找对表**。

三层数据，全部由现存产物生成，不重读页图、不改任何已验收章库：
  A 层  表号 → 表题（OCR 首行，252/270 可自动取）/ 印刷页 / 章 / 章名
  B 层  表号 → 是否已入库 + 库内字典名（扫 lib/handbook/*.py 里带 "表号" 键的 dict）
  C 层  用途 → 判据函数 → 表号（扫已入库章库的公开函数 docstring 里的「表N-N」）

用法：
    import _index
    _index.表("表6-1")                  # {'表号','表题','页','章','入库','字典'}
    _index.找("轴承 安装尺寸")            # 按关键词搜表题 + 用途，返回候选列表
    _index.用途("轴径")                  # 用途里含「轴径」的判据函数
    _index.未入库(章=1)                  # 该章还没沉淀的表号
    _index.统计()

重新生成索引快照：
    python3 _index.py build     # 写 <mdkit>/books/handbook/索引.json
"""
from __future__ import annotations

import glob
import importlib
import inspect
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MDKIT = os.path.dirname(os.path.dirname(HERE))                  # …/mdkit
BOOKS = os.path.join(MDKIT, "books", "handbook")
RAW_SRC = os.path.expanduser("~/Documents/Obsidian/机械知识库/raw/sources/handbook")
SNAPSHOT = os.path.join(BOOKS, "索引.json")
DATA = os.path.join(HERE, "_data")                     # 随库分发的快照（公开版没有 books/）
SNAPSHOT_BUNDLED = os.path.join(DATA, "索引.json")


def _data_file(name: str) -> str:
    """books/ 优先（完整仓库/作者机），其次 lib/handbook/_data/（只带库的发行版）。"""
    for path in (os.path.join(BOOKS, name), os.path.join(DATA, name)):
        if os.path.exists(path):
            return path
    return os.path.join(BOOKS, name)                   # 都不在：返回原路径，报错时便于定位


def _snapshot_path():
    """已生成的索引快照：books/ 优先，其次随库快照；都没有则 None（改现场重建）。"""
    for path in (SNAPSHOT, SNAPSHOT_BUNDLED):
        if os.path.exists(path):
            return path
    return None

TABLE_NO = re.compile(r"表\s*(\d{1,2})\s*[-—–]\s*(\d{1,2})")
TABLE_LINE = re.compile(r"^\s*表\s*(\d{1,2})\s*[-—–]\s*(\d{1,2})\s*[ 　]*(.+)$")
PAGE_LINE = re.compile(r"^##\s*p\.(\d+)")

_cache = None


def _norm(no: str) -> str:
    """'表 6 - 1' / '表6–1' → '表6-1'"""
    m = TABLE_NO.search(no)
    if not m:
        return no.strip()
    return f"表{int(m.group(1))}-{int(m.group(2))}"


# ---------------------------------------------------------------- A 层：表题
def _titles() -> dict:
    """从全章 OCR 里抽 表号 → (表题, 首页)。表题取页内首行，正文续行（全数字开头）跳过。"""
    out = {}
    for path in sorted(glob.glob(os.path.join(RAW_SRC, "ch*-全章OCR.md"))):
        ch = int(re.search(r"ch(\d+)", os.path.basename(path)).group(1))
        page = None
        for line in open(path, encoding="utf-8", errors="ignore"):
            m = PAGE_LINE.match(line)
            if m:
                page = int(m.group(1))
                continue
            m = TABLE_LINE.match(line)
            if not m or int(m.group(1)) != ch:
                continue
            no = f"表{ch}-{int(m.group(2))}"
            title = m.group(3).strip()
            if no in out or title[:1].isdigit() or len(title) < 4:
                continue
            out[no] = {"表题": re.sub(r"\s+", " ", title)[:60], "页": page}
    return out


# ------------------------------------------------- 清单（哪些表号应该存在）
def _inventory() -> dict:
    inv = json.load(open(_data_file("表清单.json"), encoding="utf-8"))
    out = {}
    for ck, ch in inv.items():
        for no in ch["tables"]:
            out[_norm(no)] = {"章": int(ch["ch"]), "章名": ch["name"]}
    return out


# ---------------------------------------------------------------- B 层：库内字典
def _modules():
    mods = []
    for path in sorted(glob.glob(os.path.join(HERE, "*_ch*.py"))):
        name = os.path.basename(path)[:-3]
        if name.endswith("_tests"):
            continue
        try:
            mods.append((name, importlib.import_module(name)))
        except Exception as exc:                       # 坏库不该让索引整层挂掉
            print(f"[warn] import {name} 失败：{exc}", file=sys.stderr)
    return mods


def _libscan() -> tuple:
    """返回 (表号 → [字典名], 表号 → [{函数,用途,返回}])"""
    dicts, rules = {}, {}
    for mname, mod in _modules():
        for attr, obj in vars(mod).items():
            if isinstance(obj, dict) and "表号" in obj and "data" in obj:
                dicts.setdefault(_norm(str(obj["表号"])), []).append(f"{mname}.{attr}")
        for attr, obj in vars(mod).items():
            if not callable(obj) or attr.startswith("_") or getattr(obj, "__module__", "") != mname:
                continue
            doc = inspect.getdoc(obj) or ""
            nos = [f"表{a}-{b}" for a, b in re.findall(TABLE_NO, doc)]
            if not nos:
                continue
            first = doc.split("\n")[0].strip()
            for no in set(nos):
                rules.setdefault(no, []).append({"函数": f"{mname}.{attr}", "用途": first[:80]})
    return dicts, rules


def _libmeta() -> tuple:
    """从章库字典里取 表名/页 兜底（OCR 抽不到表题的 20 个表号靠这个补）。"""
    names, pages = {}, {}
    for mname, mod in _modules():
        for attr, obj in vars(mod).items():
            if not (isinstance(obj, dict) and "表号" in obj and "data" in obj):
                continue
            no = _norm(str(obj["表号"]))
            nm = str(obj.get("表名") or "").strip()
            if nm and nm != no:
                nm = re.sub(r"^表\s*\d+\s*[-–—]\s*\d+\s*", "", nm).strip()
                if nm:
                    names.setdefault(no, nm)
            pg = obj.get("页")
            if isinstance(pg, int):
                pages.setdefault(no, pg)
    return names, pages


# ------------------------------------------------------------------ 组装
def _build() -> dict:
    inv = _inventory()
    titles = _titles()
    lib_names, lib_pages = _libmeta()
    dicts, rules = _libscan()
    rows = {}
    for no, meta in inv.items():
        t = titles.get(no, {})
        rows[no] = {
            "表号": no,
            "章": meta["章"],
            "章名": meta["章名"],
            "表题": t.get("表题") or lib_names.get(no),
            "页": t.get("页") or lib_pages.get(no),
            "入库": bool(dicts.get(no)),
            "字典": dicts.get(no, []),
            "判据": rules.get(no, []),
        }
    stats = {
        "表号总数": len(rows),
        "有表题": sum(1 for r in rows.values() if r["表题"]),
        "无表题": sorted(no for no, r in rows.items() if not r["表题"]),
        "已入库": sum(1 for r in rows.values() if r["入库"]),
        "已入库章": sorted({r["章"] for r in rows.values() if r["入库"]}),
        "有判据": sum(1 for r in rows.values() if r["判据"]),
        "判据函数数": sum(len(r["判据"]) for r in rows.values()),
    }
    return {"生成时间": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
            "统计": stats, "表": rows}


def _load() -> dict:
    """快照优先：公开发行版没有 books/ 与 raw/，靠随库快照提供全量索引；
    作者机/完整仓库若快照过旧，跑 `python3 _index.py build` 刷新。"""
    global _cache
    if _cache is None:
        snap = _snapshot_path()
        _cache = (json.load(open(snap, encoding="utf-8")) if snap else _build())
    return _cache


# ------------------------------------------------------------------ 查询 API
def 统计() -> dict:
    """概况：总数 / 有表题 / 已入库 / 判据函数数。"""
    return _load()["统计"]


def 表(表号: str) -> dict:
    """按表号查：表题、印刷页、章、是否入库、库内字典名、可用的判据函数。"""
    no = _norm(str(表号))
    d = _load()["表"]
    if no not in d:
        raise KeyError(f"表号不存在：{no}")
    return d[no]


def 未入库(章: int = None) -> list:
    """还没沉淀的表号（可按章过滤）——这就是下一批的活清单。"""
    rows = _load()["表"].values()
    return sorted((r["表号"] for r in rows
                   if not r["入库"] and (章 is None or r["章"] == 章)),
                  key=lambda s: (int(s[1:].split("-")[0]), int(s.split("-")[1])))


def 找(关键词: str, 只要入库: bool = False) -> list:
    """按关键词搜表题 + 用途（空格分词，全部命中才算），返回候选表。"""
    kws = [k for k in re.split(r"[\s　,，]+", 关键词.strip()) if k]
    hits = []
    for r in _load()["表"].values():
        if 只要入库 and not r["入库"]:
            continue
        blob = " ".join(filter(None, [r["表题"] or "", " ".join(p["用途"] for p in r["判据"]),
                                      r["章名"], " ".join(d.split(".")[-1] for d in r["字典"])]))
        if all(k in blob for k in kws):
            hits.append(r)
    hits.sort(key=lambda r: (not r["入库"], r["章"], int(r["表号"].split("-")[1])))
    return hits


def 用途(关键词: str) -> list:
    """按用途搜判据函数：返回 [{函数, 用途, 表号, 表题, 页}]"""
    kws = [k for k in re.split(r"[\s　,，]+", 关键词.strip()) if k]
    out = []
    for r in _load()["表"].values():
        for p in r["判据"]:
            if all(k in p["用途"] for k in kws):
                out.append({"函数": p["函数"], "用途": p["用途"], "表号": r["表号"],
                            "表题": r["表题"], "页": r["页"]})
    return out


def build(verbose: bool = True) -> dict:
    """生成快照 books/handbook/索引.json 并打印统计。"""
    data = _build()
    targets = [SNAPSHOT] if os.path.isdir(BOOKS) else []
    if os.path.isdir(DATA):
        targets.append(SNAPSHOT_BUNDLED)
    for path in targets:
        json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if verbose:
        s = data["统计"]
        print("索引快照 → " + "、".join(targets))
        print(f"表号 {s['表号总数']} 个；有表题 {s['有表题']}（缺 {len(s['无表题'])}）；"
              f"已入库 {s['已入库']}；判据函数 {s['判据函数数']} 条覆盖 {s['有判据']} 张表")
        print("缺表题：" + "、".join(s["无表题"]))
        print("已入库章：" + "、".join(f"ch{c:02d}" for c in s["已入库章"]))
    return data


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
