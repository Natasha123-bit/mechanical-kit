#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""md2html.py — 教材范式计算书 Markdown → 可打印 HTML（KaTeX 预渲染）

用法：
    md2html.py 计算书.md                 # → 计算书.html（同目录）
    md2html.py 计算书.md --pdf           # → 计算书.html + 计算书.pdf（Chrome 打印）
    md2html.py 计算书.md -o 别的.html
    md2html.py --selftest                # 4 个坏样例必须报错、2 个好样例必须通过

Markdown 子集（够计算书用，故意不扩）：
    # / ## / ###        标题（更深一律按 h3）
    空行               分块；段落内相邻行直接拼接（中文不需要软空格）
    $…$                行内公式      **…**  粗体      <sub> 等 HTML 原样输出
    $$ … $$            独立公式（KaTeX display 模式）
    | a | b |          管道表：首行表头，第二行必须 |---|---|，列数必须一致
    表 n　标题         紧贴表格上方、以「表」开头的一段 → 表题（居中 9.5pt）
    - item / 1. item   列表

铁律：表格与公式块前后必须空行、$$ 必须成对、表列数必须与表头一致、公式语法必须正确
——任一条不满足都带行号报错退出，不静默降级（静默降级比报错更难查）。
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KA_DIR = os.path.normpath(os.path.join(HERE, os.pardir, "katex"))
KA_JS = os.path.join(KA_DIR, "katex.min.js")
KA_CSS = os.path.join(KA_DIR, "katex.min.css")
KA_FONTS = os.path.join(KA_DIR, "fonts")
RENDER_JS = os.path.join(HERE, "katex_render.js")
BOOK_CSS = os.path.join(HERE, "book.css")

CHROME_GLOBS = [
    "~/.hermes/tools/chromium-*/chrome-mac-arm64/*.app/Contents/MacOS/*",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


class MdError(Exception):
    pass


# ---------------------------------------------------------------- 行内
BOLD = re.compile(r"\*\*(.+?)\*\*")
IMG_LINE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)$")
IMATH = re.compile(r"\$(?!\$)([^$\n]+?)\$")


def inline(text, lineno, jobs):
    """提取 $…$ 与 **…**，公式换成 \x00M<i>\x00 占位。"""
    def rep(m):
        jobs.append((m.group(1).strip(), False))
        return "\x00M%d\x00" % (len(jobs) - 1)
    text = IMATH.sub(rep, text)
    text = BOLD.sub(r"<b>\1</b>", text)
    return text


# ---------------------------------------------------------------- 表格
SEP = re.compile(r"^:?-{1,}:?$")


def cells(line, lineno):
    s = line.strip()
    if not s.startswith("|"):
        raise MdError(f"第 {lineno} 行：表格行必须以 | 开头")
    s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    out, buf, esc = [], [], False
    for ch in s:
        if esc:
            buf.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == "|":
            out.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf).strip())
    return out


# ---------------------------------------------------------------- 块解析
def parse(text):
    """返回 [(kind, payload, lineno)]，kind ∈ h1..h3 / p / math / table / list。"""
    lines = text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        no = i + 1
        if not s:
            i += 1
            continue

        if s.startswith("$$"):
            body, first = [], s[2:]
            if first.endswith("$$") and first[:-2].strip():
                blocks.append(("math", first[:-2].strip(), no))
                i += 1
                continue
            if first:
                body.append(first)
            i += 1
            closed = False
            while i < len(lines):
                t = lines[i].strip()
                if t.endswith("$$"):
                    body.append(t[:-2])
                    closed = True
                    i += 1
                    break
                body.append(lines[i])
                i += 1
            if not closed:
                raise MdError(f"第 {no} 行起的 $$ 公式块没有闭合")
            tex = "\n".join(body).strip()
            if not tex:
                raise MdError(f"第 {no} 行的 $$ 公式块是空的")
            blocks.append(("math", tex, no))
            continue

        if s.startswith("#"):
            lvl = len(s) - len(s.lstrip("#"))
            if lvl > 6 or not s[lvl:].strip():
                raise MdError(f"第 {no} 行：标题格式不对（写成 # 标题）")
            blocks.append((f"h{min(lvl, 3)}", s[lvl:].strip(), no))
            i += 1
            continue

        if s.startswith("|"):
            rows, start = [], no
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append((cells(lines[i], i + 1), i + 1))
                i += 1
            if len(rows) < 2:
                raise MdError(f"第 {start} 行的表格缺少分隔行 |---|---|")
            if not all(SEP.match(c) for c in rows[1][0]):
                raise MdError(f"第 {rows[1][1]} 行：表格第二行必须是 |---|---| 分隔行")
            ncol = len(rows[0][0])
            for cs, ln in rows:
                if len(cs) != ncol:
                    raise MdError(f"第 {ln} 行：表格这一行有 {len(cs)} 列，表头是 {ncol} 列")
            blocks.append(("table", ([r[0] for r in rows[0:1]][0], [r[0] for r in rows[2:]]), start))
            continue

        if re.match(r"^\s*([-*]|\d+\.)\s+", s):
            items, start = [], no
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                items.append((re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]).strip(), i + 1))
                i += 1
            blocks.append(("list", items, start))
            continue

        m = IMG_LINE.match(s)
        if m:
            blocks.append(("img", (m.group("alt").strip(), m.group("src").strip()), no))
            i += 1
            continue

        if s.startswith("<"):
            blocks.append(("p", s, no))
            i += 1
            continue

        buf = [s]
        i += 1
        while i < len(lines):
            t = lines[i].strip()
            if not t or t.startswith(("#", "|", "$$", "<")) or re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                break
            buf.append(t)
            i += 1
        blocks.append(("p", " ".join(buf), no))
    return blocks


# ---------------------------------------------------------------- KaTeX
def render_math(jobs):
    """jobs: [(tex, display)] → [html]，一次 node 批渲染。"""
    if not jobs:
        return []
    if not os.path.isfile(KA_JS):
        raise MdError(f"找不到 KaTeX 的 node 构建：{KA_JS}（应随 mdkit/templates/katex 一起提供）")
    payload = {"katex": KA_JS, "jobs": [{"tex": t, "display": d} for t, d in jobs]}
    p = subprocess.run([node_bin(), RENDER_JS], input=json.dumps(payload),
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise MdError("公式渲染失败（KaTeX 抛错，说明 LaTeX 里有未知命令或括号不配对）：\n"
                      + (p.stderr.strip() or p.stdout.strip()))
    return json.loads(p.stdout)


def node_bin():
    for c in (os.path.expanduser("~/.local/bin/node"), "/opt/homebrew/bin/node", "/usr/local/bin/node"):
        if os.path.isfile(c):
            return c
    return shutil.which("node") or "node"


# ---------------------------------------------------------------- 渲染
def build_blocks(blocks, jobs):
    out = []          # html 行
    for idx, (kind, pay, no) in enumerate(blocks):
        if kind == "math":
            jobs.append((pay, True))
            out.append('<div class="fm">\x00M%d\x00</div>' % (len(jobs) - 1))
        elif kind in ("h1", "h2", "h3"):
            out.append(f"<{kind}>{inline(pay, no, jobs)}</{kind}>")
        elif kind == "p":
            nxt = blocks[idx + 1][0] if idx + 1 < len(blocks) else None
            if nxt == "table" and re.match(r"^表\s*\d", pay):
                out.append(f'<div class="cap">{pay}</div>')
            else:
                out.append(f"<p>{inline(pay, no, jobs)}</p>")
        elif kind == "table":
            head, rows = pay
            out.append('<div class="tbl"><table>')
            out.append("<tr>" + "".join(f"<th>{inline(c, 0, jobs)}</th>" for c in head) + "</tr>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{inline(c, 0, jobs)}</td>" for c in r) + "</tr>")
            out.append("</table></div>")
        elif kind == "img":
            alt, src = pay
            if src is None:
                raise MdError(f"第 {no} 行：插图路径没解析成功（{alt}）")
            cap = f"<figcaption>{inline(alt, no, jobs)}</figcaption>" if alt else ""
            out.append(f'<figure class="fig"><img src="{src}" alt="{alt}">{cap}</figure>')
        elif kind == "list":
            tag = "ol" if re.match(r"^\d+\.", blocks[idx][1][0][0] or "") else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(t, ln, jobs)}</li>" for t, ln in pay) + f"</{tag}>")
    return out


def resolve_img(src, md_path, out_path):
    """插图路径解析：相对 md 文件目录；输出里优先用相对 out 目录的路径，否则 file:// 绝对 URI。

    找不到文件直接抛错——说明书里一张图裂了比 md 少一行更致命。
    """
    if re.match(r"^(https?:|data:)", src):
        return src
    md_dir = os.path.dirname(os.path.abspath(md_path))
    out_dir = os.path.dirname(os.path.abspath(out_path)) if out_path else md_dir
    full = src if os.path.isabs(src) else os.path.join(md_dir, src)
    if not os.path.isfile(full):
        raise MdError(f"插图不存在：{full}（写法 ![图题](相对 md 的路径)）")
    rel = os.path.relpath(full, out_dir)
    if not rel.startswith(".." + os.sep):
        return rel.replace(os.sep, "/")
    return "file://" + full


def convert(md_path, out_path=None):
    md = open(md_path, encoding="utf-8").read()
    blocks = parse(md)
    out_path0 = out_path or os.path.splitext(md_path)[0] + ".html"
    blocks = [(k, (resolve_img(v[1], md_path, out_path0), v[0])[::-1] if k == "img" else v, n)
              for k, v, n in blocks]
    jobs = []
    body = build_blocks(blocks, jobs)
    rendered = render_math(jobs)
    html_body = "\n".join(body)
    for k, h in enumerate(rendered):
        html_body = html_body.replace("\x00M%d\x00" % k, h)
    if "\x00M" in html_body:
        raise MdError("内部错误：有公式占位符没被替换")
    if "$" in html_body:
        raise MdError("成品里残留 $（公式没配对，或正文里有裸 $）："
                      + re.search(r".{0,30}\$.{0,30}", html_body).group(0))

    title = md_path
    for kind, pay, _ in blocks:
        if kind == "h1":
            title = re.sub(r"<[^>]+>", "", inline(pay, 0, [])).replace("&ensp;", " ").strip()
            break
    css = open(BOOK_CSS, encoding="utf-8").read()
    out_path = out_path or os.path.splitext(md_path)[0] + ".html"
    open(out_path, "w", encoding="utf-8").write(
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        '<link rel="stylesheet" href="katex/katex.min.css">\n'
        f"<style>{css}</style></head><body>\n{html_body}\n</body></html>\n")
    link_katex(os.path.dirname(os.path.abspath(out_path)))
    return out_path


def link_katex(dst_dir):
    """把 katex.min.css + fonts 放到 HTML 旁边，保证离线可开。"""
    dst = os.path.join(dst_dir, "katex")
    if not os.path.isdir(dst):
        os.makedirs(dst)
    if not os.path.isfile(os.path.join(dst, "katex.min.css")):
        shutil.copy(KA_CSS, dst)
    if not os.path.isdir(os.path.join(dst, "fonts")):
        shutil.copytree(KA_FONTS, os.path.join(dst, "fonts"))


def find_chrome():
    for pat in CHROME_GLOBS:
        hits = sorted(glob.glob(os.path.expanduser(pat)))
        if hits:
            return hits[-1]
    return None


def print_pdf(html_path, pdf_path=None):
    chrome = find_chrome()
    if not chrome:
        raise MdError("找不到 Chrome（试过 ~/.hermes/tools/chromium-* 与 /Applications）")
    pdf_path = pdf_path or os.path.splitext(html_path)[0] + ".pdf"
    p = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--allow-file-access-from-files",
                        "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}",
                        "--virtual-time-budget=12000", os.path.abspath(html_path)],
                       capture_output=True, text=True)
    if not os.path.isfile(pdf_path):
        raise MdError("Chrome 没有产出 PDF：\n" + (p.stderr.strip()[-800:] or "(无 stderr)"))
    return pdf_path


# ---------------------------------------------------------------- 自检
BAD = [
    ("表格列数不齐", "| a | b |\n|---|---|\n| 1 |\n", "列"),
    ("表格缺分隔行", "| a | b |\n| 1 | 2 |\n", "分隔行"),
    ("公式块未闭合", "正文\n\n$$\na=1\n", "没有闭合"),
    ("公式语法错误", "$$\n\\frac{1}{\n$$\n", "公式渲染失败"),
    ("插图文件不存在", "# 标题\n\n![图 1　不存在](nope.svg)\n", "插图不存在"),
]
GOOD = [
    ("纯文本", "# 标题\n\n第一段。\n\n## （1）小节\n\n第二段含 **粗体** 与 <sub>1</sub>。\n"),
    ("公式与表", "# 标题\n\n$$a^{2}+b^{2}=c^{2}$$\n\n行内 $x_{1}$ 公式。\n\n"
                 "表 1　示例\n\n| 名称 | 代号 | 数值 |\n|---|---|---|\n| 模数 | m | 6.3 |\n"),
    ("插图与图题", "# 标题\n\n正文。\n\n![图 1　示例插图](fig.svg)\n\n后续正文。\n"),
    ("残缺标记当正文", "# 标题\n\n![图 1 缺右括号](a.svg\n"),
]


def selftest():
    import tempfile
    fails = 0
    with tempfile.TemporaryDirectory() as td:
        for name, body, key in BAD:
            p = os.path.join(td, "bad.md")
            open(p, "w", encoding="utf-8").write(body)
            r = subprocess.run([sys.executable, __file__, p], capture_output=True, text=True)
            ok = r.returncode != 0 and key in (r.stderr + r.stdout)
            print(f"  {'✓' if ok else '✗'} 坏样例「{name}」{'已报错' if ok else '没报错/报错不对'}")
            fails += 0 if ok else 1
        open(os.path.join(td, "fig.svg"), "w", encoding="utf-8").write(
            '<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="5mm" viewBox="0 0 10 5">'
            '<line x1="0" y1="0" x2="10" y2="5" stroke="#000"/></svg>')
        for name, body in GOOD:
            p = os.path.join(td, "good.md")
            open(p, "w", encoding="utf-8").write(body)
            r = subprocess.run([sys.executable, __file__, p], capture_output=True, text=True)
            ok = r.returncode == 0 and os.path.isfile(os.path.join(td, "good.html"))
            if ok:
                h = open(os.path.join(td, "good.html"), encoding="utf-8").read()
                ok = "$" not in h and "class=\"katex\"" in h if "公式" in name or "公式" in body else "$" not in h
                if "插图" in name:
                    ok = ok and "<figure class=\"fig\">" in h and "<figcaption>" in h
            print(f"  {'✓' if ok else '✗'} 好样例「{name}」{'通过' if ok else '失败：' + (r.stderr or '')[-300:]}")
            fails += 0 if ok else 1
    print(f"自检：{len(BAD) + len(GOOD)} 项，失败 {fails} 项")
    return 1 if fails else 0


def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description="计算书 Markdown → HTML/PDF")
    ap.add_argument("md", nargs="?", help="输入的 .md")
    ap.add_argument("-o", "--out", help="输出的 .html")
    ap.add_argument("--pdf", action="store_true", help="顺带用 Chrome 打印 PDF")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not a.md:
        ap.print_help()
        return 2
    try:
        html = convert(a.md, a.out)
        print("写出", html)
        if a.pdf:
            print("打印", print_pdf(html))
    except MdError as e:
        print(f"md2html: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
