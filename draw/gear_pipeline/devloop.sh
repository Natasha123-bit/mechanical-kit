#!/usr/bin/env bash
# devloop.sh —— 改图循环：build → check → 整页截图 → 按 data-view 裁局部。
#
# 和 build.sh 的分工：
#   devloop.sh  改图时用，秒级反馈，只出 PNG 给人眼看，不碰 PDF
#   build.sh    交付时用，出 PDF、逐页转 PNG、扫像素复核
#
# 用法：
#   ./devloop.sh                                   # 默认 gear_draw.py → 大齿轮零件图.svg
#   ./devloop.sh build_gear.py --svg 齿轮零件图.svg --calc calc.json --fig-no CS1-01
#   ./devloop.sh --no-build --svg 齿轮零件图.svg    # 已经 build 过，只检查+看图
#
# 为什么把四件事合成一条：拆成四次调用，agent 每步之间都要重读一遍上下文再决策，
# 一轮就是四五次模型往返。合成一条后一轮只有一次调用 + 一次 vision。
#
# 退出码：0 无 ✗ / 1 有 ✗ / 2 build 或截图失败
set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(cd ../.. && pwd)"

BUILD="gear_draw.py"
SVG="大齿轮零件图.svg"
CALC=""
FIGNO=""
OUTDIR=""      # 空 = SVG 所在目录下的 预览/
DPI=4
DO_BUILD=1

while [ $# -gt 0 ]; do
  case "$1" in
    --svg)      SVG="$2"; shift 2 ;;
    --calc)     CALC="$2"; shift 2 ;;
    --fig-no)   FIGNO="$2"; shift 2 ;;
    --outdir)   OUTDIR="$2"; shift 2 ;;
    --dpi)      DPI="$2"; shift 2 ;;
    --no-build) DO_BUILD=0; shift ;;
    -h|--help)  sed -n '2,20p' "$0"; exit 0 ;;
    *)          BUILD="$1"; shift ;;
  esac
done

# 产物跟着图走：图在哪个项目目录，预览/ 就落在哪，不落到仓库里
[ -z "$OUTDIR" ] && OUTDIR="$(dirname "$SVG")/预览"

CHROME="${CHROME:-$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing}"
mkdir -p "$OUTDIR"

# 挑解释器：build 脚本 import 的第三方包如果 python3 里没有，用 uv 现装现跑
PY="python3"
if grep -qE "^(import|from) svgwrite" "$BUILD" 2>/dev/null; then
  if ! python3 -c "import svgwrite" 2>/dev/null && command -v uv >/dev/null 2>&1; then
    PY="uv run --with svgwrite --quiet python3"
  fi
fi

# ---------- 1) build ----------
if [ "$DO_BUILD" = 1 ]; then
  echo "== 1) build：${BUILD}（${PY}）"
  if ! $PY "$BUILD" --out "$SVG" --check; then
    echo "   ✗ build 失败，停在出图这一步" >&2
    exit 2
  fi
else
  echo "== 1) build：跳过（--no-build）"
fi
[ -f "$SVG" ] || { echo "   ✗ 没有 $SVG" >&2; exit 2; }

# ---------- 2) check ----------
echo "== 2) check"
ARGS=(--fig-no "${FIGNO:-X}")
[ -n "$CALC" ] && ARGS+=(--calc "$CALC")
python3 "$ROOT/lib/drawing/charter/check.py" "$SVG" "${ARGS[@]}" > "$OUTDIR/check.txt" 2>&1
RC=$?
grep -E "✗|通过 /|未检查：|不通过：" "$OUTDIR/check.txt" || echo "   （没有 ✗）"
[ "$RC" = 2 ] && { echo "   ✗ 检查器自身出错，全文在 $OUTDIR/check.txt" >&2; exit 2; }
if grep -q "✗ C1\|✗ C4" "$OUTDIR/check.txt" 2>/dev/null; then
  echo "   → 图元缺 data-role，先补身份：python3 $ROOT/lib/drawing/charter/identify.py \"$SVG\" --write"
fi

# ---------- 3) 整页截图 ----------
echo "== 3) 截图"
read -r SW SH < <(python3 - "$SVG" <<'PY'
import re, sys
head = open(sys.argv[1], encoding="utf-8").read(800)
w = re.search(r'width="([\d.]+)mm"', head)
h = re.search(r'height="([\d.]+)mm"', head)
if w and h:
    print(w.group(1), h.group(1))
else:
    vb = re.search(r'viewBox="([-\d.\s]+)"', head)
    p = [float(x) for x in vb.group(1).split()]
    print(p[2] - p[0], p[3] - p[1])
PY
)
W=$(python3 -c "print(round($SW*$DPI))")
H=$(python3 -c "print(round($SH*$DPI))")
# SVG 可能给的是绝对路径（项目在别处），别拿 PWD 硬拼
case "$SVG" in
  /*) SRC_URI="file://$SVG" ;;
  *)  SRC_URI="file://$PWD/$SVG" ;;
esac
PAGE="$OUTDIR/整页.png"
rm -f "$PAGE"
"${CHROME}" --headless --disable-gpu --hide-scrollbars --allow-file-access-from-files \
          --force-device-scale-factor=1 --window-size="$W,$H" \
          --screenshot="$PAGE" "$SRC_URI" >/dev/null 2>&1
[ -f "$PAGE" ] || { echo "   ✗ 截图失败（CHROME=$CHROME）" >&2; exit 2; }
echo "   $SVG  ${SW}×${SH}mm → $PAGE  ${W}×${H}px"

# ---------- 4) 按视图锚点裁局部 ----------
echo "== 4) 裁局部（按 data-view）"
python3 "$ROOT/draw/gear_pipeline/devloop_crop.py" "$SVG" "$PAGE" --outdir "$OUTDIR"

echo
case "$OUTDIR" in
  /*) echo "== 全部产物在 $OUTDIR ==" ;;
  *)  echo "== 全部产物在 $PWD/$OUTDIR ==" ;;
esac
exit $([ "$RC" = 1 ] && echo 1 || echo 0)