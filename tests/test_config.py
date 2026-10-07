from __future__ import annotations

import pytest

from sportapi import ConfigurationError, SportAPI

from .conftest import API_KEY, BASE_URL


def test_no_credentials_means_demo() -> None:
    api = SportAPI()
    assert api.is_demo
    assert repr(api) == "SportAPI(demo=True)"


def test_env_vars_enable_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTAPI_KEY", API_KEY)
    monkeypatch.setenv("SPORTAPI_BASE_URL", BASE_URL + "/")
    api = SportAPI()
    assert not api.is_demo
    assert api.base_url == BASE_URL  # trailing slash removed


def test_arguments_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTAPI_KEY", "env-key")
    monkeypatch.setenv("SPORTAPI_BASE_URL", "https://env.example.test")
    api = SportAPI(api_key=API_KEY, base_url=BASE_URL)
    assert api.base_url == BASE_URL


def test_key_never_in_repr() -> None:
    api = SportAPI(api_key=API_KEY, base_url=BASE_URL)
    assert API_KEY not in repr(api)
    assert API_KEY not in repr(api._config)


@pytest.mark.parametrize(
    ("key", "url", "missing"),
    [(API_KEY, None, "SPORTAPI_BASE_URL"), (None, BASE_URL, "SPORTAPI_KEY")],
)
def test_partial_configuration_is_an_error(key: str, url: str, missing: str) -> None:
    with pytest.raises(ConfigurationError, match=missing):
        SportAPI(api_key=key, base_url=url)


def test_demo_false_requires_credentials() -> None:
    with pytest.raises(ConfigurationError):
        SportAPI(demo=False)


def test_demo_true_ignores_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTAPI_KEY", API_KEY)
    monkeypatch.setenv("SPORTAPI_BASE_URL", BASE_URL)
    assert SportAPI(demo=True).is_demo


def test_base_url_must_be_absolute() -> None:
    with pytest.raises(ConfigurationError, match="absolute"):
        SportAPI(api_key=API_KEY, base_url="api.example.test")


def test_blank_values_count_as_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPORTAPI_KEY", "  ")
    monkeypatch.setenv("SPORTAPI_BASE_URL", "")
    assert SportAPI().is_demo
