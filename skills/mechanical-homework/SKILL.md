---
name: mechanical-homework
description: Use when 查机械设计/原理公式与标准表、做题校核、画 GB/T 零件图。
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [机械设计, 机械原理, 工程制图, 齿轮传动, 教材习题, 查表, 公差, 校核, gb-t]
    related_skills: [mechanical-book-deposit, pdf, docx]
---

# 机械设计/机械原理作业（例题范式计算书 + 国标零件图）

一份 SKILL.md 只放**跨章通用**的内容：入口、交付形态、流程、书在哪、取值路径、章目录、通用陷阱。
**一章的全部知识在 `references/<book>/chNN.md`**（解题步骤 + 式子 + 表值 + 例题证据），做题时只读那一章。
公式库与工具真身在 `~/Documents/Hermes/Mechanical-Kit/mdkit`（`~/.hermes/lib/mdkit` 只是指向它的 symlink 入口，绝对路径照用），是私有 git 仓库（origin = GitHub `Natasha123-bit/mechanical-kit`）。改动在原位直接 commit；**不要再做手动备份，也不要复制进 skill 目录**。落点、访客安装方式与公开版口径见 `mechanical-book-deposit/references/version-control.md`。

## When to Use

- **单题**：用户在聊天里贴了题目截图/题目 PDF，要求做某道计算题（齿轮传动、蜗杆传动、轴、轴承、螺栓组、带/链传动…）→ 走下面「流程」，按章读 `references/<book>/chNN.md`。题目在哪不影响交付目录，一律落到下面的默认路径；他明确指定了别的目录才改。
- **要求按课本例题范式写**：要"按例题那样一步步写"、公式一个不省、取值处注明表几图几 → 见「交付形态」。
- **要成品**：要可打印的计算书（A4）+ 零件图（**A4 横放 1:2**），或要校验图是否符合国标 → 走「流程」5–6 步 + `references/gb-gear-drawing.md`。
- **整机课程设计（减速器设计说明书）**：给一组题目数据（卷筒转矩/带速/卷筒直径…）要 11 节完整说明书（电动机→传动比→齿轮→轴→轴承→键→润滑→箱体）→ 走 `references/reducer-design.md`（骨架、尺寸链闭合顺序、判据、四张示意图），公式仍按章读 `references/design/chNN.md`。
- **整章 / 多题**：一次给整章习题 → 同一章文件反复用，别重读；跨章题（如轴 + 轴承）按依赖顺序读两章。
- **只出图 / 改图**：参数已定，只画零件图或按参考图改版式 → 直接走「流程」5–6 步。
- **沉淀整本书**（"把《XX》整本沉淀""整本教材沉淀成公式库""走上次那套流程"）→ **不在这里**，走 `mechanical-book-deposit`。
- **第二本书起**（机械原理等）结构完全一样：只多一段「图解法作图步骤」，见 `references/books.md`。
## 书在哪（通则 + 例外下沉）

书清单在 `references/books.md`，**加书只改那里**（一行 + 一个 `book.md`），本文件不动。
标准件（轴承/键/联轴器）的**尺寸与 C、C₀ 不在教材里**，在《机械设计课程设计手册》（纯扫描件、无文本层）：定位法与页码换算见 `references/books.md`「标准件数据源」。

每本书（`<book>` = `design` / `mechanisms` / …）统一命名：

| 东西 | 位置 |
|---|---|
| **全书 PDF** | 一题一本，路径登记在 `references/<book>/book.md`；原始件，不拆不删 |
| 章 PDF（临时） | `~/.hermes/lib/mdkit/books/<book>/_split/chNN-<章名>.pdf` —— 渲完页图即可删，`mdkit.py prepare --split-only --only N` 随时重建 |
| 页图 | `~/Documents/Obsidian/机械知识库/raw/assets/<book>/chNN/p001….png`（三位零填充 = 章内第 k 页） |
| OCR 源 | `raw/sources/<book>/chNN-全章OCR.md`（每页 `## p.印刷页` 标记） |
| **章知识** | `references/<book>/chNN.md` —— 解题步骤 + 式子 + 表值 + 例题证据，**一章一文件** |
| 公式库 | `mdkit/lib/<book>/<主题>_chNN.py` + `_tests.py` |

**例外写到各书 `references/<book>/book.md`，不写这里**（页码偏移、缺页、错位块、未渲染的章）。

## 交付形态（默认就这么给）
- **格式按人类作业写**：`已知 → 解 → （1）（2）…` 分步；公式一个不省，但每步只写「取/查/算」，不写解释性白话、不写过程叙述、不写小结。参数取值处一句话说明依据（表几/图几）。**排版照教材例题范式**：黑字单栏、无卡片色块边框、公式独立居中且代入数值与结果同在一行、**右侧不标公式编号**、表格用纯线表、结尾「说明」①②③、无页码；用户甩一份参考 PDF 说「格式以这个为参考」时抄的是版式。细节、CSS 骨架与像素校验见 `references/calc-book-layout.md`。
- **落盘**：`~/Documents/Hermes/机械设计作业/<题号>解答/`——**一题一个目录，`<题号>` 按本题换**；**教材例题的编号带「例」字**：目录写 `例13-1解答/`、标题写「例13-1　深沟球轴承的选择」，不许简写成 `13-1`——章末习题 13-1 与教材例题 13-1 是两道不同的题，混写会串题，他核对时第一眼就会指出来。开场第一件事 `mkdir -p` 再 `cd` 进去，后面所有命令都在里面跑；**不许复用上一个题的目录**（复用一次就是两个题的产物混在一个文件夹里，事后分不开）。同名目录里已有别的题号的东西时停手报告，不要往里写。内含计算书 PDF（A4）+ 零件图 PDF（**A4 横放**，比例按外廓定：齿轮类 1:2；蜗轮 d_a2≈300 这种量级用 1:2.5，1:2 时径向尺寸加标注会顶到图框）+ 源 + SVG 矢量源。
  - **中间产物一律进 `_tmp/`**：`mdkit.py page` 的页图、裁图复核、`_校验图像`、`__pycache__` 全放 `_tmp/`，交付前 `rm -rf _tmp`；**重跑校验不必先删**——`mdkit.py page` 直接覆盖同名 PNG，链式命令里带 `rm -rf` 只会平白卡一次审批确认。根目录只留交付物（PDF/md/svg）、源脚本、资产（`fonts/`、`katex/`）——11-3 那次根目录堆了 71 张过程图 + 4 个 png 目录，93 个条目，他打开就炸。
  - **源按交付物分两类**：纯文本计算书 → `计算书.md`，跑 `mdkit.py book 计算书.md --pdf`（转换器与 CSS 在 `mdkit/templates/book/`，HTML 只是可删的中间产物）；要画示意图的题（受力分析、机构简图、图解法、轴系结构）→ 源就是 HTML + SVG（KaTeX CSS 与字体随目录拷，离线可开）。零件图一律 SVG（1 单位 = 1 mm）。别给计算书再手拼 HTML——手拼那版今天就漏出过 `\,` 和 `\qquadF`。
  - **图幅与字体**：A3 会被嫌“图纸太大”，别默认 A3；图面文字按标准字号（尺寸 3.5、小字 2.5）不随比例缩放，标题栏比例栏写实际比例。**图面汉字用仿宋**（华文仿宋 `STFangsong` 即可），别留系统默认的 PingFang/宋体/黑体——字体随图落地见 `references/svg-pipeline.md`「字体落地」。
  - **多题一次交付**：每题一个目录 + 各自一个生成脚本（`build_13_1.py` 这类，别用一个脚本同时写三份），每题单独跑 `mdkit.py book`；回话里按题一条 `MEDIA:` 分开发，不要拼成一个 PDF 或压 zip（他说「把三个计算书发我」要的是三份）。三份都出完再一起报，每题给一句结论数。
- **他说「桌面放一份」= 复制，不是移动**：`cp` 到 `~/Desktop/`，正本留在归档目录；桌面那份是临时查看点，他说归档/清理时删副本、归档目录不动。副本名带题号（`11-3计算书.pdf`）。他不说就不主动往桌面放。
- **交完就清，清前先打捞**：用户说某次作业「已交、可以删了」时，先扫一遍有没有下次还要用的东西——程序化出图脚本（`gear_draw.py` 这类，一千多行的参数化管线）、KaTeX 字体、一张成品图当版式样例——移到 `mdkit/draw/` 与 `mdkit/templates/katex/` 再整体删。成品 PDF、题目截图、课本副本属于当次成果，跟着删。报的时候分开说「删了什么」与「打捞到哪」，只报「删了多大」会让用户怀疑代码一并没了；反过来，题目截图和已交成品别自作主张留档。
- **交前自检**（用户会逐项核）：尺寸链是否闭合、结构形式判据是否用对、每个查图/查表取值是否说得清、前提假设是否点明。再加一道**跨文件互校**：计算书正文里写到的每个表面粗糙度、配合代号、结构尺寸，图上必须能一一对到（书写了"端面 Ra3.2"，图上就得有这处标注）；图上参数表逐行对计算书的结构尺寸表，別只对模数齿数。

## 开工前：先定范式、先定预算

- **第一版动手前先要范式**：要两份参照——计算书参考件（一份真实例题解答 PDF/截图）、零件图参考件（教材图例或他以前的作业图），一句话问「照这个排，可以吗」。没参照就先说默认口径（教材例题范式 + GB 简化标题栏 + A4 横放），等一个字再开工。**别自拟版式**：自拟等于盲做，一张图一轮返工就能吃掉整份作业的时间；他手里基本都有范式图，问一句比返两轮便宜得多。
- **预算**：单份作业（计算书 + 一张零件图）目标 ≤20 分钟。**vision 不是验收工具**：图像已走原生通道（0.02 s/次，判定链见 `hermes-provider-config` 的「Image input」节），速度不再是理由，但它**会编读数**——594 px 缩图上 `46` 读成 `16`、`φ25` 读成 `φ40H11`。所以：题目/范式图读一次、交付前整页观感 1~2 次，其余「有没有这条线 / 压没压线 / 数字对不对」全部走坐标断言、像素探针、生成文本 grep；要读图上小字就传 `region` 裁切，别整页缩图。
- **探针写在出图之前**：先把该量的坐标、线位、留白、字数列成断言，再出图跑断言；不是出图→截图→问 vision→再补探针。
- **分段报时**：算完 / 计算书出 PDF / 图纸出 PDF / 按意见改完，各报一句「还剩什么、大约还要多久」；超过 40 分钟没交付主动报卡点，让他能叫停。
- **改图前先过清单，不是事后查百科**：`references/part-drawing-a3.md`、`gb-gear-drawing.md` 里的条目是**出图前逐条打勾的检查表**。同一类错（漏封闭线、倒角反向、剖面比例、尺寸界线、字体与标题栏）被指出第二次，先怀疑“没照着清单过”，而不是“缺一条规则”——再补一条新规则，下一次还是照旧漏。
- **同一张图被退两次就停手重来，别接着 micro-fix**：连续几轮只改坐标、改引线位置而结论仍被否，说明错在**结构与画法判断**上（整套台阶轮廓、投影关系、剖切范围），不是在毫米上。停下渲参考件/手册图成 PNG 与自己的图**并排逐项对**，改版式与结构，别再在坐标上打补丁。
- **自检不等于验收，措辞要分开**：交付只陈述“改了什么、依据哪张参考图/手册图、哪几处没做/没核”。像素采样、断言全绿、测试退出码这些是**自检结论**，不是图正确的证据；把它们写成“已核/已验证”，用户会当成你替他签了字——这是图纸被反复退回的直接原因之一。

## 流程
1. **读题**：`vision_analyze` 看题目图片，逐字取全部数据（含表格、图注），不要凭记忆补参数。**上下文摘要/上轮结论里的参数也不可信**：出图前回 `解答.html` / PDF 原件 grep 一遍模数、齿数、齿顶圆、精度等级（`m=2.5、z₂=54、d=135` 这种只要一个数错，参数表、标题栏、所有尺寸会一起错，而且 check 内部自洽查不出来）。
2. **取课本范式**：先跑 `mdkit.py probe 书.pdf` 探针（页数 + 逐页 `chars` + 首行字符），判断文本层能不能用：纯扫描页 `chars=0`，坏 CID 的页会吐出 `W-tiWlW`、`$n[^I io-5` 这类乱码，PDF 里 `/Font` 对象多寡不能当证据。文本层可用才 grep `例`、`表10-`、`图10-` 定位例题与表格；不可用就整册走 `mdkit.py ocrpdf 书.pdf 首页 末页 输出目录`（macOS Vision OCR，中文识别准）。同一本书两卷可能不一样：实测《机械设计》第10章 PDF 有字但全是 CID 乱码，《机械制图》（331 页 Z-Library 版）是 0 字符纯扫描——每本都要探，不能凭上一本的结果类推。
3. **算式按该章的解题步骤**：顺序见 `references/<book>/chNN.md` 的「解题步骤」，不许跳步（齿轮那种"试算→修正"两遍 K，跳过修正会被一眼看出没按范式）。
4. **查图系数**：见 `references/textbook-chart-reading.md`（扫描图上的曲线要标定坐标读，别估）。
5. **出零件图**：见 `references/gb-gear-drawing.md`（线型、参数表、标题栏、公差、版面）；**A3 单张图与 gbdraw 的坑见 `references/part-drawing-a3.md`**。图要反复改参数就写程序化管线（参数 schema → render → check → PDF/PNG），见 `references/svg-pipeline.md`，别手改坐标。用户甩参考图并说“只改数据”时：抄它的**版式**（视图名写在图下、参数表栏目、直径引线、键槽标法、技术要求措辞、标题栏分格、投影法符号），换**数据**，但**结构形式按本题 d_a 判据**决定；与参考图不一致处主动说明原因并给出改法。
6. **出 PDF**：CDP `Page.printToPDF`，`preferCSSPageSize=true` + `printBackground=true`；A4 用 `@page size:A4`，A4 横放写 `@page{size:A4 landscape;margin:0}` 并置 `paperWidth=11.693, paperHeight=8.268`（A3 横放则 16.535/11.693）。base64 直接写盘。计算书里插横放附图用 CSS 命名页，别转图：`@page figpage{size:A4 landscape;margin:8mm 10mm}` + `.figpage{page:figpage}`，图片给 `max-height:174mm`，否则会溢到第二张横放页。
7. **校验**：`mdkit.py page 图.pdf 输出目录` 把 PDF 逐页转 PNG。**几何校验不调 vision**：`mdkit.py check 图.png --page 297x210 --scan y=85 --scan x=75`，把检出线位与理论值逐条对（齿顶/齿根/孔壁/剖面线范围/端面是否落在 X0、X1）。vision 只在交付前做 1~2 次整页观感确认，只核“有没有压字 / 重叠 / 缺行 / 被裁”；它在缩略图上会编读数（φ25 读成 φ40H11、65 读成 50），数字与线位一律别拿它当依据，读小字用 `region` 裁切。取样时探测列避开中心线（点画线的 dash 会给假读数）、墨量带避开线本身 ±0.4 mm。

## 取值路径（三步，别跳）

1. **有公式库函数 → 直接调**。式号即函数名，数值只信 assert 跑过的结果，不让模型代数。
2. **要条文/符号说明/公式号 → grep OCR 源**（`grep -rn "导程角" raw/sources/` 实测 `0.00s`），命中就 `read_file` 读那一段，引原文时带页码。
3. **要表值/曲线 → 读页图**，见 `references/textbook-chart-reading.md`（坐标标定后按像素读，别估）。

## 章目录（做题前先定位到这一行）

| 章 | 主题 | 公式库（`mdkit/lib/design/`） | 章文件（`references/design/`） |
|---|---|---|---|
| 1 | 绪论 | —（概念章） | `ch01.md` |
| 2 | 机械设计总论 | —（概念章） | `ch02.md` |
| 3 | 机械零件的强度 | `strength_ch03.py` | `ch03.md` |
| 4 | 摩擦磨损及润滑概述 | —（概念章） | `ch04.md` |
| 5 | 螺纹连接和螺旋传动 | `screw_ch05.py` | `ch05.md` |
| 6 | 键花键无键连接和销连接 | `key_ch06.py` | `ch06.md` |
| 7 | 铆接焊接胶接和过盈连接 | `weld_ch07.py` | `ch07.md` |
| 8 | 带传动 | `belt_ch08.py` | `ch08.md` |
| 9 | 链传动 | `chain_ch09.py` | `ch09.md` |
| 10 | 齿轮传动 | `gear_ch10.py` | `ch10.md` |
| 11 | 蜗杆传动 | `worm_ch11.py` | `ch11.md` |
| 12 | 滑动轴承 | `bearing_s_ch12.py` | `ch12.md` |
| 13 | 滚动轴承 | `bearing_r_ch13.py` | `ch13.md` |
| 14 | 联轴器和离合器 | `clutch_ch14.py` | `ch14.md` |
| 15 | 轴 | `shaft_ch15.py` | `ch15.md` |

概念章（1/2/4）无编号公式库，只有术语与关系清单。第 10 章三套范式（直齿/斜齿/锥齿）都在 `ch10.md`。

## 常用校核式
- d_a=d+2m；d_f=d−2.5m；h=2.25m；a=(d₁+d₂)/2；s=πm/2
- 公法线 W_k=m·cosα[π(k−0.5)+z·invα]，k≈z/9+0.5 取整（z=54 → k=7, W=49.86），inv20°=0.014904
- 键槽（GB/T 1095，按孔径查区间，别沿用上一题）：22<d≤30 → b=8、h=7、t₁=4.0、t₂=3.3（φ26 → 毂槽深 29.3）；44<d≤50 → b=14、h=9、t₁=5.5、t₂=3.8（φ50 → 毂槽深 53.8）；d=25 → 28.3。**毂槽深 = d+t₂**，绘图时 `R_KEY = Rw(bore/2 + t₂)`，不是 `Rw(毂槽深/2)`
- 轴径估算 d≥C·∛(P/n)，45 钢 C=112，有键槽再放大并取标准值

## 陷阱（33 条，按主题分两处，别整份读）

原文 33 条一条不删，按「这事该在哪一步想」拆成两份，做题时只读相关那份：

- `references/pitfalls-calc.md` —— **计算 / 取值 / 单位 / 页码** 12 条：题干缺图、角度量纲（`eq10_19` 吃度、同章别的吃弧度）、`inspect.signature` 先于猜式号、T 的 N·m 与 N·mm、查表分类型参数要抄原文、别拿 vision 磨整章页图、页码会漂、动手前先扫库、改一个尺寸连带一整圈、从略要补算、中间量按书位数、参考图结构不照抄。
- `references/pitfalls-drawing.md` —— **出图 / 标注 / 版式 / 校验** 19 条：不许用生图模型画零件图、不引 SVG 库、剖面线不用 `<pattern>`、`fill` 不生效、弧线只发 `<polyline>`、PDF 版面先量再改、check 报警先核口径、参数表不另存数值、「0 处问题」不是依据、全剖视图逐条勾、先写口径断言、口径闸量生成物、分世代、Chrome 打 A3 退回 Letter、尺寸标注五件事、标题栏字不压线、按图题坐标抄版式。

三条最贵的，压在这里当提醒：**量纲混用不报错只出错**；**vision 会编读数，几何与数字一律走坐标/像素/文本**；**同一张图被退两次就停手重排，别 micro-fix**。

## 库的分工

| 路径 | 放什么 | 谁维护 |
|---|---|---|
| `~/Documents/Obsidian/机械知识库/raw/` | 教材 OCR 源 + 页图，**按书写层**：`raw/{assets,sources}/<book>/`（**只增不改**） | 我 |
| `~/Documents/Obsidian/机械知识库/wiki/` | ~~编译产物~~ **已清空，不再生成**（详见下面"不要为查条文去跑编译"） | — |
| `~/Documents/Obsidian/个人知识库/` | **非机械**的一切知识（AI 信息流、视频、读书、决策） | 我，按 `schema.md` |
| `~/Documents/Hermes/Mechanical-Kit/mdkit/`（入口 `~/.hermes/lib/mdkit`） | 公式库 + 工具（**skill 外**，curator 不动，私有 git 仓库） | 我 |
| `~/.hermes/skills/engineering/` | 操作规程 + 章知识 + 书映射 | curator 管，**不放原文/大段知识** |

原 `llm-wiki-desktop` skill 已移到 `~/.hermes/skills-disabled/`（不再进上下文），需要重启时再移回。

## 支持文件

**章知识（做题只读这一章）**：`references/design/ch01.md … ch15.md`，固定结构 = 解题步骤 → 页码↔页图 → 编号公式（式号→函数名→页→页图→状态）→ 表（rows×cols、空格处理）→ 例题逐项对比（书值/库值/偏差）→ 抽查证据 → 交叉验算 → 未核清单 → 查图指引 → 用法代码 → 易错点。

| 文件 | 一句话 | 什么时候读 |
|---|---|---|
| `references/books.md` | 书清单（书名 / 书根 / 章数 / 章映射 / 公式库目录） | **加书只改这里** |
| `references/design/book.md` | 《机械设计》页码映射、偏移（1–7 章 +4、8 章起 +3）、缺页（ch11 缺 p.280）、错位块（287–292）、ch10 未渲染 | 进这本书前 |
| `references/pitfalls-calc.md` | 计算/取值/单位/页码 12 条陷阱 | 列式、取数、写页码前 |
| `references/pitfalls-drawing.md` | 出图/标注/版式/校验 19 条陷阱 | 画图、出 PDF、被退回时 |
| `references/gb-gear-drawing.md` | 齿轮/蜗轮零件图：视图、线型、全剖四类必画线、标注通则、参数表、标题栏、字体、投影法 | 画齿轮类零件图 |
| `references/part-drawing-a3.md` | A3 单张图的版式与 `gbdraw` 的坑（出图前逐条打勾） | 出 A3 图 |
| `references/svg-pipeline.md` | 参数化出图管线：四块 schema、render/check 九项、反向测试、字体落地、SVG→A4 PDF | 参数要反复改 |
| `references/reducer-design.md` | 整机课程设计 11 节骨架、尺寸链闭合顺序、判据、四张示意图、表19-1 三栏 | 减速器设计说明书 |
| `references/calc-book-layout.md` | 计算书排版（教材例题范式）、`mdkit.py book` 链路、`«占位»`、插图链路、像素校验、常见退回点 | 写计算书 |
| `references/drawing-book-ast.md` | 制图库 AST：`图形().加`、图框/标题栏/明细栏/序号已实现、`_tests.py` 运行器、`落图()` 纵横比坑 | 画装配图/明细栏 |
| `references/textbook-chart-reading.md` | 扫描教材曲线（K_v / K_Hβ / K_HN）标定读法 | 查图系数 |
| `references/mech-frame.md` | 说明书插图四件套（轴草图/力学模型/弯矩图/转矩图）的 7 条画法口径 | 画说明书插图 |
| `scripts/verify_drawing_conventions.py` | 口径闸：量生成物 SVG 八条硬判据，非零退出 | 交付前最后一道自动关口 |
| `lib/drawing/charter/check.py` | 出图闸：L0~L3 + 零件层共 46 条规则，一次给通过/不通过/未检查 | 交图前必跑（`--part shaft/gear`、`--calc`、`--fig-no`） |

**工具**（真身 `~/Documents/Hermes/Mechanical-Kit/mdkit/`，入口 `~/.hermes/lib/mdkit`，skill 外共享，私有 git 仓库，改动就 commit）：

- `mdkit.py` —— 统一入口，25 个子命令（`mdkit.py help` 看全；验收/对账的 audit·ranges·missing·state·span·index·numbering 都在里面）；`selftest` 一把过（路径 + 二进制 + 全库断言 + gbdraw）
- `lib/design/*_chNN.py` + `_tests.py` —— 12 个公式库；断言口径以 `mdkit.py test all` 实跑为准
- `bin/` —— `ocrbox`（带坐标 OCR，67 KB arm64）、`ocrpdf`（整册 OCR）、`renderall`、`chmap`、`pdfsplit`、`pdftextlayer` + `.swift` 源码
- `book/book_prepare.py` —— 拆章总控（`--slug` 定落点，`--split-only` 秒级重建）；目录页码在 `--toc` 指定的 json
- `check/` —— `verify_table_cells.py`（表值逐格）、`verify_drawing_lines.py`（像素扫线）、`verify_numbers.py`（答案数字回原文核）、`span_check.py`（跨页判定）、`index_diff.py`（三方对账）、`verify_numbering.py`（式/表/图编号闭环）
- `templates/book/` —— 计算书 Markdown → PDF：`md2html.py` + `book.css`（版式唯一真源）+ `katex_render.js`；`templates/katex/` 自包含
- `draw/gbdraw.py`（GB 图元，1 单位 = 1 mm，`--selftest` 5 项）、`draw/mech_frame.py`（说明书插图，见 `references/mech-frame.md`）
