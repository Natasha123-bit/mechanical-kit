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
