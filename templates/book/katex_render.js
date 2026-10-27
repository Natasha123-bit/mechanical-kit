#!/usr/bin/env node
// katex_render.js — 批渲染公式：stdin 收 {katex, jobs:[{tex,display}]}，stdout 回 HTML 数组
// 渲染失败（未知命令、括号不配对）直接非零退出并把 TeX 带出来，绝不静默降级成红色问号。
const fs = require('fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const katex = require(payload.katex);
const out = payload.jobs.map((j, i) => {
  try {
    return katex.renderToString(j.tex, {
      displayMode: !!j.display,
      throwOnError: true,
      strict: 'ignore',
      output: 'html',
    });
  } catch (e) {
    process.stderr.write(`公式 #${i} 渲染失败: ${e.message}\n  TeX: ${j.tex}\n`);
    process.exit(1);
  }
});
process.stdout.write(JSON.stringify(out));
