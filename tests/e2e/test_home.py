"""End to end spec for the public home page via the django test client."""

from django.test import Client


class DescribeHomePage:
    def it_responds_200_to_the_root_path(self, client: Client) -> None:
        assert client.get("/").status_code == 200

    def it_serves_plain_text(self, client: Client) -> None:
        response = client.get("/")
        assert response.headers["Content-Type"].startswith("text/plain")

    def it_returns_404_for_unknown_paths(self, client: Client) -> None:
        assert client.get("/unknown").status_code == 404
