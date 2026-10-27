# `lib/drawing/` —— 工程制图书那套图面 AST（图框 / 标题栏 / 明细栏 / 序号 / 整页组装）

`mdkit` 里有**两套互不相通的出图体系**，开工前先认准要走哪套，别混着拼：

| | `lib/drawing/`（本条） | `draw/gbdraw.py`（`references/svg-pipeline.md`） |
|---|---|---|
| 做法 | 先建 `图形()` AST，再 `落图(g, path, W, H)` 一次性导出 SVG | 直接 `Sheet/L/T/ARROW…` 拼 SVG 字符串 |
| 擅长 | 图框、标题栏、明细栏、序号、件号表、装配图整页、投影关系校验 | 零件图/示意图的具体轮廓、剖面线、尺寸标注 |
| 断言 | `lib/drawing/_tests.py`（自带运行器） | `*_tests.py`（自有框架）+ 像素探针 |
| 谁在用 | `设计测试/图纸/*.py` 里的成品零件图是 gbdraw 路线；装配图整页走这条 | |

## 一、先查库里有没有，别从头画

`lib/drawing/` 已经验收过的能力（用 `search_files(pattern="^def ", path="lib/drawing")` 扫一遍即可，别信笔记）：

- `sheet.py` —— `幅面()` / `图框(幅面, 比例, 装订边, 横放)` / `标题栏(...)`，A3 左装订时标题栏原点 **(235, 5)、尺寸 180×56**
- `assembly.py` —— `序号(编号, 起点, 终点, 形式)` / `明细栏(件表, x, y, 完整)` / `装配结构()` / `滑动轴承装配图()` / `拆画泵体零件图()` / **`装配图一页()`**

待办或旧笔记里写「明细栏/序号 未做」是**过期信息**——动手前先扫一遍确认，别按笔记重写一遍。

## 二、`装配图一页()`：整页版式与四条闸

```python
from lib.drawing import assembly
from lib.drawing._prim import 落图

g = assembly.装配图一页(
    视图=assembly.滑动轴承装配图(),          # 原点随意，函数会平移居中
    件表=[dict(序号=1, 代号="", 名称="轴承座", 数量=1, 材料="HT150", 单件="2.10", 总计="2.10")],
    序号表=[],                               # 视图自带序号时留空，否则双重编号
    件名="滑动轴承", 图号="ZQ-01", 比例="1:1", 幅面="A3", 装订边="左",
    单位名称="…", 设计="…", 日期="2026.10.26")
print(落图(g, "out.svg", 420, 297))          # 单位 mm，A3 横放 420×297
```

版式（`g.参数` 里能复查）：标题栏贴图框右下角；明细栏紧贴标题栏上沿、同宽 180、**表头在上、数据行自下而上**（序号 1 在最下一行）；空白区是 L 形两个候选（栏块左侧全高 / 栏块上沿以上全宽），取面积大且装得下的那个，视图平移后在其中居中。

四条版面闸（任一不过直接 `ValueError`，不出半张图）：视图必须整个落在空白区内；件表序号集合 == 图上序号编号集合；编号不重复；序号引线不越图框、不压标题栏/明细栏。

## 三、陷阱

- **视图若自带序号，就别再传 `序号表`**：书目图例函数（如 `滑动轴承装配图()`）本身带 1~5 号件号，再叠自己的 `序号表` 就是同一张图两套编号，页码上看着像重号。要么只传 `件表`（让书图自己的号对明细），要么换一个无号视图。
- **明细行数会吃掉视图空间**：明细栏高 = 表头 14 + 7×行数，从标题栏上沿往上长；行多到一定程度只剩左边那条带，视图还放不下就直接报错——报错信息里有「可用区 W×H」，照它缩比例或减行。
- **别拿 qlmanage 的 PNG 做 mm→px 标定**：`qlmanage -t` 一律出方形画布、内容居中留白，按图宽算比例会整体偏大（拿它当标定基准，边距、字宽全错）。要正确纵横比就用 `"$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing" --headless=new --screenshot=a3.png --window-size=1680,1188 file://$PWD/装配图A3.svg`（1680:1188 = 420:297）。
- **A3 PDF 不能直接对 SVG 打印**：`chrome --headless --print-to-pdf=out.pdf file://…/x.svg` 会退回 **Letter（612×792 pt）**，整张图的「mm」就全作废。包一层 HTML 再打：`<style>@page{size:420mm 297mm;margin:0}html,body{margin:0}img{display:block;width:420mm;height:297mm}</style><img src="x.svg">`，然后 `--headless --no-pdf-header-footer --print-to-pdf=out.pdf file://…/_print_x.html`；打完回读 `strings out.pdf | grep MediaBox` 核尺寸（A3 横放 = `[0 0 1191.12 841.92]`）。

## 四、测试运行器（不是 pytest）

```bash
/usr/bin/python3 lib/drawing/_tests.py     # → 通过 134，失败 0；断言 632 条
```

- 用例文件 `lib/drawing/test_<主题>.py`，函数名 `test_*`，**失败用裸 `assert`**（运行器靠 assert 计数）。
- 本机没装 pytest，**不许 `import pytest`**（会在运行器里直接炸）；期望抛错写成小工具函数：

```python
def _应抛ValueError(fn):
    try: fn()
    except ValueError: return True
    return False

assert _应抛ValueError(lambda: assembly.装配图一页(件表=[dict(序号=1)], 序号表=[]))
```

- 负向用例要**顺着闸门走**：想测「件表与序号集合不一致」，坐标就必须先合法（如 `(100,150)→(120,170)`），否则先被「引线越图框」拦下，测试绿了但测的不是那条规则。
- 测「视图放不下」时别靠行数硬堆——直接搭一个超尺寸视图（`图形().加(矩形(0,0,400,260,"thick")).范围(...)`）最稳。
