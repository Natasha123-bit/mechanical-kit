#!/bin/bash
# 批1 靶子图出图链：SVG → Chrome PDF(A3 横放) → renderall PNG(8×) → 像素扫线 + 闭合检查
# 用法：./build.sh            全部六张
#       ./build.sh fig8-21    只跑一张
set -e
cd "$(dirname "$0")"
PY=/usr/bin/python3
CHROME="$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
RENDER="$HOME/.hermes/lib/mdkit/bin/renderall"

if [ ! -x "$CHROME" ]; then echo "缺 Chrome：$CHROME" >&2; exit 1; fi
if [ ! -x "$RENDER" ]; then echo "缺 renderall：$RENDER" >&2; exit 1; fi

echo "== 1) 生成 SVG + 校验图元 =="
$PY ch08_figures.py

if [ -n "$1" ]; then NAMES="$1"; else NAMES="fig8-21 fig8-23 fig8-40 fig8-54 fig8-60 fig8-64"; fi

for N in $NAMES; do
  echo "== 2) $N → PDF → PNG =="
  cat > _wrap.html <<EOF
<!doctype html><meta charset="utf-8">
<style>@page{size:297mm 210mm;margin:0}html,body{margin:0;padding:0;background:#fff}img{display:block;width:297mm;height:210mm}</style>
<img src="$N.svg">
EOF
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
            --print-to-pdf="$N.pdf" _wrap.html >/dev/null 2>&1
  rm -rf "png_$N"
  "$RENDER" "$N.pdf" "png_$N" 8 >/dev/null
done

echo "== 3) 像素扫线 + 闭合检查 =="
$PY verify_all.py

echo "== 完成：$NAMES.svg / .pdf / png_*/p001.png / verify.log =="
