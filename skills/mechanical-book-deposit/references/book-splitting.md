# 扫描教材：按章拆分与验收

适用：一本几百页的扫描教材（无可用文本层，或文本层是 CID 乱码），要拆成单章 PDF + 页图 + 全章 OCR 源，供后续逐章沉淀/查表。工具全在 `mdkit`（`~/.hermes/lib/mdkit/`）：`bin/chmap` + `bin/pdfsplit` + `bin/renderall` + `bin/ocrpdf`、`book/book_prepare.py` + `book/book_toc.json`；统一入口 `mdkit.py`（首次调用自动 swiftc 编译）。

## 1. 三条命令

```bash
MK=~/.hermes/lib/mdkit/mdkit.py      # 首次调用自动 swiftc 编译所需工具

$MK chmap "<整本.pdf>" -o ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl     # 406 页约 6 分钟
$MK prepare --book "<整本.pdf>" --chmap ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl --report-only
$MK prepare --book "<整本.pdf>" --chmap ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl \
    [--only 5,8] [--skip-existing] [--split-only] [--no-ocr]
```

`--report-only` 只打印章节地图（秒级），**先看地图再拆**：宁可在这一步改 `book_toc.json`，也不要在 800MB 页图跑完才发现边界错。

## 2. 边界的定法与算法

- **目录页是权威**：`book_toc.json` 的 `printed_start` 必须从教材「目录」OCR 里抄（`ocrpdf book.pdf 1 18 outdir`），人工核一遍再填。章首页没有页眉，靠页眉找章号必然漏掉章首那几页。
- **页眉只用来标定偏移**：`chmap` 每页给「第N章 + 印刷页码」，用于算 `偏移 = 书内页 − 印刷页`。
- **偏移不是全书常数**：扫描件中间掉一页，前段 +4、后段就成 +3。`book_prepare.py` 的做法可复用：
  1. 取所有 `(pdf, printed)` 对，只留 `2 ≤ pdf − printed ≤ 5` 且 `printed` 严格递增的（单页 OCR 误读会造成整段漂移，必须过滤）；
  2. 锚点之间线性插值出逐页印刷号，首尾按最近锚点偏移外推；
  3. 按目录把印刷号归章，连续同章的页合成一段 → 就是章范围。
- **章末错位块**：扫描件偶发「篇首页/下一章章首页/某正文页各重复一次，中间夹着上一章的尾巴（如习题页）」。症状是章页数比目录多出几页、且尾部页眉页码回跳。处理：`book_toc.json` 里给该章加 `exclude_pdf: [...]`，把重复块剔出；被夹在里面的真页（习题页）用 `pdfsplit` 单独抽成 `chNN-补页-xxx.pdf`，页图补进 `assets/chNN/` 的下一个序号。
- **文件里没有的章**：`book_toc.json` 里标 `in_scan: false`，`book_prepare.py` 自动跳过（多篇书的 PDF 常只含前几篇）。

## 3. 验收（必做，十来分钟，别省）

1. **与已知手工拆分对齐**（最硬的证据）：若手上已有某一两章手工拆的 PDF，比对「页数」+「首页 OCR 首行」。本书 201–254 拆出 54 页、255–286 拆出 32 页，与手工件逐页一致 —— 这一步通过，说明整套边界与偏移可信。
2. **逐章自动化断言**（一次脚本看全部）：
   ```python
   secs = re.findall(r"^## p\.(\d+)", txt, re.M)
   assert len(secs) == c["pages"]              # OCR 段数 == 地图页数
   assert f"第{c['ch']}章" in 首段正文           # 首段就是该章章首页
   ```
   章名逐条打印出来目检，错误一眼可见。
3. **抽样视觉**：抽一章的 `p001.png` 给 vision，确认是章首页、正文与表格清晰、无裁切。
4. **页数三处一致**：`章节地图.json` 的 `pages`、`mdls -name kMDItemNumberOfPages` 的 PDF 页数、`ls assets/chNN | wc -l` 的页图数。

## 4. 命名与格式约定（下游全靠它，别自创）

| 产物 | 路径 | 规则 |
|---|---|---|
| 章 PDF（临时） | `<workdir>/_split/chNN-章名.pdf` | NN 两位，章名取教材原词；渲完页图即可删，`--split-only` 随时重建 |
| 页图 | `机械知识库/raw/assets/<book>/chNN/p001.png…` | **三位零填充**，`p{k}` = 该章第 k 页 |
| 全章 OCR | `机械知识库/raw/sources/<book>/chNN-全章OCR.md` | 每页一段 `## p.印刷页（章内第 k 页，chNN/p{k:03d}.png）` |
| 地图 | `~/.hermes/lib/mdkit/books/design/章节地图.{json,md}` | 章 / 书内页 / 印刷页 / 页数 / 偏移 |
| 勘误 | `~/.hermes/lib/mdkit/books/design/章节地图.md` | 缺页、错位、未收全、偏移跳变 |

OCR 源里公式体和表体必坏（实测残迹如 `dm'z3`、`op-L53KT2`），所以每个 `## p.` 段都要能被定位回页图；下游沉淀只允许从页图核公式与表值。

## 5. 交付时必须写「勘误」

地图只写页码范围不够。缺页（印刷页跳号）、错位块、章首页缺失、章被截断、整篇不在文件里——**这几类都要在勘误文件里写清楚，并标「正常现象，不是拆分错」**，否则接手的人或子代理会当故障排查半天，或者反过来把缺页当正常继续做。

勘误必须由**生成脚本**写进 `章节地图.md` 末节（`book_prepare.py` 里的 `ERRATA` 常量），不要手工往生成的文件里加：`--report-only` 每次运行都会重写这个文件，手工补的内容下次重跑就没了；勘误也不该另立第二个 md，否则两处描述迟早不一致。

## 6. 工具坑

- `renderall` 的输出名必须零填充（`p%03d`），否则 `p1.png … p10.png` 排序错乱，而 OCR 源里写的是 `p001.png`，下游按名字取图会取不到。
- OCR 逐页文本**首行常常是空的**（页眉识别在第二行）。想核对页码用 `grep -m1 -E '第N章|[0-9]{3}'`，别用 `head -1`。
- 一次性探测脚本写成 `scratch/xxx.py` 再 `/usr/bin/python3 scratch/xxx.py` 跑；在 terminal 里塞 `<<'PY'` 多行 heredoc，引号一嵌套就容易卡到超时。
- `chmap` 用 `.accurate` + scale 4（`.fast` 认不出小号页眉中文），代价是 406 页约 6 分钟；这条只在拆书时跑一次，值得。
- `页眉扫描.jsonl` 要落在持久目录（如 `~/.hermes/lib/mdkit/books/design/`），别放 scratch——scratch 24h 自动清理，补拆一章时就没缓存了。

## 7. 没有「第N章」页眉的书（手册类，实测《机械设计课程设计手册》第5版）

`chmap` 只认页眉里的「第N章」+ 行尾页码。手册类扫描件常常**整本没有页眉**，页码只在页脚（形如 `•56•`），
此时 `chmap` 输出会全军 `ch:null, printed:null`，跑 6 分钟白费。判据：开跑前 OCR 一页正文，看第一行是不是「第N章」+章名；
不是就换下面这条链：

1. **整本逐页 OCR 一次**：`bin/ocrpdf <整本.pdf> 1 <总页> _full_ocr`（330 页约 6 分钟，`p%03d.txt` 一页一个）。
2. **抠页脚页码造伪 chmap**：
   ```bash
   python3 scripts/handbook_scan.py footer _full_ocr -o books/<book>/页脚扫描.jsonl
   ```
   它从每页末尾两行抓 `[•·]\s*(\d{1,3})`（尾部标点可能是 `．。，`，正则别要求数字结尾），
   产 `{pdf, printed, head, flag}` 的 jsonl，并顺手打印**偏移众数**与跳号/回跳页。
   `book_prepare.build()` 只用 `pdf` / `printed` 两个字段，`ch` 留空即可。
   同一脚本的 `tables` 子命令把每页正文的 `表N-x` 按章归集，出 `表清单.json` 当派活清单（见下第 7 条）。
3. **偏移用众数而不是写死区间**：锚点过滤改成「全书偏移众数 ±2」。手册类偏移可能到 +12，写死 `2 <= pdf-printed <= 5` 会把锚点全丢掉，地图直接空。
   改完必须拿老书跑一遍 `--report-only` 与既有 `章节地图.json` **diff 到一字不差**再收工。
4. **复用那份 OCR 组装章源**：`book/assemble_sources.py 章节地图.json _full_ocr <sources>/<book> --slug <book> --chmap 页脚扫描.jsonl`，
   格式与 `book_prepare` 完全一致；`book_prepare` 用 `--no-ocr` 只拆章 PDF + 渲页图，别让它按章再 OCR 一遍（白花 20 分钟）。
5. **逐章核对章首页**：伪 chmap 只能给页码，章号得自己验——每章 `start` 页 OCR 首行应当是「第N章 章名」，不是就说明目录页码错。
   实测本书目录写第15章起于 p.207，实际章首页在 p.208（目录把 207 给了上一章的续表）。
6. **页脚页码读不到是常态**：章首页、整页图表页没有页脚，330 页里有 46 页读不到，别当缺页；靠恒定偏移推出后与章首页标题对齐即可。
7. **表清单的 `pages` 是「出现页」，不是表头页**：按 `表N-x` 扫正文，正文引用处（「见表6-1」「表6-1 续表」）也会被收进来，一张 2 页的表可能列出 7 页；还有十几个表号是「正文引用但表体在别章/纯文字说明」，会显示「无页」。
   派活时必须写明这一点，让执行方**回页图核起始页**、把差异写进 `00-清单.json`，否则它会按清单第一页去切表，整张表从中间开始错。

---

## OCR 分工（谁都能做，不必 Hermes 亲自）

> 自 `SKILL.md` 下沉（2026-10-26 文档整理，正文未改）。

- `mdkit/bin/ocrbox` 是 **67 KB 独立 arm64 二进制**（Apple Vision 封装），只依赖 macOS，无 Hermes 依赖：任何有 shell 的 agent（ZCode 子代理也行）直接 `./ocrbox 某页.png` 就出 `x y w h 文本`，再按 y 聚行即可当表用。
- 批量转文字（整册 406 页、一页 3~5 s）必须交给脚本，不能交给模型逐页抄：LLM 抄书慢、贵、每次输出还不同，无法复现和 diff。
- 模型视觉只用在难处：表格窄列、乱码公式、被 OCR 并成一个 token 的相邻数字。ZCode 的 handoff JSON 里 `"how": "vision"` + `"png": "p017.png"` 就是它自己看图的记录，说明它具备这个能力。
- 所以正确分层是：**脚本出全量文本 → agent 视觉补难格 → 验收再用脚本逐格比 + 抽查页图**。若重做全书 OCR，让 ZCode 跑 `ocrbox` + `book_prepare.py` 完全可行，前提是先验一条它能否真执行 shell（未验证项）。

---

## 整本书拆章（第 0 步：把"翻书"变成查表）

> 自 `SKILL.md` 下沉（2026-10-26 文档整理，正文未改）。

单章 PDF 可以按章拆，不要手工翻整本。工具在 `mdkit`（`~/.hermes/lib/mdkit/mdkit.py`），三步：

```bash
MK=~/.hermes/lib/mdkit/mdkit.py
# 1) 页眉扫一遍整本书 → 每页的「第N章」+ 印刷页码（.accurate，406 页约 6 分钟）
$MK chmap "/path/to/整本.pdf" -o ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl
# 2) 用教材目录页码（mdkit/book/book_toc.json，已人工核过）+ 页眉偏移 → 章节地图；只打印不落地
$MK prepare --book "/path/to/整本.pdf" --chmap ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl --report-only
# 3) 真的拆：章节 PDF → 页图(scale 4) → 全章 OCR 源
$MK prepare --book "/path/to/整本.pdf" --chmap ~/.hermes/lib/mdkit/books/design/页眉扫描.jsonl \
    [--only 8,9] [--skip-existing] [--split-only] [--no-ocr]

# 本书已经拆完（2026-10-20）：15 章 PDF + 13 章页图/OCR 都在盘上，别重跑；补章用 --only。
```

产物：`~/.hermes/lib/mdkit/books/<book>/章节地图.{json,md}`、`_split/chNN-章名.pdf`（临时）、
`机械知识库/raw/assets/<book>/chNN/p001….png`（三位零填充）、`raw/sources/<book>/chNN-全章OCR.md`（每页 `## p.印刷页`）。

**必须知道的坑（都踩过）**：
1. **偏移不是全书常数**：本扫描件第 1–7 章是「书内页 = 印刷页 + 4」，第 8 章起变成 +3（扫描中间少了一页）。别拿一个偏移算到底，`book_prepare.py` 是按页眉逐段插值的。
2. **章首页没有页眉**（只有大号章名），所以章节边界靠**目录页码**定，页眉只用来标定偏移；边界页要在页图上看一眼确认。
3. **目录页才是权威**：`book_toc.json` 的数字来自 `目录` 页 OCR，改版/换书必须重新读目录，不要沿用。
4. **这本 PDF 只有第一至四篇**（第 1–15 章），扫描止于印刷页 403，第 15 章「轴」没收全；第 16–18 章（弹簧/机座/减速器）不在文件里。拆分时 `book_prepare.py` 会自动跳过 `in_scan: false` 的章。
5. **章末可能夹着错位块**：扫描件会把「篇首页 / 下一章章首页 / 某正文页」各重复一次，中间还夹着上一章的尾巴（例如第 11 章习题页被塞在第 12 章章首页之后）。症状是章页数比目录多、尾部页码回跳；处理是 `book_toc.json` 给该章加 `exclude_pdf` 剔掉重复块，再把夹在里面的真页单抽成 `chNN-补页-xxx.pdf`。
6. **拆完必须验收，不要看地图就算完**：先与手上已知的手工拆分对齐（页数 + 首页 OCR 首行），再逐章断言「OCR 段数 == 地图页数 且首段含第N章」，最后页数三处对齐（地图 / `mdls kMDItemNumberOfPages` / `ls assets | wc -l`）。整套验收步骤、边界算法与命名约定见 `references/book-splitting.md`。
7. **`--report-only` 不是只读，生成文件里的手写勘误会被下一次重跑抹掉**：它照样重写 `章节地图.{json,md}`。表格由脚本生成，但事后实测补的边界勘误（第4/5、7/8、13/14 章实测比目录窄这类）如果只写在 md 里，`prepare` 一跑就静默丢失。规矩：**勘误一律回写进 `book_prepare.py` 的 `ERRATA` 常量**，改完重跑 `--report-only` 用 `diff` 确认「只剩预期差异」，不要手工维护生成文件的正文。
