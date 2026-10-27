#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""identify.py —— 给零件图 SVG 补 data-role / data-name（L0 的前置）。

L0 查的是"每个图元能不能被机器认出来"。旧图有三种缺身份的情况：

  1. role 用了章程没登记的别名 —— 输出轴图里 "label"（文字）、"zone-range"、
     "zone-boundary"（区段代号）；label 还分得清，zone 两个纯属自造。
  2. role 对但 name 空 —— 尺寸线 19 条、箭头 55 个、界线 23 条全无名，
     L1 想按 "这条尺寸" 取箭头就取不到，只能靠几何猜。
  3. 压根没打 role —— 齿轮管线出的图（gear_draw.py）239 个图元零身份。

本脚本只做前两种：把别名映射回章程角色，再给无名图元按几何位置编稳定编号。
判不出来的一律留空并计数，由 L0 报红——留空的代价是 L0 不过，瞎猜的代价是
L1/L2 拿错元数据算出"通过"，后者更难查。

编号规则（可复算，重跑结果一致）：按 role 分组，组内按 (y, x) 排序后从 1 编号，
不影响渲染：只写 data-* 属性，几何与样式一字不动。

用法：
    python3 lib/drawing/charter/identify.py 图.svg               # 只报告
    python3 lib/drawing/charter/identify.py 图.svg --write       # 写回（留 .orig）
    python3 lib/drawing/charter/identify.py 图.svg --write --inplace-backup-dir /tmp
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib.drawing.sem import ROLE_TAGS, ROLES, MULTI_OK  # noqa: E402

SKIP = {"svg", "style", "title", "desc", "defs", "metadata", "g"}

# 别名 -> 章程角色。值 None 表示"还要看 data-name 前缀"，见 LABEL_ROLE。
ALIAS = {
    "label": None,
    "zone-range": "zone-mark",      # 区段位置代号（a/b/c 点划线）
    "zone-boundary": "zone-mark",   # 区段两端的短界线
}

# 文字的自述名字前缀 -> 角色。生成器写 data-name="dimension 41" 这种，前缀即语义。
LABEL_ROLE = (
    ("upper deviation", "dimension"),
    ("lower deviation", "dimension"),
    ("diameter", "dimension"),
    ("radius", "dimension"),
    ("dimension", "dimension"),
    ("common datum", "datum"),
    ("datum", "datum"),
    ("section name", "view-label"),
    ("roughness", "roughness"),
    ("geometric tolerance", "text"),
)

PREFIX = {
    "dimension": "dim", "arrow": "arr", "extension": "ext", "leader": "lead",
    "datum": "dat", "tolerance-frame": "gdt", "tolerance-symbol": "sym",
    "cutting-plane": "cp", "outline": "out", "section-outline": "sec",
    "key-outline": "key", "hatch": "hat", "sheet": "sheet", "title-grid": "tit",
    "table-grid": "tab", "text": "txt", "view-label": "view", "roughness": "ra",
    "hidden": "hid", "centerline": "cen", "projection-symbol": "proj",
    "zone-mark": "zone",
}


# 生成器给的 id 自带语义（tip_top 是齿顶线、dimline_v1 是尺寸线），直接照搬。
ID_ROLE = (
    ("frame_", "sheet"), ("tb_", "title-grid"),
    ("axis_", "centerline"), ("pitch_", "centerline"),
    ("tip_", "outline"), ("root_", "outline"), ("bore_", "outline"),
    ("hub_", "outline"), ("side_", "outline"), ("face_", "outline"),
    ("key_", "key-outline"), ("dimline_", "dimension"),
    ("ra_", "roughness"), ("rest_", "roughness"),
)


def _bbox(tag, a):
    """图元包围盒（图面 mm）。判分区用。"""
    try:
        if tag == "line":
            xs = sorted((float(a["x1"]), float(a["x2"])))
            ys = sorted((float(a["y1"]), float(a["y2"])))
            return xs[0], ys[0], xs[1], ys[1]
        if tag == "rect":
            x, y = float(a["x"]), float(a["y"])
            return x, y, x + float(a["width"]), y + float(a["height"])
        if tag == "text":
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            return x, y, x, y
        if tag == "circle":
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
            return cx - r, cy - r, cx + r, cy + r
        if tag in ("polygon", "polyline"):
            pts = re.findall(r"([-\d.]+)\s*[,\s]\s*([-\d.]+)", a.get("points", ""))
            if pts:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                return min(xs), min(ys), max(xs), max(ys)
        if tag == "path":
            # 不能按奇偶取数字：A 命令有 7 个参数（rx ry rot large sweep x y），
            # 奇偶会错位，包围盒算出 (0,0)-(104,106) 这种不可能的框。
            pts = [p for cmd, _n, p0, p1 in _path_cmds(a.get("d", "")) for p in (p0, p1)]
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return min(xs), min(ys), max(xs), max(ys)
    except (KeyError, ValueError):
        pass
    return 0.0, 0.0, 0.0, 0.0


def _zone(box):
    """版面分区：参数表在右上、标题栏在右下、主视图在左、端面图在中。"""
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    if cx >= 212 and cy <= 72:
        return "table"
    if cx >= 140 and cy >= 158:
        return "title"
    if cx <= 100:
        return "main"
    if 100 < cx < 210:
        return "end"
    return "other"


def _id_role(eid, tag):
    for pre, role in ID_ROLE:
        if eid.startswith(pre):
            if role == "roughness" and tag == "text":
                return "text"          # 粗糙度注写里的 "Ra 3.2" 是文字，符号才是 roughness
            return role
    return None


def _is_diag(a, tag):
    """45° 斜线 = 剖面线。轴线/界线/尺寸线都是水平或竖直，斜的只剩剖面线和引出线。"""
    if tag != "line":
        return False
    try:
        dx = abs(float(a["x2"]) - float(a["x1"]))
        dy = abs(float(a["y2"]) - float(a["y1"]))
    except (KeyError, ValueError):
        return False
    return dx > 0.5 and abs(dx - dy) <= 0.05 * max(dx, dy)


def _touches_dim(x1, y1, x2, y2, dims, tol=1.0):
    """界线本身没有独立语义，它的语义是"接到哪条尺寸线上"。

    与某条尺寸线相交的细直线才是尺寸界线；从公差框/粗糙度符号引出的斜线是引出线。
    不这样分，端面图上那几条公差框引线会被当成尺寸界线，L1-03 量出 49.5mm 的
    "离轮廓距离"，报的其实是引出线自己的长度。
    """
    horiz = abs(y1 - y2) < 1e-6
    vert = abs(x1 - x2) < 1e-6
    for dx1, dy1, dx2, dy2 in dims:
        if horiz and abs(dx1 - dx2) < 1e-6:                 # 水平界线 × 竖直尺寸线
            # 交点是 (dx1, y1)：尺寸线的 y 范围要含界线的 y，界线的 x 范围要含尺寸线的 x
            if (min(dy1, dy2) - tol <= y1 <= max(dy1, dy2) + tol
                    and min(x1, x2) - tol <= dx1 <= max(x1, x2) + tol):
                return True
        elif vert and abs(dy1 - dy2) < 1e-6:                # 竖直界线 × 水平尺寸线
            if (min(dx1, dx2) - tol <= x1 <= max(dx1, dx2) + tol
                    and min(dy1, dy2) - tol <= dy1 <= max(dy1, dy2) + tol):
                return True
    return False


def infer_roles(root):
    """给没有 data-role 的图元按 (id 前缀, 元素类型, 线型, 版面分区) 判角色。

    分两遍：第一遍按 id/类型/分区能定下来的；第二遍收拾视图区的细直线——
    它们要么是尺寸界线要么是引出线，得先知道哪几条是尺寸线才判得了。
    """
    inferred, unresolved = [], []
    els = [e for e in root.iter() if e.tag.split("}")[-1] not in SKIP]
    dims, pending = [], []

    for e in els:
        if e.attrib.get("data-role"):
            continue
        tag = e.tag.split("}")[-1]
        a = e.attrib
        role = _id_role(a.get("id", ""), tag)
        if role is None:
            z = _zone(_bbox(tag, a))
            cls = a.get("class", "")
            if tag == "rect":
                w = _bbox(tag, a)[2] - _bbox(tag, a)[0]
                role = ("sheet" if w > 250 else
                        "table-grid" if z == "table" else
                        "title-grid" if z == "title" else
                        "tolerance-frame")
            elif tag == "circle":
                role = {"center": "centerline", "thick": "outline", "thin": "outline"}.get(cls)
            elif tag == "polygon":
                role = "arrow"
            elif tag == "polyline":
                role = "roughness" if cls == "thin" else "outline"
            elif tag == "line":
                x1, y1, x2, y2 = _bbox(tag, a)
                if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
                    unresolved.append((tag, a.get("id", ""), "零长度线（图上不可见）"))
                    continue
                if cls == "center":
                    role = "centerline"
                elif cls == "dim":
                    role = "dimension"
                elif cls == "thick":
                    role = "outline"
                elif _is_diag(a, tag):
                    role = "hatch"
                elif z in ("table", "title"):
                    role = "table-grid" if z == "table" else "title-grid"
                else:
                    pending.append(e)                       # 界线还是引出线，第二遍定
                    continue
            elif tag == "text":
                t = (e.text or "").strip()
                if z == "table":
                    role = "table-grid"
                elif z == "title":
                    role = "title-grid"
                else:
                    sentence = len(t) > 12 or any(ch in t for ch in "，。；、：")
                    ref = re.match(r"^[（(]?[φΦ]?[\d.]+[）)]?\s*\S{0,7}$", t)   # (φ128.75) 是参考尺寸
                    role = "text" if sentence else ("dimension" if ref else "text")
        if role and tag in ROLE_TAGS.get(role, set()):
            a["data-role"] = role
            inferred.append((tag, a.get("id", ""), role))
            if role == "dimension" and tag == "line":
                dims.append(_bbox(tag, a))
        elif role:
            unresolved.append((tag, a.get("id", ""), "判出 %r 但 %s 不在允许类型" % (role, tag)))

    for e in pending:
        tag = e.tag.split("}")[-1]
        a = e.attrib
        x1, y1, x2, y2 = _bbox(tag, a)
        role = "extension" if _touches_dim(x1, y1, x2, y2, dims) else "leader"
        if tag in ROLE_TAGS.get(role, set()):
            a["data-role"] = role
            inferred.append((tag, a.get("id", ""), role))
        else:
            unresolved.append((tag, a.get("id", ""), "未能判定界线/引出线"))
    return inferred, unresolved


def _pos(tag, a):
    """图元中心点（图面 mm，y 向下）。只用来说"谁在前谁在后"，不参与任何判据。"""
    try:
        if tag == "line":
            return (float(a["x1"]) + float(a["x2"])) / 2, (float(a["y1"]) + float(a["y2"])) / 2
        if tag == "text":
            return float(a.get("x", 0)), float(a.get("y", 0))
        if tag == "circle":
            return float(a["cx"]), float(a["cy"])
        if tag == "rect":
            return float(a["x"]) + float(a["width"]) / 2, float(a["y"]) + float(a["height"]) / 2
        if tag in ("polygon", "polyline"):
            pts = re.findall(r"([-\d.]+)\s*[,\s]\s*([-\d.]+)", a.get("points", ""))
            if pts:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                return sum(xs) / len(xs), sum(ys) / len(ys)
        if tag == "path":
            m = re.search(r"M\s*([-\d.]+)[\s,]+([-\d.]+)", a.get("d", ""))
            if m:
                return float(m.group(1)), float(m.group(2))
    except (KeyError, ValueError):
        pass
    return 0.0, 0.0


def fix_roles(root):
    """把未登记的 role 归一；返回 (改动, 判不出的)。"""
    fixed, unresolved = [], []
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in SKIP:
            continue
        role = e.attrib.get("data-role")
        if not role:
            continue                      # 没 role 的交给 infer_roles，不在这里记账
        if role in ROLES:
            continue
        new = ALIAS.get(role, "?")
        if new is None:                                  # label：按 name 前缀判
            nm = (e.attrib.get("data-name") or "").strip().lower()
            new = next((v for k, v in LABEL_ROLE if nm.startswith(k)), None)
            if new is None:
                t = (e.text or "").strip()
                new = "view-label" if re.fullmatch(r"[A-Z]", t) else "text"
        if new not in ROLES:
            unresolved.append((tag, e.attrib.get("id", ""), "role=%r 判不出" % role))
            continue
        if tag not in ROLE_TAGS.get(new, set()):
            unresolved.append((tag, e.attrib.get("id", ""),
                               "%r→%r 但 %s 不在 %s 的允许类型里" % (role, new, tag, new)))
            continue
        e.attrib["data-role"] = new
        fixed.append((tag, e.attrib.get("id", ""), role, new))
    return fixed, unresolved


def assign_names(root):
    """给无名图元编稳定编号；MULTI_OK 的角色（剖面线/表格网格/中心线/界线）不编，
    L0 的 C5 本来就不问它们要名字，硬编号只会把覆盖率的数字冲好看。"""
    buckets = defaultdict(list)
    for e in root.iter():
        tag = e.tag.split("}")[-1]
        if tag in SKIP:
            continue
        role = e.attrib.get("data-role")
        if not role or role in MULTI_OK:
            continue
        if (e.attrib.get("data-name") or "").strip() or (e.attrib.get("data-feature") or "").strip():
            continue
        buckets[role].append((e, tag))
    added = []
    for role, items in buckets.items():
        items.sort(key=lambda it: (round(_pos(it[1], it[0].attrib)[1], 1),
                                   round(_pos(it[1], it[0].attrib)[0], 1)))
        for i, (e, tag) in enumerate(items, 1):
            nm = "%s.%d" % (PREFIX.get(role, role[:3]), i)
            e.attrib["data-name"] = nm
            added.append((role, tag, nm))
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--write", action="store_true", help="写回 SVG（先留一份 .orig）")
    a = ap.parse_args()
    path = Path(a.svg)
    tree = ET.parse(path)
    root = tree.getroot()

    fixed, unresolved = fix_roles(root)
    inferred, still = infer_roles(root)
    unresolved = unresolved + still
    added = assign_names(root)

    print("\n身份标注 — %s" % path.name)
    print("  role 归一 %d 处；按几何推断 %d 处；补 name %d 处；判不出 %d 处"
          % (len(fixed), len(inferred), len(added), len(unresolved)))
    if inferred:
        agg = defaultdict(int)
        for _tag, _id, role in inferred:
            agg[role] += 1
        print("  推断：%s" % ", ".join("%s×%d" % (k, v) for k, v in sorted(agg.items())))
    if fixed:
        agg = defaultdict(int)
        for _tag, _id, old, new in fixed:
            agg["%s → %s" % (old, new)] += 1
        for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
            print("    %-28s %d" % (k, v))
    if added:
        agg = defaultdict(int)
        for role, _tag, _nm in added:
            agg[role] += 1
        print("  补名：%s" % ", ".join("%s×%d" % (k, v) for k, v in sorted(agg.items())))
    if unresolved:
        print("  判不出（留给 L0 报红）：")
        for tag, _id, why in unresolved[:10]:
            print("    %-8s %-10s %s" % (tag, _id, why))

    if a.write:
        bak = path.with_name(path.name + ".orig")
        if not bak.exists():
            bak.write_bytes(path.read_bytes())
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        tree.write(path, encoding="utf-8", xml_declaration=True)
        print("  已写回；原文件备份为 %s" % bak.name)
    else:
        print("  （未写回，加 --write 落盘）")
    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())