#!/bin/bash
# 把 Hermes skill 目录里的机械类 skill 单向镜像进本仓库 skills/。
# 方向固定：~/.hermes/skills/engineering/ → <本仓库>/skills/
# 原位仍是权威副本（Hermes 加载的就是它），这里存的是可 diff 的快照。
#
# 用法：./sync-skills.sh [提交说明]
#   ./sync-skills.sh            # 只同步并打印差异
#   ./sync-skills.sh "批6验收"   # 同步 + 提交
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
SRC="$HOME/.hermes/skills/engineering"
SKILLS=(mechanical-book-deposit mechanical-homework)

mkdir -p "$REPO/skills"
for s in "${SKILLS[@]}"; do
  [ -d "$SRC/$s" ] || { echo "缺 skill：$SRC/$s" >&2; exit 1; }
  rsync -a --delete --exclude '.DS_Store' "$SRC/$s/" "$REPO/skills/$s/"
done

echo "== 同步后与本仓库的差异 =="
git -C "$REPO" status --porcelain skills/ || true

if [ $# -ge 1 ]; then
  msg="$1"; shift
  git -C "$REPO" add -A skills/
  if git -C "$REPO" diff --cached --quiet; then
    echo "== 无变化，未提交 =="
  else
    git -C "$REPO" commit -m "skills: $msg"
    echo "== 已提交 =="
  fi
fi
