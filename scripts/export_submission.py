#!/usr/bin/env python3
"""Print the archived MarketMaker class for a compatible contest template."""

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def extract_class() -> str:
    source = (ROOT / "bot.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    maker = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MarketMaker")
    return "\n".join(source.splitlines()[maker.lineno - 1:maker.end_lineno]) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Write a new class-only file instead of printing it")
    args = parser.parse_args()
    source = extract_class()
    if args.output is None:
        print(source, end="")
        return
    if args.output.exists():
        raise SystemExit(f"Already exists: {args.output}. Choose a new output path.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(source, encoding="utf-8")
    print(f"Saved the class to {args.output}; use it with the surrounding template types and imports.")


if __name__ == "__main__":
    main()
