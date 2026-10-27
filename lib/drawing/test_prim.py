# -*- coding: utf-8 -*-
"""test_prim.py —— 图元契约的看门狗（不是章库用例，是接口自保）

这几条断言的作用：ZCode 若绕过 _prim 手写 SVG、或用 STYLES 之外的线型，必须当场炸掉。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing._prim import 图形, 校验图元, 线, 圆, 拼  # noqa: E402


def test_正常图元通过():
    g = 图形().加(线(0, 0, 10, 0, "thick"), 线(0, 2, 10, 2, "thin"), 圆(5, 5, 2))
    ok, msg = 校验图元(g.elems)
    assert ok, msg
    assert len(g) == 3


def test_手写SVG会被拒():
    坏 = [("path", dict(d="M0 0 L10 10", style="hairline"))]
    try:
        校验图元(坏)
    except ValueError as e:
        assert "hairline" in str(e)
        return
    raise AssertionError("手写路径 / 非标线型必须被拒")


def test_加字符串会被拒():
    try:
        图形().加('<line x1="0" y1="0" x2="10" y2="0"/>')
    except TypeError:
        return
    raise AssertionError("图形.加() 不该接受 SVG 字符串")


def test_拼与包围盒():
    a = 图形().加(线(0, 0, 10, 0)).范围(0, 0, 10, 0)
    b = 图形().加(线(0, 5, 10, 5)).范围(0, 5, 10, 5)
    c = 拼(a, b)
    assert c.bbox == (0, 0, 10, 5), c.bbox
    assert len(c) == 2
