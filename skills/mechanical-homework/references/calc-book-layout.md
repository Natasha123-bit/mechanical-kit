# 计算书排版（教材例题范式）

用户拿一份真实例题解答当“格式参考”时，抄的是**版式**不是内容。以下是已经通过的基准（教材作业解答的观感）。

> **样例里不许留某道题的答案数。** 这里原先拿“d_{1t}≥…=52.31 mm”当示范，52.31 其实是某次作业（10-6）的结果，久了自己也分不清“这是模板还是答案”。代入式只写成 `=d_{1t}` 或 `=«结果»` 占位，真实数字由 Python 注入。

## 一、版式基准（逐条照做）

- A4 **纵向单栏**，纯黑字：**没有**卡片、灰底、边框、彩色标签、图标。工程作业不是 PPT。
- 标题**一行居中加粗**：「11-3 普通圆柱蜗杆传动设计」，不加副标题、不写作者日期。
- 「已知：P₁=5.0 kW，n₁=960 r/min，…」**一段正文**（不用表格、不用框）；紧接「解：L_h=8×300×7 h=16 800 h。」开始算。
- 层级只用四种：`（1）（2）…` → `1）2）3）` → `①②③` → `（i）（ii）`。标题加粗但与正文**同字号**，不放大、不加下划线。
- **公式**：独立成行、居中；**代入数值与结果写在同一个式子里**，例如
  `d_{1t}\ge\sqrt[3]{…}=d_{1t}\ \mathrm{mm}`（占位，真数由 Python 注入）；
  **右侧不标公式编号**（(10-11) 之类只在正文里引用“由式（11-11）”）。一条公式一个 div，不要塞回段落里。
- **表格**：纯线表（0.5 pt 全框、表头加粗居中、无斑马纹无灰底），表题在表上方**居中一行**（“表 1　蜗杆、蜗轮几何尺寸”）。几何尺寸用 `名称|代号|计算式|数值` 四列；结论用 `项目|结果` 双栏拼成四列。
- **结尾**：校核处只写短结论句（“齿根弯曲疲劳强度足够。”）；最后「说明」①②③＝强度结论／结构画法依据（GB/T 4459.2、4457.4、1184、1095）／单位与附图。
- **无页眉、无页脚、无页码**。
- 零件图作为**最后一页并进同一个 PDF**，图下写一行：`附图　蜗轮零件图（齿圈式，m=6.3，z₂=46，8 级，A4 横放，1:2.5）`。

## 二、版式与转换（走 `mdkit.py book`）

版式唯一真源是 `~/.hermes/lib/mdkit/templates/book/book.css`（A4、Songti、10.5pt/1.45、`.fm` 公式块、`.cap` 表题、`.5pt` 纯线表）。要改版式改那一份——在作业目录里另抄一版 CSS，结果只会是两处不一样、只有一处生效。

- **`p { break-after: avoid }` 不要加**：它会把段落和后面的公式焊在一起，页面出现 30~45 mm 空洞；防孤行用 `orphans/widows: 2` 足矣。
- `.cap`（表题）要 `break-after: avoid`、`.fm` 要 `break-inside: avoid`，否则表题与表、公式会被分页拆开。
- KaTeX 的 `katex.min.css` + `fonts/` 必须随目录拷贝，HTML 才离线可开（`md2html.py` 自动拷 `templates/katex/`）。
- **公式模板别用 f-string 直写 LaTeX**：`\frac{a}{b}` 的花括号要和 f-string 的转义打架。用占位符替换：
  ```python
def tex(tp, **kw):          # 第一个形参别叫 t —— 会被 t=… 关键字撞上
    for k, v in kw.items():
        tp = tp.replace("«" + k + "»", str(v))
    return tp
fm(tex(r"m^{2}d_{1}\ge«K»\times«T»\left(\frac{480}{«z2»\times«sH»}\right)^{2}=«v»\ \mathrm{mm^{3}}", …))
  ```
  公式先收进 `{id: latex}` 跑 KaTeX 批渲染，正文里放 `@@id@@` 占位，渲染完再替换成 `<div class="fm">…</div>`。
- 数值一律由公式库变量格式化后注入（`n(x, 2)`、科学计数用 `«a»\times10^{5}`），**不在 LaTeX 里手打数字**。

## 三、校验（像素＋文本，不靠肉眼）

1. 打印：`Chrome --headless=new --print-to-pdf=计算书.pdf 计算书.html`（`--no-pdf-header-footer`），再 `mdkit.py page 计算书.pdf png`。
2. 逐页扫墨迹 bbox（PIL，阈值 <160）：
   - 左右必须落在版心内（左 25 mm、右 188 mm）——越界就是公式溢出；
   - 底边留白 = 297 − 最后墨行；**末页留 100 mm 属正常收尾**。判孤行页看末页墨迹底边 **< 60 mm**（版心 25–272 mm）：**先并条删字**——把「说明」里能合并的两条并成一条、删套话，通常一次就回到前一页；压行距（1.45→1.40、`.fm` margin 1.1→0.9 mm）是最后手段，改 CSS 会波及所有页。**加内容同样造孤行**：多写一条说明往往正好把最后一页撑出第三页，先并再补。
3. 表格不跨页：`table{break-inside:avoid}` 后逐页确认表头与表体同页、没有行被切半。
4. 页数用 `mdls -name kMDItemNumberOfPages x.pdf`；`grep -c '/Type /Page'` 会把 `/Type /Pages` 也算进去，多 1。
5. **数字真伪从 `formulas_rendered.json` 剥标签后 grep，别读渲染图**：vision 在 1250 px 下会把 `46` 读成 `16`、把已经贴住图框的参数表说成“有明显空白”。判据排序：像素测量 > 生成文本 > vision。vision 只用来判观感（压字、重叠、缺行、被裁）。

## 四、常见退回点

- 排版像网页（卡片、色块、粗边框）→ 重做。
- 公式右侧带 (11-10) 编号 → 参考件没有，删掉；改成正文“由式（11-10）”。
- 只写公式、代数值另起一段 → 参考件是同一行式子；合并。
- 「已知」做成表格或灰框 → 改正文段。
- 表格跨页、表头与表体分家 → `break-inside: avoid`。
- 末页只剩一行说明 → 按「三、校验」第 2 条并条删字（合并说明条目、删套话），别一上来就改 CSS 行距。
- **用户临时改图上一个尺寸（轴孔 φ26→φ50 这类）→ 图上改了、计算书没改**：那一节要把估算**降格为“强度下界”**（“d≥24.46 mm，计键槽 25.69 mm，为轴孔直径的强度下界；按实际配合的轴径取 φ50 H7，强度裕量充分”），并同步重算依赖项（键槽 b/h/t₁/t₂、毂槽深 d+t₂）。“说明”里也提一句“实际值由配合轴径决定，估算只作校核”。只改图不改书，交付时一核就是“图上 φ50、书上算 φ26”，比初始就取 φ50 还难解释。

## 六、插图链路（md 子集没有图片）

`md2html` 的子集**不支持图片和图题**，但整份说明书不必为此手写成 HTML（手拼 HTML 会漏 `\,`、`\qquadF`）：md 照写公式与表格，图用占位符，转档后替换。已验证的做法：

1. md 里把图独立成段写 `@@FIG1@@`（前后空行）。
2. `md2html.convert(md, html)` 生成 HTML，占位符会变成 `<p>@@FIG1@@</p>`。
3. 把 **SVG 源码原样内联**，不要用 `<img src="figs/fig1.svg">`：
   ```python
   svg = re.sub(r'^\s*<\?xml[^>]*\?>', '', open(p, encoding='utf-8').read()).strip()
   svg = svg.replace('<svg ', '<svg preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto" ', 1)
   block = f'<div class="figwrap">{svg}<div class="figcap">{cap}</div></div>'
   html = html.replace('<p>@@FIG1@@</p>', block)
   ```
   同一份图用 `<img>` 引用时，Chrome 打印会把整页缩到约一半宽、图文并排；内联 SVG 按容器宽排版就正常。
4. 在 `</head>` 前插三行 CSS（不动 `book.css`）：`.figwrap{margin:2.4mm 0 3mm;break-inside:avoid;text-align:center}`、`.figwrap svg{width:100%;height:auto;display:block}`、`.figcap{text-align:center;font-size:9.5pt;margin:1.4mm 0 0;break-before:avoid}`。
5. 替换计数必须等 4 处、打印后再 `mdkit.py page` 回看：图题在图上、图不跨页、`break-inside:avoid` 生效后上一页留白属正常。

图的源文件本身建议同时留 ASCII 名（`fig1.svg`）与中文名（`fig1_传动方案.svg`）：HTML 只引用 ASCII 名，中文名给人看，避免 `file://` 下的 URL 转义问题。

## 五、源文件形态（纯文本优先，别手写标签）

用户问「用 Markdown 出源文件、再转 PDF 行不行」——行，而且这才是该有的形态；但**转档引擎决定能拿到什么**：

- **零安装路线（默认，已落地）**：`mdkit.py book 计算书.md [--pdf]`。实现在 `~/.hermes/lib/mdkit/templates/book/`：`md2html.py`（md 子集解析 + KaTeX 批渲染 + 套 CSS + 拷 katex 目录 + Chrome 打印）、`book.css`（版式唯一真源）、`katex_render.js`；KaTeX 的 node 构建放到 `templates/katex/katex.min.js`（自包含，**不再依赖 `~/.hermes/hermes-agent/node_modules`**，否则 `hermes update`/`npm ci` 会把它清掉）。实测收益不在行数——11-3：389→343 行，因为正文本身就有 250 行；收益在于 md 可读可改、`计算书.html` 降为可删的中间产物、版式只由 `book.css` 决定、公式不再经 f-string 拼接（`\,`、`\qquadF` 这类漏字在 md 结构里根本不会出现）。
- **md 子集与铁律**：`#/##/###`、段落、`$$…$$`、`$…$`、`**粗体**`、`|表|`（第二行必须 `|---|`、列数必须与表头一致）、以「表 n」开头的一段紧贴表格上方即成表题、`<sub>` 等 HTML 直通。违反任一条带行号报错退出，**不静默降级**；`mdkit.py book --selftest` 是 4 个坏样例 + 2 个好样例。写完 md 先跑一次自检，再盯 PDF。
- **TeX 路线**：pandoc + XeLaTeX/ctex（或 tectonic）才有真正的 TeX 排版与分页，公式基线最好；属安装，先征得同意再动。判断标准：作业交付用零安装路线，他说「论文级 / 学院模板」才上 TeX。
- 无论哪条路，**数值永远由 Python 注入**（`«K»` 占位符替换），Markdown 里不出现手打结果——否则改了参数，md 与公式库就此分家，后面的互校全部失效。
- 源文件落盘用 UTF-8 的 `.md`，与 PDF/HTML 同目录；交付时给 PDF，md 作为可改源附带提一句即可。

## 七、md2html 三个会咬人的坑

1. **表格单元格里的反斜杠是转义符**：`md2html.parse` 的 `cells()` 把 `\` 当转义前缀吞掉，所以单元格里写 `$\dfrac{a}{b}$` 到 KaTeX 时只剩 `dfrac`，渲染成字母 d-f-r-a-c，而且**不报错、不残留 `$`**，只有翻 PDF 才看得见。表格单元格内的公式一律双写：`$\\dfrac{...}$`、`$\\times$`、`$\\text{mm}$`。段落里的 `$...$` 不受影响。批量修法：只对以 `|` 开头的行做 `l.replace('\\','\\\\')`，改完必须回读截图确认。表格通常由脚本重写，所以**每次程序化重写表格后都要再跑一遍双写检查**（生成时就直接写双写，别指望事后补）——否则同一份文档会「改好了又复发」，因为新表是另一段脚本生成的。
2. **长表整体不拆会留半页空白**：`book.css` 的 `.tbl{break-inside:avoid}` 让 20 行以上的表整块跳到下一页，前一页底下空三分之一。在 build 脚本注入的 `<style>` 里补 `.tbl{break-inside:auto}` + `.tbl table tr{break-inside:avoid}`（同选择器、后出现者胜），长表按整行跨页，短表照旧不拆。代价是跨页后表头不重复（要重复得改 md2html 加 `<thead>`，别在测试期动套件）。
3. **本机没有 pdftoppm**：`which pdftoppm` 为空、也没装 fitz/Quartz。渲页做像素复核用 Swift + PDFKit 十来行（`swiftc -O` 约 3 s）：`PDFDocument(url:)` → `page.draw(with:.mediaBox,to:ctx)` → `NSBitmapImageRep` 存 PNG，`scale` 传 2 即 2× 分辨率。渲完用 `mdls -name kMDItemNumberOfPages` 或 Swift 打的 pageCount 取页数——**mdls 有缓存，刚覆盖 PDF 时会报旧值**，以实际渲染出的文件数为准。
