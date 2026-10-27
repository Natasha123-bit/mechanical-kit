#!/bin/bash
# 验 mdkit 的落点与可达性：入口解析、git 历史、章库测试、绝对路径 import、具名路径、体积、远端。
# 搬完 / 换机 / 怀疑断链时先跑它，别手敲十步。
# 用法: scripts/verify_install.sh [入口路径]    # 默认 ~/.hermes/lib/mdkit
set -uo pipefail

E="${1:-$HOME/.hermes/lib/mdkit}"
fail=0
ok()  { printf '  %-30s %s\n' "$1" "$2"; }
bad() { printf '  %-30s %s\n' "$1" "$2"; fail=1; }

echo "入口: $E"
if [ -L "$E" ]; then
  ok "类型" "symlink -> $(readlink "$E")"
elif [ -d "$E" ]; then
  ok "类型" "真实目录（原位形态）"
else
  bad "入口存在" "缺失（断链或未安装）"
  exit 1
fi
[ -d "$E/" ] && ok "可进入" "是（断链时会失败）" || bad "可进入" "否，入口断链"

# git：一律走入口，不手写真身路径（这才是 107 处引用真实依赖的东西）
if git -C "$E" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ok "git 可读" "$(git -C "$E" log --oneline -1 2>/dev/null)"
  n=$(git -C "$E" status --porcelain | wc -l | tr -d ' ')
  [ "$n" = 0 ] && ok "工作区" "干净" || ok "工作区" "$n 项未提交（不一定是故障）"
else
  bad "git 可读" "不是 git 仓库"
fi

# 章库测试
tmp="$(mktemp -t mdkit_test.XXXXXX)"
if python3 "$E/mdkit.py" test all >"$tmp" 2>&1; then
  ok "mdkit.py test all" "$(tail -1 "$tmp")"
else
  bad "mdkit.py test all" "退出码非 0，日志 $tmp"
fi

# 按 skill 的写法用入口绝对路径 import
if python3 -c "import sys; sys.path.insert(0,'$E'); from lib.design import gear_ch10" 2>/dev/null; then
  ok "绝对路径 import" "lib.design.gear_ch10"
else
  bad "绝对路径 import" "失败"
fi

# skill 里被点名的具名路径
for p in lib/design/gear_ch10.py bin/ocrbox draw/gbdraw.py books/design/章节地图.json; do
  [ -f "$E/$p" ] && ok "存在 $p" "是" || bad "存在 $p" "缺失"
done

# 体积：symlink 形态不加 -L 会显示 0B
ok "体积（du -L）" "$(du -Lsh "$E" 2>/dev/null | awk '{print $1}')"

# 远端：推过才比，未推过只是提示
if git -C "$E" remote get-url origin >/dev/null 2>&1; then
  l=$(git -C "$E" rev-parse HEAD 2>/dev/null)
  r=$(git -C "$E" ls-remote origin refs/heads/main 2>/dev/null | cut -f1)
  if [ -n "$r" ] && [ "$l" = "$r" ]; then
    ok "远端同步" "HEAD == origin/main (${l:0:7})"
  else
    ok "远端同步" "本地 ${l:0:7} vs 远端 ${r:0:7}（有未推提交）"
  fi
fi

echo
if [ "$fail" = 0 ]; then echo "全部通过"; else echo "有 FAIL 项，逐条看上面"; fi
exit "$fail"
