# drawing · 《机械制图》（丁一、钮志红主编，2012）

这本书是**「怎么画」的权威**，与 handbook（怎么标）、design（怎么算）三分。

## 书源与页码

| 项 | 值 |
|---|---|
| PDF | `~/Documents/机械制图.pdf`，331 页，23 MB，**无文本层**（整本 OCR） |
| 页图 | `~/Documents/Obsidian/机械知识库/raw/assets/drawing/chNN/pNNN.png`，scale 4，238 MB |
| 全章 OCR | `~/Documents/Obsidian/机械知识库/raw/sources/drawing/chNN-全章OCR.md`（11 个） |
| 章节地图 | `~/.hermes/lib/mdkit/books/drawing/章节地图.{json,md}` |
| 图表清单 | `books/drawing/图表清单.json`：440 图 / 31 表 / 49 附表 |
| 页码 | 页眉 `12  第一章 制图的基本知识` → **印刷页 = PDF 页 − 8**，136 页锚点零例外 |
| 章号 | **汉字**（第一章…第九章），`chmap` 的阿拉伯数字正则失效，用 `books/drawing/parse_header_pages.py` |
| 章首页 | 无页眉（标题居中），章界以目录 + `book_prepare` 的 `--toc` 为准；`book_prepare` 的边界复核已支持汉字章号 |

## 结构（9 章 + 附录）

- ch1 制图基本知识 3（**§1-2 图线/图幅/比例/字体**在 p.6）
- ch2–ch5 投影 31–142（平面体、回转体、组合体、轴测）
- ch6 常用表达方法 143（视图/剖视/断面/局部放大/第三角）
- ch7 零件图 174（表达方案、结构分析、尺寸标注、技术要求、读图）
- **ch8 标准件与常用件 221**（螺纹 221、紧固件连接 230、键销 237、齿轮 241、弹簧 246、滚动轴承 250）——`gbdraw` 缺的画法全在这
- ch9 装配图 254（序号标题栏 264、读图 269、拆画零件图 271）
- ch10 附录 282（螺纹 282、标准结构尺寸 286、常用标准件 287、极限与配合 303、金属材料 316、几何公差带 318）——与 handbook 表3/表9 同源，可互校

## 沉淀形态：图元与画法（不是表字典）

`gbdraw.py` 现状（2026-10 盘点）：图元 13 个、线型 6 种（`thick 0.5` / `thin 0.25` / `center` / `hidden` / `wavy` / `phase` 近似的假双折线）、`Sheet` 只有 `add/svg/write/count`。
缺：粗虚线、粗点画线、细双点画线、真双折线；图框/标题栏/明细栏/序号；**全部标准件画法**；剖切符号与剖面符号；工艺流程结构（倒角/退刀槽/越程槽/中心孔/滚花）。

三层交付：
- **L1** 表与图线几何规定 → `lib/drawing/tables/`、`lib/drawing/rules/line_types.json`
- **L2** 画法函数 → `lib/drawing/*.py`，返回 `图形`，**必须**经 `_prim` 的原语（`线/圆/弧/矩形/文/剖面线/尺寸H/尺寸V/引出线/公差框/基准/粗糙度`）
- **L3** 图幅层 → `lib/drawing/sheet.py`（`图框()` `标题栏()` `明细栏()` `序号()`）

## 已就位的接口（Hermes 写，ZCode 不许重写）

- `lib/drawing/_prim.py`：`图形`（elems/注记/bbox）+ `拼()` + `校验图元()` + `落图()`。`校验图元` 拒收非 AST 元素、未知图元种类、`STYLES` 之外线型（手写 `<path>`/`hairline` 直接抛错），双解释器自检通过。
- `lib/drawing/_demo_thread.py`：M12 外螺纹画法样板，**已跑通全链**——SVG → Chrome → PDF → `bin/renderall` → PNG → `verify_drawing_lines.py`。像素实测：大径线 50–95 mm 全长（粗 0.36 mm）、小径线从倒角内侧 52 mm 起（细 0.18 mm），2 : 1 线宽档成立；空白行 0 段（无误画）。
- 出图链模板：`draw/gear_pipeline/build.sh`（`gear_draw.py` 参数化零件图 + 六项几何校验 + `verify_raster.py`）。

## 容易踩的坑

- `bin/pdftextlayer` 对含全角分号/括号的长文件名会报 "could not find"，先 `cp` 成短名再处理；本书文件名里还藏着多余的「, 丁一, 钮志红」，`ls 机械制图*.pdf` 取到再判断。
- 整本 OCR 会出现大量 `Error (…): Unknown segment type in JBIG2 stream`，是 PDFKit 的告警，**不代表页失败**：331 页全部出文本，0 空页，平均 584 字/页。
- `Sheet._y()` 把 y 轴翻转（`y_svg = H − y`），扫像素时要按 `210 − y` 换算，否则会得出「0 段」的假结论。
- 制图书 2012、handbook 2018，同一表对不上时以新为准并写 `E.json`（例：图线标准 GB/T 4457.4 与 GB/T 17450 的分工）。
