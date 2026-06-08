"""Integration spec for the static pipeline: collectstatic must run cleanly.

Exercises Django's staticfiles framework end-to-end against WhiteNoise's
manifest storage, writing into a throwaway directory so the test is isolated.
"""

from pathlib import Path

from django.core.management import call_command
from django.test import override_settings


class DescribeCollectstatic:
    def it_collects_without_error(self, tmp_path: Path) -> None:
        with override_settings(STATIC_ROOT=str(tmp_path)):
            call_command("collectstatic", "--noinput", "--clear", verbosity=0)
        # WhiteNoise's manifest storage writes this; its presence proves the
        # hashing/manifest step completed.
        assert (tmp_path / "staticfiles.json").exists()

    def it_collects_the_project_stylesheet(self, tmp_path: Path) -> None:
        with override_settings(STATIC_ROOT=str(tmp_path)):
            call_command("collectstatic", "--noinput", "--clear", verbosity=0)
        assert (tmp_path / "css" / "main.css").exists()
