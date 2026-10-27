#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check() 的反向测试：故意把图改坏，确认六项校验每项都真的会报错。

正向"全绿"只说明 check() 没报错，不能说明它有效；这里逐个注入典型错误，
要求对应的项号出现在问题清单里。跑法：
    python3 test_check.py
"""
from __future__ import annotations

import re
import sys

import gear_draw as G


def tag_of(svg: str, eid: str) -> str:
    m = re.search(r'<[a-z]+[^>]*\bid="%s"[^>]*>' % re.escape(eid), svg)
    if not m:
        raise AssertionError("SVG 里找不到 id=%s 的元素" % eid)
    return m.group(0)


def set_attr(svg: str, eid: str, attr: str, val: str) -> str:
    t = tag_of(svg, eid)
    if re.search(r'\b%s="[^"]*"' % attr, t):
        nt = re.sub(r'\b%s="[^"]*"' % attr, '%s="%s"' % (attr, val), t)
    else:
        nt = t.replace("/>", ' %s="%s"/>' % (attr, val))
    return svg.replace(t, nt, 1)


def _span(svg: str, eid: str):
    """返回 (元素整体起止下标, 开标签, 内容, 闭标签) —— 只看开标签会漏掉文字。"""
    t = tag_of(svg, eid)
    i = svg.index(t)
    close = "</text>" if t.startswith("<text") else "/>"
    if close == "/>":
        return i, i + len(t), t, ""
    j = svg.index("</text>", i)
    return i, j + len(close), t, svg[i + len(t):j]


def set_text(svg: str, eid: str, new_text: str) -> str:
    i, j, t, _ = _span(svg, eid)
    if not t.startswith("<text"):
        raise AssertionError("id=%s 不是文本元素" % eid)
    return svg[:i] + t + new_text + "</text>" + svg[j:]


def drop(svg: str, eid: str) -> str:
    i, j, _, _ = _span(svg, eid)
    return svg[:i] + svg[j:]


def main() -> int:
    p = G.default_params()
    svg = G.render(p)
    base = G.check(svg, p)
    fails = 0

    def expect(name: str, svg2: str, item: int, keyword: str = ""):
        nonlocal fails
        issues = G.check(svg2, p)
        hit = [i for i in issues if i.startswith("[%d " % item)
               and (keyword in i if keyword else True)]
        print("%-40s %s  %s" % (name, "捕获" if hit else "漏检!",
                                hit[0].split("] ", 1)[-1] if hit else "（问题清单无该项）"))
        if not hit:
            fails += 1

    if base:
        print("基线不干净，先修渲染：\n" + G.format_report(base))
        return 1
    print("基线：0 处问题\n")

    # ---- 项 1 第一角画法 ----
    def shift_views(s):
        def rep(m):
            tag = m.group(0)
            for attr in ("cx", "x1", "x2"):
                mm = re.search(r'\b%s="([\d.]+)"' % attr, tag)
                if mm:
                    tag = tag.replace('%s="%s"' % (attr, mm.group(1)),
                                      '%s="%.2f"' % (attr, float(mm.group(1)) - 40))
            return tag
        return re.sub(r'<[a-z]+[^>]*\bid="(?:L_|ra_(?:text|lead|sym))[^>]*>', rep, s)

    expect("项1：端面图整体挪到主视图左侧", shift_views(svg), 1)
    expect("项1：删掉「第一角投影法」标注", set_text(svg, "proj_label", ""), 1)

    # ---- 项 2 三线画法 ----
    r_df = re.search(r'\br="([\d.]+)"', tag_of(svg, "L_circle_df")).group(1)
    expect("项2：齿根圆半径写错 +1.2",
           set_attr(svg, "L_circle_df", "r", "%.3f" % (float(r_df) + 1.2)), 2)
    expect("项2：齿顶圆画成细实线",
           set_attr(svg, "L_circle_ta", "stroke-width", "0.25"), 2)
    tg = tag_of(svg, "M_hatch_3")
    y1 = float(re.search(r'\by1="([\d.]+)"', tg).group(1))
    y2 = float(re.search(r'\by2="([\d.]+)"', tg).group(1))

    def shift_hatch(dy):
        s2 = set_attr(svg, "M_hatch_3", "y1", "%.3f" % (y1 + dy))
        return set_attr(s2, "M_hatch_3", "y2", "%.3f" % (y2 + dy))

    expect("项2：剖面线间距被打乱（整条平移 1.4）", shift_hatch(1.4), 2)
    expect("项2：剖面线画进齿区（整条上移 5）", shift_hatch(-5.0), 2)

    # ---- 项 3 尺寸标注 ----
    expect("项3：删掉键槽深的箭头", drop(svg, "arrow_keyway_depth_1"), 3)
    expect("项3：齿宽尺寸线塞进图形里",
           set_attr(set_attr(svg, "dimline_b", "y1", "120.0"), "dimline_b", "y2", "120.0"), 3)
    # 注入一条与齿宽尺寸重合的尺寸线（重复标注）
    dup = ('<line class="dimline" id="dimline_dup" stroke="#000" stroke-width="0.2" '
           'x1="58.75" x2="91.25" y1="151.0" y2="151.0" />')
    expect("项3：同一段尺寸重复标注", svg.replace("</svg>", dup + "</svg>"), 3)
    # 注入两段拼成整体的尺寸线（尺寸链封闭）
    chain = ('<line class="dimline" id="dimline_c1" stroke="#000" stroke-width="0.2" '
             'x1="58.75" x2="75.0" y1="154.0" y2="154.0" />'
             '<line class="dimline" id="dimline_c2" stroke="#000" stroke-width="0.2" '
             'x1="75.0" x2="91.25" y1="154.0" y2="154.0" />')
    expect("项3：尺寸链封闭", svg.replace("</svg>", chain + "</svg>"), 3)

    # ---- 项 4 表格/标题栏/技术要求 ----
    expect("项4：参数表齿数写成 53", set_text(svg, "tbl_val_z", "53"), 4)
    expect("项4：标题栏设计人清空", set_text(svg, "tb_designer", ""), 4)
    expect("项4：技术要求删掉 GB/T 10095", set_text(svg, "tr_3", "3. 齿轮按国标制造，7 级精度。"), 4)

    # ---- 项 5 粗糙度/形位公差 ----
    expect("项5：齿面粗糙度写成 Ra3.2", set_text(svg, "ra_text_tooth", "Ra 3.2"), 5)
    expect("项5：形位公差数值写成 0.050", set_text(svg, "gdt_value_1", "0.050"), 5)
    expect("项5：粗糙度引线脱离齿面",
           set_attr(set_attr(svg, "ra_lead_tooth", "y1", "78"), "ra_lead_tooth", "y2", "78"), 5)
    expect("项5：基准字母写成 B", set_text(svg, "datum_A", "B"), 5)

    # ---- 项 6 数值逐项比对 ----
    expect("项6：齿宽标注写成 66", set_text(svg, "dimtext_b", "66h11"), 6)
    expect("项6：毂槽深写成 30.3", set_text(svg, "dimtext_keyway_depth", "30.3"), 6)
    expect("项6：齿顶圆标注写成 φ141", set_text(svg, "dimtext_d_a", "φ141h11（齿顶圆）"), 6)

    # ---- 参数自相矛盾（不是改图，是改参数）----
    p2 = G.default_params()
    p2["geometry"]["d_a"] = 141.0
    issues = G.check(G.render(p2), p2)
    hit = [i for i in issues if i.startswith("[6 ")]
    print("%-40s %s  %s" % ("项6：参数里 d_a 与 d=mz 不自洽",
                            "捕获" if hit else "漏检!",
                            hit[0].split("] ", 1)[-1] if hit else "（无）"))
    if not hit:
        fails += 1

    print("\n%s" % ("反向测试全部通过：六项校验都有实际约束力" if not fails else
                    "有 %d 项注入未被捕获，校验函数存在盲区" % fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
