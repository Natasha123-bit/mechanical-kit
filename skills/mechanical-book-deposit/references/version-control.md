# mdkit 的版本管理（git 仓库化）

适用范围：给 `~/.hermes/lib/mdkit` 这套沉淀资产做备份、回溯、迁移，以及向用户交代「仓库在哪、装了什么」。

## 1. 落点：作者本机真身在 `~/Documents/Hermes/Mechanical-Kit/mdkit`；访客/新机直放 `~/.hermes/lib/mdkit`

**两种布局，别混用。** 用户本人的心智模型是「项目 = `~/Documents/` 下的一个文件夹」（`Codex/`、`DSH-Default/`、`Zcode_Project/`、`deepseek-harness/` 都这样放，Hermes 相关的一律进 `~/Documents/Hermes/`）。他自己的机器上才用「真身放项目目录 + `.hermes/lib` 留入口」，图的是作为开发者管起来方便。**别人安装不该继承这套**——访客直接 `git clone` 到 `~/.hermes/lib/mdkit`，真身就在标准位置，不建任何链接。

| 布局 | 真身 | 运行时入口 | 要改的引用 | 可逆 |
|---|---|---|---|---|
| **作者本机（项目化）** | `~/Documents/Hermes/Mechanical-Kit/mdkit` | `~/.hermes/lib/mdkit` → symlink（56 字节） | 0（symlink 透明） | 删链接、搬回 |
| **访客 / 新机（标准）** | `~/.hermes/lib/mdkit` | 同名，无链接 | 0 | — |

**先一行报位置，别先建。** 内容固定三样——根在哪、新建了哪几项、原有文件是否零改动（附 `stat -f "%Sm %N"` 证据）；再给可逆路径。他自己会说要不要换地方，一句就够。（本轮教训：没问就原位 init，他的反应是「我还什么都不知道呢你就给建好了」。）

首提交实测（两种形态都一样）：**1085 文件 / 11.3 MB / 229,220 行**，`.git` 6.8 MB，工作区 47 MB（含被 ignore 的 29.5 MB 渲染图）。
2026-10-26 现状：**1,216 文件 / 66 MB 工作区 / `.git` 10 MB**（新增了 handoff、20 份章知识、templates/katex）。

## 2. 什么入库、什么不入库

判据只有一条：**重建成本**。分钟级能重出的不入库，人工核出来的必须入库。

| 入库 | 理由 |
|---|---|
| `lib/<书>/` 公式库、表字典、`_tests.py` | 人工核出来的，丢了重核几十小时 |
| `books/<书>/` 章节地图、handoff、`验收记录.md`（旧书曾按批分 `批N-验收.md`）、`批N-快照.sha256`、`章知识/` | 证据链，用来回头证明「这一格当时核过」 |
| `bin/` + 同名 `.swift` | 6 个 arm64 工具与源码（464 KB） |
| `draw/` 的 `gbdraw.py`、各章 `build.sh` / `chNN_figures.py` / `verify_all.py` | 出图管线源码，产物是派生物 |
| `templates/katex/` | 离线渲染依赖（js/css + 60 个字体文件，1.4 MB），没网也要能出 PDF |
| `skills/` | 两个 mechanical skill 的镜像，见第 3 节 |

`.gitignore` 只有这几条，**不要扩大**：

```gitignore
__pycache__/
*.pyc
.DS_Store
draw/**/*.png
draw/**/*.svg
draw/**/*.pdf
draw/**/*.html
draw/**/*.log
books/**/_split/
```

- `draw` 的图：单章 `build.sh` 约 3 分钟重出（`RESULT: PASS` 可验），实测被排除 29.5 MB。
- `_split/`：`book_prepare.py --split-only` 秒级重建。
- **不要写成全局 `*.png` / `*.pdf`**：`templates/` 与未来入库的图表资源会被误伤，忽略规则按目录限定。

页图与 OCR 源不在本仓库，在 Obsidian vault 的 `机械知识库/raw/{assets,sources}/<书>/`——那是另一份资产（重渲 + 整册 OCR 半小时以上），单独备份，别为了「一个仓管全部」把它们拉进来：vault 是数据仓，仓库是代码/证据仓。

## 3. skill 侧：单向镜像，不是软链

```bash
cd ~/.hermes/lib/mdkit
./sync-skills.sh              # 只同步 + 打印 git status
./sync-skills.sh "批6验收"     # 同步 + 提交
```

- 方向固定 `~/.hermes/skills/engineering/{mechanical-book-deposit,mechanical-homework}` → `<仓库>/skills/`，`rsync -a --delete --exclude .DS_Store`。
- 原位是权威（Hermes 加载的是它），`skills/` 是快照；**不要手改 `skills/` 里的文件**，下次同步会被覆盖。
- **作者本机别用 `install.sh` 装 skill**：它的方向是「仓库快照 → Hermes」，而作者本机的真身可能比快照新，装一次就回退一次。`install.sh` 已对此设护栏——检测到「克隆不在标准位置」就跳过 skill 安装并提示用 `sync-skills.sh`；确要覆盖得显式加 `--force-skills`（在作者本机等于自毁，别加）。
- 为什么不用软链把 skill 目录指到仓库：技能发现走 `rglob("SKILL.md")`，`skills_tool` 明确守卫「SKILL.md 指向 root 之外」的情况，`credential_files` 见到 skills 树里的 symlink 会去造临时副本。软链结果是不确定与降级，不是「同一份文件」。**能搬的只有 mdkit，skill 目录永远留原位**——这也是「项目化」时唯一不能动的部分。
- 为什么值得镜像：curator 会高频 patch skill（`skills/.curator_ledger.jsonl` 里 mechanical 两个已 200+ 条），此前没有任何文本历史。同步后 `git diff skills/` 就是「后台改了什么」的账。**curator 也会把当轮的操作写进 skill**（本轮它自己产出了这份文档的初版，并把未经用户确认的「原位 init」写成了规矩）——所以发现 skill 里出现自己刚做、但用户还没拍板的决定时，按用户口径改，别当既定事实沿用。

## 4. symlink 入口的实测行为（真身在 Documents 时用）

在 scratch 里建同构样本实测（`ln -s <真身> <入口>`），结论：

| 操作 | 结果 |
|---|---|
| `cd <入口> && cat` / `pwd` | ✅ 正常，`pwd` 显示入口路径 |
| Python import（`Path(__file__).resolve().parents[2]`） | ✅ 正常，`__file__` 解析成真身路径，自算的根仍对 |
| `git -C <入口> add/commit/log` | ✅ 正常，工作区就是真身 |
| `rsync -a <入口>/ dest/` | ✅ 复制内容（不是复制链接） |
| `find <入口> -name "*.py"` | ❌ 一个不返回（要 `find -L`） |
| `du -sh <入口>` | ❌ 显示 `0B`（要 `du -L`） |
| `tar -cf` | ❌ 存成链接条目（要 `tar -h`） |
| `hermes backup` | ❌ 不收录：源码 `os.walk(..., followlinks=False)` 两处 |

判据：**运行时全部透明，盘点/打包类工具默认不跟随。** 所以搬完要交代一句「mdkit 不再进 `hermes backup`，它的备份交给 Documents（Time Machine / 手动拷贝）」。断链报错是直白的 `No such file or directory`，真身在 Documents 里无损，一条 `ln -s` 恢复。

## 5. 常用核对

```bash
cd ~/.hermes/lib/mdkit
git config core.quotepath false   # 中文路径（章知识/）不转义，日志可读
git log --oneline --stat -1
git status --porcelain --ignored | grep '^!!' | wc -l   # 应只列产物
git ls-files | awk -F/ '{print $1}' | sort | uniq -c     # 各目录入库文件数
diff -r --exclude .DS_Store ~/.hermes/skills/engineering/mechanical-homework skills/mechanical-homework
python3 mdkit.py test all          # 0.6s，design 章库全绿，证明入库没破坏导入
```

汇报给用户时给三样：仓库绝对路径、新增项清单（`.git` / `.gitignore` / `README.md` / `sync-skills.sh` / `skills/`）、以及「原有文件 mtime 一个没变」的证据（`stat -f "%Sm %N"` 几个代表文件 + `find -newermt <今天>` 只命中新建项）。用户要的是「你没动别的东西」这句话的证据，不是自我声明。

## 6. 新机恢复

```bash
mkdir -p ~/.hermes/lib
git clone git@github.com:Natasha123-bit/mechanical-kit-dev.git ~/.hermes/lib/mdkit
cd ~/.hermes/lib/mdkit && ./install.sh
```

标准布局下真身就在 `~/.hermes/lib/mdkit`，`install.sh` 只做一件事：把 `skills/*` 装进 `~/.hermes/skills/engineering/`，然后提示跑 `mdkit.py test all`。

**作者本机**（真身在 `~/Documents/Hermes/Mechanical-Kit/mdkit`、入口是链接）用 `./install.sh --dev-link` 建入口，其余同。脚本按三种情况判定：本体已在标准位置 → 直接装；入口已指向自己 → 直接装；克隆在别处又没给 `--dev-link` → 报错并打印两条该走的路。

之后：

- `bin/` 是 arm64 二进制；换 Intel 机器要用同名 `.swift` 重新 `swiftc` 编译。
- 页图/OCR 源从 Obsidian vault 备份恢复，各书路径见 `books/<书>/book.md` / `references/<书>/book.md`。
- 原始 PDF 不自带（版面设计不公开、179 MB 也不该进 git）：`~/Documents/机械设计 第11版.pdf`、`…课程设计手册第5版.pdf`、`…机械制图.pdf` 自备。
- `python3 mdkit.py test all` 全绿、`./draw/ch08/build.sh` 出 `RESULT: PASS`，即可用。
- skill 侧：仓库 `skills/` 是快照，原位才是权威（curator 改的是原位）。装新机用 `install.sh` 复制过去；之后想核对就用 `./sync-skills.sh` 看 diff。

## 6b. 公开版怎么生成（脚本裁树，不共享历史）

开发版仓库 `mechanical-kit-dev` 保持完整（含 `books/` 读数与 `_full_ocr`）。公开版**不是分支、不是把仓库改可见性**，而是用 `scripts/make-public.sh` 裁一棵树、另建一个仓库：

```bash
./scripts/make-public.sh /tmp/mk-public        # dry-run：列白名单 + 文件数，不写盘
./scripts/make-public.sh --go /tmp/mk-public   # 真写盘 + 过四道闸
```

白名单（**只有这些能出去**）：`mdkit.py VERSION README.md LICENSE LICENSE-DATA NOTICE install.sh sync-skills.sh .gitignore` + `lib/ bin/ check/ draw/ templates/ skills/ scripts/ book/ docs/`。实测 **324 文件 / 7.3 MB**。

四道闸：① 越界（不得有 `books/ raw/ _split/ handoff-* *.pdf *.log`；内容不得含 `/Users/<用户名>`；不得有 >5MB 文件）② 必备文件齐 ③ 账目（文件数/体积/版本）④ **在目标树裸跑 `mdkit.py selftest`**（既没 `books/` 也没 `raw/`）→ 60 目标 / 8,700 断言 / 跳过 10 / 全绿 → `RESULT: PASS`。

**为什么用白名单，不用 rsync 排除表**：文件清单来自 `git ls-files --cached --others --exclude-standard`，被 ignore 的渲染物根本不进候选；排除表漏一条就漏一条内容，白名单漏一条只会少带文件，而闸 1b 会直接报缺。

三处脚本坑（都踩过，改完就别退回去）：`set -euo pipefail` 下 `grep` 无命中返回 1 会误杀脚本（管道末加 `|| true`）；`[ 条件 ] && {...}` 在 `set -e` 下为零会中断（写 `if`）；自检会在目标树里生成 `__pycache__`（`PYTHONDONTWRITEBYTECODE=1` + 收尾清理，否则文件数从 324 虚涨到 402）。

公开仓库建法：导出树里 `git init -b main` → **单个 initial commit**（不带私有历史，别用 `--mirror`）→ `gh repo create <名> --public --source . --push` → `git tag -a v0.1.0-alpha.1` → 设描述 / topics / Issues 开、PR 开、Discussions 关（README 写「个人项目，不承诺响应」）。

**要交代的边界**（不是 bug）：`lib/**` 的 docstring 里仍有「依据：books/…/handoff-ch08/…」这类内部引用，公开版没有那些文件，读者只能当"作者核过"的标记；`check/` 四个验收器都要**页图**当输入，访客得拿自己的图跑（`verify_table_cells.py --assets <根目录>` 可指定，默认指向作者的 Obsidian vault）。

## 7. 推远端与「哪些内容不能出仓」

GitHub 账号 `Natasha123-bit`（`gh auth status` 已登录，含 `repo` scope）。推送属于「对外发」红线，**先问再推**。

开发版私有仓库：`https://github.com/Natasha123-bit/mechanical-kit-dev`（2026-10-23 建，原名 `mechanical-kit`，为给公开仓库腾名字于 2026-10-27 改名）；公开仓库 `https://github.com/Natasha123-bit/mechanical-kit` 由导出树首次推送建立，**与开发版不共享历史**。他已授权开发版的日常推送；**新建仓库、或把任何仓库的可见性从 private 改 public，仍必须等他说出「公开仓库」**。

推完必须读回验证（不能只信 `gh` 的成功输出）：`gh repo view --json visibility`、`git rev-parse HEAD` 对比 `git ls-remote origin refs/heads/main`、再查远端树里 `.pdf` 计数为 0。

**版权口径按用户的判断走，不要套用「教材内容一律敏感」。** 他的立场：知识、公式、参数本身可公开；受保护的是**图书的版面设计**和**书上的字句原文**。据此切分：

| 内容 | 能否公开 | 依据 |
|---|---|---|
| `lib/` 表值、公式库、画法函数 | 可以 | 知识本身不受保护；他会明确说「教材的知识内容都是可公开的」 |
| 整本书 PDF | **不行** | 版面设计受保护；且 179 MB 不该进 git |
| `books/<书>/_full_ocr/`、handoff 的 `definition` 等原文摘录 | **不行** | 那是书上的字句而非知识；实测 150 段 / 10,089 字符 |
| `draw/` 源码、`bin/`、`check/`、`templates/` | 可以 | 自己的工具 |

所以「公开」不是 publish 整个仓库：**公开版只带** `lib/ bin/ check/ draw/ templates/ skills/ mdkit.py`（约 7 MB），`books/` 留在私有完整仓库。两边不共享历史——公开那份当一次性发布产物生成，私有仓库保持可验收。反复劝「表值有版权风险」只会被驳回，他已经就此表明过立场。

## 8. 三个常被提出、但都不该做的「优化」

1. **别把整本 PDF 收进项目目录再 gitignore。** ignore 掉的文件 clone 不会带（空目录 git 也不追踪），本地收进去只换来 Finder 好看；README 写一行「原始 PDF 自备 + 路径」就够。他的判断：进不了 commit 的东西放哪儿都一样，收进项目是多此一举。
2. **别为了公开而挪 `_full_ocr/` 或 handoff。** 体量不值得：`_full_ocr` 两本共 2.6 MB，handoff 长原文摘录 150 段 / 10,089 字符。挪走的代价却是硬的——handoff 是 `audit_handoff_vs_lib.py` 的输入、`批N-快照.sha256` 记着它的哈希；`_full_ocr` 是 `assemble_sources.py` 的输入，重跑要 330 页 OCR（约 6 分钟）。正确做法是公开版不带 `books/`，不是搬文件。
3. **别担心这些文件拖慢 skill。** 日常做题读的是 Obsidian 的 `raw/sources/<书>/chNN-全章OCR.md`（`grep` 0.00s），库是 `import`，进 skill 只读 `SKILL.md` + `references/`；`_full_ocr` 与 handoff 只被整本书级的一次性脚本读。

## 9. 交代时别把用户绕晕

这套结构（skill 说明书 / mdkit 工具箱 / .git 存档 / 107 处路径）一次全倒出来，他的反应是「给我绕晕了」。正确姿势：**一句类比 + 一张图**，再进数字。类比固定用「skill = 说明书，mdkit = 工具箱和成品，.git = 版本存档；中间靠路径串起来」，配一张两栏图（左 `~/.hermes/skills/`，右 `~/.hermes/lib/mdkit/`，中间箭头写 78 处引用）。图用 HTML 内嵌或 PNG 交付；HTML **必须带 `<meta charset="utf-8">` 且是完整文档**，否则他双击打开中文全乱码；`::preview{file=...}` 的路径相对会话 cwd，写成 `Documents/xxx` 会退化成文件卡片。

## 10. 写这些脚本时才踩到的坑

- **`$VAR` 后面紧跟中文标点必须写 `${VAR}`。** bash 把全角标点的字节也当变量名的一部分，`set -u` 下直接 `REPO?: unbound variable` 退出——`echo "本仓库在 $REPO，但…"`、`echo "…（$cur）"` 实测各中一次，都是分支走到才炸，主路径看不出问题。写完扫一遍：`grep -n '\$[A-Za-z_][A-Za-z0-9_]*[^ -~]' install.sh sync-skills.sh`，命中就是隐患。
- **测脚本分支用假 HOME，别在真身上试。** `HOME=/tmp/fh ./install.sh` 会把 `ENTRY`、`SKILLS_ROOT` 一起导到假目录，五种分支（无参数 / `--dev-link` / `--force-skills` / 入口已指向自己 / 入口指向别处）都能安全跑一遍；`HERMES_SKILLS_ROOT=/tmp/x ./install.sh` 还能单独把 skill 装到临时目录，不碰真身。
- **`install.sh` 与 `sync-skills.sh` 方向相反，谁都不能替代谁。** 前者「仓库快照 → Hermes」（装新机/访客），后者「Hermes 真身 → 仓库」（作者回写）。在作者本机跑前者会把尚未同步的真身改动盖回去，所以脚本里有「克隆不在标准位置就跳过 skill 安装」的护栏，绕过它要显式 `--force-skills`。

## 11. README 与版本号

README 是仓库的门面，只当**路由**：每一节回答一个读者问题，细节一律指向 `books/<书>/` 的状态文件或 skill 的 `references/`，**不搬证据、不重复表格**。常用骨架（按这个顺序）：一句话定位 + 徽章 → 架构图 → 是什么/不是什么 → 目录（带一列「丢了怎么办」：`lib/` 标「不能重建」） → 三本书状态表 → 一分钟上手 + 「想干的事 → 命令」表 → 版本 → 文档地图 → 安装 → 不进仓库/公开版 → 仓库体检。

- **README 里的数字必须是当天实测的**：子命令数（`grep CMDS` 或 `mdkit.py help`）、断言数（`mdkit.py test all` 的收尾行）、文件数/体积（`git ls-files | wc -l`、`du -sh`）。旧 README 漂移的根因就是手写数字 + 多处副本；正文数字后面附一句「具体状态以状态文件为准」。
- **版本号只有 `VERSION` 一个真源**（纯文本、不带 `v`）：`mdkit.py --version` 在运行时读它（**不在代码里写死常量**），`selftest` 头部、`install.sh` 收尾也读它。仍靠手写同步的只剩三处：README 标题、README 徽章、`docs/architecture.svg` 的副标题——改版本时要一起 grep：`grep -rn "$(cat VERSION)" README.md docs/`。
- **发版动作**：改 `VERSION` → 三处手写同步 → `git commit` → `git tag -a v<版本> -m "…"`。**tag 与 push 都是对外动作**：tag 本地可打，push 先问。
- **改仓库可见性（private → public）必须等用户说出「公开仓库」这四个字**：任何「准备公开」的轮次都止步于「导出到临时目录 + 自检」，不建公开仓库、不改 visibility、不发 release、不建镜像仓库。用户只批准过一次私有推送，不等于批准公开。
- **`0.x.y-alpha.N` 的语义要写进 README**：`0.x` = 还没到公开版，`alpha` = 主流程能跑通但接口未冻结（`lib/` 函数名、`mdkit.py` 子命令会改，改了升 `alpha.N`）。不要给它套 1.0 的承诺。
- **架构图放 `docs/architecture.svg`，图源就是 SVG**，README 用相对路径 `![](docs/architecture.svg)` 嵌入（GitHub 会渲染；HTML 文件嵌不进去，`<img>` 里的 SVG 会被 sanitize 掉脚本与外链字体）。**不要同时提交 PNG 快照**——两份必然漂移；需要位图（聊天里预览）就渲染到临时目录，不入库。出图流程与中文文字宽度自检见 skill `architecture-diagram`。
- **徽章用 shields 静态徽章**：`https://img.shields.io/badge/<label>-<message>-<color>`，中文与空格必须 percent-encode（`断言`→`%E6%96%AD%E8%A8%80`），消息里的 `/` 写成 `%2F`，否则整条 404。
