"""End to end spec for the public home page via the django test client."""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


class DescribeHomePage:
    def it_responds_200_to_the_root_path(self, client: Client) -> None:
        assert client.get("/").status_code == 200

    def it_serves_html(self, client: Client) -> None:
        response = client.get("/")
        assert response.headers["Content-Type"].startswith("text/html")

    def it_returns_404_for_unknown_paths(self, client: Client) -> None:
        assert client.get("/unknown").status_code == 404

    def it_sets_no_cookies(self, client: Client) -> None:
        # Public routes are cookie-free: the session is never touched, so no
        # sessionid/csrftoken is emitted (constitution: no cookies on public routes).
        response = client.get("/")
        assert not response.cookies
        assert "Set-Cookie" not in response.headers

    def it_sets_no_cookies_even_on_a_missing_path(self, client: Client) -> None:
        assert not client.get("/unknown").cookies
