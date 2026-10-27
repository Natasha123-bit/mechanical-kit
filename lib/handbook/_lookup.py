# -*- coding: utf-8 -*-
"""_lookup.py — 《机械设计课程设计手册》表字典通用查询（各章库共用）

表字典统一结构（ZCode 落库时照此写）：

    表04_1_平键 = {
        "表号": "表4-1",
        "表名": "平键连接的剖面和键槽尺寸、普通平键的形式和尺寸",
        "页": 56,
        "单位": "mm",
        "rows": ["6~8", ">8~10", ">10~12", ...],      # 行标签照书上原文
        "cols": ["轴d", "键b×h", "宽度b/轴H9", "宽度b/毂D10", "深度t", "深度t1", "半径r/最小"],  # 两级表头用 / 连
        "data": [[...], [...]],                        # rows × cols，空格照书
        "merges": [[0, 2, 3], ...],                    # 纵向合并单元格：[首行, 末行, 列号]，值取首行
        "注": "原表 p.56；«—“”表破折号 2 处，存 None",
    }

用法：
    取(表, "6~8", "键b×h")          -> "2×2"
    区间取(表, 7.5, "键b×h")         -> "2×2"    # 7.5 落在 "6~8" 档
    行(表, "6~8")                   -> {"轴d": "6~8", "键b×h": "2×2", ...}

合并单元格**不许补值**：`data` 里被合并的格写 ``None``，另在 ``merges`` 里登记
``[首行, 末行, 列号]``；``取()`` 会自动回落到合并区首格。这样既不失真，也能查到值。

约定：**档内不插值**（手册给的是阶梯值，插值会造出标准外的数）；
需要插值的场合由调用方显式用 ``线性插值``，并在 docstring 里写明理由。
"""
from __future__ import annotations

import re

__all__ = ["取", "行", "区间取", "区间取2", "区间行列取", "双参行号", "区间行号", "区间列号",
           "数值", "列号", "行号", "线性插值", "校验"]

_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def 数值(x):
    """表里的数字：'1.5' -> 1.5；'—' / '' / None -> None（原表破折号一律 None，不当 0）"""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(" ", "")
    if s in {"", "—", "-", "－", "——", "/", "–"}:
        return None
    m = _NUM.search(s)
    return float(m.group()) if m else None


def 行号(表, 行键):
    rows = [str(r).strip() for r in 表["rows"]]
    key = str(行键).strip()
    if key in rows:
        return rows.index(key)
    cand = [i for i, r in enumerate(rows) if key in r]
    if len(cand) == 1:
        return cand[0]
    raise KeyError(f"{表.get('表号')} 找不到行 {行键!r}（前几行：{rows[:5]}）")


def 列号(表, 列键):
    cols = [str(c).strip() for c in 表["cols"]]
    key = str(列键).strip()
    if key in cols:
        return cols.index(key)
    cand = [i for i, c in enumerate(cols) if key in c or c in key]
    if len(cand) == 1:
        return cand[0]
    raise KeyError(f"{表.get('表号')} 找不到列 {列键!r}（列名：{cols}）")


def _合并区(m):
    """merges 项归一：
    3 元 [首行, 末行, 列]            → 纵向合并（c0=c1）
    4 元 [首行, 末行, 首列, 末列]    → 矩形合并（ch10 的跨列表头用这种）
    """
    if len(m) >= 4:
        return int(m[0]), int(m[1]), int(m[2]), int(m[3])
    return int(m[0]), int(m[1]), int(m[2]), int(m[2])


def _在合并区(表, i, j):
    """该格是否属于某个合并区（且不是首格）→ 返回首格 (r0, c0)，否则 None"""
    for m in 表.get("merges") or []:
        r0, r1, c0, c1 = _合并区(m)
        if r0 <= i <= r1 and c0 <= j <= c1 and (i, j) != (r0, c0):
            return r0, c0
    return None


def _合并回落(表, i, j):
    """被合并的格 → 取合并区首格的值。纵向与矩形合并都支持。

    没有这层，4 元矩形合并（如 ch10 附表6 的跨 10 列表头）会被当成「只在首列合并」，
    右边那些合并格查出来是 None —— 表在，值查不到。
    """
    hit = _在合并区(表, i, j)
    if hit:
        return 表["data"][hit[0]][hit[1]]
    return 表["data"][i][j]


def 取(表, 行键, 列键):
    """精确取值（行键必须与书上标签一致，或唯一子串匹配）；合并单元格自动回落"""
    i, j = 行号(表, 行键), 列号(表, 列键)
    v = _合并回落(表, i, j)
    if v is None and _在合并区(表, i, j):
        raise KeyError(f"{表.get('表号')} 行{行键!r} 列{列键!r} 在合并区但首格为 None")
    return v


def 行(表, 行键):
    """整行 -> {列名: 值}（合并格已回落）"""
    i = 行号(表, 行键)
    return {str(c): _合并回落(表, i, j) for j, c in enumerate(表["cols"])}


def _区间(label):
    """把 '6~8' '>8~10' '≤6' 'a≤150' '自 6~8' '—~18' '50~120（推力球轴承）' 解析成 (lo, hi, lo_inc, hi_inc)

    书的行标签有五种脏写法，2026-10-22 验收时实测会让 `区间取` 直接 KeyError：
      1. 前缀「自」：'自 6~8'（表4-1 首档，d=6~8 全部查不到）
      2. 带变量名：'a≤150'（表11-4 视孔盖按中心距选）
      3. 下界开口：'—~18'（表6-16/6-17 轴承内径档）
      4. 尾随括注：'50~120（推力球轴承）'
      5. 全角符号：'～' '≤' '≥' '—'
    非区间标签（公差带代号 f7/N7/M8、纯文字）必须仍返回 None，不许当单值。
    """
    s = str(label).strip()
    s = s.replace("＋", "+").replace("－", "-").replace("～", "~").replace("　", " ")
    s = re.sub(r"[（(][^）)]*[）)]\s*$", "", s).strip()      # 4. 去尾随括注
    s = re.sub(r"^[（(][^）)]*[）)]\s*", "", s).strip()
    s = re.sub(r"^[A-Za-zδΔφΦ]\s*(?=[≤≥<>])", "", s).strip()  # 2. 去前置变量名（仅当后面紧跟比较符）
    s = re.sub(r"^自\s*", "", s).strip()                      # 1. 去「自」
    s = s.replace(" ", "")
    if not s:
        return None
    # 3. 下界开口：—~18 / -~18 / ~18
    m0 = re.match(r"^(?:—|–|-|~)\s*~\s*(-?\d+(?:\.\d+)?)$", s)
    if m0:
        return (float("-inf"), float(m0.group(1)), False, True)
    m = re.match(r"^(≥|>|≤|<)?\s*(-?\d+(?:\.\d+)?)\s*(?:~\s*(-?\d+(?:\.\d+)?))?$", s)
    if not m:
        return None
    op, a, b = m.group(1), float(m.group(2)), m.group(3)
    if b is None:
        if op in (">", "≥"):
            return (a, float("inf"), op == "≥", False)
        if op in ("<", "≤"):
            return (float("-inf"), a, False, op == "≤")
        return (a, a, True, True)          # 单值标签
    lo_inc = op != ">"
    return (a, float(b), lo_inc, True)


def 区间行号(表, 值, 行键列=0):
    """按数值落在哪一行档位 → 行号。返回 None 表示所有行标签都解析不出区间。"""
    v = float(值)
    for i, label in enumerate(表["rows"]):
        if i == 0 and str(label).strip() in {str(表["cols"][行键列]).strip(), "轴径d", "d"}:
            continue                        # 首行有时是列名
        iv = _区间(label)
        if not iv:
            continue
        lo, hi, lo_inc, hi_inc = iv
        if (v > lo or (lo_inc and v == lo)) and (v < hi or (hi_inc and v == hi)):
            return i
    return None


def 区间取(表, 值, 列键):
    """按数值档位查值（档内不插值）；查不到抛 KeyError，不猜相邻行"""
    i = 区间行号(表, 值)
    if i is None:
        raise KeyError(f"{表.get('表号')} 没有能容纳 {值} 的档位（rows={表['rows'][:5]}…）")
    return 表["data"][i][列号(表, 列键)]


def 区间列号(表, 值):
    """列标签落在哪个区间 → 列号；非区间列（表头文字/标签列）跳过。返回 None 表示没有列能容纳该值。"""
    v = float(值)
    for j, label in enumerate(表["cols"]):
        iv = _区间(label)
        if not iv:
            continue
        lo, hi, lo_inc, hi_inc = iv
        if (v > lo or (lo_inc and v == lo)) and (v < hi or (hi_inc and v == hi)):
            return j
    return None


def _行号或区间(表, 值):
    """行值先按区间找，找不到再按精确标签找（精度等级这类离散行用得上）。"""
    i = 区间行号(表, 值)
    if i is None:
        i = 行号(表, 值)
    return i


_段双 = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(<=|<|=|~|～)\s*[A-Za-zμ_'’]*\s*(<=|<|=|~|～)?\s*(-?\d+(?:\.\d+)?)\s*$")
_段单 = re.compile(r"^\s*(<=|<|>=|>)\s*(\d+(?:\.\d+)?)\s*$")


def _段(label):
    """把一段档位文字解析成 (lo, hi, lo_inc, hi_inc)，支持手册里出现的四种写法：

        '20<d≤50'  '5≤d≤20'  '0.5≤m≤2'   ← 齿轮公差表最常见的「下限<参数≤上限」
        '6~10' '>8~10' '—~125'            ← 普通区间
        '≤6' 'm≤6' '>25' 'm>25'           ← 单边
    """
    if label is None:
        return None
    s = (str(label).strip().replace(" ", "").replace("＜", "<").replace("≤", "<=")
         .replace("＞", ">").replace("≥", ">="))
    s = s.replace("（", "(").replace("）", ")")
    m = _段单.match(s)
    if m:
        sym, num = m.group(1), float(m.group(2))
        return (-float("inf"), num, False, True) if sym in ("<", "<=") else (num, float("inf"), False, False)
    m = _段双.match(s)
    if m:
        lo, sym1, sym2, hi = m.group(1), m.group(2), m.group(3), m.group(4)
        lo, hi = float(lo), float(hi)
        if sym1 in ("~", "～", "="):
            lo_inc = True
        else:
            lo_inc = sym1 == "<="
        hi_inc = sym2 in (None, "", "~", "～", "=", "<=")
        return (lo, hi, lo_inc, hi_inc)
    # 兜底：交给既有 _区间（'自 6~8'、'—~18'、'50~120（推力球轴承）' 等脏写法）
    return _区间(label)


def 双参行号(表, 值1, 值2):
    """行标签是「参数1档 / 参数2档」两段（如 '20<d≤50 / 2<m≤3.5'）时 → 行号。不是这种表返回 None。"""
    v1, v2 = float(值1), float(值2)
    for i, label in enumerate(表["rows"]):
        parts = re.split(r"[/／]", str(label))
        if len(parts) != 2:
            continue
        a, b = _段(parts[0]), _段(parts[1])
        if not a or not b:
            continue
        ok1 = (v1 > a[0] or (a[2] and v1 == a[0])) and (v1 < a[1] or (a[3] and v1 == a[1]))
        ok2 = (v2 > b[0] or (b[2] and v2 == b[0])) and (v2 < b[1] or (b[3] and v2 == b[1]))
        if ok1 and ok2:
            return i
    return None


def 区间取2(表, 值1, 值2, 列键=None):
    """**双参数查表**：行标签本身就是两段档位（d 档 × m 档），列是精度等级 —— 齿轮公差表的主力形态。

        区间取2(T05, 30, 4, "7级")   # 表10-6 单个齿距偏差：d=30 落 '20<d≤50'、m=4 落 '3.5<m≤6'
                                     # → 返回该行的「7级」列值
        区间取2(T05, 30, 4)          # 省略列键 → 返回整行 {列名: 值}（多列一起看时用）

    典型表：表10-6(1)(2)(3) 的 ±f_pt / F_p / F_α / f_fα / ±f_Hα / F_β / f_fβ / ±f_Hβ，
    行标签形如 '20<d≤50 / 2<m≤3.5'，列是 4~9 级。

    **不插值、不猜档**：越界一律 KeyError。手册给的是阶梯值，插值会造出标准外的数。
    行标签不是两段式的表（如 表10-15 行是精度等级区间、列是中心距区间）请用 ``区间行列取``。
    """
    i = 双参行号(表, 值1, 值2)
    if i is None:
        raise KeyError(
            f"{表.get('表号')} 没有哪个「参数×参数」档位同时容纳 {值1} 与 {值2}"
            f"（rows 形如 {表['rows'][0]!r}；两种参数顺序别弄反）"
        )
    if 列键 is None:
        return 行(表, 表["rows"][i])
    return 取(表, 表["rows"][i], 列键)


def 区间行列取(表, 行值, 列值):
    """**行列各一个参数、两边都是区间**的查表（表10-15 精度等级档 × 中心距档、表10-16 等级 × 模数档）。

        区间行列取(T22, 6, 40)      # 表10-15：6 级、中心距 40 → f_a
        区间行列取(T23, 6, 4)       # 表10-16：6 级、模数 4 → Ra 推荐值

    行值/列值若落在离散标签上（如精度等级 5/6/7）也能命中，不必自己改成 '5~6'。
    """
    i = _行号或区间(表, 行值)
    if i is None:
        raise KeyError(f"{表.get('表号')} 行值 {行值!r} 既不在任何档位、也不是精确标签（rows={表['rows'][:4]}…）")
    j = 区间列号(表, 列值)
    if j is None:
        try:
            j = 列号(表, 列值)
        except KeyError:
            raise KeyError(
                f"{表.get('表号')} 列值 {列值!r} 不落在任何列档位、也不是精确列名（cols={表['cols'][:6]}…）"
            ) from None
    v = _合并回落(表, i, j)
    if v is None and _在合并区(表, i, j):
        raise KeyError(f"{表.get('表号')} 行{行值!r} 列{列值!r} 在合并区但首格为 None")
    return v


def 线性插值(x, x1, y1, x2, y2):
    """显式插值（手册默认不插值；只在调用方 docstring 写明理由时用）"""
    if float(x2) == float(x1):
        raise ZeroDivisionError("插值两点横坐标相同")
    return float(y1) + (float(x) - float(x1)) * (float(y2) - float(y1)) / (float(x2) - float(x1))


def 校验(表):
    """结构体检：rows/cols/data 维度一致；返回问题列表（空 = 通过）"""
    bad = []
    r, c, d = len(表["rows"]), len(表["cols"]), len(表["data"])
    if r != d:
        bad.append(f"rows({r}) != data({d})")
    for i, row in enumerate(表["data"]):
        if len(row) != c:
            bad.append(f"第{i}行 {len(row)} 格 != cols({c})")
    if not 表.get("页"):
        bad.append("缺页码")
    return bad


if __name__ == "__main__":
    表 = {"表号": "表4-1", "表名": "测试", "页": 56, "单位": "mm",
          "rows": ["6~8", ">8~10", ">10~12", ">12~17"], "cols": ["轴径d", "键宽b", "键高h"],
          "data": [["6~8", 2, 2], [">8~10", 3, 3], [">10~12", 4, 4], [">12~17", 5, 5]], "注": ""}
    assert 取(表, ">8~10", "键宽b") == 3
    assert 区间取(表, 6, "键宽b") == 2          # 边界归下一档
    assert 区间取(表, 8, "键宽b") == 2
    assert 区间取(表, 8.5, "键宽b") == 3
    assert 区间取(表, 17, "键宽b") == 5
    assert 数值("—") is None and 数值("1.5") == 1.5
    assert 校验(表) == []
    # 合并单元格：第 0~2 行第 2 列合并，首格 2，其余 None
    表2 = {"表号": "表测试", "表名": "合并", "页": 1, "单位": "mm",
           "rows": ["6~8", ">8~10", ">10~12"], "cols": ["轴径d", "键宽b", "键高h"],
           "data": [["6~8", 2, 2], [">8~10", None, 3], [">10~12", None, 4]],
           "merges": [[0, 2, 1]], "注": "键宽两行合并"}
    assert 取(表2, ">10~12", "键宽b") == 2      # 回落合并首格
    assert 行(表2, ">8~10")["键宽b"] == 2
    assert 校验(表2) == []
    try:
        区间取(表, 99, "键宽b")
    except KeyError:
        pass
    else:
        raise AssertionError("超范围应抛 KeyError")
    print("_lookup.py 自检通过")
