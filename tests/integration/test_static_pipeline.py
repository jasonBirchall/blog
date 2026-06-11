"""Integration spec for the static pipeline: collectstatic must run cleanly.

Exercises Django's staticfiles framework end-to-end against WhiteNoise's
manifest storage (the production storage), writing into a throwaway directory.
The test settings use plain storage so templates resolve {% static %} without a
manifest, so these specs opt into the manifest storage explicitly.
"""

from pathlib import Path

from django.core.management import call_command
from django.test import override_settings

_MANIFEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}


class DescribeCollectstatic:
    def it_collects_without_error(self, tmp_path: Path) -> None:
        with override_settings(STATIC_ROOT=str(tmp_path), STORAGES=_MANIFEST_STORAGES):
            call_command("collectstatic", "--noinput", "--clear", verbosity=0)
        # The manifest storage writes this; its presence proves hashing completed.
        assert (tmp_path / "staticfiles.json").exists()

    def it_collects_the_project_stylesheet(self, tmp_path: Path) -> None:
        with override_settings(STATIC_ROOT=str(tmp_path), STORAGES=_MANIFEST_STORAGES):
            call_command("collectstatic", "--noinput", "--clear", verbosity=0)
        assert (tmp_path / "css" / "main.css").exists()
