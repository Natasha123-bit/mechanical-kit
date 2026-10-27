# -*- coding: utf-8 -*-
"""_demo_ch10.py —— ch10 附录表库的三个典型查询（验收用）

运行：/usr/bin/python3 lib/drawing/_demo_ch10.py
对应任务书第 3 节：“M12 螺距多少？”“φ30H7 偏差多少？”
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from lib.handbook._lookup import 取  # noqa: E402

T = json.loads((Path(__file__).resolve().parent / "tables" / "ch10.json")
               .read_text(encoding="utf-8"))


def main():
    p = 取(T["附表1"], "12", "螺距 P/粗牙")
    print(f"M12 粗牙螺距 P = {p} mm")

    h7u = 取(T["附表25"], "24~30", "H7/上偏差")
    h7l = 取(T["附表25"], "24~30", "H7/下偏差")
    print(f"φ30 H7 = {h7u}/{h7l} μm（30 落在 24~30 档，合并格回落到 +21/0）")

    h6u = 取(T["附表24"], "24~30", "h6/上偏差")
    h6l = 取(T["附表24"], "24~30", "h6/下偏差")
    print(f"φ30 h6 = {h6u}/{h6l} μm")

    d = 取(T["附表22"], "6206", "深沟球轴承/d")
    D = 取(T["附表22"], "6206", "深沟球轴承/D")
    B = 取(T["附表22"], "6206", "深沟球轴承/B")
    print(f"6206 轴承 d×D×B = {d}×{D}×{B} mm")

    b = 取(T["附表18"], "22~30", "键尺寸 b×h")
    t1 = 取(T["附表18"], "22~30", "键槽/深度/轴 t₁/公称尺寸")
    print(f"φ30 轴（>22~30）平键 b×h = {b}，轴槽深 t₁ = {t1} mm")

    assert p == "1.75" and h7u == "+21" and h7l == "0"
    assert (d, D, B) == ("30", "62", "16") and b == "8×7"
    return 0


if __name__ == "__main__":
    sys.exit(main())
