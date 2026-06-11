"""Structural a11y and HTML5-validity specs for the base template.

A browserless proxy for the axe/HTML5 acceptance: assert the semantic skeleton
(landmarks, one h1, lang, skip link, feed discovery, no JS) and that the
rendered page parses with zero HTML5 parse errors.
"""

import html5lib
from django.test import Client


def _html(client: Client) -> str:
    return client.get("/").content.decode()


class DescribeBaseTemplate:
    def it_serves_html(self, client: Client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/html")

    def it_declares_language_and_charset(self, client: Client) -> None:
        html = _html(client)
        assert "<html lang=" in html
        assert "<meta charset=" in html

    def it_is_responsive(self, client: Client) -> None:
        assert 'name="viewport"' in _html(client)

    def it_has_a_single_h1(self, client: Client) -> None:
        assert _html(client).count("<h1") == 1

    def it_uses_landmark_elements(self, client: Client) -> None:
        html = _html(client)
        for tag in ("<header", "<nav", "<main", "<footer"):
            assert tag in html

    def it_offers_a_skip_link_to_main(self, client: Client) -> None:
        html = _html(client)
        assert 'href="#main"' in html
        assert 'id="main"' in html

    def it_advertises_the_atom_feed(self, client: Client) -> None:
        html = _html(client)
        assert 'rel="alternate"' in html
        assert 'type="application/atom+xml"' in html
        assert "/feed.xml" in html

    def it_links_a_stylesheet(self, client: Client) -> None:
        assert 'rel="stylesheet"' in _html(client)

    def it_ships_no_javascript(self, client: Client) -> None:
        assert "<script" not in _html(client)


class DescribeHtml5Validity:
    def it_parses_with_no_html5_errors(self, client: Client) -> None:
        parser = html5lib.HTMLParser()
        parser.parse(client.get("/").content)
        assert parser.errors == []
