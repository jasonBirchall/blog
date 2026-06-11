"""sync_content management command (a thin adapter over blog.sync)."""

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from blog.sync import read_documents, sync_content
from blog.tags import load_tag_vocabulary


class Command(BaseCommand):
    help = "Sync content/ Markdown into the database, or validate it with --check."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--check", action="store_true", help="Validate only; never write.")
        parser.add_argument("--content", type=Path, default=Path("content"))
        parser.add_argument("--tags", type=Path, default=Path("tags.yml"))

    def handle(self, *args: Any, **options: Any) -> None:
        documents = read_documents(options["content"])
        vocabulary = load_tag_vocabulary(options["tags"])
        report = sync_content(documents, vocabulary, write=not options["check"])

        for problem in report.errors:
            self.stderr.write(f"{problem.path}:{problem.line}: {problem.message}")
        if report.errors:
            raise CommandError(f"{len(report.errors)} content problem(s); database unchanged.")

        if options["check"]:
            self.stdout.write(
                self.style.SUCCESS(f"OK: {len(documents)} file(s) valid; nothing written.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Synced: {report.created} created, {report.updated} updated, "
                    f"{report.deactivated} deactivated."
                )
            )
