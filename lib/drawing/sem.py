# -*- coding: utf-8 -*-
"""sem.py —— 带语义身份的 Sheet（drawing 章程 §12 "为每个图元保留可检查的身份"）

为什么在库里：语义标记只有成为库的一部分才可能被强制。临时放在项目目录里的
那份副本（设计测试/图纸/sem.py）只覆盖一张图，换图即失效。

身份四字段（章程 §12）：
    data-role     图元在制图语义里的角色，必须在 ROLES 白名单内
    data-name     视图/断面/基准的归属名（"A—A"、"B—B"、"A"）
    data-feature  结构特征 id，来自模型字段路径（"seg2.od"、"key.A.len"）
    data-view     视图 id（"main"、"A"、"B"、"table"、"title"）
    data-src      取值来源（"表7"、"GB/T 1096"），用于回溯证据

用法：
    from lib.drawing.sem import SemSheet, R, G
    sh = SemSheet(420, 297, title="…")
    sh.add(R("hatch", "B—B", L(…)))                        # 旧写法仍可用
    sh.add(R("outline", elem=L(…), feature="seg3.od", view="main", src="表7"))
    sh.add(G("dimension", L(…), T(…), name="B—B", view="main"))

章程要求"缺失即不通过"，所以 SemSheet 会把没打 role 的图元记进 `self.missing`，
出图前可以直接 `sh.missing` 自查，不必等校验器。
"""
from draw.gbdraw import Sheet

# 章程 §12 的角色表。新增角色必须同时加进 charter/rules.json 的 role→允许元素类型表，
# 否则 L0 契约检查会按"未登记角色"报错。
ROLES = {
    "sheet", "title-grid", "table-grid",          # 图纸本体与表格
    "outline", "hidden", "centerline",            # 轮廓类（GB/T 4457.4 线型）
    "section-outline", "key-outline",             # 断面/键槽专属
    "hatch",                                      # 剖面线
    "dimension", "extension", "arrow", "leader",  # 尺寸四件套
    "datum", "tolerance-frame", "tolerance-symbol",  # 几何公差
    "roughness",                                  # 表面结构
    "cutting-plane", "view-label",                # 剖切位置与视图名
    "zone-mark",                                  # 轴向区段代号（a/b/c）与其界线
    "projection-symbol",                          # 投影法符号
    "text",                                       # 不属于以上任何类的说明文字
}

# L0 用：每个角色允许出现哪些 SVG 元素类型
ROLE_TAGS = {
    "sheet": {"rect", "line"},
    "title-grid": {"line", "rect", "text", "polygon"},
    "table-grid": {"line", "rect", "text", "polygon"},
    "outline": {"line", "path", "circle", "rect", "polygon", "polyline"},
    "hidden": {"line", "path"},
    "centerline": {"line", "path"},
    "section-outline": {"line", "path", "circle", "polyline"},
    "key-outline": {"line", "path", "polyline"},
    "hatch": {"line"},
    "dimension": {"line", "path", "text"},       # 尺寸数字属于尺寸标注本体
    "extension": {"line", "path"},
    "arrow": {"polygon", "poly", "path"},
    "leader": {"line", "path", "polyline"},
    "datum": {"line", "path", "polygon", "rect", "text"},   # 基准符号=三角+连线+方框+字母
    "tolerance-frame": {"rect", "line", "text"},
    "tolerance-symbol": {"line", "path", "text", "polygon", "circle"},   # 圆度符号就是个圆
    "roughness": {"line", "path", "text", "polygon", "polyline"},
    "cutting-plane": {"line", "polygon", "text"},
    "view-label": {"text"},
    "zone-mark": {"line", "text"},       # 区段代号点划线、两端短界线、代号字母
    "projection-symbol": {"line", "circle", "ellipse", "path"},
    "text": {"text"},
}

# 这几种角色的图元数量天然很多（剖面线、表格网格），L0 不对它们设数量上限
MULTI_OK = {"hatch", "title-grid", "table-grid", "centerline", "extension", "zone-mark"}

# 分组内按元素类型分派子角色：`G("dimension", L, ARROW, T)` 里箭头是 arrow、文字是 text，
# 不能一律继承 dimension——否则 L0 的 C3（role 与元素类型匹配）会把这些记成越界，
# 更要紧的是检查器会把尺寸线、箭头、数字混成一类，配平与碰撞都无从谈起。
G_SUB = {
    "dimension": {"line": "dimension", "path": "dimension", "circle": "dimension",
                  "polygon": "arrow", "poly": "arrow", "text": "dimension"},
    "cutting-plane": {"line": "cutting-plane", "polygon": "arrow", "poly": "arrow",
                      "text": "view-label"},
    "tolerance-frame": {"rect": "tolerance-frame", "line": "tolerance-frame",
                        "text": "text", "polygon": "tolerance-symbol"},
    "projection-symbol": {"line": "projection-symbol", "circle": "projection-symbol",
                          "ellipse": "projection-symbol", "path": "projection-symbol",
                          "text": "text"},
    "section-outline": {"line": "section-outline", "path": "section-outline",
                        "circle": "section-outline", "text": "text"},
    "title-grid": {"line": "title-grid", "rect": "title-grid", "text": "title-grid",
                   "polygon": "title-grid"},
    "table-grid": {"line": "table-grid", "rect": "table-grid", "text": "table-grid",
                   "polygon": "table-grid"},
    "datum": {"line": "datum", "rect": "datum", "text": "datum", "polygon": "datum",
              "poly": "datum", "path": "datum"},
    "roughness": {"line": "roughness", "path": "roughness", "text": "text",
                  "polygon": "roughness", "poly": "roughness"},
}


def _tag(elem) -> str:
    """从 AST 元组取元素种类。"""
    return elem[0] if isinstance(elem, tuple) and len(elem) == 2 else ""


def _mark(elem, **kw):
    """把 role/name/feature/view/src 写进 AST 的 dict；None 值不写。"""
    if isinstance(elem, tuple) and len(elem) == 2 and isinstance(elem[1], dict):
        for k, v in kw.items():
            if v is not None:
                elem[1][k] = v
    return elem


def R(role, name=None, elem=None, *, feature=None, view=None, src=None):
    """给单个图元打角色。

    两种调用形态都支持：
        R("hatch", "B—B", L(...))                      # 位置参数（旧写法）
        R("hatch", elem=L(...), name="B—B", feature=…)  # 关键字
    """
    if role not in ROLES:
        raise ValueError("未登记的 role: %r（合法值见 lib/drawing/sem.py:ROLES）" % (role,))
    if elem is None:
        raise ValueError("R(%r) 没有给 elem" % (role,))
    return _mark(elem, role=role, name=name, feature=feature, view=view, src=src)


def G(role, *elems, name=None, view=None, src=None):
    """把一组图元打成 group。

    role 是分组的语义，但子元素按类型拿自己的角色（见 G_SUB）：
    `G("dimension", 尺寸线, 箭头, 文字)` → dimension / arrow / text，
    不会把箭头和数字一起抹成 dimension。子元素自己打了 role 则优先。
    """
    if role not in ROLES:
        raise ValueError("未登记的 role: %r（合法值见 lib/drawing/sem.py:ROLES）" % (role,))
    sub = G_SUB.get(role, {})
    items = []
    for e in elems:
        if isinstance(e, tuple) and len(e) == 2 and isinstance(e[1], dict):
            if not e[1].get("role"):
                _mark(e, role=sub.get(e[0], role))
        items.append(e)
    return ("group", dict(items=items, role=role, name=name, view=view, src=src))


class SemSheet(Sheet):
    """在 Sheet 的基础上，把 AST 里的 role/name/feature/view/src 落成 data-* 属性。"""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.missing: list = []          # [(tag, 缺什么)]，仅内存审计用

    def _emit(self, e, inherited=None, inherited_name=None, inherited_view=None):
        kind, a = e
        role = a.get("role", inherited)
        view = a.get("view", inherited_view)
        nm = a.get("name", inherited_name)
        feat, src = a.get("feature"), a.get("src")
        if kind == "group":
            return "\n".join(self._emit(x, role, nm, view) for x in a.get("items", []))
        clean = {k: v for k, v in a.items()
                 if k not in ("role", "name", "feature", "view", "src")}
        s = super()._emit((kind, clean))
        attrs = ""
        if role:
            attrs += ' data-role="%s"' % role
        else:
            self.missing.append((kind, "role"))
        if nm:
            attrs += ' data-name="%s"' % nm
        if feat:
            attrs += ' data-feature="%s"' % feat
        if view:
            attrs += ' data-view="%s"' % view
        if src:
            attrs += ' data-src="%s"' % src
        if attrs:
            if s.rstrip().endswith("/>"):
                s = s.rstrip()[:-2].rstrip() + attrs + "/>"
            else:                                  # text 等非自闭合标签
                i = s.index(">")
                s = s[:i] + attrs + s[i:]
        return s