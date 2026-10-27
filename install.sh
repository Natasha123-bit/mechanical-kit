#!/bin/bash
# 把 mechanical-kit 装到这台机器上。
#
# 两种布局：
#   标准（访客 / 新机）  仓库本体就在 ~/.hermes/lib/mdkit，脚本只把 skill 装进 Hermes
#   开发（作者本机）     真身在 ~/Documents/Hermes/Mechanical-Kit/mdkit，靠 --dev-link 建入口
#
# 用法：
#   ./install.sh              标准安装（仓库已在 ~/.hermes/lib/mdkit）
#   ./install.sh --dev-link   把当前仓库 symlink 成入口（作者本机）
set -euo pipefail

MODE="guest"
FORCE_SKILLS=0
for a in "$@"; do
  case "$a" in
    --dev-link)     MODE="dev" ;;
    --force-skills) FORCE_SKILLS=1 ;;
    *) echo "未知参数：${a}（可用：--dev-link / --force-skills）" >&2; exit 2 ;;
  esac
done

REPO="$(cd -P "$(dirname "$0")" && pwd)"
SKILLS_ROOT="${HERMES_SKILLS_ROOT:-$HOME/.hermes/skills}/engineering"
ENTRY="$HOME/.hermes/lib/mdkit"

# ---------- 1) 落点 ----------
if [ "$REPO" = "$ENTRY" ]; then
  echo "标准布局：本体就在 $ENTRY"
elif [ -L "$ENTRY" ]; then
  cur="$(readlink "$ENTRY")"
  if [ "$cur" = "$REPO" ]; then
    echo "开发布局：入口已指向本仓库（${cur}）"
  else
    echo "!! 入口已指向别处：$cur" >&2
    echo "   要改指本仓库：rm \"$ENTRY\" && ./install.sh --dev-link" >&2
    exit 1
  fi
elif [ -e "$ENTRY" ]; then
  echo "!! $ENTRY 已存在且不是链接，未改动。" >&2
  echo "   若那是旧的独立安装，先挪开再重跑本脚本。" >&2
  exit 1
elif [ "$MODE" = "dev" ]; then
  mkdir -p "$(dirname "$ENTRY")"
  ln -s "$REPO" "$ENTRY"
  echo "已建开发入口：$ENTRY -> $REPO"
else
  cat >&2 <<EOF
!! 本仓库在 ${REPO}，但标准安装位置是 ${ENTRY}。

   访客 / 新机请直接克隆到标准位置（真身就放在 Hermes 私有目录，不建链接）：
     mkdir -p ~/.hermes/lib
     git clone <本仓库地址> ~/.hermes/lib/mdkit
     cd ~/.hermes/lib/mdkit && ./install.sh

   作者本机（真身在 Documents，只为本机管理方便）改用：
     ./install.sh --dev-link
EOF
  exit 1
fi

# ---------- 2) skill 装进 Hermes ----------
# 方向是「仓库快照 -> Hermes」。作者本机的真身可能比快照新，硬装等于回退。
if [ "$REPO" != "$ENTRY" ] && [ "$FORCE_SKILLS" = 0 ]; then
  echo
  echo "开发布局：跳过 skill 安装（仓库快照可能比本机真身旧，装了会回退）。"
  echo "  回写方向（Hermes 真身 -> 仓库快照）：$REPO/sync-skills.sh 说明"
  echo "  确实要用快照覆盖真身：./install.sh --dev-link --force-skills"
  echo
  echo "版本：mechanical-kit $(cat "$ENTRY/VERSION" 2>/dev/null || echo unknown)"
echo "验证：python3 $ENTRY/mdkit.py test all"
  exit 0
fi

mkdir -p "$SKILLS_ROOT"
for s in "$REPO"/skills/*/; do
  [ -d "$s" ] || continue
  name="$(basename "$s")"
  rsync -a --delete --exclude .DS_Store "$s" "$SKILLS_ROOT/$name/"
  echo "已装 skill：$SKILLS_ROOT/$name"
done

echo
echo "版本：mechanical-kit $(cat "$ENTRY/VERSION" 2>/dev/null || echo unknown)"
echo "验证：python3 $ENTRY/mdkit.py test all"
echo "改完 skill 回写快照：$ENTRY/sync-skills.sh \"说明\""
