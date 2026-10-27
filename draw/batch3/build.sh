#!/bin/bash
set -e
cd "$(dirname "$0")"
PY=/usr/bin/python3
CHROME="$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
RENDER="$HOME/.hermes/lib/mdkit/bin/renderall"
$PY batch3_figures.py
NAMES="${1:-fig7-1 fig7-15 fig7-20 fig7-49 fig9-2 fig9-25}"
for N in $NAMES; do
  case "$N" in
    fig7-15|fig7-20) PW=297; PH=210 ;;
    *) PW=420; PH=297 ;;
  esac
  cat > _wrap.html <<W
<!doctype html><meta charset="utf-8">
<style>@page{size:${PW}mm ${PH}mm;margin:0}html,body{margin:0;padding:0;background:#fff}img{display:block;width:${PW}mm;height:${PH}mm}</style>
<img src="$N.svg">
W
  "$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$N.pdf" _wrap.html >/dev/null 2>&1
  rm -rf "png_$N"; "$RENDER" "$N.pdf" "png_$N" 8 >/dev/null
done
$PY verify_all.py
