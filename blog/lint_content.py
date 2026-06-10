"""Standalone content linter CLI (the I/O adapter around blog.linting).

    uv run python -m blog.lint_content [content_dir] [--tags tags.yml]

Exit codes: 0 clean, 1 problems found, 2 bad invocation.
"""

import argparse
import sys
from pathlib import Path

from blog.linting import lint_content
from blog.tags import load_tag_vocabulary


def _read_documents(content_dir: Path) -> dict[str, str]:
    return {
        str(path.relative_to(content_dir)): path.read_text(encoding="utf-8")
        for path in sorted(content_dir.rglob("*.md"))
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lint-content", description="Lint content/ Markdown.")
    parser.add_argument("content_dir", nargs="?", default="content", type=Path)
    parser.add_argument("--tags", default="tags.yml", type=Path)
    args = parser.parse_args(argv)

    content_dir: Path = args.content_dir
    if not content_dir.is_dir():
        print(f"No such content directory: {content_dir}", file=sys.stderr)
        return 2

    documents = _read_documents(content_dir)
    vocabulary = load_tag_vocabulary(args.tags)
    errors = lint_content(documents, vocabulary)
    for error in errors:
        print(f"{error.path}:{error.line}: {error.message}")
    summary = f"{len(errors)} problem(s) in {len(documents)} file(s)."
    print(summary, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
