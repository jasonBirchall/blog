"""Specs for the static-files configuration (WhiteNoise)."""

from django.conf import settings


class DescribeStaticConfiguration:
    def it_serves_static_through_whitenoise(self) -> None:
        assert "whitenoise.middleware.WhiteNoiseMiddleware" in settings.MIDDLEWARE

    def it_places_whitenoise_directly_after_security_middleware(self) -> None:
        security = settings.MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
        whitenoise = settings.MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware")
        assert whitenoise == security + 1

    def it_uses_whitenoise_compressed_manifest_storage(self) -> None:
        assert (
            settings.STORAGES["staticfiles"]["BACKEND"]
            == "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )

    def it_includes_the_project_static_directory(self) -> None:
        assert any(str(path).endswith("static") for path in settings.STATICFILES_DIRS)
