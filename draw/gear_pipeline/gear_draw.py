#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""齿轮零件图 SVG 渲染管线（GB/T 4459.2 齿轮画法 / GB/T 4457.4 图线 /
GB/T 1184 形位公差 / GB/T 1095 键槽 / GB/T 10095 精度）。

三段式：
    params(dict)  --render()-->  svg 字符串  --check()-->  问题清单

参数分四块，一次列全（见 SCHEMA）：
    geometry    几何：m、z、α、x、d/d_a/d_f、b、键槽(宽×深×长)、轴孔、轮毂、
                      腹板/轮辐结构形式、倒角/圆角
    annotation  标注：各尺寸公差、表面粗糙度（部位→Ra）、形位公差
    tables      表格：齿轮参数表、标题栏、技术要求
    sheet       图纸：图幅、比例、视图布置、版面锚点、线宽

坐标约定
--------
图纸坐标单位 mm，viewBox 原点在图纸左上角。零件尺寸(mm) 乘比例系数 s 得图纸长度：
    1:2  ->  s = 0.5
所有关键坐标 = 版面锚点 + 零件尺寸 × s，函数内以「# 算：」注明算式。
本文件不含任何零件几何的硬编码坐标；只有 sheet.layout 里的 7 个版面锚点
（主视图左端面、端面图圆心、参数表、标题栏、技术要求、投影法符号的落位）
是图纸版式参数，不是零件尺寸。

线型（GB/T 4457.4）
------------------
    粗实线 0.5  可见轮廓（齿顶线/齿顶圆、齿根线、端面、孔壁）
    细实线 0.25 齿根圆（端面图）、尺寸界线、引出线、剖面线 0.18
    细点画线 0.25 分度圆/分度线、轴线（长点间隔 7-1.2-0.8-1.2）
    细实线 0.2  尺寸线/尺寸界线

注意 齿根的两套画法（GB/T 4459.2）：
    · 端面图（左视图）：齿根 **圆** 画细实线 —— 即本任务要求的"齿根圆细实线"；
    · 主视图（全剖）：轮齿按不剖画，齿顶 **线**、齿根 **线** 均为粗实线，
      分度线为细点画线，齿区不画剖面线。

几处"不能靠肉眼看出、只能靠算"的地方
------------------------------------
· 剖面线不用 SVG pattern：Chrome 打印 PDF 时 pattern 不落地，改为按 spacing 逐条
  生成 45° 线段（c = x+y 取全局等距网格），PDF/PNG 里都能看见，也便于 check 量间距。
· 端面图的轴孔是"弧"不是"整圆"：键槽口处孔的轮廓必须中断，弧的起止点由
  √(r_bore²-(b_k/2)²) 算出，槽壁也从该交点起画。
· 参数表的数值不在 tables 里另存一份，每行用 from="geometry.m" 现场解析，
  改模数表就跟着变，check 再拿渲染出来的字和参数逐格对。
· 分度线/轴线两端超出轮齿轮廓 2~3mm（点划线规矩），尺寸线不得与点画线重合。

用法
----
    python3 gear_draw.py --out 大齿轮零件图.svg --check     # 出图 + 六项自检
    python3 gear_draw.py --json params.json --out x.svg     # 换一套参数
    ./build.sh                                             # SVG→PDF→PNG→扫像素复核
    python3 test_check.py                                  # 反向测试：把图改坏，确认六项都会报
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Tuple

import svgwrite

# --------------------------------------------------------------------------- #
# 0. 常量
# --------------------------------------------------------------------------- #

SHEET_SIZES = {"A4": (297.0, 210.0), "A3": (420.0, 297.0)}

# 字体：中文宋体（GB/T 14691 长仿宋体的可用替代），数值同字体
FONT_CN = "Songti SC, STSong, SimSun, serif"

CHECK_ITEMS = [
    "第一角画法正确",
    "三线画法正确（齿顶圆/分度圆/齿根圆）",
    "尺寸标注完整、不重复、不封闭、箭头规范",
    "参数表、标题栏、技术要求齐全且内容与参数一致",
    "粗糙度、公差标注位置规范",
    "所有标注的尺寸值与输入参数一致",
]

# 表面 -> id 后缀（粗糙度/公差元素用 ASCII id）
SURF_ID = {"齿面": "tooth", "轴孔": "bore", "端面": "face", "其余": "other"}

# 引线式尺寸（只有一个箭头）与线性尺寸（两个箭头）
LEADER_DIMS = {"bore", "keyway_depth"}

# 尺寸键 -> (中文名, 计量形式)
DIM_KEYS = {
    "d_a": ("齿顶圆直径", "diameter"),
    "d": ("分度圆直径", "diameter_ref"),
    "d_f": ("齿根圆直径", "diameter_ref"),
    "b": ("齿宽", "length"),
    "bore": ("轴孔直径", "diameter"),
    "keyway_width": ("键槽宽", "length"),
    "keyway_depth": ("毂槽深 d+t2", "length"),
}


# --------------------------------------------------------------------------- #
# 1. 参数 schema —— 四块，一次列全
# --------------------------------------------------------------------------- #

def _leaf(t: type, unit: str, doc: str, **extra: Any) -> Dict[str, Any]:
    d = {"type": t, "unit": unit, "doc": doc}
    d.update(extra)
    return d


SCHEMA: Dict[str, Dict[str, Any]] = {
    # ---------------- 几何 ----------------
    "geometry": {
        "m": _leaf(float, "mm", "模数（标准值）", gt=0),
        "z": _leaf(int, "-", "齿数", gt=0),
        "alpha_deg": _leaf(float, "°", "压力角"),
        "x": _leaf(float, "-", "变位系数"),
        "d": _leaf(float, "mm", "分度圆直径 d=mz"),
        "d_a": _leaf(float, "mm", "齿顶圆直径 d_a=d+2m(1+x)"),
        "d_f": _leaf(float, "mm", "齿根圆直径 d_f=d-2.5m+2xm"),
        "b": _leaf(float, "mm", "齿宽"),
        "structure": _leaf(str, "-", "结构形式：实心式 / 腹板式", enum=["实心式", "腹板式", "轮辐式"]),
        "bore_d": _leaf(float, "mm", "轴孔直径"),
        "keyway": {
            "width": _leaf(float, "mm", "键槽宽 b（GB/T 1095）"),
            "t2": _leaf(float, "mm", "毂槽深 t2（毂槽深 d+t2 由此算出）"),
            "length": _leaf(float, "mm", "键槽长（通槽时 = 齿宽）"),
        },
        "hub": {  # 实心式为 None
            "d": _leaf(float, "mm", "轮毂外径"),
            "length": _leaf(float, "mm", "轮毂长度"),
        },
        "web": {  # 实心式为 None；腹板式必填
            "thickness": _leaf(float, "mm", "腹板厚度"),
            "rim_inner_d": _leaf(float, "mm", "轮缘内径"),
            "hole_d": _leaf(float, "mm", "腹板孔直径"),
            "hole_count": _leaf(int, "-", "腹板孔数"),
            "hole_pcd": _leaf(float, "mm", "腹板孔分布圆直径"),
        },
        "chamfer": _leaf(float, "mm", "未注倒角 C（45°）"),
        "fillet": _leaf(float, "mm", "未注圆角 R"),
    },
    # ---------------- 标注 ----------------
    "annotation": {
        "dims": {  # 每个尺寸的公差表达
            "d_a": _leaf(dict, "-", '{"tol":"h11"} 或 {"reference":True}'),
            "d": _leaf(dict, "-", "参考尺寸，画作 (φ135)"),
            "d_f": _leaf(dict, "-", "参考尺寸"),
            "b": _leaf(dict, "-", '{"tol":null} 表示未注公差'),
            "bore": _leaf(dict, "-", '{"tol":"H7","datum":"A"}'),
            "keyway_width": _leaf(dict, "-", '{"tol":"JS9"}'),
            "keyway_depth": _leaf(dict, "-", '{"tol_upper":0.2,"tol_lower":0.0}'),
        },
        "roughness": _leaf(dict, "μm", "部位→Ra：齿面/轴孔/端面/其余"),
        "gdt": _leaf(list, "-", "形位公差项列表 {symbol,value,datum,feature}"),
    },
    # ---------------- 表格 ----------------
    "tables": {
        "grade": _leaf(str, "-", "精度等级（参数表与技术要求共用）"),
        "param_table": _leaf(list, "-", "齿轮参数表行 [{name,sym,from,fmt}]，值由 from 指向的参数现场解析"),
        "title_block": _leaf(dict, "-", "标题栏 {name,material,drawing_no,designer,date,org,sheet,sheet_no}"),
        "tech_req": _leaf(list, "-", "技术要求条目"),
    },
    # ---------------- 图纸 ----------------
    "sheet": {
        "size": _leaf(str, "-", "图幅", enum=list(SHEET_SIZES)),
        "orientation": _leaf(str, "-", "landscape"),
        "scale": _leaf(str, "-", "比例，如 1:2"),
        "projection": _leaf(str, "-", "第一角"),
        "views": _leaf(dict, "-", "视图布置 {main,left}"),
        "margins": _leaf(dict, "mm", "图框：左25 其余5"),
        "line_widths": _leaf(dict, "mm", "粗0.5 细0.25 尺寸0.2 剖面0.18"),
        "hatch": _leaf(dict, "-", '{"angle":45,"spacing":2.6}'),
        "fonts": _leaf(dict, "mm", "字号：尺寸3.5 小字2.5"),
        "layout": _leaf(dict, "mm", "版面锚点：main_x0/left_cx/table_y/title_x/tech_y/proj_x/other_ra_x"),
    },
}


def default_params() -> Dict[str, Any]:
    """10-6 题大齿轮的实际参数（取自 10-6解答，实心式 m=2.5 z=54）。"""
    return {
        "geometry": {
            "m": 2.5, "z": 54, "alpha_deg": 20.0, "x": 0.0,
            "d": 135.0, "d_a": 140.0, "d_f": 128.75,
            "b": 65.0,
            "structure": "实心式",
            "bore_d": 25.0,
            "keyway": {"width": 8.0, "t2": 3.3, "length": 65.0},
            "hub": None,
            "web": None,
            "chamfer": 1.0, "fillet": 2.5,
        },
        "annotation": {
            "dims": {
                "d_a": {"tol": "h11"},
                "d": {"reference": True},
                "d_f": {"reference": True},
                "b": {"tol": None},
                "bore": {"tol": "H7", "datum": "A"},
                "keyway_width": {"tol": "JS9"},
                "keyway_depth": {"tol_upper": 0.2, "tol_lower": 0.0},
            },
            "roughness": {"齿面": 1.6, "轴孔": 1.6, "端面": 3.2, "其余": 6.3},
            "gdt": [
                {"symbol": "↗", "value": 0.030, "datum": "A", "feature": "左端面", "kind": "端面圆跳动"},
                {"symbol": "↗", "value": 0.040, "datum": "A", "feature": "齿顶圆", "kind": "齿顶圆径向圆跳动"},
            ],
        },
        "tables": {
            # 表内数值一律由 geometry / grade 现场解析，不在这里另存一份
            "grade": "7 级",
            "param_table": [
                {"name": "模数", "sym": "m", "from": "geometry.m", "fmt": "n"},
                {"name": "齿数", "sym": "z", "from": "geometry.z", "fmt": "n"},
                {"name": "压力角", "sym": "α", "from": "geometry.alpha_deg", "fmt": "n°"},
                {"name": "变位系数", "sym": "x", "from": "geometry.x", "fmt": "n"},
                {"name": "齿宽", "sym": "b", "from": "geometry.b", "fmt": "n"},
                {"name": "精度等级", "sym": "", "from": "tables.grade", "fmt": "s"},
            ],
            "title_block": {
                "name": "大齿轮",
                "material": "45 钢，调质",
                "drawing_no": "10-06-02",
                "designer": "雷小康",
                "date": "2026.10",
                "org": "中南林业科技大学",
                "sheet": "共 1 张",
                "sheet_no": "第 1 张",
            },
            "tech_req": [
                "1. 未注圆角 R{fillet}～R{fillet_hi}。",
                "2. 未注倒角 C{chamfer}×45°。",
                "3. 齿轮按 GB/T 10095.1—2008 制造，{grade}精度。",
                "4. 未注尺寸单位为 mm。",
            ],
        },
        "sheet": {
            "size": "A4", "orientation": "landscape", "scale": "1:2",
            "projection": "第一角",
            "views": {"main": "主视图（全剖）", "left": "左视图（端面图）"},
            "margins": {"left": 25.0, "right": 5.0, "top": 5.0, "bottom": 5.0},
            "line_widths": {"thick": 0.5, "thin": 0.25, "dim": 0.2, "hatch": 0.18},
            "hatch": {"angle": 45, "spacing": 2.6},
            "fonts": {"dim": 3.5, "tol": 2.3, "small": 2.6, "note": 2.8,
                      "label": 3.2, "title": 6.0},
            "layout": {
                "main_x0": 58.75,      # 主视图左端面
                "left_cx": 170.0,      # 端面图圆心 x
                "table_y": 8.0,        # 参数表上边
                "title_x": 112.0,      # 标题栏左边
                "tech_y": 162.0,       # "技术要求" 标题基线
                "proj_x": 38.0,        # 投影法符号左边
                "other_ra_x": 196.0,   # "其余 Ra6.3" 落位
            },
        },
    }


# --------------------------------------------------------------------------- #
# 2. 参数校验
# --------------------------------------------------------------------------- #

def _type_ok(t: type, v: Any) -> bool:
    if t is float:
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t is int:
        return isinstance(v, int) and not isinstance(v, bool)
    if t is str:
        return isinstance(v, str)
    if t is dict:
        return isinstance(v, dict)
    if t is list:
        return isinstance(v, list)
    return isinstance(v, t)


def validate_params(p: Dict[str, Any]) -> List[str]:
    """按 SCHEMA 逐块检查：缺块/缺键/类型不符/枚举越界。"""
    problems: List[str] = []
    for block, spec in SCHEMA.items():
        if block not in p:
            problems.append("缺参数块 %s" % block)
            continue
        got = p[block]
        if not isinstance(got, dict):
            problems.append("参数块 %s 应为 dict" % block)
            continue
        for key, leaf in spec.items():
            name = "%s.%s" % (block, key)
            if "type" not in leaf:                 # 嵌套块：keyway / hub / web
                if key not in got:
                    problems.append("缺参数 %s" % name)
                    continue
                if got[key] is None:               # hub/web 允许 None（实心式）
                    continue
                if not isinstance(got[key], dict):
                    problems.append("参数 %s 应为 dict" % name)
                    continue
                for sub, subleaf in leaf.items():
                    sname = "%s.%s" % (name, sub)
                    if sub not in got[key]:
                        problems.append("缺参数 %s" % sname)
                    elif not _type_ok(subleaf["type"], got[key][sub]):
                        problems.append("参数 %s 类型应为 %s" % (sname, subleaf["type"].__name__))
                continue
            if key not in got:
                problems.append("缺参数 %s" % name)
                continue
            v = got[key]
            t = leaf["type"]
            if not _type_ok(t, v):
                problems.append("参数 %s 类型应为 %s，实为 %s"
                                % (name, t.__name__, type(v).__name__))
            elif "enum" in leaf and v not in leaf["enum"]:
                problems.append("参数 %s=%r 不在可选值 %s 内" % (name, v, leaf["enum"]))
    if p.get("geometry", {}).get("structure") == "轮辐式":
        problems.append("结构形式「轮辐式」尚未实现（本管线只渲染实心式/腹板式）")
    if p.get("geometry", {}).get("structure") == "腹板式":
        for blk in ("hub", "web"):
            if not p.get("geometry", {}).get(blk):
                problems.append("腹板式结构必须给出 geometry.%s 参数" % blk)
    return problems


def _scale_factor(txt: str) -> float:
    """"1:2" -> 0.5   （图纸长度 = 零件尺寸 × 该系数）"""
    a, b = str(txt).split(":")
    f = float(a) / float(b)
    if f <= 0:
        raise ValueError("比例非法：%r" % txt)
    return f


def _fmt(v: float, nd: int = 2) -> str:
    s = ("%." + str(nd) + "f") % float(v)
    s = s.rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def _resolve(p: Dict[str, Any], path: str) -> Any:
    """按 "geometry.m" / "tables.grade" 取值，参数表因此永远与几何参数同源。"""
    cur: Any = p
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError("参数表引用的路径不存在：%s" % path)
        cur = cur[part]
    return cur


def _cell(value: Any, fmt: str) -> str:
    if fmt in ("s", "", None):
        return str(value)
    if fmt.startswith("n"):
        num = float(value)
        txt = ("%d" % num) if abs(num - round(num)) < 1e-9 else ("%g" % num)
        return txt + fmt[1:]
    return str(value)


def derive(p: Dict[str, Any]) -> Dict[str, float]:
    """由 m、z、x 反算三个直径，供 check() 与参数表核对。"""
    g = p["geometry"]
    m, z, x = g["m"], g["z"], g["x"]
    d = m * z
    return {
        "d": d,
        "d_a": d + 2.0 * m * (1.0 + x),
        "d_f": d - 2.5 * m + 2.0 * x * m,
        "h": 2.25 * m,
        "keyway_depth": g["bore_d"] + g["keyway"]["t2"],
    }


# --------------------------------------------------------------------------- #
# 3. 画笔
# --------------------------------------------------------------------------- #

class Pen:
    """把「线型 + 图层语义」封装成 svgwrite 元素，所有元素带 id/class 便于 check() 复核。"""

    def __init__(self, dwg: svgwrite.Drawing, sheet: Dict[str, Any]):
        self.dwg = dwg
        self.lw = sheet["line_widths"]
        self.ht = sheet["hatch"]
        self.fs = sheet["fonts"]
        self._init_hatch()

    # ---- 剖面线：45° 实线组（不用 pattern：Chrome 打印 PDF 时 pattern 不落地）----
    def _init_hatch(self) -> None:
        self.dwg.defs.add(self.dwg.clipPath(id="clip_hatch"))

    def hatch(self, rects, prefix: str = "M_hatch") -> int:
        """在给定矩形内生成等间距 45° 剖面线，线数与位置由 spacing 算出。"""
        sp = self.ht["spacing"]
        step = sp * math.sqrt(2.0)          # 45° 线沿 c=x+y 的间隔 = 法向间距×√2
        grp = self.dwg.g(**{"class": "hatch"})
        clip = self.dwg.defs.elements[-1]
        n = 0
        for (x0, y0, w, h) in rects:
            x1, y1 = x0 + w, y0 + h
            clip.add(self.dwg.rect(insert=(x0, y0), size=(w, h)))
            # c = x + y 取全局等距网格（k·step），各剖切区相位一致、间距严格均匀
            ka = int(math.ceil((x0 + y0) / step))
            kb = int(math.floor((x1 + y1) / step))
            for k in range(ka, kb + 1):
                c = k * step
                xa, xb = max(x0, c - y1), min(x1, c - y0)   # 直线 x+y=c 被矩形截取
                if xb - xa < 0.05:
                    continue
                el = self.dwg.line((xa, c - xa), (xb, c - xb), stroke="#000",
                                   stroke_width=self.lw["hatch"],
                                   **{"class": "hatch"})
                el.attribs["id"] = "%s_%d" % (prefix, n)
                grp.add(el)
                n += 1
        grp.attribs["clip-path"] = "url(#clip_hatch)"
        self.dwg.add(grp)
        return n

    # ---- 基本图元 ----
    def line(self, x1, y1, x2, y2, role="thin", id=None, cls=None):
        sw = self.lw.get(role, self.lw["thin"])
        cls = cls or role
        kw = dict(stroke="#000", stroke_width=sw, fill="none", **{"class": cls})
        if role == "center":
            kw["stroke_dasharray"] = "7 1.2 0.8 1.2"
        el = self.dwg.line((x1, y1), (x2, y2), **kw)
        if id:
            el.attribs["id"] = id
        self.dwg.add(el)
        return el

    def circle(self, cx, cy, r, role="thick", id=None):
        sw = self.lw.get(role, self.lw["thin"])
        kw = dict(stroke="#000", stroke_width=sw, fill="none", **{"class": role})
        if role == "center":
            kw["stroke_dasharray"] = "7 1.2 0.8 1.2"
        el = self.dwg.circle(center=(cx, cy), r=r, **kw)
        if id:
            el.attribs["id"] = id
        self.dwg.add(el)
        return el

    def rect(self, x, y, w, h, role="thin", id=None, fill="none"):
        sw = self.lw.get(role, self.lw["thin"])
        el = self.dwg.rect(insert=(x, y), size=(w, h), stroke="#000",
                           stroke_width=sw, fill=fill, **{"class": role})
        if id:
            el.attribs["id"] = id
        self.dwg.add(el)
        return el

    def path(self, d, role="thin", id=None, fill="none", cls=None):
        sw = self.lw.get(role, self.lw["thin"])
        el = self.dwg.path(d=d, stroke="#000", stroke_width=sw, fill=fill,
                           **{"class": cls or role})
        if id:
            el.attribs["id"] = id
        self.dwg.add(el)
        return el

    def text(self, s, x, y, size=None, anchor="middle", id=None, bold=False,
             rot=None, fill="#000", idx=None):
        size = self.fs["note"] if size is None else size
        el = self.dwg.text(s, insert=(x, y), font_size=size, font_family=FONT_CN,
                           text_anchor=anchor, fill=fill, id=idx)
        if id:
            el.attribs["id"] = id
        if bold:
            el.attribs["font-weight"] = "bold"
        if rot is not None:
            ang, rx, ry = rot
            g = self.dwg.g(transform="rotate(%g %g %g)" % (ang, rx, ry))
            g.add(el)
            self.dwg.add(g)
            return el
        self.dwg.add(el)
        return el

    # ---- 箭头（GB/T 4457.4：长 3、宽 0.9）----
    def arrow(self, tip, deg, id=None, length=3.0):
        a = math.radians(deg)
        ux, uy = math.cos(a), math.sin(a)       # 由尾指向尖
        bx, by = tip[0] - ux * length, tip[1] - uy * length
        half = length * 0.15
        px, py = -uy * half, ux * half
        d = "M%.3f,%.3f L%.3f,%.3f L%.3f,%.3f Z" % (
            tip[0], tip[1], bx + px, by + py, bx - px, by - py)
        return self.path(d, role="dim", id=id, fill="#000", cls="arrow")

    # ---- 线性尺寸（两端箭头向外）----
    def dim_linear(self, key, p1, p2, horizontal, text, size=None,
                   tol=None, tol_x=0.0, over=3.0):
        """p1/p2 为被注要素的两端点；尺寸线画在这两点之间（同一 y 或同一 x）。"""
        x1, y1 = p1
        x2, y2 = p2
        size = size or self.fs["dim"]
        self.line(x1, y1, x2, y2, role="dim", id="dimline_%s" % key, cls="dimline")
        if horizontal:
            self.arrow((x1, y1), 180.0, id="arrow_%s_1" % key)
            self.arrow((x2, y2), 0.0, id="arrow_%s_2" % key)
            self.text(text, (x1 + x2) / 2.0, y1 - 1.2, size=size, id="dimtext_%s" % key,
                      anchor="middle")
        else:
            self.arrow((x1, y1), 270.0, id="arrow_%s_1" % key)
            self.arrow((x2, y2), 90.0, id="arrow_%s_2" % key)
            midy = (y1 + y2) / 2.0
            # 竖排数字写在尺寸线左侧 0.7mm 处（旋转 -90 后字身沿 -x 展开，
            # 直接放 x1 上会让尺寸线穿过字，等于标注压线）
            tx0 = x1 - (size * 0.35 + 1.45)
            g = self.dwg.g(transform="rotate(-90 %g %g)" % (tx0, midy))
            t = self.dwg.text(text, insert=(tx0, midy + size * 0.35), font_size=size,
                              font_family=FONT_CN, text_anchor="middle",
                              fill="#000", id="dimtext_%s" % key)
            g.add(t)
            self.dwg.add(g)

    # ---- 表面粗糙度符号：60° 双划 + 顶横 + Ra 值 ----
    def ra_symbol(self, key, tip, normal_deg, note="Ra 1.6", label_dx=4.6,
                  label_dy=0.0, anchor="start", stand_off=1.0):
        """tip = 加工表面上的点；normal_deg = 指向外部的法线方向（屏幕坐标，y 向下）。"""
        a = math.radians(normal_deg)
        nx, ny = math.cos(a), math.sin(a)          # 法线（由材料指向外）
        tx, ty = -ny, nx                           # 切向
        ax, ay = tip[0] + nx * stand_off, tip[1] + ny * stand_off   # 符号基点
        # 算：两条与表面成 60° 的短划，短划 1.6，长划 4.4
        c60, s60 = math.cos(math.radians(60)), math.sin(math.radians(60))
        lx, ly = ax + (-tx * c60 + nx * s60) * 1.6, ay + (-ty * c60 + ny * s60) * 1.6
        rx, ry = ax + (tx * c60 + nx * s60) * 4.4, ay + (ty * c60 + ny * s60) * 4.4
        self.line(tip[0], tip[1], ax, ay, role="thin", id="ra_lead_%s" % key)
        self.line(lx, ly, ax, ay, role="thin", id="ra_sym1_%s" % key)
        self.line(ax, ay, rx, ry, role="thin", id="ra_sym2_%s" % key)
        # 去除材料：顶端加横线（GB/T 131）
        bx2, by2 = rx - tx * 2.6, ry - ty * 2.6
        self.line(bx2, by2, rx + tx * 0.8, ry + ty * 0.8, role="thin",
                  id="ra_bar_%s" % key)
        self.text(note, rx + label_dx, ry + label_dy + 1.0, size=self.fs["note"],
                  id="ra_text_%s" % key, anchor=anchor)

    # ---- 形位公差框：3 格 [符号 | 数值 | 基准] ----
    def gdt_frame(self, idx, x, y, cells, sym, value, datum):
        h = 6.0
        w = sum(cells)
        self.rect(x, y, w, h, role="thin", id="gdt_frame_%s" % idx)
        cx = x
        for i, cw in enumerate(cells[:-1]):
            cx += cw
            self.line(cx, y, cx, y + h, role="thin", id="gdt_cell_%s_%d" % (idx, i))
        self.text(sym, x + cells[0] / 2.0, y + 4.4, size=3.4,
                  id="gdt_sym_%s" % idx)
        self.text(value, x + cells[0] + cells[1] / 2.0, y + 4.2, size=3.0,
                  id="gdt_value_%s" % idx)
        self.text(datum, x + cells[0] + cells[1] + cells[2] / 2.0, y + 4.4,
                  size=3.4, id="gdt_datum_%s" % idx)
        return w, h


# --------------------------------------------------------------------------- #
# 4. 渲染
# --------------------------------------------------------------------------- #

def render(params: Dict[str, Any]) -> str:
    problems = validate_params(params)
    if problems:
        raise ValueError("参数不完整/不合法：\n  " + "\n  ".join(problems))
    return _render(params)


def _render(p: Dict[str, Any]) -> str:
    g, an, tb, sh = p["geometry"], p["annotation"], p["tables"], p["sheet"]
    W, H = SHEET_SIZES[sh["size"]]
    mg = sh["margins"]
    fx0, fy0 = mg["left"], mg["top"]
    fx1, fy1 = W - mg["right"], H - mg["bottom"]
    fw, fh = fx1 - fx0, fy1 - fy0
    s = _scale_factor(sh["scale"])
    lay = sh["layout"]
    fs = sh["fonts"]

    # ---- 关键几何（图纸 mm）----
    cy = fy0 + fh / 2.0            # 算：两视图共用轴线高度 = 图框竖向中线（高平齐）
    x0 = lay["main_x0"]            # 主视图左端面（版面锚点）
    x1 = x0 + g["b"] * s           # 算：右端面 = 左端面 + 齿宽×比例
    ra = g["d_a"] / 2.0 * s        # 算：齿顶圆半径 = d_a/2 × s
    rr = g["d"] / 2.0 * s          # 算：分度圆半径
    rf = g["d_f"] / 2.0 * s        # 算：齿根圆半径
    rb = g["bore_d"] / 2.0 * s     # 算：轴孔半径
    c = g["chamfer"] * s           # 算：倒角 C1 -> 图纸 0.5
    # 端面图圆心：以版面锚点为下限，但保证与主视图至少留 10mm 空隙（大齿轮端面图更大）
    lcx = max(lay["left_cx"], x1 + 10.0 + ra)   # 算：锚点 170 vs 91.25+10+35=136.25
    struct = g["structure"]
    solid = (struct == "实心式")

    # 键槽：毂槽深 d+t2 自孔底量起 -> 槽顶 y = 孔底 y - (d+t2)×s
    kw_half = g["keyway"]["width"] / 2.0 * s
    t2s = g["keyway"]["t2"] * s                  # 键槽深（图纸长度）
    slot_top = cy + rb - (g["bore_d"] + g["keyway"]["t2"]) * s   # 算：111.25-14.15=97.10

    dwg = svgwrite.Drawing(size=("%gmm" % W, "%gmm" % H),
                           viewBox="0 0 %g %g" % (W, H))
    dwg.attribs["baseProfile"] = "full"
    P = Pen(dwg, sh)

    # ---------------- 4.1 图框 ----------------
    P.rect(fx0, fy0, fw, fh, role="thick", id="frame")

    # ---------------- 4.2 主视图（全剖）----------------
    # 齿顶线 / 齿根线：粗实线（GB/T 4459.2 剖视图中轮齿按不剖画）
    for tag, dy in (("t", -1), ("b", 1)):
        P.line(x0, cy + dy * ra, x1, cy + dy * ra, role="thick", id="M_ta_%s" % tag)
        P.line(x0, cy + dy * rf, x1, cy + dy * rf, role="thick", id="M_df_%s" % tag)
        # 分度线是点划线，两端须超出轮齿轮廓 2~3mm（取 2.5）
        P.line(x0 - 2.5, cy + dy * rr, x1 + 2.5, cy + dy * rr,
               role="center", id="M_d_%s" % tag)

    # 轴孔壁（粗实线）
    P.line(x0, cy - rb, x1, cy - rb, role="thick", id="M_bore_t")
    P.line(x0, cy + rb, x1, cy + rb, role="thick", id="M_bore_b")
    # 键槽在主剖视图中的轮廓：剖切平面过键槽中线，故槽底(d/2+t2)是材料边界，
    # 槽底线与孔壁线之间用两条短竖线在两端封住（键槽两侧在端面处是实体）
    P.line(x0, cy - rb - t2s, x1, cy - rb - t2s, role="thick", id="M_kw_bot")
    P.line(x0, cy - rb - t2s, x0, cy - rb, role="thick", id="M_kw_end_l")
    P.line(x1, cy - rb - t2s, x1, cy - rb, role="thick", id="M_kw_end_r")

    hatch_rects: List[Tuple[float, float, float, float]] = []

    if solid:
        # 端面竖线：从齿顶倒角末端直落孔口倒角起点
        for xf, sgn in ((x0, 1), (x1, -1)):
            # 上半：端面线止于键槽槽底（槽以上是实体，槽以下到孔壁由 M_kw_end_* 补齐）
            P.line(xf, cy - ra + c, xf, cy - rb - t2s, role="thick", id="M_face_%s_t" % ("l" if xf == x0 else "r"))
            P.line(xf, cy + rb + c, xf, cy + ra - c, role="thick", id="M_face_%s_b" % ("l" if xf == x0 else "r"))
            # 倒角 C1×45°：外圆口 + 孔口
            P.line(xf, cy - ra + c, xf + sgn * c, cy - ra, role="thick", id="M_ch_ta_%s" % ("l" if xf == x0 else "r"))
            P.line(xf, cy + ra - c, xf + sgn * c, cy + ra, role="thick", id="M_ch_ba_%s" % ("l" if xf == x0 else "r"))
            # 上孔口倒角被键槽切开（槽宽 8 跨过 12 点位置），不再画；下孔口倒角保留
            P.line(xf, cy + rb + c, xf + sgn * c, cy + rb, role="thick", id="M_ch_bb_%s" % ("l" if xf == x0 else "r"))
        # 剖面线区域：齿根圆与轴孔之间（齿区不剖）。
        # 上半区止于键槽槽底：剖切平面过轴线也过键槽中线，槽底才是材料边界
        hatch_rects = [(x0, cy - rf, x1 - x0, rf - rb - t2s),
                       (x0, cy + rb, x1 - x0, rf - rb)]
    else:
        # ---- 腹板式：轮缘 + 腹板 + 轮毂 ----
        hub = g["hub"] or {}
        web = g["web"] or {}
        r_hub = hub.get("d", 0) / 2.0 * s
        r_rim = web.get("rim_inner_d", 0) / 2.0 * s
        t_web = web.get("thickness", 0) * s
        xc = (x0 + x1) / 2.0
        xw0, xw1 = xc - t_web / 2.0, xc + t_web / 2.0
        hl = hub.get("length", g["b"]) * s
        xh0, xh1 = xc - hl / 2.0, xc + hl / 2.0
        for tag, dy in (("t", -1), ("b", 1)):
            P.line(x0, cy + dy * r_rim, x1, cy + dy * r_rim, role="thick", id="M_rim_%s" % tag)
            P.line(xh0, cy + dy * r_hub, xh1, cy + dy * r_hub, role="thick", id="M_hub_%s" % tag)
            P.line(xw0, cy + dy * r_hub, xw0, cy + dy * r_rim, role="thick", id="M_web_%s_l" % tag)
            P.line(xw1, cy + dy * r_hub, xw1, cy + dy * r_rim, role="thick", id="M_web_%s_r" % tag)
        for xf, sgn in ((x0, 1), (x1, -1)):
            P.line(xf, cy - ra + c, xf, cy - r_rim, role="thick", id="M_face_%s_t" % ("l" if xf == x0 else "r"))
            P.line(xf, cy + r_rim, xf, cy + ra - c, role="thick", id="M_face_%s_b" % ("l" if xf == x0 else "r"))
            P.line(xf, cy - ra + c, xf + sgn * c, cy - ra, role="thick", id="M_ch_ta_%s" % ("l" if xf == x0 else "r"))
            P.line(xf, cy + ra - c, xf + sgn * c, cy + ra, role="thick", id="M_ch_ba_%s" % ("l" if xf == x0 else "r"))
        for xf, sgn in ((xh0, 1), (xh1, -1)):
            P.line(xf, cy - r_hub, xf, cy - rb, role="thick", id="M_hubface_%s_t" % ("l" if xf == xh0 else "r"))
            P.line(xf, cy + rb, xf, cy + r_hub, role="thick", id="M_hubface_%s_b" % ("l" if xf == xh0 else "r"))
        hatch_rects = [(x0, cy - rf, x1 - x0, rf - r_rim),
                       (x0, cy + r_rim, x1 - x0, rf - r_rim),
                       (xw0, cy - r_rim, xw1 - xw0, r_rim - r_hub),
                       (xw0, cy + r_hub, xw1 - xw0, r_rim - r_hub),
                       (xh0, cy - r_hub, xh1 - xh0, r_hub - rb),
                       (xh0, cy + rb, xh1 - xh0, r_hub - rb)]

    # 剖面线：按剖切区逐条生成 45° 线，再用 clipPath 兜底裁在轮体内
    P.hatch(hatch_rects)

    # 主视图轴线（细点画线，两端超出轮廓 6mm）
    P.line(x0 - 6.0, cy, x1 + 6.0, cy, role="center", id="M_axis")

    # ---------------- 4.3 左视图（端面图）----------------
    P.circle(lcx, cy, ra, role="thick", id="L_circle_ta")       # 齿顶圆 粗实线
    P.circle(lcx, cy, rf, role="thin", id="L_circle_df")        # 齿根圆 细实线
    P.circle(lcx, cy, rr, role="center", id="L_circle_d")       # 分度圆 细点画线
    # 轴孔：槽口处孔的轮廓必须中断（GB 键槽画法），故画大弧而不是整圆
    dy_kw = math.sqrt(max(rb * rb - kw_half * kw_half, 0.0))    # 算：√(r_bore²-(b_k/2)²)=5.92<6.25
    P.path("M %.4f %.4f A %.5f %.5f 0 1 0 %.4f %.4f"
           % (lcx - kw_half, cy - dy_kw, rb, rb, lcx + kw_half, cy - dy_kw),
           role="thick", id="L_circle_bore")
    if not solid:
        hub = g["hub"] or {}
        web = g["web"] or {}
        r_hub = hub.get("d", 0) / 2.0 * s
        r_rim = web.get("rim_inner_d", 0) / 2.0 * s
        P.circle(lcx, cy, r_hub, role="thick", id="L_circle_hub")
        P.circle(lcx, cy, r_rim, role="thin", id="L_circle_rim")
        n = int(web.get("hole_count", 0) or 0)
        rh = web.get("hole_d", 0) / 2.0 * s
        rp = web.get("hole_pcd", 0) / 2.0 * s
        for i in range(n):                       # 腹板孔均布
            a = 2 * math.pi * i / max(n, 1)
            P.circle(lcx + rp * math.cos(a), cy + rp * math.sin(a), rh,
                     role="thick", id="L_hole_%d" % i)

    # 键槽：与孔连通的矩形缺口（宽 8、槽顶 97.10）
    P.line(lcx - kw_half, cy - dy_kw, lcx - kw_half, slot_top, role="thick", id="L_kw_l")
    P.line(lcx + kw_half, cy - dy_kw, lcx + kw_half, slot_top, role="thick", id="L_kw_r")
    P.line(lcx - kw_half, slot_top, lcx + kw_half, slot_top, role="thick", id="L_kw_top")

    # 中心线：细点画线，超出轮廓 4mm
    P.line(lcx - ra - 4.0, cy, lcx + ra + 4.0, cy, role="center", id="L_axis_h")
    P.line(lcx, cy - ra - 4.0, lcx, cy + ra + 4.0, role="center", id="L_axis_v")

    # ---------------- 4.4 尺寸标注 ----------------
    dv = an["dims"]

    # (1) 齿宽 b：主视图下方，尺寸线在齿顶线外 6mm
    dy_b = cy + ra + 6.0                        # 算：齿顶线 + 6
    P.line(x0, cy + ra, x0, dy_b + 3.0, role="dim", id="dim_ext_b_1", cls="dimext")
    P.line(x1, cy + ra, x1, dy_b + 3.0, role="dim", id="dim_ext_b_2", cls="dimext")
    tol = dv["b"].get("tol")
    P.dim_linear("b", (x0, dy_b), (x1, dy_b), True,
                 _fmt(g["b"]) + (tol or ""), size=fs["dim"])

    # (2) 齿顶圆/分度圆/齿根圆直径：标在主视图（全剖）右侧。
    #     GB/T 4458.4：盘套类零件的径向尺寸注在剖视图上，端面图只注键槽与轴孔。
    #     三条竖向尺寸线依次外移 8mm，各自上下两条尺寸界线引自对应的水平线。
    for i, (key, r) in enumerate((("d_a", ra), ("d", rr), ("d_f", rf))):
        # 算：右端面 +11.25 +9i —— 起点避开轴线超出量(2.5)与数字宽度，文字不压点画线
        xd = x1 + 11.25 + 9.0 * i
        for k, sgn in ((1, -1), (2, 1)):
            P.line(x1, cy + sgn * r, xd + 2.0, cy + sgn * r, role="dim",
                   id="dim_ext_%s_%d" % (key, k), cls="dimext")
        if dv[key].get("reference"):
            label = "(φ%s)" % _fmt(g[key])       # 参考尺寸加括号，不注公差
        else:
            label = "φ%s%s" % (_fmt(g[key]), dv[key].get("tol") or "")
        P.dim_linear(key, (xd, cy - r), (xd, cy + r), False, label, size=fs["dim"])

    # (3) 键槽宽 8JS9：槽口上方水平尺寸线。
    #     原来沿竖直中心线引出的做法与中心线重合（违反"尺寸线不得用中心线代替"），
    #     改为两条尺寸界线 + 水平尺寸线，箭头外置（8mm×0.5=4mm 塞不进两个箭头）。
    wy = slot_top - 6.0
    P.line(lcx - kw_half, slot_top, lcx - kw_half, wy - 1.2, role="thin",
           id="dim_ext_keyway_width_1")
    P.line(lcx + kw_half, slot_top, lcx + kw_half, wy - 1.2, role="thin",
           id="dim_ext_keyway_width_2")
    P.line(lcx - kw_half, wy, lcx + kw_half, wy, role="dim",
           id="dimline_keyway_width", cls="dimline")
    P.arrow((lcx - kw_half, wy), 0.0, id="arrow_keyway_width_1")     # 尖在左端、尾在左外
    P.arrow((lcx + kw_half, wy), 180.0, id="arrow_keyway_width_2")   # 尖在右端、尾在右外
    # 文字放尺寸线右端外侧：竖直中心线正好穿过槽口中线，居中对齐必被点画线劈开
    P.text("%s %s" % (_fmt(g["keyway"]["width"]), dv["keyway_width"].get("tol") or ""),
           lcx + kw_half + 1.5, wy - 2.4, size=fs["dim"],
           id="dimtext_keyway_width", anchor="start")

    # (4) 毂槽深 d+t2：引线式。
    #     竖直线性尺寸跨过端面图水平中心线，数字必被点画线劈开（28.3 字长 7.7mm
    #     > 槽顶到中心线的 7.9mm），故按 GB/T 4458.4「位置不够时引出标注」用引线。
    kd = g["bore_d"] + g["keyway"]["t2"]        # 算：25+3.3=28.3
    tipp = (lcx - kw_half, slot_top)            # 算：槽口左上角
    elb = (tipp[0] - 7.0, tipp[1] - 7.6)        # 算：沿 135° 引出
    P.line(tipp[0], tipp[1], elb[0], elb[1], role="thin", id="dim_ext_keyway_depth_1")
    P.arrow(tipp, 45.0, id="arrow_keyway_depth_1", length=2.6)   # 尾在左上、尖指向槽角
    P.text(_fmt(kd), elb[0] - 0.4, elb[1] - 1.2, size=fs["dim"],
           id="dimtext_keyway_depth", anchor="end")
    up = dv["keyway_depth"].get("tol_upper", 0.0)
    lo = dv["keyway_depth"].get("tol_lower", 0.0)
    tol_txt = "%+g / %s" % (up, _fmt(lo)) if up else ""
    if tol_txt:
        P.text(tol_txt, elb[0] - 0.4, elb[1] + 2.0, size=fs["tol"],
               id="dimtext_keyway_depth_tol", anchor="end")

    # (5) 轴孔 φ25H7：端面图径向引线 + 基准 A
    ang_bore = 136.0                                  # 孔壁取点方位（屏幕：左下方）
    ab = math.radians(ang_bore)
    bx, by = lcx + rb * math.cos(ab), cy + rb * math.sin(ab)   # 算：孔壁上一点
    L_lead = ra + 1.0                             # 算：引出线拉到齿顶圆外 1mm（半径 36）
    ex, ey = lcx + L_lead * math.cos(ab), cy + L_lead * math.sin(ab)
    P.line(bx, by, ex, ey, role="thin", id="dim_ext_bore_1")
    P.arrow((bx, by), ang_bore + 180.0, id="arrow_bore_1", length=2.6)  # 箭头指向孔壁
    P.line(ex, ey, ex - 6.1, ey, role="thin", id="dim_ext_bore_2")      # 折平 6.1mm
    P.text("φ%s%s" % (_fmt(g["bore_d"]), dv["bore"].get("tol") or ""),
           ex - 6.5, ey - 1.4, size=fs["dim"], id="dimtext_bore", anchor="end")
    # 基准符号 A：三角形跨在折平段上，字母框在其正下方
    apex_x = ex - 3.1
    tri_y = ey + 2.6
    P.path("M%.2f,%.2f L%.2f,%.2f L%.2f,%.2f Z"
           % (apex_x, ey, apex_x - 1.9, tri_y, apex_x + 1.9, tri_y),
           role="thin", id="datum_tri", fill="#000")
    P.line(apex_x, tri_y, apex_x, tri_y + 3.0, role="thin", id="datum_lead")
    P.rect(apex_x - 3.2, tri_y + 3.0, 6.4, 6.4, role="thin", id="datum_box")
    P.text("A", apex_x, tri_y + 7.6, size=3.4, id="datum_A")

    # ---------------- 4.5 表面粗糙度 ----------------
    rough = an["roughness"]
    # 齿面：主视图齿顶线上取点，法线向上
    tip_x = x0 + (x1 - x0) * 0.8
    # 齿轮的齿面粗糙度惯例注在轮齿区（引出线指齿廓），文字注明「齿面」以免被读成齿顶面
    P.ra_symbol(SURF_ID["齿面"], (tip_x, cy - ra), 270.0, "齿面 Ra %s" % _fmt(rough["齿面"], 1),
                label_dx=4.2, label_dy=-0.6)
    # 轴孔：端面图孔壁 45° 点，法线朝外（右下）
    a45 = math.radians(45.0)
    P.ra_symbol(SURF_ID["轴孔"], (lcx + rb * math.cos(a45), cy + rb * math.sin(a45)), 45.0,
                "Ra %s" % _fmt(rough["轴孔"], 1), label_dx=5.0, label_dy=0.4)
    # 端面：主视图左端面上取点（齿根与孔之间），法线朝左
    # 端面粗糙度落在左端面上；取齿根与孔壁之间的中点，实心/腹板式都落在实体上
    if g.get("web"):
        face_y = cy + (g["web"]["rim_inner_d"] / 2.0 * s + ra) / 2.0   # 腹板式：标在轮缘端面
    else:
        face_y = cy + (rf + rb) / 2.0                                  # 实心式：齿根与孔之间
    P.ra_symbol(SURF_ID["端面"], (x0, face_y), 180.0,
                "Ra %s" % _fmt(rough["端面"], 1), label_dx=-4.6, label_dy=-2.4,
                anchor="end")
    # 其余：图框右上角，不附表面
    ox = lay["other_ra_x"]
    P.text("其余", ox, 13.0, size=fs["note"] + 0.1, id="ra_other_label")
    P.path("M%.2f,16.50 L%.2f,13.60 L%.2f,19.10" % (ox + 0.5, ox + 2.2, ox + 4.4),
           role="thin", id="ra_sym_other")
    P.line(ox + 5.1, 13.10, ox + 8.1, 17.90, role="thin", id="ra_bar_other")
    P.text("Ra %s" % _fmt(rough["其余"], 1), ox + 9.2, 18.10, size=fs["small"] + 0.3,
           id="ra_text_other", anchor="start")

    # ---------------- 4.6 形位公差 ----------------
    gdt = an["gdt"]
    # 第 1 项（端面圆跳动）：主视图左侧，引线水平指向左端面
    if len(gdt) >= 1:
        gy = cy - (rf + rb) / 2.0 - 3.0
        fx = fx0 + 1.0
        w1, h1 = P.gdt_frame("1", fx, gy - 3.0, (9.0, 13.0, 8.0),
                             gdt[0]["symbol"], "%.3f" % gdt[0]["value"], gdt[0]["datum"])
        P.line(fx + w1, gy, x0, gy, role="thin", id="gdt_leader_1")
        P.arrow((x0, gy), 0.0, id="gdt_arrow_1", length=2.4)
    # 第 2 项（齿顶圆径向圆跳动）：端面图上方，引线斜指齿顶圆
    if len(gdt) >= 2:
        fw2, fh2 = 30.0, 6.0
        fx2 = lcx - 20.0
        fy2 = cy - ra - 18.0
        w2, h2 = P.gdt_frame("2", fx2, fy2, (9.0, 13.0, 8.0),
                             gdt[1]["symbol"], "%.3f" % gdt[1]["value"], gdt[1]["datum"])
        a2 = math.radians(-127.7)
        px2 = lcx + ra * math.cos(a2)
        py2 = cy + ra * math.sin(a2)            # 算：齿顶圆上 232.3° 处
        P.line(fx2 + w2, fy2 + 6.0, px2 + 9.7, py2 - 15.0, role="thin", id="gdt_leader_2a")
        P.line(px2 + 9.7, py2 - 15.0, px2, py2, role="thin", id="gdt_leader_2b")
        P.arrow((px2, py2), math.degrees(math.atan2(18.9, -9.7)), id="gdt_arrow_2", length=2.6)

    # ---------------- 4.7 视图名称 ----------------
    P.text(sh["views"]["main"], (x0 + x1) / 2.0, cy + ra + 12.0, size=fs["label"],
           id="view_title_main")
    P.text(sh["views"]["left"], lcx, cy + ra + 12.0, size=fs["label"],
           id="view_title_left")

    # ---------------- 4.8 参数表 ----------------
    tx0 = fx1 - 5.0 - 68.0
    ty0 = lay["table_y"]
    row_h = 5.4
    cols = (30.0, 14.0, 24.0)
    rows = tb["param_table"]
    th = row_h * (len(rows) + 1)
    P.rect(tx0, ty0, sum(cols), th, role="thick", id="table")
    P.line(tx0, ty0 + row_h, tx0 + sum(cols), ty0 + row_h, role="thick", id="table_headline")
    P.text("齿 轮 参 数 表", tx0 + sum(cols) / 2.0, ty0 + 3.8, size=3.2, bold=True,
           id="table_title")
    P.line(tx0 + cols[0], ty0 + row_h, tx0 + cols[0], ty0 + th, role="thick", id="table_v1")
    P.line(tx0 + cols[0] + cols[1], ty0 + row_h, tx0 + cols[0] + cols[1], ty0 + th,
           role="thick", id="table_v2")
    keymap = ["m", "z", "alpha", "x", "b", "grade"]
    for i, row in enumerate(rows):
        ry = ty0 + row_h * (i + 1)
        if i:
            P.line(tx0, ry, tx0 + sum(cols), ry, role="thick", id="table_row_%d" % i)
        k = keymap[i] if i < len(keymap) else str(i)
        P.text(row["name"], tx0 + 2.0, ry + 3.6, size=2.7, anchor="start",
               id="tbl_name_%s" % k)
        P.text(row.get("sym", ""), tx0 + cols[0] + cols[1] / 2.0, ry + 3.6, size=2.6,
               id="tbl_sym_%s" % k)
        cell = _cell(_resolve(p, row["from"]), row.get("fmt", "s"))
        P.text(cell, tx0 + cols[0] + cols[1] + 2.0, ry + 3.6, size=2.7,
               anchor="start", id="tbl_val_%s" % k)

    # ---------------- 4.9 技术要求 ----------------
    P.text("技术要求", fx0, lay["tech_y"], size=3.4, anchor="start", bold=True, id="tech_title")
    for i, line_txt in enumerate(tb["tech_req"]):
        line_txt = (line_txt.replace("{grade}", str(tb.get("grade", "")))
                           .replace("{fillet}", _fmt(g["fillet"]))
                           .replace("{fillet_hi}", _fmt(g["fillet"] + 1.0))
                           .replace("{chamfer}", _fmt(g["chamfer"])))
        P.text(line_txt, fx0, lay["tech_y"] + 6.5 + 6.0 * i, size=fs["note"],
               anchor="start", id="tr_%d" % (i + 1))

    # 第一角投影法符号：圆台两视图
    px = lay["proj_x"]
    py = lay["tech_y"] + 25.0
    P.path("M%.2f,%.2f L%.2f,%.2f L%.2f,%.2f L%.2f,%.2f Z" %
           (px, py, px + 6.0, py + 2.5, px + 6.0, py + 11.5, px, py + 14.0),
           role="thin", id="proj_cone")
    P.circle(px + 14.0, py + 7.0, 5.0, role="thin", id="proj_circle")
    P.circle(px + 14.0, py + 7.0, 2.4, role="thin", id="proj_hole")
    P.line(px + 7.0, py + 7.0, px + 21.0, py + 7.0, role="center", id="proj_axis")
    P.text("第一角投影法", px + 26.0, py + 8.2, size=fs["small"], anchor="start",
           id="proj_label")

    # ---------------- 4.10 标题栏 ----------------
    bx = lay["title_x"]
    by = fy1 - 42.0
    bw_, bh_ = fx1 - bx, 42.0
    P.rect(bx, by, bw_, bh_, role="thick", id="titleblock")
    P.line(bx, by + 16.0, bx + bw_, by + 16.0, role="thick", id="tb_h1")
    P.line(bx, by + 26.0, bx + bw_, by + 26.0, role="thick", id="tb_h2")
    P.line(bx, by + 34.0, bx + bw_, by + 34.0, role="thick", id="tb_h3")
    P.line(bx + 92.0, by, bx + 92.0, by + 16.0, role="thick", id="tb_v1")
    tb_ = tb["title_block"]
    P.text(tb_["name"], bx + 46.0, by + 10.0, size=fs["title"], bold=True, id="tb_name")
    P.text("材料", bx + 96.0, by + 6.4, size=fs["small"], anchor="start", id="tb_mat_label")
    P.text(tb_["material"], bx + 96.0, by + 13.2, size=3.0, anchor="start", id="tb_material")

    # 第二行：比例 / 图号
    c2 = (18.0, 22.0, 22.0)
    xcut = [bx + c2[0], bx + c2[0] + c2[1], bx + c2[0] + c2[1] + c2[2]]
    P.line(xcut[0], by + 16.0, xcut[0], by + 26.0, role="thick", id="tb_v2")
    P.line(xcut[1], by + 16.0, xcut[1], by + 26.0, role="thick", id="tb_v3")
    P.line(xcut[2], by + 16.0, xcut[2], by + 26.0, role="thick", id="tb_v4")
    P.text("比例", bx + c2[0] / 2.0, by + 22.6, size=fs["small"], id="tb_scale_label")
    P.text(sh["scale"], xcut[0] + c2[1] / 2.0, by + 22.6, size=3.0, id="tb_scale")
    P.text("图号", xcut[1] + c2[2] / 2.0, by + 22.6, size=fs["small"], id="tb_no_label")
    P.text(tb_["drawing_no"], xcut[2] + 2.0, by + 22.6, size=2.8, anchor="start",
           id="tb_no")

    # 第三行：设计 / 日期 / 张次
    x3a, x3b, x3c = bx + 18.0, bx + 62.0, bx + 130.0
    P.line(x3a, by + 26.0, x3a, by + 34.0, role="thick", id="tb_v5")
    P.line(x3b, by + 26.0, x3b, by + 34.0, role="thick", id="tb_v6")
    P.line(x3c, by + 26.0, x3c, by + 34.0, role="thick", id="tb_v7")
    P.text("设计", bx + 9.0, by + 32.0, size=fs["small"], id="tb_design_label")
    P.text(tb_["designer"], bx + 20.0, by + 32.0, size=2.8, anchor="start", id="tb_designer")
    P.text(tb_["date"], bx + 44.0, by + 32.0, size=fs["small"], anchor="start", id="tb_date")
    P.text(tb_["sheet"], bx + 96.0, by + 32.0, size=2.8, anchor="start", id="tb_sheet")
    P.text(tb_["sheet_no"], bx + 136.0, by + 32.0, size=2.8, anchor="start", id="tb_sheet_no")
    P.text(tb_["org"], bx + bw_ / 2.0 + 12.0, by + bh_ - 2.5, size=fs["label"],
           id="tb_org")

    return dwg.tostring()


# --------------------------------------------------------------------------- #
# 5. 校验
# --------------------------------------------------------------------------- #

_NS = "{http://www.w3.org/2000/svg}"


def _tag(el) -> str:
    return el.tag.split("}")[-1]


def _f(el, key, default=None):
    v = el.get(key)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


class Parsed:
    """把 SVG 拆成可查询的图元表。"""

    def __init__(self, svg: str):
        self.root = ET.fromstring(svg.encode("utf-8"))
        self.lines: List[Dict[str, Any]] = []
        self.circles: List[Dict[str, Any]] = []
        self.rects: List[Dict[str, Any]] = []
        self.paths: List[Dict[str, Any]] = []
        self.texts: List[Dict[str, Any]] = []
        self.ids: Dict[str, Dict[str, Any]] = {}
        self.width = _f(self.root, "width", 0.0)
        vb = self.root.get("viewBox", "0 0 297 210").replace(",", " ").split()
        self.vb = [float(x) for x in vb]
        self._walk(self.root)

    @staticmethod
    def _style(el) -> Dict[str, Any]:
        return {
            "id": el.get("id"),
            "cls": el.get("class"),
            "sw": _f(el, "stroke-width", 0.0),
            "dash": el.get("stroke-dasharray"),
            "fill": el.get("fill"),
            "transform": el.get("transform"),
            "clip": el.get("clip-path"),
        }

    def _walk(self, el, ptf=None) -> None:
        for ch in list(el):
            t = _tag(ch)
            if t == "g":
                tf = ptf
                tr = ch.get("transform") or ""
                m = re.match(r"rotate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)", tr)
                if m:
                    tf = (float(m.group(2)), float(m.group(3)))
                self._walk(ch, tf)
                continue
            if t == "line":
                rec = self._style(ch)
                rec.update(x1=_f(ch, "x1", 0), y1=_f(ch, "y1", 0),
                           x2=_f(ch, "x2", 0), y2=_f(ch, "y2", 0))
                self.lines.append(rec)
                if rec["id"]:
                    self.ids[rec["id"]] = rec
            elif t == "circle":
                rec = self._style(ch)
                rec.update(cx=_f(ch, "cx", 0), cy=_f(ch, "cy", 0), r=_f(ch, "r", 0))
                self.circles.append(rec)
                if rec["id"]:
                    self.ids[rec["id"]] = rec
            elif t == "rect":
                rec = self._style(ch)
                rec.update(x=_f(ch, "x", 0), y=_f(ch, "y", 0),
                           w=_f(ch, "width", 0), h=_f(ch, "height", 0))
                self.rects.append(rec)
                if rec["id"]:
                    self.ids[rec["id"]] = rec
            elif t == "path":
                rec = self._style(ch)
                rec.update(d=ch.get("d", ""), clip=ch.get("clip-path"))
                self.paths.append(rec)
                if rec["id"]:
                    self.ids[rec["id"]] = rec
            elif t == "text":
                txt = "".join(ch.itertext())
                rec = self._style(ch)
                rec.update(x=_f(ch, "x", 0), y=_f(ch, "y", 0),
                           size=_f(ch, "font-size", 0), text=txt,
                           anchor=ch.get("text-anchor", "start"), ptf=ptf)
                self.texts.append(rec)
                if rec["id"]:
                    self.ids[rec["id"]] = rec
            else:
                self._walk(ch)

    # ---- 查询 ----
    def get(self, el_id: str) -> Optional[Dict[str, Any]]:
        return self.ids.get(el_id)

    def text_of(self, el_id: str) -> Optional[str]:
        rec = self.get(el_id)
        return rec["text"] if rec else None

    def by_prefix(self, prefix: str) -> List[Dict[str, Any]]:
        return [r for k, r in self.ids.items() if k.startswith(prefix)]

    def first_num(self, el_id: str) -> Optional[float]:
        t = self.text_of(el_id)
        if t is None:
            return None
        m = re.search(r"-?\d+(?:\.\d+)?", t.replace("φ", " "))
        return float(m.group(0)) if m else None

    def bbox(self, prefix: str) -> Optional[Tuple[float, float, float, float]]:
        xs, ys = [], []
        for r in self.by_prefix(prefix):
            if "x1" in r:
                xs += [r["x1"], r["x2"]]
                ys += [r["y1"], r["y2"]]
            elif "cx" in r:
                xs += [r["cx"] - r["r"], r["cx"] + r["r"]]
                ys += [r["cy"] - r["r"], r["cy"] + r["r"]]
            elif "x" in r:
                xs += [r["x"], r["x"] + r["w"]]
                ys += [r["y"], r["y"] + r["h"]]
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)


def _rect_hit(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _seg_point_dist(p, s) -> float:
    """点 p 到线段 s=(x1,y1,x2,y2) 的距离。"""
    px, py = p
    x1, y1, x2, y2 = s
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _text_bbox(t: Dict[str, Any], default_size: float = 3.5):
    """估算文字外接框（无字体度量时按 CJK 1.0×字高、西文 0.55×字高计宽）。"""
    txt = (t.get("text") or "").strip()
    if not txt:
        return None
    size = t.get("size") or default_size
    w = sum(size * (1.0 if ord(ch) > 0x2E80 else 0.55) for ch in txt)
    h = size
    x = t["x"]
    if t.get("anchor") == "middle":
        x -= w / 2.0
    elif t.get("anchor") == "end":
        x -= w
    box = (x, t["y"] - size * 0.78, x + w, t["y"] + size * 0.22)
    ptf = t.get("ptf")
    if ptf:                                   # 父级 rotate(-90 cx cy)：(x,y)->(cx+dy, cy-dx)
        cx, cy = ptf
        pts = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
        rp = [(cx + (y - cy), cy - (x - cx)) for (x, y) in pts]
        xs = [q[0] for q in rp]
        ys = [q[1] for q in rp]
        box = (min(xs), min(ys), max(xs), max(ys))
    return box


def _seg_rect_hit(s, b, pad: float = 0.0) -> bool:
    """线段是否穿过（或触碰）矩形 b。"""
    x1, y1, x2, y2 = s
    bx0, by0, bx1, by1 = b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad
    if max(x1, x2) < bx0 or min(x1, x2) > bx1 or max(y1, y2) < by0 or min(y1, y2) > by1:
        return False
    if bx0 <= x1 <= bx1 and by0 <= y1 <= by1:
        return True
    if bx0 <= x2 <= bx1 and by0 <= y2 <= by1:
        return True
    edges = [((bx0, by0), (bx1, by0)), ((bx1, by0), (bx1, by1)),
             ((bx1, by1), (bx0, by1)), ((bx0, by1), (bx0, by0))]

    def cross(o, a, c):
        return (a[0] - o[0]) * (c[1] - o[1]) - (a[1] - o[1]) * (c[0] - o[0])

    for (p1, p2) in edges:
        d1 = cross((x1, y1), (x2, y2), p1)
        d2 = cross((x1, y1), (x2, y2), p2)
        d3 = cross(p1, p2, (x1, y1))
        d4 = cross(p1, p2, (x2, y2))
        if d1 * d2 < 0 and d3 * d4 < 0:
            return True
    return False


def _circle_cross(b, cx: float, cy: float, r: float, pad: float = 0.05) -> bool:
    """圆是否与矩形相交（圆心在框内时用角点最大距离）。"""
    corners = [(b[0], b[1]), (b[2], b[1]), (b[0], b[3]), (b[2], b[3])]
    dmin = min(math.hypot(max(b[0], min(cx, b[2])) - cx, max(b[1], min(cy, b[3])) - cy),
               math.hypot(cx - min(max(cx, b[0]), b[2]), cy - min(max(cy, b[1]), b[3])))
    if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
        dmin = 0.0
    dmax = max(math.hypot(px - cx, py - cy) for (px, py) in corners)
    return dmin - pad <= r <= dmax + pad


def _audit_texts(P: "Parsed", ids: List[str], lw_thick: float) -> List[str]:
    """检查指定文字：是否被图线/圆穿过、是否互相重叠、是否越出图框。"""
    out: List[str] = []
    segs = [(l["x1"], l["y1"], l["x2"], l["y2"]) for l in P.lines]
    boxes = []
    for eid in ids:
        t = P.get(eid)
        b = _text_bbox(t) if t else None
        if not b:
            continue
        boxes.append((eid, b, t))
        for s in segs:
            if _seg_rect_hit(s, b, 0.1):
                out.append("%s 文字被图线穿过（框 %.1f,%.1f~%.1f,%.1f）"
                           % (eid, b[0], b[1], b[2], b[3]))
                break
        for c in P.circles:
            if _circle_cross(b, c["cx"], c["cy"], c["r"]):
                out.append("%s 文字压住 r=%g 的圆线" % (eid, c["r"]))
                break
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _rect_hit(boxes[i][1], boxes[j][1]):
                out.append("%s 与 %s 文字重叠" % (boxes[i][0], boxes[j][0]))
    return out


def check(svg: str, params: Dict[str, Any]) -> List[str]:
    """逐项校验渲染结果，返回问题清单（空列表 = 全部通过）。

    每条问题写成「[项号 项名] 具体错在哪（实测值 vs 期望值）」。
    """
    issues: List[str] = []

    def bad(item: int, msg: str) -> None:
        issues.append("[%d %s] %s" % (item, CHECK_ITEMS[item - 1], msg))

    try:
        P = Parsed(svg)
    except ET.ParseError as exc:
        bad(1, "SVG 无法解析：%s" % exc)
        return issues

    g, an, tb, sh = params["geometry"], params["annotation"], params["tables"], params["sheet"]
    s = _scale_factor(sh["scale"])
    der = derive(params)
    fs = sh["fonts"]
    lw = sh["line_widths"]
    W, H = SHEET_SIZES[sh["size"]]
    mg = sh["margins"]
    fx0, fy0, fx1, fy1 = mg["left"], mg["top"], W - mg["right"], H - mg["bottom"]

    ra, rr, rf, rb = g["d_a"] / 2 * s, g["d"] / 2 * s, g["d_f"] / 2 * s, g["bore_d"] / 2 * s
    ax0 = P.get("M_axis")
    cy = ax0["y1"] if ax0 else 0.0
    c_ta = P.get("L_circle_ta")
    lcx = c_ta["cx"] if c_ta else sh["layout"]["left_cx"]   # 端面图圆心取渲染结果，不信任参数
    slot_top = cy + rb - (g["bore_d"] + g["keyway"]["t2"]) * s   # 算：槽顶 = 孔底 - (d+t2)×s

    # ---------- 项 1：第一角画法 ----------
    bb_m = P.bbox("M_")
    bb_l = P.bbox("L_")
    if bb_m is None or bb_l is None:
        bad(1, "找不到主视图/端面图的图元（id 前缀 M_ / L_）")
    else:
        if not bb_l[0] > bb_m[2]:
            bad(1, "左视图未落在主视图右侧（第一角：左视图在右），"
                   "主视图 x≤%.2f，左视图 x≥%.2f" % (bb_m[2], bb_l[0]))
        if bb_l[0] - bb_m[2] < 8.0:
            bad(1, "两视图间距 %.2f mm < 8 mm，版面过挤" % (bb_l[0] - bb_m[2]))
        ax = P.get("M_axis")
        cy_m = ax["y1"] if ax else None
        cy_l = (bb_l[1] + bb_l[3]) / 2.0
        if cy_m is None:
            bad(1, "主视图缺轴线（M_axis）")
        elif abs(cy_m - cy_l) > 0.5:
            bad(1, "两视图未「高平齐」：主视图轴线 y=%.2f，端面图中心 y=%.2f" % (cy_m, cy_l))
    if not (P.text_of("proj_label") or "").strip() and "第一角" not in svg:
        bad(1, "缺第一角投影法符号/标注")
    if not P.get("proj_cone") or not P.get("proj_circle"):
        bad(1, "投影法符号图形不全（圆锥台 + 圆两个视图）")
    if P.text_of("view_title_main") is None or P.text_of("view_title_left") is None:
        bad(1, "缺视图名称")
    for lid, part in (("L_axis_h", "水平"), ("L_axis_v", "竖直")):
        rec = P.get(lid)
        if rec is None:
            bad(1, "端面图缺%s中心线" % part)
        else:
            ext = (abs(rec["x1"] - rec["x2"]) / 2.0 - ra) if part == "水平" else \
                  (abs(rec["y1"] - rec["y2"]) / 2.0 - ra)
            if not (3.0 <= ext <= 5.0):
                bad(1, "端面图%s中心线超出轮廓 %.2f mm，应为 3~5 mm" % (part, ext))

    # ---------- 项 2：三线画法 ----------
    expect_circle = [("L_circle_ta", ra, "thick", "齿顶圆"),
                     ("L_circle_d", rr, "center", "分度圆"),
                     ("L_circle_df", rf, "thin", "齿根圆")]
    for cid, exp_r, role, name in expect_circle:
        rec = P.get(cid)
        if rec is None:
            bad(2, "端面图缺%s（%s）" % (name, cid))
            continue
        if abs(rec["r"] - exp_r) > 0.05:
            bad(2, "端面图%s半径 %.3f ≠ 期望 %.3f（%s 由参数算出）"
                   % (name, rec["r"], exp_r, _fmt(exp_r / s * 2)))
        want_sw = lw.get(role, lw["thin"])
        if abs(rec["sw"] - want_sw) > 1e-6:
            bad(2, "%s线宽 %.2f ≠ GB/T 4457.4 规定的 %.2f" % (name, rec["sw"], want_sw))
        if role == "center" and not rec["dash"]:
            bad(2, "分度圆应为细点画线，实测无 dasharray")
        if role != "center" and rec["dash"]:
            bad(2, "%s不应为虚线" % name)
    # 主视图三线（GB/T 4459.2：齿顶线/齿根线粗实线，分度线细点画线）
    for lid, role, exp_y, name in (("M_ta_t", "thick", -ra, "齿顶线"),
                                   ("M_df_t", "thick", -rf, "齿根线"),
                                   ("M_d_t", "center", -rr, "分度线")):
        rec = P.get(lid)
        ax = P.get("M_axis")
        if rec is None or ax is None:
            bad(2, "主视图缺%s（%s）" % (name, lid))
            continue
        if abs((rec["y1"] - ax["y1"]) - exp_y) > 0.05:
            bad(2, "主视图%s位置偏差：y-轴线=%.3f，应为 %.3f" % (name, rec["y1"] - ax["y1"], exp_y))
        want = lw.get(role, lw["thin"])
        if abs(rec["sw"] - want) > 1e-6:
            bad(2, "主视图%s线宽 %.2f ≠ %.2f" % (name, rec["sw"], want))
        if role == "center" and not rec["dash"]:
            bad(2, "主视图分度线应为细点画线")
    mt = P.get("M_ta_t")          # 轮齿轮廓 x 范围以齿顶线为准
    xo0, xo1 = (min(mt["x1"], mt["x2"]), max(mt["x1"], mt["x2"])) if mt else (0.0, 0.0)
    for lid, name, lo, hi in (("M_d_t", "分度线", 2.0, 3.2), ("M_axis", "轴线", 2.0, 12.0)):
        rec = P.get(lid)
        if rec is None or not mt:
            continue
        ov = (xo0 - min(rec["x1"], rec["x2"]), max(rec["x1"], rec["x2"]) - xo1)
        if not (lo <= ov[0] <= hi and lo <= ov[1] <= hi):
            bad(2, "%s应超出轮齿轮廓 2~3mm，实际左 %.2f / 右 %.2f mm" % (name, ov[0], ov[1]))
    # 剖面线：45°、等间距、只落在剖切区（齿区与孔内留白）
    hat = [l for k, l in P.ids.items() if k.startswith("M_hatch_")]
    if len(hat) < 8:
        bad(2, "剖面线不足（检出 %d 条，应 ≥8）" % len(hat))
    else:
        angles_ok = True
        for l in hat:
            dx, dy = l["x2"] - l["x1"], l["y2"] - l["y1"]
            if abs(dx) < 1e-6 or abs(abs(dy / dx) - 1.0) > 0.02:
                bad(2, "剖面线非 45°（%s：dx=%.2f dy=%.2f）" % (l["id"], dx, dy))
                angles_ok = False
                break
        if angles_ok:
            cs = sorted(set(round(l["x1"] + l["y1"], 3) for l in hat))
            want = sh["hatch"]["spacing"] * math.sqrt(2.0)
            if len(cs) > 1:
                worst = max(abs(cs[i + 1] - cs[i] - want) for i in range(len(cs) - 1))
                if worst > 0.06:
                    bad(2, "剖面线间距不均匀：最大偏差 %.3f mm（应等间距 %.2f mm）"
                           % (worst, sh["hatch"]["spacing"]))
            for l in hat:
                for py in (l["y1"], l["y2"]):
                    if abs(py - cy) > rf + 0.05:
                        bad(2, "剖面线画到齿根线以外（y=%.2f，齿根线 cy±%.2f）——齿区应留白不剖"
                               % (py, rf))
                    elif abs(py - cy) < rb - 0.05:
                        bad(2, "剖面线伸进轴孔（y=%.2f，孔壁 cy±%.2f）" % (py, rb))
    if "clip_hatch" not in svg:
        bad(2, "剖面线未用 clipPath 裁在轮体内，可能越出端面")
    # 键槽在主剖视图中的轮廓：槽底线 + 两端短竖线（剖切平面过键槽中线，槽底是材料边界）
    kb, kl, kr = P.get("M_kw_bot"), P.get("M_kw_end_l"), P.get("M_kw_end_r")
    t2s = g["keyway"]["t2"] * s
    if kb is None or kl is None or kr is None:
        bad(2, "主视图缺键槽剖面轮廓（槽底线 M_kw_bot / 端部竖线 M_kw_end_l,r）")
    else:
        want_y = cy - rb - t2s
        if abs(kb["y1"] - want_y) > 0.05:
            bad(2, "键槽槽底线 y=%.2f，应为 cy-(d/2+t2)=%.2f" % (kb["y1"], want_y))
        mtx = P.get("M_ta_t")
        if mtx:
            xa_, xb_ = min(mtx["x1"], mtx["x2"]), max(mtx["x1"], mtx["x2"])
            for rec, name, xx in ((kl, "左", xa_), (kr, "右", xb_)):
                if abs(rec["x1"] - xx) > 0.05:
                    bad(2, "键槽端部竖线不在端面上（%s端 x=%.2f，端面 %.2f）" % (name, rec["x1"], xx))
                if abs(abs(rec["y2"] - rec["y1"]) - t2s) > 0.05:
                    bad(2, "键槽端部竖线长 %.2f ≠ 槽深 %.2f" % (abs(rec["y2"] - rec["y1"]), t2s))

    # ---------- 项 3：尺寸标注 ----------
    dim_expected = {
        "d_a": ("diameter", g["d_a"]),
        "d": ("diameter_ref", g["d"]),
        "d_f": ("diameter_ref", g["d_f"]),
        "b": ("length", g["b"]),
        "bore": ("diameter", g["bore_d"]),
        "keyway_width": ("length", g["keyway"]["width"]),
        "keyway_depth": ("length", der["keyway_depth"]),
    }
    spans: List[Tuple[str, str, float, float]] = []
    for key in dim_expected:
        if P.get("dimtext_%s" % key) is None:
            bad(3, "缺尺寸标注 %s（%s）" % (key, DIM_KEYS[key][0]))
        if P.get("dimline_%s" % key) is None and P.get("dim_ext_%s_1" % key) is None:
            bad(3, "尺寸 %s 无尺寸线/尺寸界线" % key)
        # 箭头：引线式尺寸 1 个，线性尺寸 2 个
        n_arrow = 1 if key in LEADER_DIMS else 2
        for i in range(1, n_arrow + 1):
            if P.get("arrow_%s_%d" % (key, i)) is None:
                bad(3, "尺寸 %s 缺第 %d 个箭头" % (key, i))
        if key in LEADER_DIMS:
            a = P.get("arrow_%s_1" % key)
            if a is not None:
                m = re.match(r"M\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)", a["d"])
                if m:
                    tx, ty = float(m.group(1)), float(m.group(2))
                    if key in ("d_a", "d", "d_f"):
                        want_r = {"d_a": ra, "d": rr, "d_f": rf}[key]
                        got_r = math.hypot(tx - lcx, ty - cy)
                        if abs(got_r - want_r) > 0.15:
                            bad(3, "尺寸 %s 引线箭头未落在圆上（r=%.2f，应为 %.2f）"
                                   % (key, got_r, want_r))
                    elif key == "bore":
                        got_r = math.hypot(tx - lcx, ty - cy)
                        if abs(got_r - rb) > 0.15:
                            bad(3, "轴孔尺寸引线未指向孔壁（r=%.2f，应为 %.2f）" % (got_r, rb))
                    elif key == "keyway_depth":
                        if abs(ty - slot_top) > 0.6:
                            bad(3, "键槽深引线箭头未指向槽顶边（y=%.2f，应为 %.2f）"
                                   % (ty, slot_top))
        dl = P.get("dimline_%s" % key)
        if dl is not None:
            horiz = abs(dl["y1"] - dl["y2"]) < 0.01
            for i, (ex, ey, ang) in enumerate((
                    (dl["x1"], dl["y1"], 180.0 if horiz else 270.0),
                    (dl["x2"], dl["y2"], 0.0 if horiz else 90.0)), start=1):
                a = P.get("arrow_%s_%d" % (key, i))
                if a is None:
                    continue
                m = re.match(r"M\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)", a["d"])
                if not m:
                    bad(3, "尺寸 %s 箭头路径无法解析" % key)
                    continue
                tx, ty = float(m.group(1)), float(m.group(2))
                # 箭头尖必须落在尺寸线端点（窄尺寸允许箭头外置，方向不另判）
                if math.hypot(tx - ex, ty - ey) > 0.2:
                    bad(3, "尺寸 %s 箭头尖 (%.2f,%.2f) 不在尺寸线端点 (%.2f,%.2f)"
                           % (key, tx, ty, ex, ey))
                pts = [tuple(map(float, p.split(","))) for p in re.findall(r"[-\d.]+,[-\d.]+", a["d"])]
                if len(pts) == 3:
                    alen = math.hypot(pts[0][0] - (pts[1][0] + pts[2][0]) / 2,
                                      pts[0][1] - (pts[1][1] + pts[2][1]) / 2)
                    awid = math.hypot(pts[1][0] - pts[2][0], pts[1][1] - pts[2][1])
                    if not (2.5 <= alen <= 4.5):
                        bad(3, "尺寸 %s 箭头长 %.2f mm，超出规范 2.5~4.5" % (key, alen))
                    elif not (0.2 <= awid / alen <= 0.45):
                        bad(3, "尺寸 %s 箭头宽/长 = %.2f，超出 0.2~0.45" % (key, awid / alen))
    # 三个直径必须注在主视图上（GB/T 4458.4：径向尺寸注在剖视图上）
    mt3 = P.get("M_ta_t")
    if mt3 is not None:
        xr_ = max(mt3["x1"], mt3["x2"])
        for key in ("d_a", "d", "d_f"):
            dl = P.get("dimline_%s" % key)
            if dl is None:
                bad(3, "直径 %s 缺尺寸线（应标在主视图上）" % key)
            elif abs(dl["x1"] - dl["x2"]) > 0.01:
                bad(3, "直径 %s 尺寸线应竖直（x1=%.2f x2=%.2f）" % (key, dl["x1"], dl["x2"]))
            elif dl["x1"] <= xr_:
                bad(3, "直径 %s 未标在主视图外侧（x=%.2f ≤ 主视图右端 %.2f）" % (key, dl["x1"], xr_))
    # 尺寸线集合：按 class 通用统计（不限于已知键，注入多余尺寸线也会被查出来）
    spans = []
    for l in P.lines:
        if l.get("cls") != "dimline":
            continue
        h = abs(l["y1"] - l["y2"]) < 0.01
        a_, b_ = (min(l["x1"], l["x2"]), max(l["x1"], l["x2"])) if h else \
                 (min(l["y1"], l["y2"]), max(l["y1"], l["y2"]))
        if b_ - a_ > 0.05:
            spans.append((l["id"].replace("dimline_", ""), "h" if h else "v", a_, b_))
    # 重复
    seen = {}
    for key, orient, a, b in spans:
        sig = (orient, round(a, 1), round(b, 1))
        if sig in seen:
            bad(3, "尺寸 %s 与 %s 重复标注同一段（%.1f→%.1f）" % (key, seen[sig], a, b))
        seen[sig] = key
    # 封闭
    for key, orient, a, b in spans:
        subs = [x for x in spans if x[0] != key and x[1] == orient]
        total = b - a
        for i in range(len(subs)):
            for j in range(i + 1, len(subs)):
                if abs((subs[i][3] - subs[i][2]) + (subs[j][3] - subs[j][2]) - total) < 0.05:
                    bad(3, "尺寸链封闭：%s(%.1f) = %s(%.1f) + %s(%.1f)"
                           % (key, total, subs[i][0], subs[i][3] - subs[i][2],
                              subs[j][0], subs[j][3] - subs[j][2]))
    # 尺寸数字字号
    for key in dim_expected:
        rec = P.get("dimtext_%s" % key)
        if rec and abs(rec["size"] - fs["dim"]) > 0.2 and abs(rec["size"] - 2.9) > 0.2:
            bad(3, "尺寸 %s 字高 %.2f，非标准 3.5/2.9" % (key, rec["size"]))
    # 尺寸数字不得被图线/圆穿过、不得互压（GB/T 4458.4）
    for msg in _audit_texts(P, ["dimtext_%s" % k for k in dim_expected], lw["thick"]):
        bad(3, msg)
    # 尺寸线不得压在图形上
    if bb_m:
        dl = P.get("dimline_b")
        if dl and not dl["y1"] > bb_m[3] - 0.01:
            bad(3, "齿宽尺寸线未落在齿顶线外侧（y=%.2f，主视图底 y=%.2f）" % (dl["y1"], bb_m[3]))

    # ---------- 项 4：表格 / 标题栏 / 技术要求 ----------
    if P.get("table") is None:
        bad(4, "缺齿轮参数表")
    else:
        checks4 = [("m", g["m"], "模数"), ("z", g["z"], "齿数"),
                   ("alpha", g["alpha_deg"], "压力角"), ("x", g["x"], "变位系数"),
                   ("b", g["b"], "齿宽")]
        for k, val, name in checks4:
            got = P.text_of("tbl_val_%s" % k)
            if got is None:
                bad(4, "参数表缺「%s」行" % name)
                continue
            num = re.search(r"-?\d+(?:\.\d+)?", got)
            if not num or abs(float(num.group(0)) - float(val)) > 1e-6:
                bad(4, "参数表「%s」= %r，参数为 %s" % (name, got, _fmt(val)))
        grade = P.text_of("tbl_val_grade")
        if grade is None:
            bad(4, "参数表缺「精度等级」行")
        else:
            m_grade = re.search(r"\d+", grade)
            tech_txt = (" ".join(tb["tech_req"]).replace("{grade}", str(tb.get("grade", "")))
                .replace("{fillet}", _fmt(g["fillet"])).replace("{fillet_hi}", _fmt(g["fillet"] + 1.0))
                .replace("{chamfer}", _fmt(g["chamfer"])))
            m_tech = re.search(r"(\d+)\s*级精度", tech_txt)
            m_param = re.search(r"\d+", str(tb.get("grade", "")))
            if not m_grade:
                bad(4, "参数表精度等级未写数字")
            elif m_param and m_grade.group(0) != m_param.group(0):
                bad(4, "参数表精度等级 %s 级 ≠ 参数 grade=%s" % (m_grade.group(0), tb.get("grade")))
            elif m_tech and m_grade.group(0) != m_tech.group(1):
                bad(4, "精度等级不一致：参数表 %s 级，技术要求 %s 级"
                       % (m_grade.group(0), m_tech.group(1)))
    # 标题栏
    for fid, wanted, name in (("tb_name", tb["title_block"]["name"], "图名"),
                              ("tb_material", tb["title_block"]["material"], "材料"),
                              ("tb_scale", sh["scale"], "比例"),
                              ("tb_no", tb["title_block"]["drawing_no"], "图号"),
                              ("tb_designer", tb["title_block"]["designer"], "设计人"),
                              ("tb_org", tb["title_block"]["org"], "单位")):
        got = P.text_of(fid)
        if got is None:
            bad(4, "标题栏缺%s" % name)
        elif got.strip() != str(wanted).strip():
            bad(4, "标题栏%s = %r，应为 %r" % (name, got, wanted))
    if P.get("titleblock") is None:
        bad(4, "缺标题栏外框")
    # 技术要求
    n_tr = len([k for k in P.ids if re.match(r"tr_\d+$", k)])
    if n_tr < 4:
        bad(4, "技术要求仅 %d 条，应 ≥ 4 条" % n_tr)
    joined = " ".join(P.text_of(k) or "" for k in P.ids if re.match(r"tr_\d+$", k))
    for frag, why in (("GB/T 10095", "未注明齿轮精度标准 GB/T 10095"),
                      ("%g 级" % _grade_of(tb), "未注明精度等级"),
                      ("C%g" % g["chamfer"], "未注倒角 C%g 未写" % g["chamfer"]),
                      ("R%g" % g["fillet"], "未注圆角与参数 %.1f 不符" % g["fillet"])):
        if frag not in joined:
            bad(4, "技术要求%s" % why)

    # ---------- 项 5：粗糙度 / 公差位置 ----------
    rough = an["roughness"]
    surf_map = {"齿面": (ra, "齿顶线"), "轴孔": (rb, "孔壁"), "端面": (None, "端面")}
    # 可作为"加工表面"的轮廓线：排除粗糙度符号/引出线自身（否则量到自己是 0）
    contours = [(r["x1"], r["y1"], r["x2"], r["y2"]) for r in P.lines
                if r["cls"] in ("thick", "thin")
                and not str(r.get("id") or "").startswith("ra_")]
    for surf, val in rough.items():
        sid = SURF_ID.get(surf, surf)
        rec = P.get("ra_text_%s" % sid)
        if rec is None:
            bad(5, "缺「%s」的表面粗糙度符号" % surf)
            continue
        num = re.search(r"\d+(?:\.\d+)?", rec["text"])
        if not num or abs(float(num.group(0)) - float(val)) > 1e-6:
            bad(5, "「%s」粗糙度标注 %r，参数为 Ra%s" % (surf, rec["text"], _fmt(val, 1)))
        if surf != "其余":
            lead = P.get("ra_lead_%s" % sid)
            # 引出线起点应在轮廓上（允许 2 mm）
            cand = None
            if lead is not None:
                cand = (lead["x1"], lead["y1"])
            if cand is None:
                bad(5, "「%s」粗糙度缺引出线" % surf)
            else:
                dmin = min([_seg_point_dist(cand, c) for c in contours] or [1e9])
                for c in P.circles:
                    dmin = min(dmin, abs(math.hypot(cand[0] - c["cx"], cand[1] - c["cy"]) - c["r"]))
                if sid == "bore":   # 轴孔画成弧（槽口断开），按半径判
                    dmin = min(dmin, abs(math.hypot(cand[0] - lcx, cand[1] - cy) - rb))
                if dmin > 2.0:
                    bad(5, "「%s」粗糙度引出线未指向加工表面（距最近轮廓 %.2f mm）" % (surf, dmin))
    if P.get("ra_text_other") is None:
        bad(5, "缺「其余」统一粗糙度标注")
    # 形位公差
    gdt = an["gdt"]
    for i, item in enumerate(gdt, start=1):
        fr = P.get("gdt_frame_%s" % i)
        if fr is None:
            bad(5, "缺第 %d 项形位公差框" % i)
            continue
        v = P.text_of("gdt_value_%s" % i)
        if v is None or abs(float(v) - float(item["value"])) > 1e-9:
            bad(5, "形位公差 %d 数值 %r，参数为 %.3f" % (i, v, item["value"]))
        if (P.text_of("gdt_datum_%s" % i) or "").strip() != item["datum"]:
            bad(5, "形位公差 %d 基准 = %r，应为 %s"
                   % (i, P.text_of("gdt_datum_%s" % i), item["datum"]))
        box = (fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"])
        if box[0] < fx0 or box[1] < fy0 or box[2] > fx1 or box[3] > fy1:
            bad(5, "形位公差框 %d 越出图框" % i)
        lead = P.get("gdt_leader_%d" % i) or P.get("gdt_leader_%da" % i)
        if lead is None:
            bad(5, "形位公差框 %d 无引出线" % i)
        else:
            cand = (lead["x1"], lead["y1"]) if lead["x1"] else (lead["x2"], lead["y2"])
            pts = [(lead["x1"], lead["y1"]), (lead["x2"], lead["y2"])]
            # 检查框与引出线是否相连、引出线是否指向轮廓
            other = P.get("gdt_leader_%db" % i)
            target = (other["x2"], other["y2"]) if other else pts[1]
            dmin = min([_seg_point_dist(target, c) for c in contours] or [1e9])
            for c in P.circles:
                dmin = min(dmin, abs(math.hypot(target[0] - c["cx"], target[1] - c["cy"]) - c["r"]))
            if dmin > 2.0:
                bad(5, "形位公差框 %d 引出线未指向被测要素（距最近轮廓 %.2f mm）" % (i, dmin))
    # 框与标题栏/技术要求/参数表不得重叠，且距技术要求末行 ≥8 mm
    boxes = {"参数表": P.get("table"), "标题栏": P.get("titleblock")}
    for name, rec in boxes.items():
        if rec is None:
            continue
        b1 = (rec["x"], rec["y"], rec["x"] + rec["w"], rec["y"] + rec["h"])
        for i in range(1, len(gdt) + 1):
            fr = P.get("gdt_frame_%s" % i)
            if fr and _rect_hit(b1, (fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"])):
                bad(5, "形位公差框 %d 与%s重叠" % (i, name))
    tr_last = [t for k, t in ((k, P.get(k)) for k in P.ids if re.match(r"tr_\d+$", k)) if t]
    if tr_last:
        last_y = max(t["y"] for t in tr_last)
        for i in range(1, len(gdt) + 1):
            fr = P.get("gdt_frame_%s" % i)
            if fr and last_y - (fr["y"] + fr["h"]) < 8.0 and abs(fr["x"] - fx0) < 120:
                bad(5, "形位公差框 %d 距技术要求末行仅 %.1f mm（应 ≥8 mm）"
                       % (i, last_y - (fr["y"] + fr["h"])))
    # 粗糙度/形位公差/基准文字不得压线、压字
    ann_ids = ["ra_text_%s" % SURF_ID[k] for k in rough] + \
              ["gdt_sym_%d" % i for i in range(1, len(gdt) + 1)] + \
              ["gdt_value_%d" % i for i in range(1, len(gdt) + 1)] + \
              ["gdt_datum_%d" % i for i in range(1, len(gdt) + 1)] + ["datum_A"]
    for msg in _audit_texts(P, ann_ids, lw["thick"]):
        bad(5, msg)
    # 任何文字越出图框
    for t in P.texts:
        b = _text_bbox(t)
        if b and (b[0] < fx0 - 0.5 or b[1] < fy0 - 0.5 or b[2] > fx1 + 0.5 or b[3] > fy1 + 0.5):
            bad(5, "文字 %r 越出图框（框 %.1f,%.1f~%.1f,%.1f）"
                   % (t["text"], b[0], b[1], b[2], b[3]))
    # 轴孔基准字母与参数一致
    want_datum = str(an["dims"]["bore"].get("datum") or "")
    if want_datum and (P.text_of("datum_A") or "").strip() != want_datum:
        bad(5, "轴孔基准字母 %r，应为 %s" % (P.text_of("datum_A"), want_datum))
    # 轴孔尺寸标在端面图，不标在键槽台阶上
    bore = P.get("dimtext_bore")
    bb_l2 = P.bbox("L_")
    if bore and bb_l2:
        if not (bb_l2[0] - 20 <= bore["x"] <= bb_l2[2] + 45):
            bad(5, "轴孔尺寸 φ%s 未标注在端面图附近（x=%.1f）" % (_fmt(g["bore_d"]), bore["x"]))
    # 键槽宽：水平尺寸线，界线贴槽顶，文字在尺寸线上方
    kww, kdl = P.get("dimtext_keyway_width"), P.get("dimline_keyway_width")
    if kww is None or kdl is None:
        bad(5, "键槽宽缺尺寸线/文字")
    else:
        if abs(kdl["y1"] - kdl["y2"]) > 0.01:
            bad(5, "键槽宽尺寸线不水平（y1=%.2f y2=%.2f）" % (kdl["y1"], kdl["y2"]))
        if abs(abs(kdl["x2"] - kdl["x1"]) - g["keyway"]["width"] * s) > 0.05:
            bad(5, "键槽宽尺寸线长 %.2f ≠ 槽宽×比例 %.2f"
                   % (abs(kdl["x2"] - kdl["x1"]), g["keyway"]["width"] * s))
        if not (kdl["y1"] - 4.0 <= kww["y"] <= kdl["y1"] - 0.6):
            bad(5, "键槽宽文字未落在尺寸线上方（文字 y=%.2f，尺寸线 y=%.2f）"
                   % (kww["y"], kdl["y1"]))
        if not (min(kdl["x1"], kdl["x2"]) - 2.0 <= kww["x"] <= lcx + ra):
            bad(5, "键槽宽文字离尺寸线太远（x=%.2f）" % kww["x"])
        for i in (1, 2):
            ext = P.get("dim_ext_keyway_width_%d" % i)
            if ext is None:
                bad(5, "键槽宽缺第 %d 条尺寸界线" % i)
            elif min(abs(ext["y1"] - slot_top), abs(ext["y2"] - slot_top)) > 0.6:
                bad(5, "键槽宽尺寸界线未与槽顶边相接（y=%.2f/%.2f，槽顶 %.2f）"
                       % (ext["y1"], ext["y2"], slot_top))
    # 尺寸线不得与点画线（中心线/轴线）重合
    for l in P.lines:
        if l.get("cls") != "dimline":
            continue
        for c in P.lines:
            if c.get("cls") != "center":
                continue
            hv = abs(l["y1"] - l["y2"]) < 0.01
            hvc = abs(c["y1"] - c["y2"]) < 0.01
            if hv and hvc and abs(l["y1"] - c["y1"]) < 0.3 and \
                    min(max(l["x1"], l["x2"]), max(c["x1"], c["x2"])) - \
                    max(min(l["x1"], l["x2"]), min(c["x1"], c["x2"])) > 0.5:
                bad(5, "尺寸线 %s 与中心线重合（y=%.2f），不得用中心线代替尺寸线" % (l["id"], l["y1"]))
            if (not hv) and (not hvc) and abs(l["x1"] - c["x1"]) < 0.3 and \
                    min(max(l["y1"], l["y2"]), max(c["y1"], c["y2"])) - \
                    max(min(l["y1"], l["y2"]), min(c["y1"], c["y2"])) > 0.5:
                bad(5, "尺寸线 %s 与中心线重合（x=%.2f），不得用中心线代替尺寸线" % (l["id"], l["x1"]))

    # ---------- 项 6：数值逐项比对 ----------
    for name, got, exp in (("分度圆 d=mz", g["d"], der["d"]),
                           ("齿顶圆 d_a=d+2m(1+x)", g["d_a"], der["d_a"]),
                           ("齿根圆 d_f=d-2.5m+2xm", g["d_f"], der["d_f"])):
        if abs(float(got) - float(exp)) > 5e-3:
            bad(6, "参数自相矛盾：%s 填 %.3f，按 m/z/x 算得 %.3f" % (name, got, exp))
    if abs(g["keyway"]["length"] - g["b"]) > 1e-6:
        bad(6, "键槽长 %.3f 与齿宽 %.3f 不等（通槽应相等）" % (g["keyway"]["length"], g["b"]))
    # 逐项比对印在图上/表里的数字
    num_expect = {
        "dimtext_b": g["b"], "dimtext_d_a": g["d_a"], "dimtext_d": g["d"],
        "dimtext_d_f": g["d_f"], "dimtext_bore": g["bore_d"],
        "dimtext_keyway_width": g["keyway"]["width"],
        "dimtext_keyway_depth": der["keyway_depth"],
        "tbl_val_m": g["m"], "tbl_val_z": g["z"], "tbl_val_alpha": g["alpha_deg"],
        "tbl_val_x": g["x"], "tbl_val_b": g["b"],
    }
    for eid, exp in num_expect.items():
        got = P.first_num(eid)
        if got is None:
            bad(6, "取不到标注数值（%s）" % eid)
        elif abs(got - float(exp)) > 0.005:
            bad(6, "标注不一致：%s 图上 %.3f，参数 %.3f" % (DIM_KEYS[eid[8:]][0] if eid[8:] in DIM_KEYS else eid,
                                                        got, exp))
    # 键槽深 = d + t2
    kd = P.first_num("dimtext_keyway_depth")
    if kd is not None and abs(kd - (g["bore_d"] + g["keyway"]["t2"])) > 0.005:
        bad(6, "毂槽深标注 %.2f ≠ d+t2 = %.2f" % (kd, g["bore_d"] + g["keyway"]["t2"]))
    # 所有尺寸数字字号：GB 尺寸字高 3.5
    return issues


def _grade_of(tb: Dict[str, Any]) -> int:
    m = re.search(r"\d+", str(tb.get("grade", "")))
    if m:
        return int(m.group(0))
    for line in tb["tech_req"]:
        m = re.search(r"(\d+)\s*级", line)
        if m:
            return int(m.group(0))
    return 0


def format_report(issues: Sequence[str]) -> str:
    lines = []
    for i, name in enumerate(CHECK_ITEMS, start=1):
        own = [x for x in issues if x.startswith("[%d " % i)]
        mark = "✓" if not own else "✗"
        lines.append("%s %d. %s" % (mark, i, name))
        for it in own:
            lines.append("      - " + it.split("] ", 1)[-1])
    lines.append("")
    lines.append("合计 %d 处问题" % len(issues) if issues else "全部通过：0 处问题")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 6. CLI
# --------------------------------------------------------------------------- #

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="齿轮零件图 SVG 渲染 + 校验")
    ap.add_argument("--out", "-o", default="", help="输出 SVG 路径")
    ap.add_argument("--params", "-p", default="", help="参数 JSON（默认内置 10-6 大齿轮）")
    ap.add_argument("--dump-params", action="store_true", help="打印参数 JSON 后退出")
    ap.add_argument("--check", action="store_true", help="渲染后跑校验")
    ap.add_argument("--json", action="store_true", help="校验结果以 JSON 输出")
    args = ap.parse_args(argv)

    params = default_params()
    if args.params:
        with open(args.params, encoding="utf-8") as fh:
            params = json.load(fh)

    if args.dump_params:
        print(json.dumps(params, ensure_ascii=False, indent=2))
        return 0

    problems = validate_params(params)
    if problems:
        print("参数问题：\n  " + "\n  ".join(problems))
        return 2

    svg = render(params)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("已写入 %s（%d 字节）" % (args.out, len(svg.encode("utf-8"))))

    if args.check:
        issues = check(svg, params)
        if args.json:
            print(json.dumps({"issues": issues, "passed": not issues,
                              "items": CHECK_ITEMS}, ensure_ascii=False, indent=2))
        else:
            print(format_report(issues))
        return 0 if not issues else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
