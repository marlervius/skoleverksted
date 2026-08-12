"""Compile repository Python sources while ignoring local virtualenvs/templates."""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path


SKIP_DIRECTORIES = {".git", ".venv", "venv", "node_modules", ".next", "output", "tmp"}


def main() -> int:
    roots = [Path(item) for item in sys.argv[1:]] or [Path("Skoleverksted")]
    failures: list[str] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files = [root]
        else:
            files = (
                item
                for item in root.rglob("*.py")
                if not any(part in SKIP_DIRECTORIES for part in item.parts)
            )
        for path in files:
            try:
                py_compile.compile(str(path), doraise=True)
            except py_compile.PyCompileError as exc:
                failures.append(f"{path}: {exc.msg}")
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
