#!/bin/bash
# 批2 靶子图出图链：SVG → Chrome PDF → renderall PNG(8×) → 像素核对
set -e
cd "$(dirname "$0")"
PY=/usr/bin/python3
CHROME="$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
RENDER="$HOME/.hermes/lib/mdkit/bin/renderall"

echo "== 1) 生成 SVG =="
$PY batch2_figures.py

NAMES="${1:-fig1-3 fig1-sheet fig6-section fig6-break fig6-detail fig8-21-left}"
for N in $NAMES; do
  case "$N" in
    fig1-sheet) PW=420; PH=297 ;;
    *)          PW=297; PH=210 ;;
  esac
  echo "== 2) $N → PDF (${PW}×${PH}) → PNG =="
  cat > _wrap.html <<EOF
<!doctype html><meta charset="utf-8">
<style>@page{size:${PW}mm ${PH}mm;margin:0}html,body{margin:0;padding:0;background:#fff}img{display:block;width:${PW}mm;height:${PH}mm}</style>
<img src="$N.svg">
EOF
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
            --print-to-pdf="$N.pdf" _wrap.html >/dev/null 2>&1
  rm -rf "png_$N"
  "$RENDER" "$N.pdf" "png_$N" 8 >/dev/null
done

echo "== 3) 像素核对 =="
$PY verify_all.py
echo "== 完成：$NAMES / verify.log =="
