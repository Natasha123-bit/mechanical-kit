#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mdkit —— 机械设计/机械原理工具根的统一入口。

工具根布局（本文件所在目录）：
    lib/<book>/<主题>_chNN.py + _tests.py    公式库（式号即函数名，表值 dict，例题断言）
    bin/                                     Swift 小工具：ocrbox ocrpdf renderall chmap pdfsplit pdftextlayer
    book/                                    book_prepare.py + book_toc.json（拆章总控）
    check/                                   verify_table_cells / verify_drawing_lines / verify_numbers
                                             span_check / index_diff / 编号一致性
    draw/gbdraw.py                           GB 图元函数（零件图 / 图解法作图）

常用：
    mdkit.py --version                   打印版本（读仓库根 VERSION）
    mdkit.py list                        列出某本书的全部公式库
    mdkit.py lib 8                       打印第 8 章库的公开函数签名 + docstring 首行
    mdkit.py test all                    双解释器跑全部断言（验收第一关）
    mdkit.py test 8 --py 312             只跑第 8 章、只用 python3.12
    mdkit.py ocr 页.png                  带坐标 OCR（读图上的坐标刻度）
    mdkit.py probe 书.pdf                探文本层（chars=0 或乱码 → 必须 OCR）
    mdkit.py page 图.pdf ./out            PDF 逐页转 PNG（默认 scale=2）
    mdkit.py chmap 整本.pdf -o 页眉.jsonl
    mdkit.py split 整本.pdf map.json ./章节PDF
    mdkit.py prepare ...                 透传给 book/book_prepare.py
    mdkit.py check 图.png --page 297x210 --scan y=85 --scan x=75
    mdkit.py tables belt_ch08 表8_4_单根基本额定功率P0 ch08/p009.png
    mdkit.py numbers 答案.md --corpus raw/sources/design
    mdkit.py book 计算书.md [--pdf]       Markdown 计算书 → 可打印 HTML（KaTeX 预渲染）
    mdkit.py book --selftest              转换器自检（4 坏样例必须报错 + 2 好样例必须过）

验收与对账子命令（都透传给 scripts/ 或 check/ 下的脚本，参数原样往后接）：
    mdkit.py audit  handoff-ch04 key_ch04 …   handoff ↔ 库逐格对账
    mdkit.py ranges <lib_dir>                 区间行标签能否按数值查（探针）
    mdkit.py missing <模块名…>                「空值且无 merges」的格（抓同源漏读）
    mdkit.py state handbook <lib_dir>         文档 ↔ 磁盘对账（快照/断言/状态/契约）
    mdkit.py paths                            路径迁移自检
    mdkit.py span --check                     跨页判定（续表归属；可 --md 出报告）
    mdkit.py index [--md 出.md]               表清单 ↔ 章库 ↔ 索引.json 三方对账
    mdkit.py numbering                        式/表/图编号一致性（文档 ↔ 库，check/编号一致性.py）
    mdkit.py handscan footer|tables <book>    无页眉手册：页脚造伪 chmap / 表号归集

解释器：公式库双解释器都能跑；check/*（numpy + PIL 只装在 ~/Library/Python/3.9）自动走
/usr/bin/python3，不用调用方记。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT / "lib"
BIN = ROOT / "bin"
CHECK = ROOT / "check"
BOOK = ROOT / "book"
DRAW = ROOT / "draw"

def _version() -> str:
    """版本号唯一真源：仓库根的 VERSION 文件（README、架构图、git tag 都跟它走）。"""
    vf = ROOT / "VERSION"
    return vf.read_text(encoding="utf-8").strip() if vf.exists() else "0.0.0-dev"


PY39 = Path("/usr/bin/python3")
PY312 = Path.home() / ".local/bin/python3.12"
DEFAULT_BOOK = "design"


# ---------------------------------------------------------------- helpers
def _die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"mdkit: {msg}", file=sys.stderr)
    sys.exit(2)


def _book_dir(book: str) -> Path:
    d = LIB / book
    if not d.is_dir():
        avail = ", ".join(sorted(p.name for p in LIB.iterdir() if p.is_dir())) or "(空)"
        _die(f"没有这本书的库目录: {d}\n现有: {avail}")
    return d


def _libs(book: str) -> list:
    """返回 [(chN, 主库路径, 测试路径或 None)]，按章号排序。"""
    d = _book_dir(book)
    out = []
    for p in sorted(d.glob("*_ch[0-9][0-9].py")):
        if p.name.endswith("_tests.py"):
            continue
        ch = int(p.stem.rsplit("_ch", 1)[1])
        t = p.with_name(p.stem + "_tests.py")
        out.append((ch, p, t if t.exists() else None))
    return sorted(out)


def _pick(args: list) -> Path:
    """把 '8' / 'ch08' / 'belt_ch08' 解析成一个库文件。"""
    if not args:
        _die("要给章号或库名，例如 8 / ch08 / belt_ch08")
    key = args[0].strip()
    book = DEFAULT_BOOK
    rest = [a for a in args[1:] if not a.startswith("--")]
    if "--book" in args:
        book = args[args.index("--book") + 1]
    elif rest:
        book = rest[0]
    libs = _libs(book)
    if key.isdigit():
        for ch, p, _ in libs:
            if ch == int(key):
                return p
    for _, p, _ in libs:
        if p.stem == key or p.stem.split("_ch")[0] == key or p.name == key:
            return p
    _die(f"{book} 里找不到 {key}；用 `mdkit.py list --book {book}` 看现有库")


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _bin(name: str) -> Path:
    exe = BIN / name
    if exe.exists():
        return exe
    src = BIN / f"{name}.swift"
    if src.exists():
        print(f"  编译 {src.name} …", file=sys.stderr)
        subprocess.run(["swiftc", "-O", str(src), "-o", str(exe)], check=True)
        return exe
    _die(f"bin/{name} 不存在，也没有 {name}.swift")


def _run(cmd: list, cwd: Path | None = None) -> int:
    print("+", " ".join(str(c) for c in cmd), file=sys.stderr)
    return subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None).returncode


# ---------------------------------------------------------------- 子命令
def cmd_list(argv: list) -> int:
    book = argv[argv.index("--book") + 1] if "--book" in argv else DEFAULT_BOOK
    libs = _libs(book)
    if not libs:
        _die(f"{book} 下没有 *_chNN.py")
    print(f"# {book}  ({LIB / book})")
    print(f"{'章':>3}  {'库':<22} {'字节':>7}  测试  首行 docstring")
    for ch, p, t in libs:
        doc = (inspect.getdoc(_load(p)) or "").split("\n")[0][:52] if False else ""
        doc = _first_doc(p)
        print(f"{ch:>3}  {p.name:<22} {p.stat().st_size:>7}  {'✓' if t else '—':<4}  {doc}")
    print(f"\n共 {len(libs)} 个库；测试文件 {sum(1 for _,_,t in libs if t)} 个")
    return 0


def _first_doc(p: Path) -> str:
    """取模块 docstring 首行（不 import，避免副作用）。"""
    try:
        import ast

        tree = ast.parse(p.read_text(encoding="utf-8"))
        d = ast.get_docstring(tree) or ""
        return d.split("\n")[0][:60]
    except Exception:
        return ""


def cmd_lib(argv: list) -> int:
    """打印该库的公开 API：函数签名 + docstring 首行 + 表值 dict。"""
    pos = [a for a in argv]
    path = _pick(pos)
    mod = _load(path)
    print(f"# {path.name}  ({path})")
    fns, consts = [], []
    for name, obj in vars(mod).items():
        if name.startswith("_"):
            continue
        owner = getattr(obj, "__module__", None)
        if owner and owner != mod.__name__:
            continue                      # 排除 import 进来的 math.xxx / NamedTuple 等
        if inspect.isfunction(obj):
            try:
                sig = str(inspect.signature(obj))
            except (TypeError, ValueError):
                sig = "(…)"
            doc = (inspect.getdoc(obj) or "").split("\n")[0]
            fns.append((name, sig, doc))
        elif isinstance(obj, dict):
            consts.append((name, len(obj)))
    for name, sig, doc in fns:
        print(f"  {name}{sig}")
        if doc:
            print(f"      {doc[:110]}")
    if consts:
        print("\n  表值 dict：")
        for name, n in consts:
            print(f"    {name}  ({n} 项)")
    print(f"\n共 {len(fns)} 个函数、{len(consts)} 个表 dict")
    return 0


def _books() -> list:
    """lib/ 下的书（有内容的目录）。"""
    return sorted(p.name for p in LIB.iterdir()
                  if p.is_dir() and not p.name.startswith("_") and any(p.iterdir()))


def _test_targets(book: str) -> list:
    """[(标签, 测试脚本, cwd)]。两种约定都认：
       A) 章库 <主题>_chNN.py + 同名 _tests.py（design / handbook）
       B) 测试运行器 _tests.py + test_*.py（drawing）
    """
    d = _book_dir(book)
    out = []
    cases = list(d.glob("test_*.py"))
    runner = d / "_tests.py"
    if runner.exists() and cases:
        out.append((f"runner({len(cases)} 个 test_*.py)", runner, d))
    for ch, p, t in _libs(book):
        if t:
            out.append((f"ch{ch:02d} {p.stem}", t, d))
    return out


_PASS = re.compile(r"通过\s*(\d+)")
_ASSERT = re.compile(r"断言\s*(\d+)\s*条")
_SKIP = re.compile(r"跳过\s*(\d+)")


def cmd_test(argv: list) -> int:
    """双解释器跑断言。--book 缺省 = 全部书；跑了 0 项断言按失败处理（假绿比红更危险）。"""
    book_arg = argv[argv.index("--book") + 1] if "--book" in argv else "all"
    which = argv[argv.index("--py") + 1] if "--py" in argv else "both"
    skip = {"--book", "--py", "both", "39", "312", "all", book_arg}
    target = next((a for a in argv if not a.startswith("--") and a not in skip), "all")
    books = _books() if book_arg in ("all", "") else [book_arg]
    pys = []
    if which in ("both", "39") and PY39.exists():
        pys.append(PY39)
    if which in ("both", "312") and PY312.exists():
        pys.append(PY312)
    if not pys:
        pys = [Path(sys.executable)]

    bad = ran = total = skipped = 0
    for book in books:
        targets = _test_targets(book)
        if not targets:
            print(f"\n=== {book} ===  (无测试目标：既没有 *_chNN.py+_tests.py，也没有 _tests.py+test_*.py)")
            continue
        if target != "all":
            pick = _pick([target, "--book", book])
            targets = [t for t in targets if t[1] == pick]
            if not targets:
                print(f"\n=== {book} ===  ({target} 没有测试文件)")
                continue
        for py in pys:
            print(f"\n=== {book} · {py.name} ===")
            for label, script, cwd in targets:
                r = subprocess.run([str(py), script.name], cwd=str(cwd),
                                   capture_output=True, text=True)
                out = r.stdout + r.stderr
                hits = _PASS.findall(out)          # 取最后一条汇总，别把分节小计加起来
                n = int(hits[-1]) if hits else 0
                a = _ASSERT.search(out)            # drawing 的 runner 报「用例 N / 断言 M 条」
                n_assert = int(a.group(1)) if a else n
                sk = int(_SKIP.findall(out)[-1]) if _SKIP.findall(out) else 0
                skipped += sk
                total += n_assert
                ran += 1
                last = (r.stdout.strip().split("\n") or [""])[-1][:56]
                mark = "rc=0 " if r.returncode == 0 else f"rc={r.returncode}"
                unit = f"{n:>4d} 用例/{n_assert:>5d} 断言" if a else f"{n:>5d} 项断言"
                tail = f"  ↷跳过 {sk}" if sk else ""
                print(f"  {label:<28} {mark}  {unit}{tail}  {last}")
                if r.returncode != 0:
                    bad += 1
                    print((r.stdout + r.stderr)[-800:])
    print(f"\n跑了 {ran} 个测试目标 / {total} 项断言；失败 {bad} 个"
          + (f"；跳过 {skipped} 项（缺 books/，不影响库内容）" if skipped else ""))
    if bad:
        return 1
    if ran == 0 or total == 0:
        print("★ 跑了 0 项断言 —— 这不是全绿，是没测：查 --book 与测试文件命名约定")
        return 1
    print("—— 全绿")
    return 0


def cmd_ocr(argv: list) -> int:
    return _run([_bin("ocrbox")] + argv)


def cmd_probe(argv: list) -> int:
    return _run([_bin("pdftextlayer")] + argv)


def cmd_page(argv: list) -> int:
    return _run([_bin("renderall")] + argv)


def cmd_ocrpdf(argv: list) -> int:
    return _run([_bin("ocrpdf")] + argv)


def cmd_chmap(argv: list) -> int:
    exe = _bin("chmap")
    if "-o" in argv:
        i = argv.index("-o")
        out = argv[i + 1]
        rest = [a for j, a in enumerate(argv) if j not in (i, i + 1)]
        with open(out, "w") as fh:
            return subprocess.run([str(exe)] + rest, stdout=fh).returncode
    return _run([exe] + argv)


def cmd_split(argv: list) -> int:
    return _run([_bin("pdfsplit")] + argv)


def cmd_prepare(argv: list) -> int:
    return _run([sys.executable, BOOK / "book_prepare.py"] + argv)


def cmd_check(argv: list) -> int:
    return _run([PY39, CHECK / "verify_drawing_lines.py"] + argv)


def cmd_tables(argv: list) -> int:
    libdir = _book_dir(DEFAULT_BOOK)
    env_cwd = libdir
    return _run([PY39, CHECK / "verify_table_cells.py"] + argv, cwd=env_cwd)


def cmd_numbers(argv: list) -> int:
    return _run([PY39, CHECK / "verify_numbers.py"] + argv)


def cmd_book(argv: list) -> int:
    """计算书 Markdown → HTML/PDF（templates/book/md2html.py）。"""
    return _run([sys.executable, ROOT / "templates" / "book" / "md2html.py"] + argv)


def cmd_path(argv: list) -> int:
    for k, v in [("root", ROOT), ("lib", LIB), ("bin", BIN), ("book", BOOK),
                 ("check", CHECK), ("draw", DRAW),
                 ("py39", PY39), ("py312", PY312)]:
        print(f"{k:<6} {v}  {'✓' if Path(v).exists() else '✗'}")
    return 0


# 验收/对账脚本透传：脚本真身在 skill 的 scripts/（随 skill 可移植），仓库镜像兜底。
SKILL_SCRIPTS = Path.home() / ".hermes/skills/engineering/mechanical-book-deposit/scripts"
MIRROR_SCRIPTS = ROOT / "skills" / "mechanical-book-deposit" / "scripts"


def _skill_script(name: str) -> Path:
    for d in (SKILL_SCRIPTS, MIRROR_SCRIPTS):
        if (d / name).exists():
            return d / name
    _die(f"找不到 {name}（查过 {SKILL_SCRIPTS} 与 {MIRROR_SCRIPTS}）")


def _passthrough(script: Path, argv: list) -> int:
    if not script.exists():
        _die(f"脚本不存在: {script}")
    return _run([PY39, script] + argv)


def cmd_audit(argv):     return _passthrough(_skill_script("audit_handoff_vs_lib.py"), argv)
def cmd_ranges(argv):    return _passthrough(_skill_script("check_lookup_ranges.py"), argv)
def cmd_missing(argv):   return _passthrough(_skill_script("scan_missing_cells.py"), argv)
def cmd_state(argv):     return _passthrough(_skill_script("verify_book_state.py"), argv)
def cmd_paths(argv):     return _passthrough(_skill_script("check_paths.py"), argv)
def cmd_handscan(argv):  return _passthrough(_skill_script("handbook_scan.py"), argv)
def cmd_span(argv):      return _passthrough(CHECK / "span_check.py", argv)
def cmd_index(argv):     return _passthrough(CHECK / "index_diff.py", argv)
def cmd_numbering(argv): return _passthrough(CHECK / "编号一致性.py", argv)


def cmd_selftest(argv: list) -> int:
    print(f"== 工具根自检 · v{_version()} ==")
    rc = cmd_path([])
    for name in ["ocrbox", "ocrpdf", "renderall", "chmap", "pdfsplit"]:
        exe = BIN / name
        print(f"  {name:<10} {'✓ 可执行' if exe.exists() and os.access(exe, os.X_OK) else '✗'}")
    n = cmd_test([])
    g = DRAW / "gbdraw.py"
    print(f"  gbdraw.py  {'✓' if g.exists() else '✗'}")
    if g.exists():
        n |= _run([PY39, g, "--selftest"])
    return n


CMDS = {
    "list": cmd_list, "lib": cmd_lib, "test": cmd_test,
    "ocr": cmd_ocr, "probe": cmd_probe, "page": cmd_page, "ocrpdf": cmd_ocrpdf,
    "chmap": cmd_chmap, "split": cmd_split, "prepare": cmd_prepare,
    "check": cmd_check, "tables": cmd_tables, "numbers": cmd_numbers,
    "path": cmd_path, "book": cmd_book, "selftest": cmd_selftest,
    # 验收 / 对账（透传脚本）
    "audit": cmd_audit, "ranges": cmd_ranges, "missing": cmd_missing,
    "state": cmd_state, "paths": cmd_paths, "handscan": cmd_handscan,
    "span": cmd_span, "index": cmd_index, "numbering": cmd_numbering,
}


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[1] in ("-V", "--version", "version"):
        print(f"mechanical-kit {_version()}")
        return 0
    if len(argv) < 2 or argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd not in CMDS:
        _die(f"未知子命令 {cmd}；可用: {', '.join(CMDS)}")
    return CMDS[cmd](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
