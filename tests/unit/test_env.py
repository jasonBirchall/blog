import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings.env import env_bool, env_list, require_env


class DescribeRequireEnv:
    def it_returns_the_value_when_the_variable_is_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TEST_ENV_VAR", "test_value")
        assert require_env("TEST_ENV_VAR") == "test_value"

    def it_fails_closed_when_the_variable_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EXAMPLE_KEY", raising=False)
        with pytest.raises(ImproperlyConfigured, match="EXAMPLE_KEY"):
            require_env("EXAMPLE_KEY")

    def it_treats_an_explicit_empty_string_as_a_real_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXAMPLE_KEY", "")
        assert require_env("EXAMPLE_KEY") == ""


class DescribeEnvBool:
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "Yes", "on", " on "])
    def it_reads_truthy_spellings_as_true(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLAG", raw)
        assert env_bool("FLAG") is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "banana"])
    def it_reads_everything_else_as_false(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("FLAG", raw)
        assert env_bool("FLAG") is False

    def it_uses_the_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("FLAG", raising=False)
        assert env_bool("FLAG", default=True) is True


class DescribeEnvList:
    def it_splits_a_comma_separated_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOSTS", "a.example,b.example")
        assert env_list("HOSTS") == ["a.example", "b.example"]

    def it_strips_whitespace_and_drops_empty_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOSTS", " a.example , , b.example ,")
        assert env_list("HOSTS") == ["a.example", "b.example"]

    def it_returns_the_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOSTS", raising=False)
        assert env_list("HOSTS", default=["fallback"]) == ["fallback"]
