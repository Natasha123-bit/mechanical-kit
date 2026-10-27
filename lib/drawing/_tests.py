# -*- coding: utf-8 -*-
"""_tests.py —— drawing 库的断言运行器（ZCode 每章往里加 test_*.py）

用法：
    python3 lib/drawing/_tests.py            # 跑全部
    python3 lib/drawing/_tests.py ch08       # 只跑名字含 ch08 的用例
    python3 lib/drawing/_tests.py --list     # 列用例
约定：用例文件 lib/drawing/test_<主题>.py，函数名 test_*，失败用 assert（不要 try/except 吞掉）。
"""
import importlib.util
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent


def 载入(p: Path):
    spec = importlib.util.spec_from_file_location(f"_t_{p.stem}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def 用例():
    for p in sorted(HERE.glob("test_*.py")):
        m = 载入(p)
        for name in sorted(dir(m)):
            if name.startswith("test_") and callable(getattr(m, name)):
                yield f"{p.stem}::{name}", getattr(m, name)


def 断言数(key: str) -> int:
    """按 AST 统计命中用例文件里的 assert 条数（`通过 N` 数的是函数，不是断言）。"""
    import ast
    n = 0
    for p in sorted(HERE.glob("test_*.py")):
        if key and key not in p.stem:
            continue
        n += sum(isinstance(x, ast.Assert) for x in ast.walk(ast.parse(p.read_text(encoding="utf-8"))))
    return n


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else ""
    if key == "--list":
        for n, _ in 用例():
            print(n)
        return 0
    passed, failed = 0, []
    for name, fn in 用例():
        if key and key not in name:
            continue
        try:
            fn()
            passed += 1
        except Exception:
            failed.append((name, traceback.format_exc(limit=3)))
    print(f"通过 {passed}，失败 {len(failed)}；断言 {断言数(key)} 条（AST 统计）")
    for n, tb in failed:
        print(f"\n✗ {n}\n{tb}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
