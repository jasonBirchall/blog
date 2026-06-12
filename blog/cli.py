"""Authoring CLI: scaffold posts and promote Zettelkasten notes.

    uv run python -m blog.cli new <kind> <slug>
    uv run python -m blog.cli promote <zettel-path> [--kind <kind>]

Trunk-based: these only touch the working tree. You review and commit to main;
no branches, no PRs. Pure domain — no Django, so it runs without settings.
"""

import argparse
import datetime
import os
import re
import subprocess
import sys
from pathlib import Path

from blog.enums import Kind
from blog.linting import LintError, lint_content
from blog.tags import load_tag_vocabulary

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_STRIP.sub("-", text.lower()).strip("-")


def _stub(kind: str, slug: str, *, title: str, today: datetime.date) -> str:
    lines = [
        "---",
        f"title: {title}",
        f"slug: {slug}",
        f"date: {today.isoformat()}",
        f"kind: {kind}",
        "tags: []",
        "status: draft",
    ]
    if kind == Kind.LINK.value:
        lines += ["link:", "  url: https://example.com", "  source: TODO"]
    elif kind == Kind.QUOTE.value:
        lines += ["quote:", "  text: TODO", "  source: TODO"]
    lines.append("---")
    return "\n".join(lines) + "\n"


def _write(content_dir: Path, slug: str, text: str) -> Path:
    content_dir.mkdir(parents=True, exist_ok=True)
    path = content_dir / f"{slug}.md"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(text, encoding="utf-8")
    return path


def create_post(
    content_dir: Path,
    kind: str,
    slug: str,
    *,
    title: str = "TODO",
    today: datetime.date | None = None,
) -> Path:
    """Write a draft post stub with valid kind-appropriate frontmatter."""
    if kind not in {k.value for k in Kind}:
        raise ValueError(f"Unknown kind: {kind!r}")
    today = today or datetime.date.today()
    slug = _slugify(slug)
    return _write(content_dir, slug, _stub(kind, slug, title=title, today=today))


def promote_note(
    content_dir: Path,
    tags_path: Path,
    note_path: Path,
    *,
    kind: str = "note",
    today: datetime.date | None = None,
) -> tuple[Path, list[LintError]]:
    """Copy a note into content/ under a draft stub, then lint the whole corpus."""
    if not note_path.is_file():
        raise FileNotFoundError(note_path)
    if kind not in {k.value for k in Kind}:
        raise ValueError(f"Unknown kind: {kind!r}")
    today = today or datetime.date.today()
    slug = _slugify(note_path.stem)
    title = note_path.stem.replace("-", " ").replace("_", " ").title()
    body = note_path.read_text(encoding="utf-8")
    text = _stub(kind, slug, title=title, today=today) + "\n" + body
    path = _write(content_dir, slug, text)

    documents = {p.name: p.read_text(encoding="utf-8") for p in sorted(content_dir.glob("*.md"))}
    errors = lint_content(documents, load_tag_vocabulary(tags_path))
    return path, errors


def _open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR")
    if editor:
        subprocess.run([editor, str(path)], check=False)


def _cmd_new(args: argparse.Namespace) -> int:
    try:
        path = create_post(args.content, args.kind, args.slug)
    except (ValueError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Created {path}")
    if args.edit:
        _open_editor(path)
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    try:
        path, errors = promote_note(args.content, args.tags, args.path, kind=args.kind)
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Promoted {args.path} -> {path}")
    for error in errors:
        print(f"{error.path}:{error.line}: {error.message}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} lint problem(s); fix before committing.", file=sys.stderr)
        return 1
    print("Lint clean. Review, fill in TODOs, and commit to main.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blog", description="Authoring CLI for the blog.")
    sub = parser.add_subparsers(dest="command", required=True)

    new = sub.add_parser("new", help="Scaffold a new post stub.")
    new.add_argument("kind")
    new.add_argument("slug")
    new.add_argument("--content", type=Path, default=Path("content"))
    new.add_argument("--edit", action="store_true", help="Open the new file in $EDITOR.")
    new.set_defaults(func=_cmd_new)

    promote = sub.add_parser("promote", help="Promote a Zettelkasten note into content/.")
    promote.add_argument("path", type=Path)
    promote.add_argument("--kind", default="note")
    promote.add_argument("--content", type=Path, default=Path("content"))
    promote.add_argument("--tags", type=Path, default=Path("tags.yml"))
    promote.set_defaults(func=_cmd_promote)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
