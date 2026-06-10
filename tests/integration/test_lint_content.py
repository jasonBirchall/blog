"""Integration spec: the linter CLI over a fixtures directory of known-bad files.

Exercises the filesystem walk + output formatting, and asserts the output is
precise and line-numbered (the N2.5 definition of done).
"""

from pathlib import Path

import pytest

from blog.lint_content import main

_FIXTURES = Path(__file__).parent.parent / "fixtures"
_BAD = _FIXTURES / "lint"
_TAGS = _FIXTURES / "lint_tags.yml"


class DescribeLintContentCli:
    def it_reports_line_numbered_errors_and_exits_nonzero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        code = main([str(_BAD), "--tags", str(_TAGS)])
        report = capsys.readouterr().out
        lines = report.splitlines()

        assert code == 1
        assert lines
        for line in lines:
            _path, lineno, _message = line.split(":", 2)
            assert lineno.strip().isdigit()  # every problem carries a line number

        assert any("Unknown tag" in line and "rust" in line for line in lines)
        assert any("ghost-post" in line for line in lines)
        assert any("Trailing whitespace" in line for line in lines)

    def it_exits_zero_on_an_empty_directory(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main([str(tmp_path), "--tags", str(_TAGS)]) == 0
