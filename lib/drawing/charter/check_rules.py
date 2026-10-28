#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L1 结构 / L2 几何检查 —— 章程条款的机器执行端。

三层分工：
    L0 只问「图元有没有身份」—— role/name 在不在、类型配不配（check_contract.py）
    L1 问「图元之间的关系对不对」—— 尺寸四件套、界线越过量、剖切字母与断面名、
       键槽与计算书一致（本章 A 段，10 条）
    L2 问「几何上成不成立」—— 圆弧半径够不够画、圆角端点接没接上、剖面线在不在
       轮廓内且等距、有没有完全重合的线、越不越出内框（本章 B 段，9 条）
    L3 问「东西撞不撞」—— 文字互相压、字压线、尺寸线穿插、实心符号压字
       （本章 C 段，6 条；需要 measure.py 量出的真实包围盒，CHK-06）

已知局限：不解析 transform 属性。CHK-06 要求包围盒乘根变换矩阵，这块还没做，
因此带 transform 的图元按原始坐标判——加 transform 的注错测不出来。

两条硬规矩（来由见 CHARTER.md 第 13 章）：
  1. 期望值一律从**外部来源**读：计算书 JSON、命令行给的图号，不写死在检查器里。
     写死过一次，把 10-6 的图号焊进了白名单，错误就永远通过了。
  2. 不适用 / 未检查 不算通过。exit 0 只代表「跑了的都过了」，报告里会写明范围。

用法：
    python3 lib/drawing/charter/check_rules.py 图.svg \\
        --calc calc/s3_shaft.json --fig-no SJCS-1 [--json]

退出码：0 全部必检通过；1 有违规或未检查；2 检查器异常。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ============================================================ 角色归一
# 早期生成器把文字一律记 role="label"，真实身份写在 data-name 里（"dimension 41"、
# "diameter φ40"、"upper deviation"）。label 不在章程 ROLES 白名单内，L0 会判不通过；
# 本检查器按同一张表把旧图归一成语义角色，只改内存副本，不动文件。
LABEL_ROLE = (
    ("upper deviation", "dimension"),
    ("lower deviation", "dimension"),
    ("dimension", "dimension"),
    ("diameter", "dimension"),
    ("radius", "dimension"),
    ("common datum", "datum"),
    ("datum", "datum"),
    ("section name", "view-label"),
    ("roughness", "roughness"),
    ("geometric tolerance", "text"),
)

# ============================================================ 规则注册表
RULES = []


def rule(rid, name, chapter, severity="必"):
    def deco(fn):
        RULES.append((rid, name, chapter, severity, fn))
        return fn
    return deco


# ============================================================ 上下文
class Ctx:
    """一次检查的全部输入。规则函数只读它，不碰全局。"""

    def __init__(self, svg, calc=None, fig_no=None, title_fields=None, bounds=None,
                 features=None):
        self.root = ET.parse(svg).getroot()
        self.bounds = bounds
        self.view_of = {}
        self.calc = calc or {}
        self.features = features or []
        self.fig_no = fig_no
        self.title_fields = title_fields or {}
        self.els = []                      # [(tag, attrib, text)]
        for e in self.root.iter():
            tag = e.tag.split("}")[-1]
            if tag in ("svg", "style", "title", "desc", "defs", "metadata", "g"):
                continue
            self.els.append((tag, dict(e.attrib), (e.text or "").strip()))
        # 图纸坐标（y 向上）下的几何量：SVG 已翻转，这里统一翻回来便于与模型对照
        self.h = float(self.root.attrib.get("height", "297").replace("mm", "")) or 297.0
        for _tag, a, _t in self.els:
            if a.get("data-view") and a.get("id"):
                self.view_of[a["id"]] = a["data-view"]
        self._norm_roles()
        self.scale = self._read_scale()

    def _read_scale(self):
        """从标题栏"比例"栏读 1:n。图上量到的是图面长度，零件真值 = 图面 × n。
        A3 1:1 之外还有 1:2 这种，硬按 1:1 读会把 φ140 读成 70 然后报错。"""
        for tag, a, t in self.els:
            if tag != "text" or not t:
                continue
            m = re.fullmatch(r"1\s*[:：]\s*(\d+(?:\.\d+)?)", t.strip())
            if m:
                return float(m.group(1))
        return 1.0

    def _norm_roles(self):
        """把 role="label" 按 data-name 前缀归一成语义角色（旧图兼容，不动文件）。"""
        for tag, a, t in self.els:
            if a.get("data-role") != "label":
                continue
            pre = (a.get("data-name") or "").strip().lower()
            role = next((v for k, v in LABEL_ROLE if pre.startswith(k)), None)
            if role is None:                       # 无名文字：单大写字母是剖切字母，其余是说明
                role = "view-label" if re.fullmatch(r"[A-Z]", t or "") else "text"
            a["data-role"] = role

    # ---- 取元素 ----
    def by_role(self, *roles):
        want = set(roles)
        return [e for e in self.els if e[1].get("data-role") in want]

    def groups_by_name(self, role):
        """{name: [(tag, attrib, text)]}"""
        out = defaultdict(list)
        for e in self.by_role(role):
            out[e[1].get("data-name")].append(e)
        return out

    def texts(self, role=None, name=None):
        out = []
        for tag, a, t in self.els:
            if tag != "text":
                continue
            if role and a.get("data-role") != role:
                continue
            if name is not None and a.get("data-name") != name:
                continue
            out.append((a, t))
        return out

    # ---- 几何 ----
    def segs_of(self, roles=("outline",)):
        """取轮廓类图元的线段集合，SVG 坐标（y 向下）。"""
        segs = []
        for tag, a, _ in self.els:
            if a.get("data-role") not in roles:
                continue
            if tag == "line":
                segs.append((float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"])))
            elif tag == "path":
                for cmd, nums, p0, p1 in _path_cmds(a.get("d", "")):
                    if cmd == "A" and len(nums) >= 7:
                        pts = _arc_points(p0, p1, nums[0], nums[1], nums[2],
                                          int(nums[3]), int(nums[4]))
                    else:
                        pts = [p0, p1]
                    for i in range(len(pts) - 1):
                        segs.append((pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]))
            elif tag == "circle":
                cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
                n = 48
                for i in range(n):
                    t1, t2 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
                    segs.append((cx + r * math.cos(t1), cy + r * math.sin(t1),
                                 cx + r * math.cos(t2), cy + r * math.sin(t2)))
        return segs


# ============================================================ 工具
def num(s):
    """从 "70 ⁺⁰·³₀" / "φ50k6" / "44.5 ₀⁻⁰·²" / "20 N9" 里取主值。"""
    if not s:
        return None
    t = s.replace("·", ".").strip().lstrip("（(")     # 参考尺寸写作 (φ128.75)
    m = re.match(r"[\sφΦR]*([-+]?\d+(?:\.\d+)?)", t)
    return float(m.group(1)) if m else None


def pt_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def nearest(px, py, segs):
    return min((pt_seg_dist(px, py, *s) for s in segs), default=float("inf"))


def norm(s):
    """名字归一：全角破折号、空格、大小写差异不参与比较。"""
    return re.sub(r"[\s—–\-−]", "", str(s or "")).upper()


# ============================================================ 规则
def _arrow_tips(ctx):
    """箭头尖坐标：polygon 取首点，path 取 M 后首点（arrow() 以尖为起点）。"""
    tips = []
    for tag, a, _ in ctx.els:
        if a.get("data-role") != "arrow":
            continue
        if tag == "polygon":
            pts = re.findall(r"([-\d.]+)\s*,\s*([-\d.]+)", a.get("points", ""))
            if pts:
                tips.append((float(pts[0][0]), float(pts[0][1])))
        elif tag == "path":
            m = re.search(r"M\s*([-\d.]+)[\s,]+([-\d.]+)", a.get("d", ""))
            if m:
                tips.append((float(m.group(1)), float(m.group(2))))
    return tips


def _is_dim_text(a, t):
    """偏差值、公差框数值也带 dimension 角色，但它们是附属数字，不参与尺寸配对。"""
    nm = (a.get("data-name") or "").lower()
    if nm.startswith(("upper deviation", "lower deviation", "geometric tolerance")):
        return False
    return bool(t)


def _arrow_spans(ctx, tol=0.4):
    """箭头对间距 = 被测长度。

    尺寸线会被台阶断成几段（140→167.5、167.5→178），按线长核尺寸必然错位；
    箭头尖才是真测量端点。同一行/列上相邻两个箭头尖的间距，就是该尺寸的读数。
    """
    rows, cols = defaultdict(list), defaultdict(list)
    for tag, a, _ in ctx.els:
        if a.get("data-role") != "arrow":
            continue
        if tag == "polygon":
            pts = re.findall(r"([-\d.]+)\s*,\s*([-\d.]+)", a.get("points", ""))
            if not pts:
                continue
            x, y = float(pts[0][0]), float(pts[0][1])
        elif tag == "path":
            m = re.search(r"M\s*([-\d.]+)[\s,]+([-\d.]+)", a.get("d", ""))
            if not m:
                continue
            x, y = float(m.group(1)), float(m.group(2))
        else:
            continue
        rows[round(y / tol) * tol].append(x)
        cols[round(x / tol) * tol].append(y)
    spans = []
    for y, xs in rows.items():
        xs.sort()
        spans += [abs(b - a2) for a2, b in zip(xs, xs[1:]) if abs(b - a2) > tol]
    for x, ys in cols.items():
        ys.sort()
        spans += [abs(b - a2) for a2, b in zip(ys, ys[1:]) if abs(b - a2) > tol]
    return spans


def _dim_lines(ctx):
    return [(float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]))
            for tag, a, _ in ctx.els
            if tag in ("line", "path") and a.get("data-role") == "dimension"
            and tag == "line"]


def _dim_groups(ctx, gap=1.0):
    """把同一直线上首尾相接的尺寸线段合成一条。

    台阶处的尺寸线常被断成两段画（140→167.5、167.5→178），箭头只画在台阶两侧。
    按单段判"两端要有箭头"，会把这种标准画法报成缺陷——实测输出轴 10 处、大齿轮 3 处
    全是这么误报的。合组后箭头仍要够两个，缺一个才报。
    """
    groups = []
    rows = defaultdict(list)
    cols = defaultdict(list)
    for x1, y1, x2, y2 in _dim_lines(ctx):
        if abs(y1 - y2) < 1e-6:
            rows[round(y1, 2)].append((min(x1, x2), max(x1, x2)))
        elif abs(x1 - x2) < 1e-6:
            cols[round(x1, 2)].append((min(y1, y2), max(y1, y2)))
    for y, spans in rows.items():
        spans.sort()
        cur = list(spans[0])
        for lo, hi in spans[1:]:
            if lo - cur[1] <= gap:
                cur[1] = max(cur[1], hi)
            else:
                groups.append((cur[0], y, cur[1], y))
                cur = [lo, hi]
        groups.append((cur[0], y, cur[1], y))
    for x, spans in cols.items():
        spans.sort()
        cur = list(spans[0])
        for lo, hi in spans[1:]:
            if lo - cur[1] <= gap:
                cur[1] = max(cur[1], hi)
            else:
                groups.append((x, cur[0], x, cur[1]))
                cur = [lo, hi]
        groups.append((x, cur[0], x, cur[1]))
    return groups


def _dim_chains(ctx, tol=1.0):
    """把尺寸线链成"视觉上的一条线"：同一直线上首尾相接、**且接缝处没有箭头**。

    接缝处有箭头说明那是两个不同尺寸共用一条线（41/68/10/11/85 那一行），
    接缝处没箭头说明是同一条尺寸线断成两段画（2.5 那条：140→167.5、167.5→178，
    箭头在 171.5/174 指向 2.5mm 的台阶，两端是引到文字的延长段）。
    """
    tips = _arrow_tips(ctx)
    lines = _dim_lines(ctx)
    parent = list(range(len(lines)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i, (x1, y1, x2, y2) in enumerate(lines):
        horiz = abs(y1 - y2) < 1e-6
        lo, hi = (min(x1, x2), max(x1, x2)) if horiz else (min(y1, y2), max(y1, y2))
        for j in range(i + 1, len(lines)):
            u1, v1, u2, v2 = lines[j]
            same = (abs(v1 - y1) < 0.6 and abs(v2 - y1) < 0.6) if horiz \
                else (abs(u1 - x1) < 0.6 and abs(u2 - x1) < 0.6)
            if not same:
                continue
            a, b = (min(u1, u2), max(u1, u2)) if horiz else (min(v1, v2), max(v1, v2))
            # 首尾相接
            if abs(a - hi) > tol and abs(b - lo) > tol:
                continue
            seam = lo if abs(b - lo) <= tol else hi
            # 接缝处有箭头 → 两个独立尺寸，不链
            has_arrow = any(abs(t - seam) <= 2.0 for t in
                            ([tx for tx, ty in tips if abs(ty - y1) <= 0.6] if horiz
                             else [ty for tx, ty in tips if abs(tx - x1) <= 0.6]))
            if has_arrow:
                continue
            parent[find(i)] = find(j)

    chains = defaultdict(list)
    for i, ln in enumerate(lines):
        chains[find(i)].append(ln)
    return list(chains.values())


@rule("L1-01", "每条尺寸线上至少两个箭头", "DIM-01")
def r_dim_parts(ctx):
    """判据是"视觉上的一条尺寸线上要有 ≥2 个箭头"，按 _dim_chains 的链来判。

    不能按单段判：2.5 那条断成两段、箭头在中间，单段看全是"端点无箭头"。
    也不能整行合并：41/68/10/11/85 共用一条线，合并后少个箭头看不出来。
    链的定义正好卡在中间——接缝处有箭头就断开，没箭头就连上。
    """
    chains = _dim_chains(ctx)
    if not chains:
        return "未检查", "图上没有尺寸线"
    tips = _arrow_tips(ctx)
    bad = []
    for grp in chains:
        horiz = abs(grp[0][1] - grp[0][3]) < 1e-6
        lo = min(min(g[0], g[2]) if horiz else min(g[1], g[3]) for g in grp)
        hi = max(max(g[0], g[2]) if horiz else max(g[1], g[3]) for g in grp)
        ref = grp[0][1] if horiz else grp[0][0]
        on = ([tx for tx, ty in tips if abs(ty - ref) <= 0.6] if horiz
              else [ty for tx, ty in tips if abs(tx - ref) <= 0.6])
        on = sorted(v for v in on if lo - 2.0 <= v <= hi + 2.0)
        # 要两个**不同位置**的箭头。接缝处两个尺寸的箭头常常重合在同一个 x
        # （41 的右箭头和 68 的左箭头都在 106），只看个数会把缺箭头判成合格。
        if len(on) < 2 or (on[-1] - on[0]) < 0.5:
            bad.append("尺寸线 %s 上只有 %d 个位置有箭头（%.1f~%.1f）"
                       % ("(%g,%g)-(%g,%g)" % (lo, ref, hi, ref) if horiz
                          else "(%g,%g)-(%g,%g)" % (ref, lo, ref, hi),
                          len(set(round(v, 1) for v in on)), lo, hi))
    if bad:
        return "不通过", "%d/%d 条：%s" % (len(bad), len(chains), "；".join(bad[:4]))
    return "通过", "%d 条尺寸线（按链合并）箭头都够" % len(chains)


@rule("L1-02", "尺寸文字与图面几何一致（按标题栏比例换算）", "DIM-01")
def r_dim_values(ctx):
    """逐条尺寸线核：线上的箭头尖间距 = 该线的读数，与中点旁的尺寸文字比。

    不能拿全图箭头对去凑最接近的值——图上有 φ40 段，41 改成 40 也能"凑"上一个
    合法读数，错就漏了。必须限定在**这条尺寸线上**的箭头。
    """
    lines = _dim_lines(ctx)          # 逐段核读数：合并组只给 L1-01 判箭头用
    tips = _arrow_tips(ctx)
    texts = [(a, t) for a, t in ctx.texts(role="dimension") if _is_dim_text(a, t)]
    segs = ctx.segs_of(("outline", "key-outline", "section-outline"))
    leads = [(float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]))
             for tag, a, _ in ctx.els
             if tag == "line" and a.get("data-role") == "leader"]
    if not lines or not texts:
        return "未检查", "没有尺寸线或尺寸文字"
    bad, n, skip, via_leader = [], 0, 0, 0
    for x1, y1, x2, y2 in lines:
        horiz = abs(y1 - y2) < 1e-6
        if horiz:
            on = [tx for tx, ty in tips
                  if abs(ty - y1) <= 0.6 and min(x1, x2) - 2 <= tx <= max(x1, x2) + 2]
            mid = ((x1 + x2) / 2.0, y1)
        else:
            on = [ty for tx, ty in tips
                  if abs(tx - x1) <= 0.6 and min(y1, y2) - 2 <= ty <= max(y1, y2) + 2]
            mid = (x1, (y1 + y2) / 2.0)
        if len(on) < 2:                                  # 断段或缺箭头，交给 L1-01 报
            skip += 1
            continue
        read = (max(on) - min(on)) * ctx.scale        # 图面长度 → 零件真值
        cands = []
        for a, t in texts:
            dd = math.dist(mid, (float(a.get("x", 0)), float(a.get("y", 0))))
            v = num(t)
            if dd <= 8.0 and v is not None:
                cands.append((dd, v, t, a))
        if not cands:
            skip += 1
            continue
        cands.sort()
        dd, v, t, a = cands[0]
        n += 1
        if abs(read - v) <= 0.15:
            continue
        if t.strip().startswith(("φ", "Φ")) and segs:
            tx, ty = float(a.get("x", 0)), float(a.get("y", 0))
            ok = any(min(nearest(lx1, ly1, segs), nearest(lx2, ly2, segs)) <= 6.0
                     and min(math.dist((lx1, ly1), (tx, ty)),
                             math.dist((lx2, ly2), (tx, ty))) <= 30.0
                     for lx1, ly1, lx2, ly2 in leads)
            if ok:
                via_leader += 1
                continue
        bad.append("%r 标 %.2f，线上箭头间距 %.2f" % (t, v, read))
    if not n and not via_leader:
        return "未检查", "没有一条尺寸线同时具备箭头与文字"
    if bad:
        return "不通过", "%d/%d 处：%s" % (len(bad), n, "；".join(bad[:5]))
    ev = "%d 条尺寸读数与线上箭头间距一致" % (n - via_leader)
    if abs(ctx.scale - 1.0) > 1e-9:
        ev += "（按 1:%g 换算）" % ctx.scale
    if via_leader:
        ev += "；%d 条 φ 为引出线注写" % via_leader
    if skip:
        ev += "；%d 条缺箭头或文字未核（见 L1-01）" % skip
    return "通过", ev


@rule("L1-03", "尺寸界线从轮廓或轴线引出（≤2.5mm 间隙）", "DIM-03")
def r_ext_origin(ctx):
    segs = ctx.segs_of(("outline", "centerline", "key-outline", "section-outline"))
    if not segs:
        return "未检查", "没有轮廓类图元"
    tol = 3.5
    bad, n = [], 0
    for tag, a, _ in ctx.by_role("extension"):
        if tag != "line":
            continue
        n += 1
        p1 = (float(a["x1"]), float(a["y1"]))
        p2 = (float(a["x2"]), float(a["y2"]))
        d = min(nearest(p1[0], p1[1], segs), nearest(p2[0], p2[1], segs))
        if d > tol:
            bad.append("%s 两端离轮廓 %.1fmm" % (a.get("data-name"), d))
    if not n:
        return "未检查", "图上没有 extension"
    return ("不通过", "；".join(bad[:5])) if bad else ("通过", "%d 条界线都起自轮廓附近" % n)


@rule("L1-04", "尺寸界线越过尺寸线 1.5~4.5mm", "DIM-04")
def r_ext_overshoot(ctx):
    """越过量按「外端减去最外侧那条相交尺寸线」算。

    一条界线可以同时服务多条尺寸线（41 与总长 297 共用 x=65 那条界线），
    逐条尺寸线判越界会把共用界线误判成超标 21mm。正确做法：先取离轮廓近的
    一端做起端，找与界线相交的所有垂直尺寸线，取最外侧那条，剩下的才是越过量。
    """
    lines = _dim_lines(ctx)
    exts = [(tag, a) for tag, a, _ in ctx.els
            if tag == "line" and a.get("data-role") == "extension"]
    if not lines or not exts:
        return "未检查", "没有可配对的界线/尺寸线"
    segs = ctx.segs_of(("outline", "centerline", "key-outline", "section-outline"))
    if not segs:
        return "未检查", "没有轮廓类图元，定不出起端"
    bad, n = [], 0
    for tag, e in exts:
        ex1, ey1, ex2, ey2 = (float(e[k]) for k in ("x1", "y1", "x2", "y2"))
        d1, d2 = nearest(ex1, ey1, segs), nearest(ex2, ey2, segs)
        start, end = ((ex1, ey1), (ex2, ey2)) if d1 <= d2 else ((ex2, ey2), (ex1, ey1))
        hits = []
        for dx1, dy1, dx2, dy2 in lines:
            if abs(dy1 - dy2) < 1e-6 and abs(ex1 - ex2) < 1e-6:        # 水平尺寸线 × 竖直界线
                if not (min(dx1, dx2) - 0.5 <= ex1 <= max(dx1, dx2) + 0.5):
                    continue
                if not (min(ey1, ey2) - 0.5 <= dy1 <= max(ey1, ey2) + 0.5):
                    continue
                hits.append(abs(dy1 - start[1]))
            elif abs(dx1 - dx2) < 1e-6 and abs(ey1 - ey2) < 1e-6:      # 竖直尺寸线 × 水平界线
                if not (min(dy1, dy2) - 0.5 <= ey1 <= max(dy1, dy2) + 0.5):
                    continue
                if not (min(ex1, ex2) - 0.5 <= dx1 <= max(ex1, ex2) + 0.5):
                    continue
                hits.append(abs(dx1 - start[0]))
        if not hits:
            continue
        n += 1
        over = math.dist(start, end) - max(hits)
        if not (1.5 - 1e-6 <= over <= 4.5 + 1e-6):
            bad.append("界线(%g,%g)-(%g,%g) 越过 %.1fmm" % (ex1, ey1, ex2, ey2, over))
    if not n:
        return "未检查", "没有与尺寸线相交的界线"
    if bad:
        return "不通过", "%d/%d 条超标：%s" % (len(bad), n, "；".join(bad[:5]))
    return "通过", "%d 条界线越过量在 1.5~4.5mm" % n


@rule("L1-05", "φ/R 前缀与要素相符", "DIM-06")
def r_prefix(ctx):
    bad, n = [], 0
    for a, t in ctx.texts(role="dimension"):
        if not t:
            continue
        n += 1
        name = (a.get("data-name") or "")
        if norm(name) == "TOTAL" or re.fullmatch(r"LEN\d+", norm(name) or ""):
            continue
        if "Φ" in t.upper() and not re.search(r"^\s*[（(]?\s*φ", t):   # (φ128.75) 是参考尺寸
            bad.append("%r φ 号位置不对" % t)
        if norm(name).startswith("FIL") and not re.match(r"^\s*R", t):
            bad.append("%r 圆角应写 R" % t)
    if not n:
        return "未检查", "没有尺寸文字"
    return ("不通过", "；".join(bad[:5])) if bad else ("通过", "%d 条文字前缀相符" % n)


@rule("L1-06", "剖切字母与断面名一一对应、每字母上下两组", "VIEW-08")
def r_cut_letters(ctx):
    """断面图的身份落在 hatch / key-outline / section-outline 的 data-name 上（A、B），
    而不是 view-label——早期图把断面名写在文字里，按标签取会取空。"""
    # 只认 hatch/key-outline 的名字：section-outline 的身份是"哪条轮廓"，
    # 补身份时会被编成 SEC.1…，拿来当断面名会把 A—A 判成没有对应断面。
    sec_names = {norm(a.get("data-name")) for tag, a, _ in ctx.els
                 if a.get("data-role") in ("hatch", "key-outline")
                 and a.get("data-name")}
    letters = defaultdict(int)
    for tag, a, t in ctx.els:
        if tag != "text" or not t or a.get("data-role") not in ("view-label", "cutting-plane"):
            continue
        lb = t.strip().upper()
        if re.fullmatch(r"[A-Z]", lb):          # 只认单字母；A—A 是断面名不是剖切字母
            letters[lb] += 1
    if not letters:
        return "未检查", "没有剖切字母"
    bad = []
    for L, cnt in letters.items():
        first = norm(L)[:1]
        if first not in {n[:1] for n in sec_names}:
            bad.append("字母 %s 没有对应断面（断面名 %s）" % (L, sorted(sec_names) or "无"))
        if cnt % 2:
            bad.append("字母 %s 出现 %d 次（应上下成对）" % (L, cnt))
    return ("不通过", "；".join(bad[:5])) if bad else (
        "通过", "字母 %s 与断面 %s 对应" % (sorted(letters), sorted(sec_names)))


@rule("L1-07", "标题栏字段齐全", "SHT-07")
def r_title_fields(ctx):
    tg = [e for e in ctx.els if e[1].get("data-role") == "title-grid"]
    if not tg:
        return "不通过", "没有 title-grid 图元"
    texts = [t for _, _, t in tg if t]
    need = ["材料", "比例", "图号", "数量", "制图"]
    miss = [k for k in need if not any(k in t for t in texts)]
    if miss:
        return "不通过", "缺标签：%s" % "、".join(miss)
    return "通过", "%d 个图元，标签齐（%s）" % (len(tg), "、".join(need))


@rule("L1-08", "图号与项目一致且不夹带其他题号", "GATE-01")
def r_fig_no(ctx):
    if not ctx.fig_no:
        return "未检查", "没有 --fig-no"
    tg_texts = [t for _, a, t in ctx.els if a.get("data-role") == "title-grid" and t]
    title = ctx.root.find("{http://www.w3.org/2000/svg}title")
    hay = " ".join(tg_texts) + " " + ((title.text or "") if title is not None else "")
    bad = []
    if ctx.fig_no not in hay:
        bad.append("图上没有 %s" % ctx.fig_no)
    # 图号本身就可能含题号（10-6-02 是第 10-6 题的图），先剔掉再找别题的编号
    rest = hay.replace(ctx.fig_no, " ")
    stray = re.findall(r"\b(?:10-\d|11-\d|13-\d|例\d+-\d)\b", rest)
    if stray:
        bad.append("夹带其他题号：%s" % "、".join(sorted(set(stray))))
    return ("不通过", "；".join(bad)) if bad else ("通过", "图号 %s，无外题编号" % ctx.fig_no)


@rule("L1-09", "键槽宽/槽深与计算书一致", "DIM-12")
def r_key_dims(ctx):
    ks = ctx.calc.get("键", {})
    keys = {n: v for n, v in ks.items() if isinstance(v, dict) and "b" in v}
    if not ks:
        return "未检查", "计算书缺 键 段（字段契约见 charter/calc.schema.md）；顶层键：%s" \
            % ("、".join(sorted(ctx.calc)[:10]) or "空")
    if not keys:
        return "未检查", "键 段里没有带 b 的项（见 charter/calc.schema.md）"
    bad, n = [], 0
    for name, group in ctx.groups_by_name("dimension").items():
        if not name:
            continue
        # 断面里的 20 N9 / 62.5 ₀⁻⁰·² 这类
        txts = [t[2] for t in group if t[0] == "text"]
        for t in txts:
            v = num(t)
            if v is None:
                continue
            cand = [k for k in keys.values()
                    if abs(float(k.get("b", -1)) - v) < 0.01
                    or abs(float(k.get("d", -1)) - float(k.get("t1", 0)) - v) < 0.01]
            if cand:
                n += 1
    if not n:
        return "未检查", "没找到可与键规格对应的尺寸文字"
    return ("不通过", "；".join(bad[:5])) if bad else ("通过", "%d 处与键规格吻合" % n)


@rule("L1-10", "材料与热处理与计算书一致", "GATE-01")
def r_material(ctx):
    mat = ctx.calc.get("材料45", {})
    if not mat:
        return "未检查", "计算书缺 材料45 段（字段契约见 charter/calc.schema.md）；顶层键：%s" \
            % ("、".join(sorted(ctx.calc)[:10]) or "空")
    tg_texts = [t for _, a, t in ctx.els if a.get("data-role") == "title-grid" and t]
    want = str(mat.get("材料", "")).strip()
    if want and want not in " ".join(tg_texts):
        return "不通过", "标题栏材料与计算书（%s）不符" % want
    ratio_ok = any("调质" in t for _, _, t in ctx.els if t)
    return ("通过" if ratio_ok else "警示"), (
        "材料 %s；热处理字样%s" % (want, "一致" if ratio_ok else "未在图上找到"))


# ============================================================ 运行
def _bbox(tag, a):
    """图元包围盒。L2 判越界与位置用它。"""
    try:
        if tag == "line":
            xs = sorted((float(a["x1"]), float(a["x2"])))
            ys = sorted((float(a["y1"]), float(a["y2"])))
            return xs[0], ys[0], xs[1], ys[1]
        if tag == "rect":
            x, y = float(a["x"]), float(a["y"])
            return x, y, x + float(a["width"]), y + float(a["height"])
        if tag == "circle":
            cx, cy, r = float(a["cx"]), float(a["cy"]), float(a["r"])
            return cx - r, cy - r, cx + r, cy + r
        if tag == "text":
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            return x, y, x, y
        if tag in ("polygon", "polyline"):
            pts = re.findall(r"([-\d.]+)\s*[,\s]\s*([-\d.]+)", a.get("points", ""))
            if pts:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                return min(xs), min(ys), max(xs), max(ys)
        if tag == "path":
            # 不能按奇偶取数字：A 命令有 7 个参数（rx ry rot large sweep x y），
            # 奇偶会错位，包围盒算出 (0,0)-(104,106) 这种不可能的框。
            pts = []
            for cmd, nums, p0, p1 in _path_cmds(a.get("d", "")):
                if cmd == "A" and len(nums) >= 7:
                    pts += _arc_points(p0, p1, nums[0], nums[1], nums[2],
                                       int(nums[3]), int(nums[4]))
                else:
                    pts += [p0, p1]
            if pts:
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                return min(xs), min(ys), max(xs), max(ys)
    except (KeyError, ValueError):
        pass
    return 0.0, 0.0, 0.0, 0.0


# ============================================================ L2 几何层
# CHARTER §6 几何成立性 + §13 CHK-02。这一层问的是「画出来的东西在几何上成不成立」：
# 圆弧能不能画出来、圆角端点在不在母线上、剖面线有没有跑到实体外面、
# 有没有两条线完全重合。不管画法对不对（L1），也不管文字压不压线（L3）。

PATH_RE = re.compile(r"([MLACQZmlacqz])\s*([^MLACQZmlacqz]*)")


def _path_cmds(d):
    """完整解析 path，返回 [(cmd, [参数...], 起点, 终点)]。

    segs_of 只认 M/L，圆弧被当成两端直连——GEO-05 要求核扫角与端点位置，
    按直线处理等于没查。
    """
    out = []
    cur = (0.0, 0.0)
    start = (0.0, 0.0)
    for m in PATH_RE.finditer(d or ""):
        cmd = m.group(1)
        nums = [float(x) for x in re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", m.group(2))]
        c = cmd.upper()
        if c == "M" and len(nums) >= 2:
            start = (nums[0], nums[1])
            out.append((c, nums, start, start))      # 起点即终点，别把 (0,0) 当起点
            cur = start
        elif c == "L" and len(nums) >= 2:
            nxt = (nums[0], nums[1])
            out.append((c, nums, cur, nxt))
            cur = nxt
        elif c == "A" and len(nums) >= 7:
            nxt = (nums[5], nums[6])
            out.append((c, nums, cur, nxt))
            cur = nxt
        elif c == "Q" and len(nums) >= 4:
            nxt = (nums[2], nums[3])
            out.append((c, nums, cur, nxt))
            cur = nxt
        elif c == "Z":
            out.append((c, [], cur, start))
            cur = start
    return out


def _arc_points(p0, p1, rx, ry, rot_deg, large, sweep, n=8):
    """把 SVG 的 A 命令采样成折线点。segs_of 原来只认 M/L，整条圆弧被丢掉——
    剖面线端点量"离轮廓 30mm"，量的其实是"轮廓里根本没有这段弧"。"""
    chord = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if chord < 1e-9 or min(rx, ry) < 1e-9:
        return [p0, p1]
    rx, ry = abs(rx), abs(ry)
    if rx < chord / 2.0:                    # 半径不够，按 SVG 规范放大到弦长一半
        k = chord / 2.0 / rx
        rx, ry = rx * k, ry * k
    phi = math.radians(rot_deg)
    cos_p, sin_p = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2.0, (p0[1] - p1[1]) / 2.0
    x1p = cos_p * dx + sin_p * dy
    y1p = -sin_p * dx + cos_p * dy
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    co = math.sqrt(max(num / den, 0.0)) if den else 0.0
    if large == sweep:
        co = -co
    cxp, cyp = co * rx * y1p / ry, -co * ry * x1p / rx
    cx = cos_p * cxp - sin_p * cyp + (p0[0] + p1[0]) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (p0[1] + p1[1]) / 2.0

    def ang(ux, uy, vx, vy):
        d = (ux * vx + uy * vy) / (math.hypot(ux, uy) * math.hypot(vx, vy) + 1e-12)
        a = math.acos(max(-1.0, min(1.0, d)))
        return -a if ux * vy - uy * vx < 0 else a

    th0 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dth = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dth > 0:
        dth -= 2 * math.pi
    elif sweep and dth < 0:
        dth += 2 * math.pi
    # 采样密度按弧长定：固定 8 段在大半径圆弧上弦高误差能到 1.2mm，
    # 剖面线端点就会被判"离轮廓 1.35mm"，那是采样不足，不是图错。
    span = abs(dth) * max(rx, ry)
    n = max(4, min(96, int(span / 1.0) or 4))
    pts = []
    for i in range(n + 1):
        th = th0 + dth * i / n
        x, y = rx * math.cos(th), ry * math.sin(th)
        pts.append((cos_p * x - sin_p * y + cx, sin_p * x + cos_p * y + cy))
    return pts


def _chain_segs(segs, tol=0.5):
    """把端点相接的线段串成折线。闭合的回首尾同点，用 _closed 判。"""
    pool = list(segs)
    chains = []
    while pool:
        x1, y1, x2, y2 = pool.pop(0)
        pts = [(x1, y1), (x2, y2)]
        grew = True
        while grew:
            grew = False
            for i, (a, b, c, d) in enumerate(pool):
                cand = [((a, b), (c, d)), ((c, d), (a, b))]
                for tail in (True, False):
                    px, py = pts[-1] if tail else pts[0]
                    for (sx, sy), (ex, ey) in cand:
                        if math.hypot(px - sx, py - sy) <= tol:
                            if tail:
                                pts.append((ex, ey))
                            else:
                                pts.insert(0, (ex, ey))
                            pool.pop(i)
                            grew = True
                            break
                    if grew:
                        break
                if grew:
                    break
        chains.append(pts)
    return chains


def _closed(pts, tol=0.5):
    return len(pts) >= 4 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) <= tol


def _point_in_poly(px, py, poly):
    """射线法。poly 首尾可重复，重复点不影响结果。"""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xin = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xin:
                inside = not inside
    return inside


def _ang(x1, y1, x2, y2):
    return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0


def _raw_ends(ctx):
    """原始图元的端点（圆弧只取 M/A 的端点，不取采样点）。

    L2-01 判的是"两条轮廓段接上了没有"，拿圆弧的 9 个采样点去算，同一段弧的
    相邻采样点会被当成 944 处细缝。
    """
    ends = []
    for i, (tag, a, _) in enumerate(ctx.els):
        if a.get("data-role") not in ("outline", "section-outline", "key-outline"):
            continue
        if tag == "line":
            ends.append(((float(a["x1"]), float(a["y1"])), i))
            ends.append(((float(a["x2"]), float(a["y2"])), i))
        elif tag == "path":
            for cmd, _n, _p0, p1 in _path_cmds(a.get("d", "")):
                if cmd in ("M", "L", "A", "Q"):
                    ends.append((p1, i))
        elif tag in ("polygon", "polyline"):
            ends += [((float(m.group(1)), float(m.group(2))), i)
                     for m in re.finditer(r"([-\d.]+)\s*[,\s]\s*([-\d.]+)", a.get("points", ""))]
    return ends


@rule("L2-01", "轮廓线段的端点不留细缝", "CHK-02")
def r_seam(ctx):
    """每个轮廓端点要么正好接上（≤0.02mm），要么本来就分开（>0.5mm）。

    落在 0.02~0.5mm 之间的是画漏的缝：看着连上了，放大就有洞。

    逐对比较会把同一圆角两端的间距（r=0.3 的弧弦长 0.42mm）报成缝，
    所以按"端点自己有没有接上"判：先看它有没有 ≤0.02 的伙伴，有就是接上了。
    """
    ends = _raw_ends(ctx)
    bad = []
    for i, (p, si) in enumerate(ends):
        near = sorted(math.hypot(p[0] - q[0], p[1] - q[1])
                      for j, (q, _sj) in enumerate(ends) if j != i)
        if not near:
            continue
        if near[0] <= 0.02:
            continue                      # 已经接上
        if near[0] <= 0.5:
            bad.append("(%g,%g) 最近的端点还在 %.2fmm 外" % (p[0], p[1], near[0]))
    if bad:
        return "不通过", "%d 个端点悬空：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 个轮廓端点都接上了" % len(ends)


@rule("L2-02", "圆弧半径与端点弦长相容", "GEO-05")
def r_arc_radius(ctx):
    """r < 弦长/2 的圆弧在欧氏几何里画不出来，浏览器会把半径放大到弦长一半再画，
    于是图上看到的圆角和设计值不是一回事。这条只能靠算，肉眼看不出。"""
    bad, n = [], 0
    for tag, a, _ in ctx.els:
        if tag != "path":
            continue
        for cmd, nums, p0, p1 in _path_cmds(a.get("d", "")):
            if cmd != "A" or len(nums) < 7:
                continue
            n += 1
            rx, ry = abs(nums[0]), abs(nums[1])
            chord = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if chord < 1e-6:
                continue                      # 起终点重合是整圆，归 L2-05
            need = chord / 2.0
            if min(rx, ry) + 1e-6 < need:
                bad.append("圆弧 r=%.2f 但弦长 %.2f 至少要 r=%.2f（%s）"
                           % (min(rx, ry), chord, need, a.get("id") or "无 id"))
    if not n:
        return "未检查", "图上没有 A 命令"
    if bad:
        return "不通过", "%d/%d 条：%s" % (len(bad), n, "；".join(bad[:4]))
    return "通过", "%d 条圆弧半径都 ≥ 弦长一半" % n


@rule("L2-03", "圆弧端点落在相邻轮廓线上", "GEO-02")
def r_arc_touch(ctx):
    """圆角的两个端点必须接在母线和端面上。端点悬空说明圆角是"贴"上去的，
    轮廓在圆角处断开——GEO-02 说的"不用折线拐弯或遮盖矩形伪装"。"""
    segs = ctx.segs_of(("outline", "key-outline", "section-outline"))
    if not segs:
        return "未检查", "没有轮廓线段可对照"
    bad, n = [], 0
    own = set()
    for tag, a, _ in ctx.els:
        if tag == "path":
            own.add(id(a))
    for tag, a, _ in ctx.els:
        if tag != "path":
            continue
        cmds = _path_cmds(a.get("d", ""))
        arcs = [c for c in cmds if c[0] == "A"]
        if not arcs:
            continue
        # 只核"纯圆角 path"（一两条命令，不含 Z），复杂 path 的端点归属判不准
        if len(cmds) > 3 or any(c[0] == "Z" for c in cmds):
            continue
        for cmd, nums, p0, p1 in arcs:
            for p, which in ((p0, "起点"), (p1, "终点")):
                n += 1
                d = nearest(p[0], p[1], segs)
                if d > 0.35:
                    bad.append("%s %s(%g,%g) 离轮廓 %.2fmm"
                               % (a.get("id") or "圆弧", which, p[0], p[1], d))
    if not n:
        return "未检查", "没有可判归属的圆角 path"
    if bad:
        return "不通过", "%d/%d 个端点悬空：%s" % (len(bad), n, "；".join(bad[:4]))
    return "通过", "%d 个圆弧端点都接在轮廓上" % n


@rule("L2-04", "开放圆弧不用闭合多边形", "GEO-04")
def r_open_arc(ctx):
    """用 polygon 画圆弧、首尾又不重合，浏览器会自动补一条弦——图上多出一根
    谁也没画的直线。GEO-04 说的就是这条。"""
    bad = []
    for tag, a, _ in ctx.by_role("outline", "section-outline", "key-outline"):
        if tag not in ("polygon", "polyline"):
            continue
        pts = [(float(m.group(1)), float(m.group(2)))
               for m in re.finditer(r"([-\d.]+)\s*[,\s]\s*([-\d.]+)", a.get("points", ""))]
        if len(pts) < 5:
            continue
        # 弧状：所有中间点到首尾连线的距离明显 > 0，且点列单调转折
        x1, y1 = pts[0]
        x2, y2 = pts[-1]
        chord = math.hypot(x2 - x1, y2 - y1)
        bulge = 0.0
        for px, py in pts[1:-1]:
            if chord < 1e-6:
                bulge = max(bulge, math.hypot(px - x1, py - y1))
            else:
                bulge = max(bulge, pt_seg_dist(px, py, x1, y1, x2, y2))
        if tag == "polygon" and bulge > 1.0:
            bad.append("%s 是弧状点列（弯 %.1fmm），polygon 会自动补弦"
                       % (a.get("id") or "多边形", bulge))
    if bad:
        return "不通过", "；".join(bad[:4])
    return "通过", "没有用 polygon 冒充开放圆弧"


@rule("L2-05", "整圆用 circle 图元", "GEO-06")
def r_full_circle(ctx):
    bad, n = [], 0
    for tag, a, _ in ctx.els:
        if tag != "path":
            continue
        for cmd, nums, p0, p1 in _path_cmds(a.get("d", "")):
            if cmd != "A":
                continue
            n += 1
            if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) <= 0.05:
                bad.append("%s 用圆弧画整圆（起终点重合）" % (a.get("id") or "path"))
    if not n:
        return "未检查", "图上没有 A 命令"
    if bad:
        return "不通过", "；".join(bad[:4])
    return "通过", "%d 条圆弧都不是整圆" % n


@rule("L2-06", "剖面线两端落在轮廓上", "CHK-02")
def r_hatch_inside(ctx):
    """剖面线是用轮廓裁出来的：两个端点都该贴着轮廓（或相邻剖面线/轴线）。

    原来想用"中点落在断面多边形内"判，但断面轮廓在图上不是闭合环——A—A 只有
    3 条直线段，剩下大半圈是 outline 里的圆弧，链不成多边形。端点距离是等价
    且不依赖闭合性的判据：端点离开轮廓，就是剖面线跑到实体外了。
    """
    segs = ctx.segs_of(("section-outline", "outline", "key-outline"))
    hatches = []
    for tag, a, _ in ctx.by_role("hatch"):
        if tag != "line":
            continue
        try:
            hatches.append((float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"]),
                            a.get("data-name") or ""))
        except (KeyError, ValueError):
            continue
    if not segs or not hatches:
        return "未检查", "没有轮廓或剖面线（轮廓 %d / 剖面 %d）" % (len(segs), len(hatches))
    bad = []
    for x1, y1, x2, y2, nm in hatches:
        for px, py, which in ((x1, y1, "起"), (x2, y2, "终")):
            d = nearest(px, py, segs)
            if d > 0.6:
                bad.append("断面 %s 的剖面线%s端(%g,%g) 离轮廓 %.2fmm" % (nm or "?", which, px, py, d))
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 条剖面线的两端都贴着轮廓" % len(hatches)


@rule("L2-07", "同一断面剖面线角度与间距一致", "SHT-06")
def r_hatch_uniform(ctx):
    """剖面线要平行、等距。角度或间距飘了，说明是按图元逐条算的，
    而不是按整块区域裁的——密度不均肉眼一瞥就能看出来。"""
    groups = defaultdict(list)
    for tag, a, _ in ctx.by_role("hatch"):
        if tag != "line":
            continue
        try:
            groups[a.get("data-name") or "?"].append(
                (float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"])))
        except (KeyError, ValueError):
            continue
    if not groups:
        return "未检查", "没有剖面线"
    bad, done = [], 0
    for nm, segs in groups.items():
        if len(segs) < 3:
            continue
        done += 1
        angs = [_ang(*s) for s in segs]
        if max(angs) - min(angs) > 0.5:
            bad.append("断面 %s 角度差 %.1f°" % (nm, max(angs) - min(angs)))
            continue
        # 垂直于剖面线方向的投影 = 间距序列
        th = math.radians(angs[0] + 90.0)
        ux, uy = math.cos(th), math.sin(th)
        # 半圆断面里对称位置的剖面线，中点投影会重合；先按 0.05mm 去重再算间距
        raw = sorted(((s[0] + s[2]) / 2.0) * ux + ((s[1] + s[3]) / 2.0) * uy for s in segs)
        proj = []
        for v in raw:
            if not proj or v - proj[-1] > 0.05:
                proj.append(v)
        gaps = [b - a2 for a2, b in zip(proj, proj[1:]) if b - a2 > 0.05]
        if len(gaps) >= 2:
            mean = sum(gaps) / len(gaps)
            if mean > 0 and (max(gaps) - min(gaps)) / mean > 0.15:
                bad.append("断面 %s 间距 %.2f~%.2fmm" % (nm, min(gaps), max(gaps)))
    if not done:
        return "未检查", "没有成组的剖面线（每组需 ≥3 条）"
    if bad:
        return "不通过", "；".join(bad[:4])
    return "通过", "%d 个断面的剖面线平行等距" % done


@rule("L2-08", "没有完全重合的重复线", "CHK-04")
def r_dup_lines(ctx):
    """两条线段端点完全相同（正向或反向）就是画了两遍。重合线会让线宽变深、
    打印发黑，也让"数量对不对"这类判断失效（ID-03）。"""
    seen = {}
    dups = []
    for x1, y1, x2, y2 in ctx.segs_of(("outline", "section-outline", "key-outline",
                                       "hidden", "centerline", "extension")):
        k = tuple(round(v, 2) for v in (x1, y1, x2, y2))
        rk = tuple(round(v, 2) for v in (x2, y2, x1, y1))
        if k in seen or rk in seen:
            dups.append("(%g,%g)-(%g,%g)" % (x1, y1, x2, y2))
        else:
            seen[k] = True
    if dups:
        return "不通过", "%d 条重复：%s" % (len(dups), "；".join(dups[:4]))
    return "通过", "%d 条线段无完全重合" % len(seen)


@rule("L2-09", "图元不越出内框", "CHK-04")
def r_frame(ctx):
    """图元—图框碰撞。内框取 sheet 角色里最小的那个矩形（排除零尺寸的外框线）。"""
    boxes = []
    for tag, a, _ in ctx.by_role("sheet"):
        if tag != "rect":
            continue
        try:
            x, y = float(a["x"]), float(a["y"])
            w, h = float(a["width"]), float(a["height"])
        except (KeyError, ValueError):
            continue
        if w > 50 and h > 50:
            boxes.append((x, y, x + w, y + h))
    if not boxes:
        return "未检查", "没有可用的图框矩形"
    # 内框 = 所有大矩形里最小的那个
    ix1, iy1, ix2, iy2 = min(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))
    bad, n = [], 0
    for tag, a, _ in ctx.els:
        if tag not in ("line", "path", "circle", "rect", "polygon", "polyline", "text"):
            continue
        if a.get("data-role") in ("sheet",):
            continue
        b = _bbox(tag, a)
        if b == (0.0, 0.0, 0.0, 0.0):
            continue
        n += 1
        if b[0] < ix1 - 0.6 or b[1] < iy1 - 0.6 or b[2] > ix2 + 0.6 or b[3] > iy2 + 0.6:
            bad.append("%s %s (%.1f,%.1f)-(%.1f,%.1f)" % (tag, a.get("data-role"), *b))
    if bad:
        return "不通过", "%d/%d 个图元越界（内框 %.0f,%.0f-%.0f,%.0f）：%s" % (
            len(bad), n, ix1, iy1, ix2, iy2, "；".join(bad[:3]))
    return "通过", "%d 个图元都在内框内（%.0f,%.0f-%.0f,%.0f）" % (n, ix1, iy1, ix2, iy2)

# ============================================================ L3 碰撞层
# CHARTER §13 CHK-04~08。这一层必须用浏览器量出来的包围盒（CHK-06）：
# 图上竖排的尺寸文字全在 <g transform="rotate(...)"> 里，按属性算出来的框是横的、
# 位置也是错的，拿那种框判碰撞报的全是假。包围盒由 measure.py 导出。

def _b_hit(a, b, min_ov=0.15):
    """两个轴对齐框的重叠面积够不够大。偏薄的擦边（<0.15mm）多半是抗锯齿或字体余量。"""
    ox = min(a["xmax"], b["xmax"]) - max(a["xmin"], b["xmin"])
    oy = min(a["ymax"], b["ymax"]) - max(a["ymin"], b["ymin"])
    return (ox, oy) if ox > min_ov and oy > min_ov else None


def _seg_hits_box(s, b, pad=0.0):
    """线段与矩形相交：端点在框内，或与任一条边真交叉。"""
    bx0, bx1 = b["xmin"] + pad, b["xmax"] - pad
    by0, by1 = b["ymin"] + pad, b["ymax"] - pad
    if bx0 >= bx1 or by0 >= by1:
        return False
    x1, y1, x2, y2 = s["x1"], s["y1"], s["x2"], s["y2"]

    def inside(x, y):
        return bx0 <= x <= bx1 and by0 <= y <= by1

    if inside(x1, y1) or inside(x2, y2):
        return True

    def d(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)

    for ax, ay, cx, cy in ((bx0, by0, bx1, by0), (bx1, by0, bx1, by1),
                           (bx1, by1, bx0, by1), (bx0, by1, bx0, by0)):
        d1, d2 = d(x1, y1, x2, y2, ax, ay), d(x1, y1, x2, y2, cx, cy)
        d3, d4 = d(ax, ay, cx, cy, x1, y1), d(ax, ay, cx, cy, x2, y2)
        if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)):
            return True
    return False


# ============================================================ L2-10 完备性
# 这一条和上面九条反过来：上面问"画出来的东西对不对"，它问"该画的东西画了没有"。
# 实测两轮都栽在这上面（齿轮漏 8 条线、轴漏阶梯线中段），章程全绿而图是错的。

_OUTLINE_ROLES = ("outline", "section-outline", "key-outline")


def _outline_segs(ctx):
    """图上所有可见轮廓直段（line 与 path 的 L 段），保持原坐标系。"""
    out = []
    for tag, a, _ in ctx.els:
        if a.get("data-role") not in _OUTLINE_ROLES:
            continue
        if tag == "line":
            out.append((float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"])))
        elif tag == "path":
            for cmd, _n, p0, p1 in _path_cmds(a.get("d", "")):
                if cmd == "L":
                    out.append((p0[0], p0[1], p1[0], p1[1]))
    return out


def _cover(seg, cands, perp_tol=0.15, join_tol=0.3):
    """清单段被图上共线段并集覆盖的比率，以及最大缺口（沿段方向的位置区间）。

    只取两端都贴在这条直线上的候选：一端偏 0.15mm 以上就不属于这条线。
    合并时允许 0.3mm 接缝——圆角切点处本来就会把一条边拆成几段画。
    """
    x1, y1, x2, y2 = seg
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return 1.0, None
    ux, uy = (x2 - x1) / L, (y2 - y1) / L

    def perp(px, py):
        return abs(-uy * (px - x1) + ux * (py - y1))

    spans = []
    for a, b, c, d in cands:
        if perp(a, b) > perp_tol or perp(c, d) > perp_tol:
            continue
        t0 = ux * (a - x1) + uy * (b - y1)
        t1 = ux * (c - x1) + uy * (d - y1)
        lo, hi = max(0.0, min(t0, t1)), min(L, max(t0, t1))
        if hi > lo:
            spans.append((lo, hi))
    if not spans:
        return 0.0, (0.0, L)
    spans.sort()
    merged = [list(spans[0])]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1] + join_tol:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    cover = sum(h - l for l, h in merged)
    gap, gap_sz, prev = None, 0.0, 0.0
    for lo, hi in merged:
        if lo - prev > gap_sz:
            gap_sz, gap = lo - prev, (prev, lo)
        prev = max(prev, hi)
    if L - prev > gap_sz:
        gap_sz, gap = L - prev, (prev, L)
    if gap_sz <= 1e-6:
        gap = None
    return cover / L, gap


@rule("L2-10", "要素清单里的轮廓都在图上", "CHK-02 / GEO-06")
def r_features(ctx):
    """对照生成器的要素清单查完备性：清单说有、图上没有 → 报。

    其余规则都以"图上已有的图元"为前提，漏画的东西它们一起沉默。
    齿轮漏 8 条线、轴漏阶梯线中段，两次都是章程全绿、用户看图才发现。
    """
    feats = getattr(ctx, "features", None) or []
    if not feats:
        return "未检查", "没有要素清单（features.json），查不了完备性"

    segs = _outline_segs(ctx)
    circles = [(float(a["cx"]), float(a["cy"]), float(a["r"]))
               for tag, a, _ in ctx.els if tag == "circle"]

    bad, done = [], 0
    for f in feats:
        kind, fid = f.get("类型") or "", f.get("id") or "?"
        note = ("（%s）" % f["说明"]) if f.get("说明") else ""
        tol = float(f.get("容差", 0.95))
        if kind == "线段":
            try:
                seg = (float(f["x1"]), float(f["y1"]), float(f["x2"]), float(f["y2"]))
            except (KeyError, ValueError):
                bad.append("%s 坐标不全%s" % (fid, note))
                continue
            rate, gap = _cover(seg, segs)
            if rate + 1e-9 >= tol:
                done += 1
                continue
            if gap:
                L = math.hypot(seg[2] - seg[0], seg[3] - seg[1]) or 1
                bad.append("%s%s 覆盖 %.0f%%，缺口 %.1fmm，起自 (%.1f,%.1f)"
                           % (fid, note, 100 * rate, gap[1] - gap[0],
                              seg[0] + (seg[2] - seg[0]) * gap[0] / L,
                              seg[1] + (seg[3] - seg[1]) * gap[0] / L))
            else:
                bad.append("%s%s 覆盖 %.0f%%" % (fid, note, 100 * rate))
        elif kind == "圆":
            try:
                cx, cy, r = float(f["cx"]), float(f["cy"]), float(f["r"])
            except (KeyError, ValueError):
                bad.append("%s 圆参数不全%s" % (fid, note))
                continue
            if any(abs(cx - x) <= 0.15 and abs(cy - y) <= 0.15 and abs(r - rr) <= 0.15
                   for x, y, rr in circles):
                done += 1
            else:
                bad.append("%s%s 图上没有同心同径的圆（r=%g）" % (fid, note, r))
        else:
            bad.append("%s 类型不认识：%r" % (fid, kind))

    if bad:
        return "不通过", "%d/%d 条缺失：%s" % (len(bad), len(feats), "；".join(bad[:4]))
    return "通过", "清单 %d 条轮廓图上都有（图上线段 %d、圆 %d）" % (len(feats), len(segs), len(circles))


@rule("L3-01", "文字之间不重叠", "CHK-04")
def r_text_text(ctx):
    if not ctx.bounds:
        return "未检查", "没提供 --bounds（浏览器量测的包围盒）"
    ts = ctx.bounds["texts"]
    bad = []
    for i in range(len(ts)):
        for j in range(i + 1, len(ts)):
            ov = _b_hit(ts[i], ts[j])
            if ov:
                bad.append("%r × %r 重叠 %.2f×%.2fmm"
                           % (ts[i].get("t", "")[:10], ts[j].get("t", "")[:10], ov[0], ov[1]))
    if bad:
        return "不通过", "%d 对：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 个文字框两两不重叠" % len(ts)


@rule("L3-02", "文字不压在轮廓与中心线上", "CHK-04")
def r_text_graphics(ctx):
    """轮廓线、剖切轮廓、键槽轮廓、虚线、中心线——文字压在这些上面一定看不清楚。

    尺寸线、尺寸界线、剖面线不在这条里：数字本来就贴着尺寸线写（正常间距 1~2mm），
    压不压由 L3-03 单独判。
    """
    if not ctx.bounds:
        return "未检查", "没提供 --bounds"
    roles = ("outline", "section-outline", "key-outline", "hidden", "centerline")
    segs = [s for s in ctx.bounds["segments"] if s.get("role") in roles]
    if not segs:
        return "未检查", "量测里没有轮廓类线段"
    bad = []
    for t in ctx.bounds["texts"]:
        for s in segs:
            if _seg_hits_box(s, t, pad=0.05):
                bad.append("%r 压在 %s 上" % (t.get("t", "")[:12], s.get("role")))
                break
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 个文字都没压轮廓（%d 条轮廓线）" % (len(ctx.bounds["texts"]), len(segs))


@rule("L3-03", "文字不压在尺寸线与界线上", "CHK-04")
def r_text_dims(ctx):
    """尺寸数字离自己的尺寸线 1~2mm 是正常的；真压上去（相交）就是画错了。

    公差的上下偏差之间间距只有 0.5mm 左右，那是排版惯例，不算碰撞——它们不相交。
    """
    if not ctx.bounds:
        return "未检查", "没提供 --bounds"
    segs = [s for s in ctx.bounds["segments"] if s.get("role") in ("dimension", "extension", "arrow")]
    if not segs:
        return "未检查", "量测里没有尺寸类线段"
    bad = []
    for t in ctx.bounds["texts"]:
        for s in segs:
            if _seg_hits_box(s, t, pad=0.05):
                bad.append("%r 压在 %s（%s）上"
                           % (t.get("t", "")[:12], s.get("role"), s.get("name", "")[:14]))
                break
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 个文字都没压尺寸线（%d 条）" % (len(ctx.bounds["texts"]), len(segs))


@rule("L3-04", "尺寸线之间不互相穿插", "CHK-04")
def r_dim_cross(ctx):
    """两条尺寸线真交叉（不是共用端点、不是互相垂直的正常布局）就是标注打架。

    平行且共线的（台阶处的分段尺寸线）合并后由 L1-01 处理，这里不管。
    """
    if not ctx.bounds:
        return "未检查", "没提供 --bounds"
    segs = [s for s in ctx.bounds["segments"] if s.get("role") == "dimension"]
    if len(segs) < 2:
        return "未检查", "尺寸线少于 2 条"
    bad = []
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if _cross_mid(a, b):
                bad.append("(%g,%g)-(%g,%g) × (%g,%g)-(%g,%g)"
                           % (a["x1"], a["y1"], a["x2"], a["y2"],
                              b["x1"], b["y1"], b["x2"], b["y2"]))
    if bad:
        return "不通过", "%d 对相交：%s" % (len(bad), "；".join(bad[:3]))
    return "通过", "%d 条尺寸线互不穿插" % len(segs)


def _cross_mid(a, b, eps=0.6):
    """两条线段是否在**内部**真交叉（交点在两段的中段，不是端点相接）。

    只看"线段相交"会把共用节点、互相垂直的坐标式标注全报进来。要求交点到
    每条线的两端都留有余量，才算"穿插"。
    """
    x1, y1, x2, y2 = a["x1"], a["y1"], a["x2"], a["y2"]
    x3, y3, x4, y4 = b["x1"], b["y1"], b["x2"], b["y2"]
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return False
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / den
    if not (0 < t < 1 and 0 < u < 1):
        return False
    la = math.hypot(x2 - x1, y2 - y1)
    lb = math.hypot(x4 - x3, y4 - y3)
    return min(t, 1 - t) * la > eps and min(u, 1 - u) * lb > eps


@rule("L3-05", "填充符号不与文字重叠", "CHK-07")
def r_filled_text(ctx):
    """箭头、基准三角形、粗糙度三角是**实心填充**的，不比细线——它们和文字重叠
    比线压字更糊。CHK-07 要求对填充区域做区域相交，不只查边线。"""
    if not ctx.bounds:
        return "未检查", "没提供 --bounds"
    fills = [b for b in ctx.bounds["boxes"]
             if b.get("role") in ("arrow", "datum", "roughness")
             and b.get("tag") in ("polygon", "polyline", "path")]
    if not fills:
        return "未检查", "量测里没有填充类符号"
    bad = []
    for t in ctx.bounds["texts"]:
        for f in fills:
            ov = _b_hit(t, f, min_ov=0.05)
            if ov:
                bad.append("%r 压住 %s（重叠 %.2fmm²）"
                           % (t.get("t", "")[:12], f.get("role"), ov[0] * ov[1]))
    if bad:
        return "不通过", "%d 处：%s" % (len(bad), "；".join(bad[:4]))
    return "通过", "%d 个填充符号都不与文字重叠" % len(fills)


@rule("L3-06", "不同视图的图元不互相侵入", "CHK-04")
def r_view_overlap(ctx):
    """视图—视图碰撞。判据要有视图归属才行；本批图没有 data-view，
    按 bbox 聚类猜视图等于用猜测代替身份（ID-02 明令禁止）。"""
    views = defaultdict(list)
    for b in (ctx.bounds or {}).get("boxes", []):
        v = ctx.view_of.get(b.get("id", ""))
        if v:
            views[v].append(b)
    if len(views) < 2:
        return "未检查", "图上没有 data-view，判不了视图归属（ID-02 不许靠猜）"
    names = sorted(views)
    bad = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for a in views[names[i]]:
                for b in views[names[j]]:
                    if _b_hit(a, b, min_ov=0.5):
                        bad.append("%s × %s" % (names[i], names[j]))
                        break
                else:
                    continue
                break
    if bad:
        return "不通过", "视图重叠：%s" % "、".join(sorted(set(bad))[:4])
    return "通过", "%d 个视图互不侵入" % len(names)

def run(svg, calc_path=None, fig_no=None, bounds_path=None, features_path=None):
    calc = {}
    if calc_path:
        calc = json.loads(Path(calc_path).read_text(encoding="utf-8"))
    bounds = None
    if bounds_path:
        # 也接受已经读好的 dict（check.py 一条龙跑时直接用 measure() 的返回值）
        bounds = (bounds_path if isinstance(bounds_path, dict)
                  else json.loads(Path(bounds_path).read_text(encoding="utf-8")))
    feats = []
    if features_path:
        _d = (features_path if isinstance(features_path, dict)
              else json.loads(Path(features_path).read_text(encoding="utf-8")))
        feats = _d.get("要素", []) if isinstance(_d, dict) else list(_d)
    ctx = Ctx(svg, calc=calc, fig_no=fig_no, bounds=bounds, features=feats)
    out = []
    for rid, name, chapter, sev, fn in RULES:
        try:
            status, evidence = fn(ctx)
        except Exception as e:                       # 规则自己炸了 ≠ 图合格
            status, evidence = "未检查", "规则异常：%r" % (e,)
        out.append((rid, name, chapter, sev, status, evidence))
    return out


def report(rows, svg):
    print("\nL1 结构 / L2 几何 / L3 碰撞 — %s" % Path(svg).name)
    icon = {"通过": "✓", "不通过": "✗", "警示": "!", "未检查": "?"}
    for rid, name, ch, sev, st, ev in rows:
        print("  %s %-6s %-34s %s" % (icon.get(st, " "), rid, name, ev))
    n_pass = sum(1 for r in rows if r[4] == "通过")
    n_bad = sum(1 for r in rows if r[4] == "不通过")
    n_unk = sum(1 for r in rows if r[4] == "未检查")
    n_warn = sum(1 for r in rows if r[4] == "警示")
    print("\n  %d 通过 / %d 不通过 / %d 警示 / %d 未检查（共 %d 条）" % (
        n_pass, n_bad, n_warn, n_unk, len(rows)))
    return n_bad == 0 and n_unk == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--calc", help="计算书 JSON（期望值的独立来源）")
    ap.add_argument("--fig-no", help="应出现的图号")
    ap.add_argument("--bounds", help="measure.py 导出的包围盒 JSON（L3 用）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        rows = run(a.svg, a.calc, a.fig_no, a.bounds)
    except Exception as e:
        print("检查器异常：%r" % (e,), file=sys.stderr)
        return 2
    ok = report(rows, a.svg)
    if a.json:
        print(json.dumps([{"id": r[0], "name": r[1], "chapter": r[2], "sev": r[3],
                           "status": r[4], "evidence": r[5]} for r in rows],
                         ensure_ascii=False, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())