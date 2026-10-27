#!/bin/bash
# 一键出图：SVG → 校验 → PDF(A4横放) → PNG → 扫像素复核
# 用法：./build.sh [输出名]    默认 大齿轮零件图
set -e
cd "$(dirname "$0")"
NAME="${1:-大齿轮零件图}"
CHROME="$HOME/.hermes/tools/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"

echo "== 1) 渲染 SVG + 六项校验 =="
python3 gear_draw.py --out "$NAME.svg" --check

echo "== 2) 打 A4 横放 PDF（用 HTML 包一层 @page，否则 Chrome 默认 Letter 竖放）=="
cat > "_wrap.html" <<EOF
<!doctype html><meta charset="utf-8">
<style>
@page{size:297mm 210mm;margin:0}
html,body{margin:0;padding:0;background:#fff}
img{display:block;width:297mm;height:210mm}
</style>
<img src="$NAME.svg">
EOF
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
          --print-to-pdf="$NAME.pdf" "_wrap.html" 2>&1 | tail -1

echo "== 3) PDF 逐页转 PNG =="
[ -x ./renderall ] || swiftc -O renderall.swift -o renderall
rm -rf png && ./renderall "$NAME.pdf" png 3.5

echo "== 4) 扫像素复核 =="
python3 verify_raster.py png/p1.png

echo "== 完成：$NAME.svg / $NAME.pdf / png/p1.png =="
