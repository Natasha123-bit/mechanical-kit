---
name: mechanical-book-deposit
description: Use when 把整本书或某章沉淀成公式库/画法库，或补章、重跑验收。
version: 2.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [机械设计, 教材沉淀, ocr, 公式库, 章节地图, 补章, 验收, 章知识]
    related_skills: [mechanical-homework, pdf]
---

# 教材沉淀（整本书 → 一章一库）

**低频任务**：一本新书走一次。做题 / 查表 / 画零件图请用 `mechanical-homework`。

产物只有两类，别多产（用户反感文档膨胀）：

1. `mdkit/lib/<book>/<主题>_chNN.py` + `_tests.py` —— 沉淀主体，形态见 §一
2. `references/<book>/chNN.md` —— 章知识（解题步骤 + 式子清单 + 表值 + 例题对比 + 抽查证据）

## When to Use

- 「把《XX》整本沉淀」「整本教材沉淀成公式库」「走上次那套流程」「接上次的沉淀进度」
- 某一章的核读要外包给 ZCode，需要任务书与验收标准
- 新书第一次进场：判要不要 OCR、建章节地图
- **不适用**：单题计算、画零件图、查一个表值 → `mechanical-homework`

开工前只问三件：书 PDF 路径、有没有现成目录 / 章页对照、书短代号（`design` / `handbook` / `drawing`，不给就按书名起）。PDF 已递过来且说「按上次那套流程」时，前两件不用再问。

## 一、先判形态（判错全盘错）

| 形态 | 判据 | 交付物 | 验收靶子 | 样板 |
|---|---|---|---|---|
| **公式型**（教材） | 编号式几十上百条 | 式号即函数名 + 表值 dict + 例题断言 | 双解释器 + 例题全链反算（容差 0.5%） | `lib/design/` 15 章（断言数见状态文件） |
| **表型**（手册、标准汇编） | 表号上百、编号式个位数 | **三层**：L1 表字典（证据）/ L2 判据函数 / L3 标注串 | 逐格 + 抽页图 + 用零件工作图反向复现 | `lib/handbook/` 274 表 / 56,774 格 |
| **图样型**（制图标准） | 图几百张，主体是「怎么画」 | 画法函数 + 图幅层，返回 `gbdraw` AST | 出图 → PNG → 像素扫线 | `lib/drawing/` 10 章 + 附录（134 用例 / 632 断言） |

判据读法：`grep` 整本 OCR 数编号式 `（NN-N）` 与表号 `表NN-N` —— 式号两位数是教材，表号上百是手册。

三条硬话：

- **只交 L1 ＝ 交了 270 个格子**，用户会当场驳回（「不能只是存一大堆表啊」）。L2/L3 的接口由 Hermes 先写好（`_lookup.py` + `_anno.py`），ZCode 只喂表与填判据，不许自创标注写法；接口写完**立刻用书上真值跑一个最小闭环**（3 档表 + 1 个选型 + 1 条标注 + 1 组越界拒绝），把真实输出贴给用户再派活——光给方案会被当成纸上方案。
- **「表多」不等于「表是主体」**：图样型的判据是图，不是表；图样型**禁止手写 `<path>`**，`校验图元()` 会拒收。
- 派活前先问一句「这本书管画、管标、还是管算」：管画的别去做表字典，管标的别去画图。

每本书一份 `references/<book>/book.md`（PDF / 页图 / OCR 路径、页码偏移、缺页与错位块），并在 `references/books.md` 加一行。**书的来源与例外只写这两处，不写进本文件。**

## 二、布局：四层，加一本书只动第 1、2、4 层

| 层 | 位置 | 放什么 | 重建成本 |
|---|---|---|---|
| 原始 | `~/Documents/<书名>.pdf` | 整本书 PDF，唯一原始件 | 不能重建 |
| 证据 | `Obsidian/机械知识库/raw/{assets,sources}/<book>/` | 页图 `chNN/pNNN.png`、OCR 源 `chNN-全章OCR.md` | 半小时以上 |
| 加工 | `mdkit/books/<book>/` | 章节地图、页眉扫描、handoff、进度、验收记录 | 地图重扫 6 分钟 |
| 资产 | `mdkit/{lib,bin,check,draw}/` + `skills/…/references/<book>/` | 公式库、工具、章知识 | **不能**，人工核出来的 |

四条现场规矩：

- **书根不进 `~/Documents/` 根下**：Hermes 项目一律进 `~/Documents/Hermes/`；`raw/` 也要按书加层，否则第二本书的第 8 章会撞进第一本的 `ch08/`。
- **cwd 别用空壳目录**：指 `books/<book>/` 或家目录。空壳被挪走会 `workspace_unavailable`（三种修法见 skill `hermes-agent` 的 `references/turn-forensics.md`，不在本 skill 里）。
- **可重建的派生物用完就删**，判据是**重建成本**不是「派生」：单章 PDF（`prepare --split-only` 秒级）删；页图与 OCR 源（半小时以上）留。
- **解释资产关系给一张图，不要堆数字**：skill = 说明书、mdkit = 工具箱 + 成品、仓库 = 给后者加的历史。三句说完配一张示意图（HTML + `::preview{file=…}`）。

仓库化 / symlink 入口 / 落点先问 / `sync-skills.sh` 单向镜像 / `install.sh` 方向 / 换书根要改四处 —— 全在 `references/version-control.md`，改路径前必读。本机落点已是 `~/Documents/Hermes/Mechanical-Kit/mdkit`（`~/.hermes/lib/mdkit` 只是入口 symlink）；访客机直放 `~/.hermes/lib/mdkit`。改完跑 `scripts/check_paths.py`。

## 三、阶段 0–6（细节在 playbook，这里只给过关判据）

| 阶段 | 做什么 | 过关判据 | 细节 |
|---|---|---|---|
| 0 | 判要不要 OCR（`mdkit.py probe`） | 逐页 `chars=0` / CID 乱码 / 首行不可读 → 走 OCR | `book-deposit-playbook.md` 阶段 0 |
| 1 | 章节地图 + 拆章（页图 + 全章 OCR 源） | 目录页码权威、偏移逐段插值、页数三处对齐 | `book-splitting.md` |
| 2 | 出任务书（一份、可粘贴、无元话） | 骨架 9 节齐、状态词只写「待验收」、批末停手写死 | `dispatch-contracts.md` + `templates/book-deposit-zcode-prompt.md` |
| 3 | 执行（外部 agent 逐章沉淀） | 每章一批、章内不验完不开下一章、概念章出清单不建库 | `book-deposit-playbook.md` 阶段 3–4 |
| 4 | 执行方自检 + 主代理复核 | 双解释器跑 `mdkit.py test all`（覆盖三本书，drawing 走 `_tests.py + test_*.py`；**跑了 0 项断言按失败**，不叫全绿）、断言数与进度表对得上、只增不改 | `formula-library-acceptance.md` |
| 5 | 三关验收 + 留快照 | 三关全过才算「能调用」；快照含章知识副本 | `acceptance-evidence.md` |
| 6 | 收口（索引对账 / 跨页 / 空值 / 签字） | 逐项对一遍计划清单，没做的明写 | `table-index-layer.md`、`books.md` |

## 四、硬规矩（都违反过，别重犯）

1. **不采信自述**：外部 agent 说「已验收 / 已核过」一律当「待验收」；数字自己重算，值自己抽页图核。
2. **状态词只许写「待验收」**；「已验收」是用户专用词，Hermes 也不抢先填。
3. **一批一停，续跑要配套**：发「继续」的同一步必须重启监视器（`--min-batch N+1`）；「停」要机械化写进任务书铁律第一条。
4. **只增不改**：增量/补漏的判据是 `git diff -U0 | grep -c '^-[^-]'` 为 0；启用类改动（删「未数字化」常量）改用白名单逐行归类。
5. **状态真相只有两个文件**：`books/<book>/沉淀进度.md` 与 `_批队列.md`；记忆里只留指针、不写章数。签字一次落五处，且**不回改验收记录正文**，只在末尾补记。
6. **计划变更三处同改**（任务书批次表 / 进度表批次栏 / `_批队列.md`），挪出原批的章要把差额写死——悬空缺口会在收官时才被翻出来。
7. **共享件（`_lookup` / `_anno` / `_prim`）验收后再改**：改前记 `契约变更.md`，改后跑全部断言 + 区间探针。跑批期间不动对面正在 import 的文件。
8. **数字只做量级参考**：某本书的表数、断言数、签字状态以 `books/<book>/` 那两个状态文件和 `验收记录.md` 为准；引用前先读。
9. **文档整理只搬家、不改写**：多份批验收合并成一份时用脚本逐字搬（搬完断言原文能在目标文件里原样找到），删源前先 grep 确认引用已全部改指向；**证据正文（验收记录 / 快照 / 报告）永不回改**，订正只写在末尾补记——所以被证据引用过的文件名（`draw/batch2/`、`编号一致性.py`）不要为了整齐去改名，改名就是死链。

## 五、支持文件

| 文件 | 一句话 | 什么时候读 |
|---|---|---|
| `references/book-deposit-playbook.md` | 阶段 0→6 全流程 + 逐章沉淀 8 步 + 「不要为查条文跑编译」 | 新书第一次进场、从头带一本书 |
| `references/book-splitting.md` | 拆章：目录/页眉分工、偏移插值、错位块、命名约定、手册类专用链、OCR 分工 | 做阶段 0–1 |
| `references/dispatch-contracts.md` | 任务书骨架 9 节 + 14 条硬条款 + handoff schema + 纯追加/白名单 + 派活前的图号页范围核对 | 写任务书、派活前 |
| `references/sedimentation-delegation.md` | 子代理分工（上限 7）、角色表、handoff JSON 字段、验收三关 | 设计分批与角色 |
| `references/acceptance-evidence.md` | 验收三关细化、逐格对账、页图抽核、像素判读、合并格、同源盲区、快照 | 验收前必读 |
| `references/formula-library-acceptance.md` | 四类证据、偏差归因、表值 OCR 伪影、图上系数落库约定 | 公式型/曲线类验收 |
| `references/table-index-layer.md` | 查询层坍陷四类、索引 A/B 两层、三方对账、跨页判读 | 收官与「查得到吗」类问题 |
| `references/batch-operations.md` | 跑批监控、额度两线、并发波次、ZCode CLI/provider、批次授权、报进度、签字、单价工期 | 派活与盯批 |
| `references/version-control.md` | 仓库落点与两种形态、入库判据、镜像契约、新机恢复、公开版 | 动路径/仓库/安装 |
| `references/books.md` | 已进场书的索引（形态 / 状态 / 详情） | 加书、开场定位 |
| `references/<book>/book.md` | 单本书的书源与例外（偏移、缺页、错位块） | 进某本书前 |
| `references/<book>/chNN.md` | 章知识，一章一文件 | 做题侧也会读它 |
| `templates/book-deposit-zcode-prompt.md` | 可粘贴任务书模板（改 4 个占位符） | 派活 |
| `templates/验收记录骨架.md` | 单批验收记录骨架（收官合并成 `验收记录.md`） | 验收收尾 |
| `scripts/audit_handoff_vs_lib.py` | handoff ↔ 库逐格对账 | 第二关 |
| `scripts/scan_missing_cells.py` | 空值且无 merges 的格（抓同源漏读） | 第二关 |
| `scripts/check_lookup_ranges.py` | 区间行标签能否按数值查（探针 + µs） | 每章验收 |
| `scripts/verify_book_state.py` | 文档 ↔ 磁盘对账（快照/断言/状态/契约/raw） | 用户问「做到哪了」 |
| `scripts/handbook_scan.py` | 无页眉手册：页脚造伪 chmap + 表号归集 | 手册类阶段 1 |
| `scripts/check_paths.py` | 路径迁移自检 | 改路径后 |
| `scripts/verify_install.sh` | 落点与可达性一次验完 | 搬家 / 换机 |
| `scripts/watch_batch_run.py` | 跑批监视器（信号 / 额度 / 两线 / 卡死 / 推送） | 盯批 |
| `mdkit.py` | 工具根统一入口，25 个子命令：读库 `list/lib/test`，扫描拆章 `ocr/probe/page/ocrpdf/chmap/split/prepare`，验收对账 `check/tables/numbers/audit/ranges/missing/state/paths/span/index/numbering/handscan`，排版 `book`，自检 `path/selftest` | 任何工具调用先看 `mdkit.py help` |
