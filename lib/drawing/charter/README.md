# drawing charter 检查器

生成器出图之后，用这套东西验收。四层各管一件事，一条命令跑完。

> 本文件说明**怎么用**；做到哪了、下一步做什么，见 `ITERATIONS.md`。

## 一条命令

```bash
python3 lib/drawing/charter/check.py 图.svg \
    --calc 计算书.json --fig-no SJCS-1
```

- `--calc` 计算书 JSON（期望值的独立来源，见 `calc.schema.md`）。不传则 L1-09/L1-10 判未检查。
- `--features` 要素清单 JSON（完备性来源，见 `features.schema.md`）。不传就自动找图同目录的 `features.json`；都没有则 L2-10 判未检查。
- `--fig-no` 图上应出现的图号。不传则 L1-08 判未检查。
- `--selftest` 顺带跑 L4（往临时副本里注错，验证检查器自己看得见）。
- `--part shaft|gear` 加载零件类型规则包（`common/` 那 10 条任何图都加载）。
- `--json 门禁/check.json` 把逐条结果落盘：图纸 `sha256` + 字节数 + 时间戳 + 每条 `status`/`evidence`
  + 汇总 + L4 返回码。证据和图纸版本绑死，事后能对账。
- `--no-browser` 跳过量测，L3 六条全部判未检查。

依赖：本机 headless Chromium（`~/.hermes/tools/chromium-1208/...`），可用 `CHROME` 环境变量覆盖。

## 四层

| 层 | 脚本 | 问什么 | 条数 |
|---|---|---|---|
| L0 | `check_contract.py` | 图元有没有身份：role/name 在不在、类型配不配 | 8（5 必检） |
| L1 | `check_rules.py` A 段 | 图元之间关系对不对：尺寸四件套、界线越过量、剖切字母、键槽对计算书、断面缺口方向、变换可解析 | 12 |
| L2 | `check_rules.py` B 段 | 几何成不成立：圆弧能不能画、圆角接没接上、剖面线在不在轮廓内、重复线、越框、**该画的线画了没有**、**该盖的区间盖没盖** | 11 |
| L3 | `check_rules.py` C 段 | 东西撞不撞：文字互压、字压线（含圆/弧/路径）、尺寸线穿插、实心符号压字 | 6 |
| L4 | `mutants.py` | 检查器自己看不看得见错（注错 24 个） | 24 注入 |
| common | `common/*.py` | 任何工程图都该查：基准符号、圆跳动、公差框、字体、字形覆盖、线宽、表格 | 10 |
| part | `part/*.py` | 零件类型画法（`--part` 加载）：轴 4 条 / 齿轮 3 条 | 4 / 3 |

L1~L3 在同一个文件里，`check.py` 一起跑；单独跑用：

```bash
python3 lib/drawing/charter/check_rules.py 图.svg --bounds 证据/bounds.json --calc ... --fig-no ...
```

`--bounds` 由 `measure.py` 产出：

```bash
python3 lib/drawing/charter/measure.py 图.svg -o 证据/bounds.json
```

**不传 `--bounds` 时 L3 会全部判“未检查”**，屏幕上照样一堆 ✓，很容易当成通过。`check.py` 把顺序固定死，就是为了避免这个。

## 改图循环：devloop.sh

画图过程中别每改一处就跑一遍“检查 + 截图 + 裁剪 + 目视”。`lib/drawing/charter/devloop.sh`
把四件事合成一条：

```bash
# 在你自己的项目目录里跑，生成器和图都用相对路径
python3 /path/to/mdkit/lib/drawing/charter/devloop.sh build_shaft.py \
        --svg 中间轴零件图.svg --calc calc.json --fig-no CS2-01
python3 /path/to/mdkit/lib/drawing/charter/devloop.sh --no-build --svg 图.svg
```

它做：build → check（只留 ✗ 和汇总）→ 整页截图 → 按 `data-view` 裁出各视图。

产物落在**图所在目录**的 `预览/`：`整页.png` + `局部_main.png` / `局部_end.png` /
`局部_title.png` …，一步拿到全部图片路径，一轮只要一次工具调用 + 一次 vision。

裁剪只认 `data-view` 锚点，不按 bbox 聚类猜（ID-02）。图上没有 `data-view` 时只出整页，
并提示去补锚点。`--pad` 默认 3mm，`--max` 默认 5 张。

和 `build.sh` 的分工：`devloop.sh` 是改图时的秒级反馈（只出 PNG），
`build.sh` 是交付时的 PDF + 逐页 PNG + 像素复核。

**`--part` 要自己传**（2026-10-28 起支持 `--part` / `--features` 透传）：

```bash
devloop.sh build_shaft.py --svg 轴图.svg --calc calc.json --fig-no CS2-01 --part shaft
```

不传就只有 L0~L3 + `common`，零件层规则（P-01~P-05 / P-11~P-13）不会跑。
退出码：0 无 ✗ / 1 有 ✗ / 2 build、截图或检查器自身失败——截图仍会出，方便看错在哪。

## 四种状态

| 状态 | 含义 |
|---|---|
| ✓ 通过 | 跑了，且合格 |
| ✗ 不通过 | 跑了，不合格 |
| ! 警示 | 跑了，但判据是可选项（如命名覆盖率） |
| ? 未检查 | **没有判据或缺少输入**——不算通过 |

「未检查」不会混进 ✓ 里。`check.py` 末尾会把未检查清单单独列出来（CHK-08 要求）。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 没有“不通过”（可能带若干“未检查”，范围见末尾） |
| 1 | 有规则“不通过” |
| 2 | 检查器/输入异常，或 L4 没跑成（漏抓、注入未生效、缺 Chromium 或夹具；缺 fontTools 时 G-13 记「跳过(环境)」不在此列） |

## 完备性：features.json

其余规则都以「图上已经画出来的图元」为前提，漏画的东西它们一起沉默。
L2-10 用生成器导出的**要素清单**反查：清单说有、图上没有 → 报。

```json
{"要素": [{"id": "shoulder2", "类型": "线段", "说明": "第 2 条轴肩阶梯线（画满大直径）",
           "x1": 167.0, "y1": 122.5, "x2": 167.0, "y2": 59.5}]}
```

- 线段按**并集覆盖**判：图上线可以拆成三段（圆角切点处本来就拆），覆盖率 ≥95% 算过；
- 不足时报出最大缺口的位置和长度，不是只说一句"缺了"；
- 清单里没有的线不报——清单是"至少要有"，倒角圆角可以不写。

两个项目都已导出：轴图 16 条、齿轮图 51 条（`build_*.py` 在 `seg()`/`circ()` 出口处顺手记，
与 SVG 同时写盘，不做事后补写）。齿轮生成器的模型是 y 向上，清单必须写 `H−y` 换算后的
SVG 坐标——第一版忘了这一步，48/51 条判「覆盖 0%」。

格式与坐标约定见 `features.schema.md`。**清单必须由生成器的几何模型算出，
不能从 SVG 反推**：反推永远自洽，也就永远查不出漏画。

实测：删掉轴上 63mm 长的轴肩线中段，L2-01 报"114 个端点都接上了"（全绿），
L2-10 报"覆盖 2%，缺口 63.0mm，起自 (167.0,122.5)"。

## 零件类型包：--part

```bash
python3 lib/drawing/charter/check.py 轴图.svg --calc calc.json --part shaft
python3 lib/drawing/charter/check.py 齿轮图.svg --calc calc.json --part gear
```

- `common/`（G-xx）不看零件类型，一律加载：基准三角底边贴线+顶点朝外、圆跳动单支箭头、
  公差框格、仿宋与回退、线宽四档与角色对号、表格文字与图形侵入
- 轴肩线画满那条（`L2-14`）放在 L2 而不是 part 层：只要有 `calc` 段表就能跑，不加 `--part` 也生效。
- `part/shaft.py`（P-01/P-03~P-05）从 `calc.json` 的 `派生.段界/半径/台阶/圆角/倒角` 与 `键` 读期望值，
  几何从图上看（轴线取最长水平中心线、X0 取轮廓最左点），**不靠 `data-name` 配对**
- `part/gear.py`（P-11~P-13）靠 `data-feature`（tip/root/pitch/bore/hole）定位齿部，
  读数与计算书的直径集/线性集一一对应
- 报告里单独一节；缺输入（没有 calc 段表、没有 `data-feature`）判「未检查」并说明缺什么，不算通过

## 碰撞判据：线宽胶囊 + 净距

`L3-02`/`L3-03` 不再问“文字框和线有没有交点”，而是问**净距够不够**：

- 几何统一拆成胶囊 `(x1,y1,x2,y2,half)`：`<line>`、`<path>` 的 `L`/`M`/`A`（弧按 0.5mm 采样）、
  `<circle>`（72 边）、`<polygon>`；`half` 从 `class` 查（粗 0.25 / 细 0.125 / 尺寸 0.10 / 剖面 0.09）
- 文字框优先用图旁 `inkbox.json`（`scripts/inkbox.py` 量的真实字形墨迹）；
  没有就退回浏览器 bbox，并按 `0.10×字号` 内缩——bbox 含字身侧距与上下留白，
  比墨迹宽 0.2~0.4mm，不内缩会把「引线贴字边」这种正常排版判成压线
- 判据是 `净距 < 0`，证据行报最小净距（毫米），不是只说“压了”

## 两份前置产物

**身份**（`identify.py`）：旧图常缺 `data-role` 或用了自造角色。跑一次把它归一：

```bash
python3 lib/drawing/charter/identify.py 图.svg          # 只报告
python3 lib/drawing/charter/identify.py 图.svg --write  # 写回（留 .orig 备份）
python3 lib/drawing/charter/identify.py 图.svg --views 视图区.json --write   # 人工声明视图区域
```

它只写 `data-*` 属性，不动几何与样式——改完渲染像素应与改前完全相同。

**包围盒**（`measure.py`）：L3 必须用浏览器量的框。CHK-06 的理由是图上竖排文字在
`<g transform="rotate(...)">` 里，按属性算的框是横的、位置也错。量测结果坐标是
**图面毫米**（只累乘元素到根 `<svg>` 的变换，不含 viewBox→viewport 缩放）。

## L4 自检怎么看

```bash
python3 lib/drawing/charter/mutants.py          # 全部
python3 lib/drawing/charter/mutants.py -k L2    # 只跑几何层（MUT-02）
python3 lib/drawing/charter/mutants.py --list   # 列用例
```

结果分三种，别混：

- **抓到** — 期望的规则变红，正常
- **漏抓** — 规则没红，检查器有盲区 → exit 2
- **注入未生效** — 改完图跟原图一样，用例本身坏了 → exit 2

第三种最容易骗人：正则没匹配、属性名记错，`edit` 静默返回原文，跑出来像漏抓。
所以每次注入后先比哈希，没变就直接判失败。

底图与计算书都在 `charter/fixtures/`（样例-输出轴、中间轴、齿轮零件图 + 清单/计算书），
跟仓库一起分发；夹具缺失时脚本直接 exit 2，不会静默跳过。

已登记的盲区（`known_gap`）漏抓只提示、不判失败。**目前为零**：最后一个
「键槽开口方向」已由 `L1-11` 覆盖（2026-10-28），`keyway_flip` 从盲区转为真抓。

`check_charter.py` 现在还会校验**规则引用的条款存在且状态为 A**（46 条规则 → 38 个条款），
映射漂移即 exit 1——「正文与条款表一致」只证明文档自洽，不证明规则挂得上条款。

`L1-11` 判的是**同图自洽**：剖切箭头指向 +x，断面缺口就开在 +x。这是约定的判据，
不是国标原文——所以证据行只说“一致”，不说“正确”。

## 已知局限

- **`transform` 只吃相似变换**：平移/旋转/等比缩放会累乘进属性坐标；非等比缩放、斜切下
  圆会变椭圆、弧会变椭圆弧，`L1-12` 判**未检查**并列出图元，不硬判。
- **L3-06 需要 `data-view`**：图上没有就永远未检查。不用 bbox 聚类猜视图——ID-02 禁止；
  旧图用 `identify.py --views 视图区.json` **人工声明**区域补上（区域重叠会直接报错）。
- **`calc.schema.md` 之外的字段不认**：计算书结构对不上时，L1-09/L1-10 判未检查并提示缺哪段。
- **没有「尺寸线/界线穿过轮廓」的判据**：尺寸线压在键槽长圆或剖面线上时四层全绿
  （2026-10-28 重画测试实测到一次），这一条只能靠目视或另立规则。

## 文件

```
check.py          一条命令跑 L0~L3（+ L4）
check_contract.py L0 契约
check_rules.py    L1 结构 / L2 几何 / L3 碰撞
common/           通用规则包（G-01~G-32、G-11~G-13）
fontcov.py        字形覆盖核对（要 fontTools，走 ~/.venvs/fonttools/bin/python）
part/             零件类型规则包（shaft 4 条 / gear 3 条）
measure.py        Chromium 量真实包围盒
identify.py       补 data-role / data-name
mutants.py        L4 注入变异
rules.json        145 条章程条款（机器可读）
calc.schema.md    计算书的字段契约
features.schema.md 要素清单的字段契约（完备性）
CHARTER.md        章程正文
PROMPT.md         给画图 agent 的执行指令
api.md            画法 API（由 gen_api.py 反射生成）
```