"""Spec for the preview-environment indexing guard.

The preview env must never be indexed. A single env flag (IS_PREVIEW) turns on
an X-Robots-Tag header on every response; production leaves it off.
"""

from django.test import Client, override_settings


class DescribePreviewIndexingHeader:
    def it_is_absent_on_normal_responses(self, client: Client) -> None:
        assert "X-Robots-Tag" not in client.get("/").headers

    @override_settings(IS_PREVIEW=True)
    def it_marks_every_preview_response_noindex(self, client: Client) -> None:
        assert client.get("/").headers["X-Robots-Tag"] == "noindex, nofollow"

    @override_settings(IS_PREVIEW=True)
    def it_marks_preview_404s_noindex_too(self, client: Client) -> None:
        assert client.get("/unknown").headers["X-Robots-Tag"] == "noindex, nofollow"
