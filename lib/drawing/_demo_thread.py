# -*- coding: utf-8 -*-
"""_demo_thread.py —— L1→L2→L3 闭环样板：外螺纹杆部画法（本书 ch8 §8-1）

依据：图8-21「内、外螺纹连接时的画法」与其前文规定画法（p.227 起）
  1. 大径、螺纹终止线用**粗实线**；小径用**细实线**，且画入倒角内；
  2. 倒角 45°，倒角线用粗实线；
  3. 轴线用**细点画线**，两端各伸出 3~5 mm。
这不是成品库，是给 ZCode 的样板：`lib/drawing/thread.py` 应当长成这样。
跑法：python3 _demo_thread.py            # 打印校验结果 + 关键尺寸
      python3 _demo_thread.py --svg 路径  # 顺手落一页 SVG
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from lib.drawing._prim import 图形, 校验图元, 线, 文, 落图  # noqa: E402


def 螺纹画法(d=12.0, P=1.75, 螺纹长=30.0, 杆长=45.0, 倒角=2.0, x0=50.0, y轴=60.0):
    """外螺纹杆部（主视图，轴线水平）。返回 图形。

    依据：图8-21 p.227 [核]；小径 d1 = 0.85d（粗略画法，精算需查附表1 螺距系列）。
    """
    if not (0 < 螺纹长 <= 杆长):
        raise ValueError("螺纹长必须在 (0, 杆长] 内")
    r, r1 = d / 2, 0.85 * d / 2
    x1, 终止 = x0 + 杆长, x0 + 螺纹长
    g = 图形()

    # 大径：粗实线，画到端面倒角处
    g.加(线(x0, y轴 + r, x1, y轴 + r), 线(x0, y轴 - r, x1, y轴 - r))
    # 小径：细实线，画入倒角内（起点在倒角内侧）
    g.加(线(x0 + 倒角, y轴 + r1, x1, y轴 + r1, "thin"),
         线(x0 + 倒角, y轴 - r1, x1, y轴 - r1, "thin"))
    # 倒角 + 端面
    g.加(线(x0, y轴 + r - 倒角, x0 + 倒角, y轴 + r),
         线(x0, y轴 - r + 倒角, x0 + 倒角, y轴 - r),
         线(x0, y轴 - r + 倒角, x0, y轴 + r - 倒角))
    # 螺纹终止线：粗实线，画到大径
    g.加(线(终止, y轴 - r, 终止, y轴 + r))
    # 轴线：细点画线，两端伸出 4 mm
    g.加(线(x0 - 4, y轴, x1 + 4, y轴, "center"))

    g.注(f"螺纹 M{d:g}×{P:g}，右旋", f"小径 d1≈{r1 * 2:.2f}（0.85d），画细实线并画入倒角内",
         "螺纹终止线用粗实线，画至大径")
    g.范围(x0 - 4, y轴 - r, x1 + 4, y轴 + r)
    return g


def 自检():
    g = 螺纹画法()
    r, r1 = 6.0, 5.1
    assert abs(r1 - 0.85 * 12 / 2) < 1e-9, "小径系数错"
    assert len(g) == 9, f"图元数应为 9，实为 {len(g)}"
    ok, msg = 校验图元(g.elems)
    assert ok, msg
    # 关键位置抽样：大径线 y=66 / 54，小径线 y=65.1 / 54.9，终止线 x=80
    ys = sorted({round(dd["y1"], 2) for k, dd in g.elems if k == "line"})
    assert 66.0 in ys and 54.0 in ys, f"大径线缺失：{ys}"
    assert 65.1 in ys and 54.9 in ys, f"小径线缺失：{ys}"
    assert any(k == "line" and dd["x1"] == 80.0 == dd["x2"] for k, dd in g.elems), "终止线缺失"
    print(msg)
    print("关键尺寸：大径 12（粗实线 y=66/54）、小径 10.2（细实线 y=65.1/54.9）、"
          "终止线 x=80、轴线 center、倒角 2×45°")
    return g


if __name__ == "__main__":
    g = 自检()
    if "--svg" in sys.argv:
        p = sys.argv[sys.argv.index("--svg") + 1]
        print("SVG:", 落图(g, p))
