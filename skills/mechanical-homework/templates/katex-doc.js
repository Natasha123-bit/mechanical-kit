// 计算书 HTML 骨架：KaTeX 预渲染成静态 HTML，打印时不依赖网络
// 用法：node build_doc.js  → 生成 <题号>_解答.html
// 依赖：katex 用 Hermes 自带的 node_modules（无需 npm install）
const fs = require('fs');
const path = require('path');
const HOME = process.env.HOME || '';
const katex = require(HOME + '/.hermes/hermes-agent/node_modules/katex');

const OUT = HOME + '/Desktop/机械设计作业/<题号>解答';
fs.mkdirSync(OUT, { recursive: true });

const m = t => katex.renderToString(t, { throwOnError: false, displayMode: false });
const M = t => katex.renderToString(t, { throwOnError: false, displayMode: true });

// 注意：模板字面量里写 ${m('...')} 即可，后面不要跟 $ —— 会变成字面美元符
const body = `
<h1>10-x　题目</h1>
<p class="given"><b>已知：</b>${m('P_1=7.5\\ \\mathrm{kW}')}</p>
<h2>解</h2>
<h3>（1）选择齿轮类型、精度等级、材料及齿数</h3>
${M('u=\\frac{z_2}{z_1}=2.077')}
`;

const html = `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<link rel="stylesheet" href="katex/katex.min.css">
<style>
@page { size: A4 portrait; margin: 18mm 17mm 16mm 17mm; }
body { margin:0; font-family:"Songti SC","STSong",serif; font-size:10.5pt; line-height:1.62; }
h1 { font-size:15pt; text-align:center; margin:0 0 8mm; }
h3 { font-size:11pt; margin:5mm 0 1.5mm; }
p { margin:1.2mm 0; text-align:justify; }
p.keep, h2, h3 { break-after:avoid; page-break-after:avoid; }
.katex-display { margin:1.6mm 0 !important; break-inside:avoid; page-break-inside:avoid; }
table { border-collapse:collapse; width:100%; font-size:9.5pt; }
th,td { border:.5pt solid #333; padding:1.1mm 2mm; text-align:center; }
th { background:#f2f2f2; }
.figref img { width:100%; border:.5pt solid #999; }
.cap { text-align:center; font-size:9pt; }
</style></head><body>
${body}
</body></html>`;

fs.writeFileSync(path.join(OUT, '10-x_解答.html'), html, 'utf8');
console.log('written', (html.length / 1024).toFixed(1), 'KB');

// 拷 KaTeX 资源（离线可开）：cp -R $KATEX/dist/fonts OUT/katex/ ; cp dist/katex.min.css OUT/katex/
// 打印：browser_exec → cdp('Page.printToPDF', preferCSSPageSize=True, printBackground=True)
// 自检：grep -c '\$' OUT/10-x_解答.html  必须为 0
