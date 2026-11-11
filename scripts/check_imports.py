"""Every import under src/ is one Tally allows, read from the syntax tree (CLAUDE.md § Security).

Usage: uv run python scripts/check_imports.py

The word checks in rules.json catch ``socket`` and ``float`` written out, but not
``from urllib import request as r`` or ``import ssl``. This reads each file's imports
and fails on any module outside the list below, on a float literal, and when it
finds no file to read (a check that reads nothing must not pass). Division is not
flagged: ``/`` also joins paths, which a syntax tree cannot tell apart.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SOURCE = Path("src")
# The standard library Tally uses (ADR 0001), and Tally itself. Adding one is a decision.
ALLOWED = frozenset(
    {
        "__future__",
        "argparse",
        "codecs",
        "collections",
        "contextlib",
        "csv",
        "dataclasses",
        "datetime",
        "decimal",
        "itertools",
        "json",
        "logging",
        "os",
        "pathlib",
        "re",
        "sqlite3",
        "stat",
        "sys",
        "tally",
        "time",
        "tomllib",
        "types",
        "typing",
        "unicodedata",
    }
)


def problems(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    found = []
    for node in ast.walk(ast.parse(text, str(path))):
        line: int = getattr(node, "lineno", 1)
        if "rules-check-ignore:" in lines[line - 1]:
            continue  # the same exemption check-rules.js honours, with its reason on the line
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.Call) and getattr(node.func, "id", "") == "__import__":
            found.append(f"{path}:{line}: __import__ is not allowed")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            found.append(f"{path}:{line}: a float literal; amounts are exact")
        found += [
            f"{path}:{line}: imports {name}, which is not on the allowed list"
            for name in names
            if name.split(".")[0] not in ALLOWED
        ]
    return found


def main() -> int:
    files = sorted(SOURCE.rglob("*.py"))
    if not files:
        print(f"no Python files under {SOURCE}: the check read nothing", file=sys.stderr)
        return 1
    found = [problem for path in files for problem in problems(path)]
    for problem in found:
        print(problem, file=sys.stderr)
    print(f"{len(files)} files read, {len(found)} problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
