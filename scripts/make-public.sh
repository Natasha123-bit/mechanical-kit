#!/usr/bin/env bash
# 生成「公开版」目录：只拷贝白名单内的内容，拷完自检是否越界。
# 用法：./scripts/make-public.sh /tmp/mechanical-kit-public        # 只看计划（dry-run）
#       ./scripts/make-public.sh --go /tmp/mechanical-kit-public   # 真的写盘
# 说明：本脚本从不 push、从不改 git 历史；它只负责「裁一份干净的树出来」。
set -euo pipefail

GO=0
if [ "${1:-}" = "--go" ]; then GO=1; shift; fi
DEST="${1:-}"
if [ -z "$DEST" ]; then
  echo "用法：$0 [--go] <目标目录>" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ---- 白名单：只有这里列出的东西能出去（不是「排除表」，忘了排除就会漏，这里反过来）----
WHITELIST=(
  mdkit.py
  VERSION
  README.md
  LICENSE
  LICENSE-DATA
  NOTICE
  install.sh
  sync-skills.sh
  .gitignore
  lib
  bin
  check
  draw
  templates
  skills
  scripts
  docs
  book
)

# 绝不能出去的东西（三条闸分别检查：目录名 / 文件名 / 文件内容里的绝对路径）
FORBIDDEN_DIRS=(books raw _split .git)
FORBIDDEN_NAMES=(handoff- "*.pdf" "*.ocr" "*.log")

# ---- 1) 目标目录检查 ----
if [ -e "$DEST" ]; then
  echo "目标已存在：${DEST}（先删掉或换一个）" >&2
  exit 3
fi

echo "== 白名单 =="
printf '   %s\n' "${WHITELIST[@]}"

echo "== 计划 =="
TMPLIST="$(mktemp)"
trap 'rm -f "$TMPLIST"' EXIT
# 只取 git 跟踪的文件（被 ignore 的渲染物、页图不会进来）
# --others --exclude-standard：新写但还没 add 的文件也要算进来（否则会静默漏掉 LICENSE）
git ls-files -z --cached --others --exclude-standard -- "${WHITELIST[@]}" > "$TMPLIST"
N=$(tr -cd '\0' < "$TMPLIST" | wc -c | tr -d ' ')
echo "   文件数 $N"

if [ "$GO" -eq 0 ]; then
  echo "== dry-run：没写盘。加 --go 才真做 =="
  exit 0
fi

# ---- 2) 拷贝 ----
mkdir -p "$DEST"
while IFS= read -r -d '' f; do
  mkdir -p "$DEST/$(dirname "$f")"
  cp -p "$f" "$DEST/$f"
done < "$TMPLIST"

# ---- 2b) 剥掉 dev-only 块（作者本机实例：路径、项目名、目录账本），安装者不该看到 ----
STRIPPED=$(python3 - "$DEST" <<'PY'
import os,re,sys
root=sys.argv[1]; n=0
pat=re.compile(r'<!-- dev-only:start -->\n.*?<!-- dev-only:end -->\n?', re.S)
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(('.md','.sh','.py')) or f=='make-public.sh': continue
        p=os.path.join(dp,f)
        t=open(p,encoding='utf-8',errors='surrogateescape').read()
        if 'dev-only:start' in t:
            open(p,'w',encoding='utf-8',errors='surrogateescape').write(pat.sub('',t)); n+=1
print(n)
PY
)
echo "== 已剥离 dev-only 块：$STRIPPED 个文件 =="

# ---- 2c) 本机路径映射：代码/数据里的默认路径与注释不留作者家目录，安装者不该继承 ----
REWRITTEN=$(python3 - "$DEST" <<'PY'
import os,sys
root=sys.argv[1]; n=0
MAP=[("~/Documents/Obsidian/机械知识库/","知识库根/"),
     ("~/Documents/Obsidian/机械知识库","知识库根"),
     ("~/Documents/Hermes/Mechanical-Kit/mdkit","<项目目录>"),
     ("Documents/Hermes/Mechanical-Kit/mdkit","<项目目录>"),
     ("Documents/Obsidian/机械知识库","知识库根"),
     ("~/Desktop/机械设计作业/","作业根/"),
     ("绘图测试/多段轴测试1/","示例绘图/"),
     ("设计测试/图纸/","样例图纸/"),
     ("设计测试/calc/","样例计算/"),
     ("设计测试/","样例项目/"),
     ("机械设计作业/","作业根/"),
     ("_目录账本","目录账本")]
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(('.md','.py','.json','.sh','.js')) or f=='make-public.sh': continue
        p=os.path.join(dp,f)
        t=open(p,encoding='utf-8',errors='surrogateescape').read(); o=t
        for a,b in MAP: t=t.replace(a,b)
        if t!=o:
            open(p,'w',encoding='utf-8',errors='surrogateescape').write(t); n+=1
print(n)
PY
)
echo "== 已映射本机路径：$REWRITTEN 个文件 =="

# 版本与自检
cp -p VERSION "$DEST/VERSION" 2>/dev/null || true
echo "== 已写 $DEST =="

# ---- 3) 三道闸 ----
FAIL=0
echo "== 闸 1：越界扫描 =="
for d in "${FORBIDDEN_DIRS[@]}"; do
  HITS=$(find "$DEST" -type d -name "$d" | wc -l | tr -d ' ' || true)
  if [ "$HITS" -gt 0 ]; then echo "   ✗ 出现目录 ${d}：$HITS 个"; FAIL=1; fi
done
for n in "${FORBIDDEN_NAMES[@]}"; do
  if [ "$n" = "*.pdf" ]; then
    # 例外：gear_pipeline 的零件图样例 PDF 是自己画的（无教材版面、无署名），允许公开
    HITS=$(find "$DEST" -name "$n" ! -path "*/gear_pipeline/样例-*" | wc -l | tr -d ' ' || true)
  else
    HITS=$(find "$DEST" -name "$n" | wc -l | tr -d ' ' || true)
  fi
  if [ "$HITS" -gt 0 ]; then echo "   ✗ 出现文件 ${n}：$HITS 个"; FAIL=1; fi
done
PATHS=$(grep -rIlE '/Users/[A-Za-z0-9._-]+' "$DEST" 2>/dev/null | wc -l | tr -d ' ' || true)
if [ "$PATHS" -gt 0 ]; then echo "   ✗ 内容里含 /Users/ 绝对路径：$PATHS 个文件"; FAIL=1; fi
# 作者本机实例：~/Documents 下的项目路径与他的作业目录/项目名，安装者看了会以为自己该有这些东西
PRIVATE=$(grep -rIlE 'Documents/Hermes|Documents/Obsidian|机械设计作业|设计测试/|绘图测试/|_目录账本|课设/' "$DEST" --exclude=make-public.sh 2>/dev/null | wc -l | tr -d ' ' || true)
if [ "$PRIVATE" -gt 0 ]; then echo "   ✗ 内容里含作者本机实例（~/Documents 项目路径/作业目录名）：$PRIVATE 个文件"; FAIL=1; fi
MARKERS=$(grep -rlE '^<!-- dev-only:(start|end) -->$' "$DEST" 2>/dev/null | wc -l | tr -d ' ' || true)
if [ "$MARKERS" -gt 0 ]; then echo "   ✗ dev-only 标记没剥干净：$MARKERS 个文件"; FAIL=1; fi
# 隐私词表（库外）：姓名、学校、账号、推送通道 id 这类 grep 规则拦不到的语义内容。
# 词表放 ~/.hermes/private/sanitize-deny.txt，不进仓库、不进导出树；ALLOW 段按相对路径豁免。
DENY_FILE="${MDKIT_SANITIZE_DENY:-$HOME/.hermes/private/sanitize-deny.txt}"
if [ -f "$DENY_FILE" ]; then
  DENY_REPORT=$(python3 - "$DEST" "$DENY_FILE" <<'PY'
import os, sys
dest, deny = sys.argv[1], sys.argv[2]
block, allow, sect = [], [], None
for raw in open(deny, encoding="utf-8"):
    s = raw.strip()
    if not s or s.startswith("#"):
        continue
    if s.startswith("[") and s.endswith("]"):
        sect = s.lower()
        continue
    (allow if sect == "[allow]" else block).append(s)


def allowed(rel):
    return any(rel == a or rel.startswith(a.rstrip("/") + "/") for a in allow)


hits = []
for root, dirs, files in os.walk(dest):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "node_modules")]
    for f in files:
        p = os.path.join(root, f)
        rel = os.path.relpath(p, dest)
        if allowed(rel):
            continue
        try:
            with open(p, encoding="utf-8", errors="ignore") as fh:
                t = fh.read()
        except Exception:
            continue
        for w in block:
            i = t.find(w)
            if i >= 0:
                hits.append("%s:%d: %s" % (rel, t[:i].count("\n") + 1, w))
print(len(hits))
for h in hits[:15]:
    print("   ✗ " + h)
if len(hits) > 15:
    print("   …另有 %d 处" % (len(hits) - 15))
PY
  )
  DENY_HITS=$(printf '%s\n' "$DENY_REPORT" | head -1 | tr -d ' ')
  if [ "${DENY_HITS:-0}" -gt 0 ]; then
    printf '%s\n' "$DENY_REPORT" | sed -n '2,$p'
    echo "   ✗ 隐私词表命中 ${DENY_HITS} 处（词表 $DENY_FILE；确要放行就加进 [ALLOW]）"
    FAIL=1
  else
    echo "   ✓ 隐私词表：0 命中"
  fi
else
  echo "   ! 没找到隐私词表 $DENY_FILE —— 姓名/学校/账号无人把关（建议建一份）"
fi
BIG=$(find "$DEST" -type f -size +5M | wc -l | tr -d ' ' || true)
if [ "$BIG" -gt 0 ]; then echo "   ✗ 有 >5MB 文件：$BIG 个"; FAIL=1; fi
if [ "$FAIL" -eq 0 ]; then echo "   ✓ 0 处越界（无 books//raw/_split/handoff/pdf/绝对路径/大文件）"; fi

echo "== 闸 1b：必备文件 =="
for must in mdkit.py VERSION README.md LICENSE LICENSE-DATA NOTICE lib/handbook/_data/索引.json; do
  if [ ! -e "$DEST/$must" ]; then echo "   ✗ 缺 $must"; FAIL=1; fi
done
if [ "$FAIL" -eq 0 ]; then echo "   ✓ 必备文件齐"; fi

echo "== 闸 2：账目 =="
FILES=$(find "$DEST" -type f | wc -l | tr -d ' ' || true)
SIZE=$(du -sh "$DEST" | awk '{print $1}')
echo "   文件 $FILES 个 / $SIZE"
echo "   版本 $(cd "$DEST" && python3 mdkit.py --version 2>/dev/null || echo '（无法运行）')"

echo "== 闸 3：裸跑自检（无 books/ 场景）=="
# PYTHONDONTWRITEBYTECODE：别让自检在发布树里生成 __pycache__（否则文件数与体积虚高）
(cd "$DEST" && PYTHONDONTWRITEBYTECODE=1 python3 mdkit.py selftest 2>&1 | tail -3) || FAIL=1
find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
echo "   发布树 $(find "$DEST" -type f | wc -l | tr -d ' ') 个文件 / $(du -sh "$DEST" | awk '{print $1}')"

echo
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: PASS —— $DEST 可以发布（本脚本不会 push）"
else
  echo "RESULT: FAIL —— 见上面 ✗ 项"
  exit 1
fi
