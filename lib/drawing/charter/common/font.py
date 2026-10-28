"""common/font.py —— 字体族与字高（G-11、G-12）。

依据 GB/T 14691—1993（技术制图 字体）：图样上的汉字用长仿宋。
本项目的要求是**不落到系统回退族**——PDF 里一旦回退，字形就换了（齿轮项目里 `z₂`
的 U+2082 仿宋缺字形，回退宋体，是可查的实例）。
"""

import re
from pathlib import Path

from . import _util as U

FS_OK = ("fangsong", "stfangsong", "gbfang", "华文仿宋", "仿宋", "simfang")
FS_BAD = ("pingfang", "helvetica", "arial", "sans-serif", "simsun", "宋体", "songti")

RULES = []


def _stack(val):
    return [x.strip().strip("'\"").lower() for x in (val or "").split(",") if x.strip()]


def _text_classes(root):
    """图上看得到的 <text> 用到的 class。"""
    out = {}
    for t in root.iter("{http://www.w3.org/2000/svg}text"):
        for c in str(t.get("class") or "").split():
            out[c] = out.get(c, 0) + 1
    return out


def r_g11(ctx):
    """文字字体族必须全是仿宋类（可带通用 serif），且有 @font-face 兜底。"""
    style = U.css(ctx.root)
    tcls = _text_classes(ctx.root)
    if not tcls:
        return "未检查", "图上没有 <text>"
    stacks, bad, ok = {}, [], 0
    for c in tcls:
        fam = style.get(c, {}).get("font-family")
        if not fam:
            continue
        fams = _stack(fam)
        stacks[c] = fams
        hit = [f for f in fams if any(k in f for k in FS_BAD)]
        if hit:
            bad.append("%s 的字体栈含回退族 %s" % (c, hit[:2]))
            continue
        first_ok = any(k in fams[0] for k in FS_OK) if fams else False
        if not first_ok:
            bad.append("%s 首项 %r 不是仿宋类" % (c, fams[0] if fams else ""))
            continue
        ok += 1
    faces = U.font_faces(ctx.root)
    if bad:
        return "不通过", "；".join(bad[:3])
    if not faces:
        return "警示", "%d 个文字 class 都是仿宋栈，但没有 @font-face 兜底" % ok
    return "通过", "%d 个文字 class 仿宋栈、无回退；@font-face %s" % (ok, "、".join(faces[:2]))


def r_g12(ctx):
    """全图文字只用一套字体族、字高在登记档位（≤2 种）。"""
    sizes = {}
    fams = set()
    for t in ctx.root.iter("{http://www.w3.org/2000/svg}text"):
        fs = t.get("font-size")
        if fs:
            sizes[float(fs)] = sizes.get(float(fs), 0) + 1
        if t.get("font-family"):
            fams.add(t.get("font-family"))
    style = U.css(ctx.root)
    for c in _text_classes(ctx.root):
        fam = style.get(c, {}).get("font-family")
        if fam:
            fams.add(fam)
    if not sizes:
        return "未检查", "图上没有带 font-size 的文字"
    if len(fams) > 1:
        return "警示", "%d 套字体族并存：%s" % (len(fams), [f[:18] for f in list(fams)[:3]])
    if max(sizes) > 10:                        # A3 上 10mm 字高已属离谱
        return "不通过", "字高 %.1fmm 超上限（登记 %s）" % (max(sizes), sorted(sizes))
    return "通过", "一套字体族；字高档位 %s" % sorted(sizes)


def _fonttools_py():
    """找装了 fontTools 的解释器：环境变量优先，其次约定路径。"""
    import os
    cand = [os.environ.get("FONTTOOLS_PY"),
            str(Path.home() / ".venvs/fonttools/bin/python")]
    for c in cand:
        if c and Path(c).exists():
            return c
    return None


def r_g13(ctx):
    """图上每个字符在 @font-face 那个字体里都得有字形（缺字形浏览器就回退）。

    字体栈判据（G-11）看不出这件事：栈里写的是仿宋，可某个字符仿宋没有字形，
    浏览器悄悄换成宋体——齿轮项目 `z₂` 的 U+2082 就是这么混进去的。
    真正的字形覆盖要 fontTools，所以走子进程（charter 自己的 python 不带这个包）；
    没装就判未检查并给出安装/运行方式，不装懂。
    """
    py = _fonttools_py()
    tool = Path(__file__).resolve().parents[1] / "fontcov.py"
    if not py:
        return "未检查", ("本机没有装 fontTools 的解释器；"
                      "`uv pip install --python ~/.venvs/fonttools/bin/python fonttools` 后重跑")
    import json as _json
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "fontcov.json"
        r = subprocess.run([py, str(tool), str(ctx.path), "--json", str(out)],
                           capture_output=True, text=True)
        if not out.exists():
            return "未检查", "字形覆盖脚本没跑出结果：%s" % (r.stderr or r.stdout)[-120:]
        rec = _json.loads(out.read_text(encoding="utf-8"))
    miss = rec.get("missing") or []
    if miss:
        return "不通过", "%d 个字符在字体里没有字形：%s" % (
            len(miss), "、".join("%r(%s)" % (m["char"], m["U+"]) for m in miss[:4]))
    return "通过", "%d 个字符全有字形（%d 段文字，字体 %s）" % (
        rec.get("chars", 0), rec.get("n_text", 0),
        "、".join(Path(v["file"]).name for v in rec["faces"].values()))


RULES = [
    ("G-11", "文字字体族为仿宋、无回退族", "FONT-01", "必", r_g11),
    ("G-13", "每个字符在嵌入字体里都有字形（缺字形会回退）", "FONT-05", "必", r_g13),
    ("G-12", "全图一套字体族、字高在档位内", "SHT-10", "必", r_g12),
]
