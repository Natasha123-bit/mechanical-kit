# mdkit 的版本管理（git 仓库化）

适用范围：给 `~/.hermes/lib/mdkit` 这套沉淀资产做备份、回溯、迁移，以及向用户交代「仓库在哪、装了什么」。

## 1. 落点：标准布局直放 `~/.hermes/lib/mdkit`

**安装就是标准布局**：`git clone` 到 `~/.hermes/lib/mdkit`，真身就在标准位置，不建任何链接。开发者在自己的项目目录里开发时用 `./install.sh --dev-link`。

| 布局 | 真身 | 运行时入口 | 要改的引用 | 可逆 |
|---|---|---|---|---|
| **访客 / 新机（标准）** | `~/.hermes/lib/mdkit` | 同名，无链接 | 0 | — |


**先一行报位置，别先建。** 内容固定三样——根在哪、新建了哪几项、原有文件是否零改动（附 `stat -f "%Sm %N"` 证据）；再给可逆路径。用户自己会说要不要换地方，一句就够。（本轮教训：没问就原位 init，用户的反应是「我还什么都不知道呢你就给建好了」。）

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
- **`git status --porcelain skills/` 干净只说明「快照 == 上次提交」，不代表「快照 == 真身」。** `sync-skills.sh` 带 `--delete` 整目录覆盖，会把真身里积压的所有漂移（curator 后台改的、别的会话加的文件）一次性灌进快照。实测：同步前 status 干净，同步后冒出 13 个 M + 5 个 ??，其中只有 2 个是自己的改动。所以**同步但不提交**（`./sync-skills.sh`）→ 看清 `git status --porcelain skills/` → 只 `git add <自己的路径>` 提交，其余在报告里点名列出来等用户决定；`./sync-skills.sh "<msg>"` 这种一步到位的写法会把这些漂移一起 commit，作者本机等于顺手把未经用户确认的改动（含 curator 的）推到仓库，进公开版就是另一回事了。

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

**作者本机**（真身在项目目录、入口是链接）用 `./install.sh --dev-link` 建入口，其余同。脚本按三种情况判定：本体已在标准位置 → 直接装；入口已指向自己 → 直接装；克隆在别处又没给 `--dev-link` → 报错并打印两条该走的路。

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

白名单（**只有这些能出去**）：`mdkit.py VERSION README.md LICENSE LICENSE-DATA NOTICE install.sh sync-skills.sh .gitignore` + `lib/ bin/ check/ draw/ templates/ skills/ scripts/ book/ docs/`。实测 **371 文件 / 8.7 MB**（0.1.0-alpha.2 定版树的数，含 `lib/drawing/charter/fixtures/` 8 个夹具与 `skills/…/scripts/inkbox.py`；数会随入库文件变，**报数前现测**）。

四道闸：① 越界（不得有 `books/ raw/ _split/ handoff-* *.pdf *.log`；内容不得含 `/Users/<用户名>`；不得有 >5MB 文件）② 必备文件齐 ③ 账目（文件数/体积/版本）④ **在目标树裸跑 `mdkit.py selftest`**（既没 `books/` 也没 `raw/`）→ 60 目标 / 8,700 断言 / 跳过 10 / 全绿 → `RESULT: PASS`。

**为什么用白名单，不用 rsync 排除表**：文件清单来自 `git ls-files --cached --others --exclude-standard`，被 ignore 的渲染物根本不进候选；排除表漏一条就漏一条内容，白名单漏一条只会少带文件，而闸 1b 会直接报缺。

三处脚本坑（都踩过，改完就别退回去）：`set -euo pipefail` 下 `grep` 无命中返回 1 会误杀脚本（管道末加 `|| true`）；`[ 条件 ] && {...}` 在 `set -e` 下为零会中断（写 `if`）；自检会在目标树里生成 `__pycache__`（`PYTHONDONTWRITEBYTECODE=1` + 收尾清理，否则文件数会虚涨（当时 324 → 402））。

**`LICENSE` 必须是标准 MIT 正文的最后一行。** 后面再附「本许可只覆盖代码、数据见 LICENSE-DATA」这类中文说明，GitHub 的 licensee 就匹配不上，侧栏显示 `Other`（`spdx_id=NOASSERTION`，实测一次）。范围说明写进 `NOTICE` 第一节，`LICENSE` 只留正文；发布后用 `gh api repos/<o>/<r> --jq .license.spdx_id` 复核。

公开仓库建法：导出树里 `git init -b main` → `gh repo create <名> --public --source . --push` → 设描述 / topics / Issues 开、PR 开、Discussions 关（README 写「个人项目，不承诺响应」）。首版是一个 initial commit；之后每版把新导出树 rsync 进去、按普通提交推送，**不共享私有历史**。后续修复走普通提交，等有实质变化再开 `alpha.N+1`。

**tag 规则**：tag 必须指向 `main` 上真实存在的提交（`git ls-remote` 同时查 `refs/heads/main` 与 `refs/tags/v…^{}`，两个哈希要一样）。已发 tag 不移动；只有一种例外——同一发版轮内（推送后十几分钟内、尚无外部拉取）发现该版本自身有缺陷，可以删了重指，并在 `ITERATIONS.md` 的发版记录里写明重指过。
`0.1.0-alpha.1` / `v0.1.0-alpha.2` 两版都按此办。

**日常增量更新公开版，别重建仓库**：`make-public.sh --go /tmp/mkpub-new` → `git clone <公开仓库> /tmp/mkpub-repo` → `rsync -a --delete --exclude .git /tmp/mkpub-new/ /tmp/mkpub-repo/` → 先 `git status --short | wc -l` 并逐条扫一遍改动再 `git add -A && git commit && git push`。**这一步会一次性带出「本地撤了、等在下一版才推」的提交**（rsync 不区分它们），所以改动数与预期对不上就是混进了别人的漂移，先看清再提交。两个参数都不能省：`--delete` 让上一版遗留下来的文件消失，`--exclude .git` 保住刚 clone 的历史。推完 `git ls-remote <url> HEAD` 对一次本地 `git rev-parse HEAD`，**再在 clone 里摸跑一次入口**（`check.py` / `mdkit.py selftest`）——公开树没有作者的私有路径与数据，能独立跑通才算真自包含。**每版发完再补一次逐字对比**：`make-public.sh --go /tmp/x` 后与远端克隆 `diff -r --exclude=.git`，0 行才算「线上就是导出的那棵树」。

**要交代的边界**（不是 bug）：`lib/**` 的 docstring 里仍有「依据：books/…/handoff-ch08/…」这类内部引用，公开版没有那些文件，读者只能当"作者核过"的标记；`check/` 四个验收器都要**页图**当输入，访客得拿自己的图跑（`verify_table_cells.py --assets <根目录>` 可指定，默认指向作者的 Obsidian vault）。

## 6c. 公开版不能带作者本机实例（导出期两道处理）

公开版是给陌生人装的：里面出现的每一个目录（作业根、知识库根、样例项目）都必须是用户自己会建的那一层，**不能出现作者机器上才存在的路径、项目名、账本名**——否则对方装完按 skill 干活，会去找一堆不存在的东西。

两处理，都在 `scripts/make-public.sh` 里做，原位文件保持原样（作者本机脚本靠这些默认值干活）：

- **文档用 dev-only 块**（2b 步）：作者本机专属的段落/表行用 `<!-- dev-only:start -->` 与 `<!-- dev-only:end -->` **各独占一行**包起来，导出时整块剥掉。标记写在行首（例如表格行 `<!-- dev-only:start -->| …`）正则匹配不到，会漏剥——踩过。
- **代码/数据用导出期路径映射**（2c 步）：对 `.md/.py/.json/.sh/.js` 按长度降序替换，把本机的知识库目录、工具真身目录、作业目录、两个练习/测试项目目录前缀（含其下子目录）与账本文件名（带下划线前缀那版）分别换成通用占位：`知识库根/`、`<项目目录>`、`作业根/`、`示例绘图/`、`样例图纸/`、`样例计算/`、`样例项目/`、`目录账本`。源串清单只在 `make-public.sh` 的 MAP 表里维护，**别在文档里抄一遍字面串**；新增本机路径时只改那张表，别去改原位的脚本默认值（用户靠这些默认值干活）。
- **闸 1 兜底**：导出树里再 grep 一遍——两个 `Documents/` 项目目录段、作业与课设目录名、两个练习/测试项目目录前缀、账本名，命中即 FAIL；`^<!-- dev-only:(start|end) -->$` 独占行残留也 FAIL。两条 grep 都带 `--exclude=make-public.sh`（脚本存着 MAP 表，会自我误报）；**写进 skill 的说明文字同样会触发闸 1**（本节初版就因抄了字面串让导出 FAIL），所以只写占位目标、不写源串。

**称呼统一**：两份 skill 全文用「用户」称呼对方，不用「他」（导出后 grep 应只剩「其他 / 他人」与明确指第三方的「老师」）。个人轶事（某次反应的原话、某台机器的实测数）保留——它们是判据来源，不是称呼问题。批量替换时注意 `其他`、`他人` 不能被替换，`吉他` 之类也要排除。

**导出 → 推送是一条命令链，闸没过不许推。** `make-public.sh` 自己不 push，但如果把 rsync/commit/push 写在另一个调用里（前一步 `&&` 收尾、后一步单起），闸 1 红了照样会推上去——实测推过一棵 FAIL 树，再补一个 commit 才修回。写法：`bash ./scripts/make-public.sh --go <空目录> 2>&1 | grep -q 'RESULT: PASS' && rsync … && git commit … && git push`；`--go` 的目标目录必须**不存在**（脚本不覆盖已有目录，直接报「目标已存在」，先 `rm -rf`）。

**批量改文件用 python3 heredoc，别用 bash `while IFS= read -r -d '' < <(find …)`。** 后者实测一声不响跑 0 次，`set -euo pipefail` 下也不报错——剥离步骤看着执行了，文件一个没改；换成 `python3 - "$DEST" <<'PY'` + `os.walk` 一次就对。判据不是脚本打印的行数，而是改完自己 `grep -c` 一遍命中数。

**映射后抽查「默认值」类位置。** `os.path.expanduser("…知识库根/…")` 这类被替换成非 `~` 开头时不会报错，只在没显式传参时静默变成相对路径；导出树能跑 selftest 不代表这些默认值成立——要么修，要么在报告里写明「脚本默认值是占位，调用方需显式传参」。

**读回用 GitHub 的 tarball，不只信本地 clone。** `curl -sL https://codeload.github.com/<o>/<r>/tar.gz/refs/heads/main` 解到 scratch 后跑三查：本机串 `grep -rln … --exclude=make-public.sh` 为 0、`grep -rlE '^<!-- dev-only:(start|end) -->$'` 为 0、`find . -type f | wc -l` 与导出树文件数一致——三条都过才算「陌生人拿到的那棵树是干净的」。

**闸只认串，不认语义——发版前另查三类它看不见的东西：**

1. **身份字段**：标题栏与元数据里的作者姓名、学校 / 组织名、`designer` / `org` 的默认值（`draw/**` 常写死）。公开版必须是占位（`（你的名字）` / `（你的学校）`）。**已落地**：`draw/gear_pipeline/gear_draw.py` 的 `identity(key)` 按顺序取值——环境变量 `MDKIT_DESIGNER` / `MDKIT_ORG` → 库外配置 `~/.hermes/private/drawing-identity.json`（`{"designer": …, "org": …}`）→ 都没读到才输出占位。作者本机有这个 json，出图照旧印真名，一条命令不用改；陌生人没有，自然印占位。新增第二个出图入口时照这个三段式写，别再写死。不处理的话，陌生人画自己的图会在标题栏印上作者的名字与学校——比路径泄露更难看，也正是「装完发现不是自己的东西」那类投诉。
2. **账号与通道**：通知脚本里的 bot id、IM 通道标识、邮箱、仓库 owner 之外的任何 handle。
3. **私有工作流细节**：批处理流水、内部信号文件名、某台机器的实测数。

做法（**已落地，闸 1c**）：库外词表 `~/.hermes/private/sanitize-deny.txt`，绝不进任何仓库或导出树。格式两段：`[BLOCK]` 每行一条做全树字面扫描（跳过 `.git` / `__pycache__` / `node_modules`），命中即 FAIL 并打印 `相对路径:行号: 词`（最多 15 条）；`[ALLOW]` 每行一个相对 DEST 的路径或目录前缀，命中但路径在豁免里就放行（确有该发的敏感字时加一行，不改脚本）。脚本在 MARKERS 检查之后跑，首行给命中数是给 bash 判断用的，别改成中文；`MDKIT_SANITIZE_DENY` 可覆盖词表路径；词表缺失只打印警告不失败（新机器上别让它静默通过）。词表加一条永久生效，比每次记着改脚本可靠；词表抓不到的新表述，靠「上次发版以来的 diff」语义复核补。**别把姓名/校名写进本文件**——本文件会被导出到公开树，词表闸的顺序是先扫后报，写进来自己就把自己拦住了（也算一种提醒）。

**夹具也会带实名**：`lib/drawing/charter/fixtures/*.svg` 是 golden 底图，标题栏 `data-role="title-grid"` 的文本节点里印着真名与校名，闸 1c 第一次跑就抓出 2 文件 4 处。处置是把文本换成 `示例` / `示例单位`（比原串短，不会碰格子溢出类断言），改完必须重跑 `mutants.py`（判据：注入 27 / 抓到 27 / 漏抓 0）和 `check_charter.py`（145 条一致）才算没破夹具。凡是「从真实交付物拷进来的底图」都要按这条查一遍。

**「0 命中」不算闸通了——先看它红过一次。** 词表闸要按三步验：①在导出树里临时塞一行 `BLOCK` 词（`echo 词 >> <树>/docs/x.md`）→ 跑闸，必须 FAIL 并报出 `相对路径:行号: 词`；②把那行路径写进 `[ALLOW]` → 必须 PASS；③撤掉临时文件与豁免。只看全绿就交付，等于把「词表路径写错、`[BLOCK]` 段没解析到」这类静默失效当成了通过。同理，`[ALLOW]` 只在真的红过一次之后才加——先加豁免再跑，永远不知道自己豁免掉了什么。

**测纯函数分支时 stub 掉 import 期的第三方依赖，别为了测试去装包。** 出图脚本常在模块顶 `import svgwrite` 之类，环境里没有就整段测不了；用 `python3 -c "import sys,types; sys.modules['svgwrite']=types.ModuleType('svgwrite'); sys.path.insert(0,'draw/gear_pipeline'); import gear_draw as g; print(g.identity('designer'))"` 就能只测取值逻辑。配合 `HOME=/tmp/nohome` 跑一次，验证「没有私有配置 → 印占位」那条分支；再在真 HOME 下跑一次验证「有配置 → 印真名」。两条分支都看到，才算参数化生效。

**同一棵树既做本地使用又做公开来源是对的决策，边界放在发版这一步。** 拆「本地树 / 公开树」两份，代价是每改一条 skill 都要判通用性再同步两处，漂移成本高于闸的维护成本；而泄出去的唯一通道是 `make-public.sh` 那一步，闸与词表只要在那一步跑就够。前提是承认「写法规矩」不算防线。

## 7. 推远端与「哪些内容不能出仓」

GitHub 账号 `Natasha123-bit`（`gh auth status` 已登录，含 `repo` scope）。推送属于「对外发」红线，**先问再推**。

开发版私有仓库：`https://github.com/Natasha123-bit/mechanical-kit-dev`（2026-10-23 建，原名 `mechanical-kit`，为给公开仓库腾名字于 2026-10-27 改名）；公开仓库 `https://github.com/Natasha123-bit/mechanical-kit` 由导出树首次推送建立，**与开发版不共享历史**。用户已授权开发版的日常推送；**新建仓库、或把任何仓库的可见性从 private 改 public，仍必须等用户说出「公开仓库」**。

推完必须读回验证（不能只信 `gh` 的成功输出）：`gh repo view --json visibility`、`git rev-parse HEAD` 对比 `git ls-remote origin refs/heads/main`、再查远端树里 `.pdf` 计数为 0。

**版权口径按用户的判断走，不要套用「教材内容一律敏感」。** 用户的立场：知识、公式、参数本身可公开；受保护的是**图书的版面设计**和**书上的字句原文**。据此切分：

| 内容 | 能否公开 | 依据 |
|---|---|---|
| `lib/` 表值、公式库、画法函数 | 可以 | 知识本身不受保护；用户会明确说「教材的知识内容都是可公开的」 |
| 整本书 PDF | **不行** | 版面设计受保护；且 179 MB 不该进 git |
| `books/<书>/_full_ocr/`、handoff 的 `definition` 等原文摘录 | **不行** | 那是书上的字句而非知识；实测 150 段 / 10,089 字符 |
| `draw/` 源码、`bin/`、`check/`、`templates/` | 可以 | 自己的工具 |

所以「公开」不是 publish 整个仓库：**公开版只带** `lib/ bin/ check/ draw/ templates/ skills/ mdkit.py`（约 7 MB），`books/` 留在私有完整仓库。两边不共享历史——公开那份当一次性发布产物生成，私有仓库保持可验收。反复劝「表值有版权风险」只会被驳回，用户已经就此表明过立场。

## 8. 三个常被提出、但都不该做的「优化」

1. **别把整本 PDF 收进项目目录再 gitignore。** ignore 掉的文件 clone 不会带（空目录 git 也不追踪），本地收进去只换来 Finder 好看；README 写一行「原始 PDF 自备 + 路径」就够。用户的判断：进不了 commit 的东西放哪儿都一样，收进项目是多此一举。
2. **别为了公开而挪 `_full_ocr/` 或 handoff。** 体量不值得：`_full_ocr` 两本共 2.6 MB，handoff 长原文摘录 150 段 / 10,089 字符。挪走的代价却是硬的——handoff 是 `audit_handoff_vs_lib.py` 的输入、`批N-快照.sha256` 记着它的哈希；`_full_ocr` 是 `assemble_sources.py` 的输入，重跑要 330 页 OCR（约 6 分钟）。正确做法是公开版不带 `books/`，不是搬文件。
3. **别担心这些文件拖慢 skill。** 日常做题读的是 Obsidian 的 `raw/sources/<书>/chNN-全章OCR.md`（`grep` 0.00s），库是 `import`，进 skill 只读 `SKILL.md` + `references/`；`_full_ocr` 与 handoff 只被整本书级的一次性脚本读。

## 9. 交代时别把用户绕晕

这套结构（skill 说明书 / mdkit 工具箱 / .git 存档 / 107 处路径）一次全倒出来，用户的反应是「给我绕晕了」。正确姿势：**一句类比 + 一张图**，再进数字。类比固定用「skill = 说明书，mdkit = 工具箱和成品，.git = 版本存档；中间靠路径串起来」，配一张两栏图（左 `~/.hermes/skills/`，右 `~/.hermes/lib/mdkit/`，中间箭头写 78 处引用）。图用 HTML 内嵌或 PNG 交付；HTML **必须带 `<meta charset="utf-8">` 且是完整文档**，否则用户双击打开中文全乱码；`::preview{file=...}` 的路径相对会话 cwd，写成 `Documents/xxx` 会退化成文件卡片。

## 10. 写这些脚本时才踩到的坑

- **execute_code 里别用 f-string 包 shell heredoc。** `f"""bash … <<'PY' … {len(x)/4000:.1%} …"""` 会在发出前把 heredoc 内部的 `{}` 当 f-string 表达式求值，代码被就地截断——典型表现是 `NameError`，且 `tool_calls_made: 0`（一条都没执行，看着像脚本自己崩了）。用普通字符串拼接、或把 Python 逻辑写成独立的 `.py` 再 `python3 <文件>`；heredoc 本体用引号版 `<<'PY'` 阻止 shell 展开。

- **`$VAR` 后面紧跟中文标点必须写 `${VAR}`。** bash 把全角标点的字节也当变量名的一部分，`set -u` 下直接 `REPO?: unbound variable` 退出——`echo "本仓库在 $REPO，但…"`、`echo "…（$cur）"` 实测各中一次，都是分支走到才炸，主路径看不出问题。写完扫一遍：`grep -n '\$[A-Za-z_][A-Za-z0-9_]*[^ -~]' install.sh sync-skills.sh`，命中就是隐患。
- **测脚本分支用假 HOME，别在真身上试。** `HOME=/tmp/fh ./install.sh` 会把 `ENTRY`、`SKILLS_ROOT` 一起导到假目录，五种分支（无参数 / `--dev-link` / `--force-skills` / 入口已指向自己 / 入口指向别处）都能安全跑一遍；`HERMES_SKILLS_ROOT=/tmp/x ./install.sh` 还能单独把 skill 装到临时目录，不碰真身。
- **`install.sh` 与 `sync-skills.sh` 方向相反，谁都不能替代谁。** 前者「仓库快照 → Hermes」（装新机/访客），后者「Hermes 真身 → 仓库」（作者回写）。在作者本机跑前者会把尚未同步的真身改动盖回去，所以脚本里有「克隆不在标准位置就跳过 skill 安装」的护栏，绕过它要显式 `--force-skills`。
- **脚本里比路径一律比物理路径。** `ENTRY="$HOME/.hermes/lib/mdkit"` 是逻辑路径，`REPO=$(cd -P … && pwd)` 是物理路径；`$HOME` 带软链（macOS `/tmp → /private/tmp`、外置盘 home）时两者不等，标准布局会被误判成「已存在且不是链接」→ `exit 1`，skill 一个都装不上。写法：`ENTRY_REAL="$(cd -P "$ENTRY" 2>/dev/null && pwd -P || echo "")"`，落点判定与「跳过 skill 安装」那道闸都拿它与 `$REPO` 比。
- **解释器别写死一个位置。** `PY312 = Path.home()/".local/bin/python3.12"` 只在作者机成立；访客把 3.12 装在 Homebrew 或 PATH 里就只跑单解释器，断字数掉一半（8,700 → 4,350）。查找顺序写成 `~/.local/bin` → `/opt/homebrew/bin` → `/usr/local/bin` → `/usr/bin` → `PATH`。README 里报断言数时注明「双解释器 N 条，单解释器约一半」。
- **发布前在假 HOME 里把公开版当陌生人装一遍**（`git clone <公开地址> /tmp/sh/.hermes/lib/mdkit` → `HOME=/tmp/sh ./install.sh` → `HOME=/tmp/sh python3 mdkit.py selftest` → 看 `/tmp/sh/.hermes/skills` 里 skill 在不在）。上面两条都是这一步才现形的：作者机路径不带软链、3.12 恰好在 `~/.local/bin`，两个 bug 在自己的机器上永远看不见。
  - **克隆必须落在 `$HOME/.hermes/lib/mdkit`**：`install.sh` 对「不在标准位置又没给 `--dev-link`」的克隆会直接拒绝并打印两条路，所以在 `/tmp/xxx/mdkit` 这种位置测「安装」永远测不到 skill 那一段；只在测 Python 部分时才随便放。
  - **假 HOME 里别起 Chromium。** 无头 Chromium 会去 `$HOME/Library/Keychains` 找 login 钥匙串，假 HOME 下没有 → macOS 逐个弹「找不到用于储存 Chromium 的钥匙串」（每个进程一个，24 次注入就是 24 个）。假 HOME 只跑纯 Python（`install.sh`、`mdkit.py selftest`、`check_charter.py`）；要跑 `check.py` / `mutants.py` 就换回真 HOME，或显式 `CHROME=<路径>` 但 HOME 仍用真的。
  - 这一步还会暴露两类**只在别人机器上才有**的缺陷，除非修掉否则公开版永远是红的：缺 Chromium 时脚本抛 `FileNotFoundError` 栈（要改成提示设 `CHROME=` + exit 2）；缺 fontTools 时字形规则只能出「未检查」，硬记成「漏抓」会把环境问题报成检查器盲区（要单列「跳过(环境)」，不算漏抓也不算通过）。

## 11. README 与版本号

README 是仓库的门面，只当**路由**：每一节回答一个读者问题，细节一律指向 `books/<书>/` 的状态文件或 skill 的 `references/`，**不搬证据、不重复表格**。常用骨架（按这个顺序）：一句话定位 + 徽章 → 架构图 → 是什么/不是什么 → 目录（带一列「丢了怎么办」：`lib/` 标「不能重建」） → 三本书状态表 → 一分钟上手 + 「想干的事 → 命令」表 → 版本 → 文档地图 → 安装 → 不进仓库/公开版 → 仓库体检。

- **README 里的数字必须是当天实测的**：子命令数（`grep CMDS` 或 `mdkit.py help`）、断言数（`mdkit.py test all` 的收尾行）、文件数/体积（`git ls-files | wc -l`、`du -sh`）。旧 README 漂移的根因就是手写数字 + 多处副本；正文数字后面附一句「具体状态以状态文件为准」。
- **版本号只有 `VERSION` 一个真源**（纯文本、不带 `v`）：`mdkit.py --version` 在运行时读它（**不在代码里写死常量**），`selftest` 头部、`install.sh` 收尾也读它。仍靠手写同步的只剩三处：README 标题、README 徽章、`docs/architecture.svg` 的副标题——改版本时要一起 grep：`grep -rn "$(cat VERSION)" README.md docs/`。
- **发版动作**（2026-10-28 alpha.2 实战后定稿，顺序别换）：
  1. 改 `VERSION` → 三处手写同步（README 标题/徽章、`docs/architecture.svg` 两处副标题）→ `grep -rn "alpha\.N" README.md docs/ lib/ skills/` 扫残留；
  2. 更新文档（README 版本节、`charter/ITERATIONS.md` 发版记录、受影响的手册数字）；
  3. `mdkit.py selftest` + `check_charter.py` + `mutants.py` 全绿 → `git commit`；
  4. **先推分支，再推 tag**：`git push origin HEAD:main`，然后 `git tag -a v<版本> -m "…"` + `git push origin v<版本>`。顺序反了会出现「tag 指向 main 上不存在的提交」——alpha.2 就犯过，远端 `main` 落后一个提交而 tag 已经往前指；
  5. 公开版：`make-public.sh --go /tmp/pub` → 克隆公开仓库 → `rsync -a --delete --exclude .git /tmp/pub/ 仓库/` → commit → push → **在同一提交上重打 tag**；
  6. 读回验证：`git ls-remote` 的 `main` 与 `tags/v…^{}` 相同、`gh api …/commits/main` 与本地 HEAD 相同、`gh repo view --json visibility`、`gh api … --jq .license.spdx_id` 为 `MIT`；
  7. `gh release create v<版本> -R <owner>/<公开仓库> --title "…" --notes-file …`，然后 `gh api …/releases/latest --jq .tag_name` 读回。Release 正文按「相对上一版的变化 / 新增 / 接口与契约 / 文档 / 测试 / 已知限制 / 怎么开始 / 许可」写，已知限制不许省略；体例照上一版——标题格式、是否 `--prerelease` 与上一版保持一致，别一版一个样。
  - **Release 读回，别信命令的成功输出**：`gh release view v<版本> -R <o>/<r> --json tagName,isPrerelease,isDraft,targetCommitish,body`，逐项核 `isPrerelease`/`isDraft` 与上一版一致、`targetCommitish` 是 `main`、`grep -cE '^### '` 的节数与预期相同；再看 `gh release list --limit 3` 确认 Latest 落在新版本上。
  - **查 tag 指向时注意 `gh api git/refs/tags/<t> --jq .object.sha` 给的是 tag 对象的哈希**（annotated tag），不是提交哈希；要剥一层 `git/tags/<sha>`，或直接比 `git ls-remote <url> refs/heads/main 'refs/tags/v<版本>^{}'`——两个哈希相同才算 tag 真的指在 main 上。
  **推分支、推 tag、建 Release 都是对外动作**：本地可以打 tag，push 与 release 先等用户说。
- **Release 之后的纯文档修复走普通提交，不重指 tag**：报告里写明「main 比 tag 多 N 个文档提交」，下次 `alpha.N+1` 一并带上。
- **发布后发现「有东西放错了家 / 内容不对」：本地撤，对外只补口径。** 撤走那部分留在本地等下一版一起推，**不重指 tag、不改已自动历史的提交**；对外用 `gh release edit v<版本> --notes-file <整份正文>` 在「已知限制」节声明「…（已知问题，下一版本修复，改走 X）」，改完读回 `prerelease` 与其余正文都完整（`gh release edit` 吃整份 notes，不是追加）。撤掉的文件要在**发布后的树**里验，不是本地：`gh api repos/<o>/<r>/contents/<路径>` 返回 404、目录列表里不再有它，并用 `find . -type f | wc -l` 与导出树的文件数对一次（差几个就是撤掉的那几个）。不要在正文里悄悄删掉那句话装没发生——用户当时就是冲着「已知问题」这四个字让留的。
- **改仓库可见性（private → public）必须等用户说出「公开仓库」这四个字**：任何「准备公开」的轮次都止步于「导出到临时目录 + 自检」，不建公开仓库、不改 visibility、不发 release、不建镜像仓库。用户只批准过一次私有推送，不等于批准公开。
- **`0.x.y-alpha.N` 的语义要写进 README**：`0.x` = 还没到公开版，`alpha` = 主流程能跑通但接口未冻结（`lib/` 函数名、`mdkit.py` 子命令会改，改了升 `alpha.N`）。不要给它套 1.0 的承诺。
- **架构图放 `docs/architecture.svg`，图源就是 SVG**，README 用相对路径 `![](docs/architecture.svg)` 嵌入（GitHub 会渲染；HTML 文件嵌不进去，`<img>` 里的 SVG 会被 sanitize 掉脚本与外链字体）。**不要同时提交 PNG 快照**——两份必然漂移；需要位图（聊天里预览）就渲染到临时目录，不入库。出图流程与中文文字宽度自检见 skill `architecture-diagram`。
- **徽章用 shields 静态徽章**：`https://img.shields.io/badge/<label>-<message>-<color>`，中文与空格必须 percent-encode（`断言`→`%E6%96%AD%E8%A8%80`），消息里的 `/` 写成 `%2F`，否则整条 404。
