# drawing charter 检查器

生成器出图之后，用这套东西验收。四层各管一件事，一条命令跑完。

## 一条命令

```bash
python3 lib/drawing/charter/check.py 图.svg \
    --calc 计算书.json --fig-no SJCS-1
```

- `--calc` 计算书 JSON（期望值的独立来源，见 `calc.schema.md`）。不传则 L1-09/L1-10 判未检查。
- `--fig-no` 图上应出现的图号。不传则 L1-08 判未检查。
- `--selftest` 顺带跑 L4（往临时副本里注错，验证检查器自己看得见）。
- `--no-browser` 跳过量测，L3 六条全部判未检查。

依赖：本机 headless Chromium（`~/.hermes/tools/chromium-1208/...`），可用 `CHROME` 环境变量覆盖。

## 四层

| 层 | 脚本 | 问什么 | 条数 |
|---|---|---|---|
| L0 | `check_contract.py` | 图元有没有身份：role/name 在不在、类型配不配 | 8（5 必检） |
| L1 | `check_rules.py` A 段 | 图元之间关系对不对：尺寸四件套、界线越过量、剖切字母、键槽对计算书 | 10 |
| L2 | `check_rules.py` B 段 | 几何成不成立：圆弧能不能画、圆角接没接上、剖面线在不在轮廓内、重复线、越框 | 9 |
| L3 | `check_rules.py` C 段 | 东西撞不撞：文字互压、字压线、尺寸线穿插、实心符号压字 | 6 |
| L4 | `mutants.py` | 检查器自己看不看得见错（注错 17 个） | 17 注入 |

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

画图过程中别每改一处就跑一遍“检查 + 截图 + 裁剪 + 目视”。`draw/gear_pipeline/devloop.sh`
把四件事合成一条：

```bash
cd draw/gear_pipeline
./devloop.sh build_gear.py --svg 齿轮零件图.svg --calc calc.json --fig-no CS1-01
./devloop.sh --no-build --svg 齿轮零件图.svg      # 图已生成，只检查+看图
```

它做：build → check（只留 ✗ 和汇总）→ 整页截图 → 按 `data-view` 裁出各视图。

产物落在**图所在目录**的 `预览/`：`整页.png` + `局部_main.png` / `局部_end.png` /
`局部_title.png` …，一步拿到全部图片路径，一轮只要一次工具调用 + 一次 vision。

裁剪只认 `data-view` 锚点，不按 bbox 聚类猜（ID-02）。图上没有 `data-view` 时只出整页，
并提示去补锚点。`--pad` 默认 3mm，`--max` 默认 5 张。

和 `build.sh` 的分工：`devloop.sh` 是改图时的秒级反馈（只出 PNG），
`build.sh` 是交付时的 PDF + 逐页 PNG + 像素复核。

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
| 2 | 检查器自身异常，或 L4 自检漏抓/注入未生效 |

## 两份前置产物

**身份**（`identify.py`）：旧图常缺 `data-role` 或用了自造角色。跑一次把它归一：

```bash
python3 lib/drawing/charter/identify.py 图.svg          # 只报告
python3 lib/drawing/charter/identify.py 图.svg --write  # 写回（留 .orig 备份）
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

已登记的盲区（`known_gap`）漏抓只提示、不判失败。目前一个：**键槽开口方向**
（把断面键槽开到轴线另一侧，25 条规则没有一条管）。

## 已知局限

- **不解析 `transform`**：L1/L2 按属性坐标判，带 `transform` 的图元会判不准。L3 绕过了
  （用 `measure.py` 的真实框），L1/L2 还没。
- **L3-06 需要 `data-view`**：图上没有就永远未检查。不用 bbox 聚类猜视图——ID-02 禁止。
- **`calc.schema.md` 之外的字段不认**：计算书结构对不上时，L1-09/L1-10 判未检查并提示缺哪段。

## 文件

```
check.py          一条命令跑 L0~L3（+ L4）
check_contract.py L0 契约
check_rules.py    L1 结构 / L2 几何 / L3 碰撞
measure.py        Chromium 量真实包围盒
identify.py       补 data-role / data-name
mutants.py        L4 注入变异
rules.json        145 条章程条款（机器可读）
calc.schema.md    计算书的字段契约
CHARTER.md        章程正文
PROMPT.md         给画图 agent 的执行指令
api.md            画法 API（由 gen_api.py 反射生成）
```