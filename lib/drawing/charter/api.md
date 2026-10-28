# drawing 模块接口表

> 本文件由 `charter/gen_api.py` 从代码反射生成，**不要手改**。
> 接口以本文件为准；`CHARTER.md` 第 9 章不抄签名。

## 图元层（中文名，画法函数只依赖这一层）

`lib/drawing/_prim.py`

| 接口 | 签名 | 说明 |
|---|---|---|
| `图形` | `class` | 一个画法的产出：AST 元素 + 注记（技术要求条目）+ 包围盒(mm)。 |
| `图形.加` | `(self, *els) -> "'图形'"` |  |
| `图形.注` | `(self, *条目) -> "'图形'"` |  |
| `图形.范围` | `(self, x0, y0, x1, y1) -> "'图形'"` |  |
| `线` | `(x1, y1, x2, y2, style='thick')` |  |
| `圆` | `(cx, cy, r, style='thick', fill='none')` |  |
| `矩形` | `(x, y, w, h, style='thick', fill='none')` |  |
| `弧` | `(cx, cy, r, a1, a2, style='thick')` | a1→a2 逆时针，度。 |
| `文` | `(x, y, s, h=3.5, anchor='middle', rotate=None, style='text')` |  |
| `剖面线` | `(poly, spacing=2.0, angle=45.0, style='thin')` | 剖面线：按 angle 方向的平行线族逐条生成线段（**不用 SVG pattern** —— |
| `箭头` | `(x1, y1, x2, y2, size=3.0)` | 实心箭头，从 (x1,y1) 指向 (x2,y2)，箭头在 (x2,y2)。 |
| `校验图元` | `(nodes, strict: 'bool' = True)` | 校验元素来源与线型。返回 (ok, msg)；strict 时不合格抛 ValueError。 |
| `平移` | `(g: '图形', dx: 'float' = 0.0, dy: 'float' = 0.0) -> '图形'` | 整图平移（mm），供出图时把轴线在图幅里摆位；不动线型、不改图元种类。 |
| `拼` | `(*图形s) -> '图形'` |  |
| `落图` | `(g: '图形', path, w=297.0, h=210.0) -> 'str'` | 把图形写成一页 SVG（A3 横放默认），供 gear_pipeline/build.sh 那条 Chrome→PDF→PNG 链使用。 |

## 幅面、图框、标题栏

`lib/drawing/sheet.py`

| 接口 | 签名 | 说明 |
|---|---|---|
| `幅面尺寸` | `(幅面='A3')` | 表1-1 p.7 [核]。返回 {b,l,a,c,e}（mm）：b 短边、l 长边；e/c/a 为留边与装订边。 |
| `图框` | `(幅面='A3', 比例='1:1', 装订边='左', 横放=True)` | 图1-11 p.7 / 图1-12 p.8 [核]：纸边 thin + 图框 thick + 四边中点对中符号。 |
| `标题栏` | `(件名='零件', 材料='45', 比例='1:1', 图号='', 设计='', 审核='', 日期='', 单位名称='', 幅面='A3', 装订边='左', 横放=True)` | 图1-15 p.9 [核]：180×56，8 行×7，列宽 10/10/16/16/12/16 + 26 + 12 + 12 + 50。 |

## 语义身份（章程 §12）

`lib/drawing/sem.py`

| 接口 | 签名 | 说明 |
|---|---|---|
| `R` | `(role, name=None, elem=None, *, feature=None, view=None, src=None)` | 给单个图元打角色。 |
| `G` | `(role, *elems, name=None, view=None, src=None)` | 把一组图元打成 group。 |
| `SemSheet` | `class` | 在 Sheet 的基础上，把 AST 里的 role/name/feature/view/src 落成 data-* 属性。 |
| `ROLES` | `{arrow, centerline, cutting-plane, datum, dimension, extension, hatch, hidden…}` | 共 22 项 |
| `ROLE_TAGS` | `dict`，22 项 | 键：sheet, title-grid, table-grid, outline, hidden, centerline, section-outline, key-outline |
| `MULTI_OK` | `{centerline, extension, hatch, table-grid, title-grid, zone-mark}` | 共 6 项 |

## 底层原语与输出器（英文名）

`draw/gbdraw.py`

| 接口 | 签名 | 说明 |
|---|---|---|
| `L` | `(x1, y1, x2, y2, style='thick')` |  |
| `CIRCLE` | `(cx, cy, r, style='thick', fill='none')` |  |
| `RECT` | `(x, y, w, h, style='thick', fill='none')` |  |
| `ARC` | `(cx, cy, r, a1, a2, style='thick')` | a1→a2 逆时针，度。 |
| `T` | `(x, y, s, h=3.5, anchor='middle', rotate=None, style='text')` |  |
| `HATCH` | `(poly, spacing=2.0, angle=45.0, style='thin')` | 剖面线：按 angle 方向的平行线族逐条生成线段（**不用 SVG pattern** —— |
| `ARROW` | `(x1, y1, x2, y2, size=3.0)` | 实心箭头，从 (x1,y1) 指向 (x2,y2)，箭头在 (x2,y2)。 |
| `PATH` | `(d, style='thin', fill='none')` |  |
| `PHASE` | `(x1, y1, x2, y2, amp=1.5, period=12.0, style='thin')` | 双折线：沿 (x1,y1)→(x2,y2) 的**真折线**（每周期两个折角），用于断裂边界。 |
| `WAVY` | `(x1, y1, x2, y2, amp=1.2, wavelength=6.0, style='thin')` | 波浪线：沿两点方向的**真波浪**（正弦，端点收在轴线上），用于断裂/局部剖边界。 |
| `DIM_H` | `(y, x1, x2, text, ext_from=(0, 0), h=3.5, above=1.0, tick=None)` | 水平尺寸：尺寸界线（从 ext_from 起）+ 尺寸线 + 两端箭头 + 数字在上方。 |
| `DIM_V` | `(x, y1, y2, text, h=3.5, right=1.0)` |  |
| `LEAD` | `(x1, y1, x2, y2, text, h=3.5, anchor='start', shelf=4.0)` | 引线：从被标注处 (x1,y1) 到 (x2,y2)，带水平托线写字。 |
| `ROUGH` | `(x, y, ra='Ra3.2', h=2.5, flip=False)` | 表面粗糙度：60° 尖角 + 长边 + 数值（GB/T 131）。flip=True 用于下表面。 |
| `TOL_FRAME` | `(x, y, cells, h=3.5, pad=1.6)` | 公差框格：cells 依次为符号/公差值/基准，横向排列，左上角 (x,y)。 |
| `DATUM` | `(x, y, label='A', h=3.5, up=True)` | 基准符号：涂黑三角 + 方框字母。 |
| `iter_path_commands` | `(d: 'str')` | 把 `d` 拆成 [(cmd, [原文字符串...]), ...]；一个命令后跟多组参数拆成多段。 |
| `STYLES` | `dict`，9 项 | 键：thick, thin, center, hidden, wavy, phase, thick-hidden, thick-center |
| `TEXT_H` | `3.5` | 常量 |
| `TEXT_S` | `2.5` | 常量 |
| `Sheet` | `class` | Sheet(w: 'float', h: 'float', y_up: 'bool' = True, items: 'list' = <factory>, title: 'str' = '') |
| `Sheet.add` | `(self, *els)` |  |
| `Sheet.count` | `(self) -> 'int'` |  |
| `Sheet.svg` | `(self) -> 'str'` |  |
| `Sheet.write` | `(self, path) -> 'str'` |  |

## 已知输出层约束

- 路径翻转只认 SVG 1.1 的 `M/L/H/V/C/S/Q/T/A/Z`（大小写均可）。
  `C/S/Q/T` 保留为原生曲线；相对命令（小写）的 dy 取反而不是 `h − y`。
- 命令元数不合法、出现未识别字符时抛 `ValueError`，不静默降级。
- 需要更复杂的路径特性（`A` 多组参数、弧的 sweep 语义）时先用最小样例验证，
  不能假定全部原语都自动适配 `y_up`。
