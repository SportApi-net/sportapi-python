"""Live mode: requests are checked against a mocked transport (respx)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from sportapi import (
    LINE,
    LIVE,
    AccessDeniedError,
    AccessRestrictedError,
    APIError,
    AuthenticationError,
    GameFinishedError,
    GameNotFoundError,
    HTTPStatusError,
    InvalidKeyError,
    InvalidLanguageError,
    InvalidLineTypeError,
    KeyBlockedError,
    KeyExpiredError,
    KeyNotActiveError,
    LanguageNotAvailableError,
    MissingKeyError,
    PermissionDeniedError,
    SportAPI,
    TransportError,
    UnexpectedResponseError,
)

from .conftest import API_KEY, BASE_URL, example


def ok(body: Any, page: str = "/v1/x", **headers: str) -> httpx.Response:
    return httpx.Response(200, json={"status": 1, "page": page, "body": body}, headers=headers)


@pytest.fixture
def api() -> SportAPI:
    return SportAPI(api_key=API_KEY, base_url=BASE_URL)


@pytest.fixture
def mock() -> respx.MockRouter:
    with respx.mock(base_url=BASE_URL, assert_all_called=True) as router:
        yield router


@pytest.mark.parametrize(
    ("call", "path", "params"),
    [
        (lambda a: a.menu(LIVE), "/v1/menu/live/en", {}),
        (lambda a: a.menu(LINE, cybersport=True), "/v1/menu/line/en", {"cybersport": "true"}),
        (lambda a: a.sports(LIVE, lang="es"), "/v1/sports/live/es", {}),
        (lambda a: a.countries(1, LINE), "/v1/countries/1/line/en", {}),
        (lambda a: a.tournaments(1, 4, LIVE), "/v1/tournaments/1/4/live/en", {}),
        (lambda a: a.events(1, LIVE), "/v1/events/1/0/sub/50/live/en", {}),
        (
            lambda a: a.events(1, LIVE, tournament_id=1205475, odds=False),
            "/v1/events/1/1205475/sub/50/live/en",
            {"odds": "false"},
        ),
        (
            lambda a: a.events(1, LINE, full_line=True),
            "/v1/events/1/0/sub/50/line/en",
            {"match": "all"},
        ),
        (
            lambda a: a.events(40, LIVE, cybersport=True),
            "/v1/events/40/0/sub/50/live/en",
            {"cybersport": "true"},
        ),
        (
            lambda a: a.events_by_period(1, hours=2),
            "/v1/events/1/0/sub/50/line/2/0/en",
            {},
        ),
        (
            lambda a: a.events_by_period(1, tournament_id=1706694, days=2, odds=False),
            "/v1/events/1/1706694/sub/50/line/0/2/en",
            {"odds": "false"},
        ),
        (lambda a: a.search("Manchester City", LINE), "/v1/search/line/en/Manchester%20City", {}),
        (lambda a: a.search("a/b?c", LIVE), "/v1/search/live/en/a%2Fb%3Fc", {}),
        (lambda a: a.topmatches(LIVE), "/v1/topmatches/live/en", {}),
        (
            lambda a: a.topmatches(LINE, full=True, odds=False),
            "/v1/topmatches/line/en",
            {"full": "true", "odds": "false"},
        ),
        (lambda a: a.toplist(1), "/v1/toplist/1/en", {}),
        (lambda a: a.toplist(1, odds=False), "/v1/toplist/1/en", {}),  # odds needs full
        (lambda a: a.toplist(3, full=True), "/v1/toplist/3/en", {"full": "true"}),
        (lambda a: a.topchampionships(LINE), "/v1/topchampionships/line/en", {}),
    ],
)
def test_list_methods_build_documented_urls(
    api: SportAPI, mock: respx.MockRouter, call: Any, path: str, params: dict
) -> None:
    route = mock.get(path).mock(return_value=ok([]))
    assert call(api) == []
    request = route.calls.last.request
    assert request.url.raw_path.decode().split("?")[0] == path
    assert dict(request.url.params) == params
    assert request.headers["Package"] == API_KEY
    assert request.headers["Accept"] == "application/json"
    assert API_KEY not in str(request.url)


def test_event_url_and_parsing(api: SportAPI, mock: respx.MockRouter) -> None:
    payload = example("event.game-746146992.group.live.en.json")
    route = mock.get("/v1/event/746146992/group/live/en").mock(
        return_value=httpx.Response(200, json=payload)
    )
    match = api.event(746146992, LIVE)
    assert route.called
    assert match.opp_1_name == "Arsenal"
    assert len(match.markets) == 49


def test_event_odds_false_param(api: SportAPI, mock: respx.MockRouter) -> None:
    route = mock.get("/v1/event/5/group/line/en").mock(return_value=ok({"game_id": 5}))
    api.event(5, LINE, odds=False)
    assert dict(route.calls.last.request.url.params) == {"odds": "false"}


def test_account(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/account").mock(
        return_value=ok({"client": {"name": "Example"}, "your_ip": "203.0.113.7", "keys": []})
    )
    assert api.account().your_ip == "203.0.113.7"


def test_key_expiry_header_is_tracked(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/sports/live/en").mock(
        return_value=ok([], **{"X-Key-Expires": "2026-11-03T14:34:23.479Z"})
    )
    assert api.key_expires is None
    api.sports(LIVE)
    assert api.key_expires == datetime(2026, 11, 3, 14, 34, 23, 479000, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("code", "message", "exc", "base"),
    [
        (100, "Missing Package header", MissingKeyError, AuthenticationError),
        (100, "Invalid Package", InvalidKeyError, AuthenticationError),
        (100, "Package has expired", KeyExpiredError, AuthenticationError),
        (100, "Package is blocked", KeyBlockedError, AuthenticationError),
        (100, "Package is not active yet", KeyNotActiveError, AuthenticationError),
        (
            100,
            "Access from IP 203.0.113.50 is not allowed for this Package",
            AccessRestrictedError,
            AuthenticationError,
        ),
        (
            100,
            "Access from site example.org is not allowed for this Package",
            AccessRestrictedError,
            AuthenticationError,
        ),
        (100, "Access denied", AccessDeniedError, PermissionDeniedError),
        (
            100,
            "The language is not available in your package.",
            LanguageNotAvailableError,
            PermissionDeniedError,
        ),
        (100, "Invalid language", InvalidLanguageError, APIError),
        (90, "Wrong data type (accept only live or line)", InvalidLineTypeError, APIError),
        (100, "Something new", APIError, APIError),
    ],
)
@pytest.mark.parametrize("http_status", [200, 403])
def test_documented_errors_map_to_exceptions(
    api: SportAPI,
    mock: respx.MockRouter,
    code: int,
    message: str,
    exc: type,
    base: type,
    http_status: int,
) -> None:
    mock.get("/v1/menu/live/en").mock(
        return_value=httpx.Response(
            http_status, json={"error_code": code, "error_message": message}
        )
    )
    with pytest.raises(exc) as info:
        api.menu(LIVE)
    error = info.value
    assert isinstance(error, base)
    assert error.code == code and error.message == message
    assert error.http_status == http_status
    assert not error.retryable
    assert API_KEY not in str(error)


@pytest.mark.parametrize(
    ("message", "exc"),
    [("Game not found", GameNotFoundError), ("Game id finished", GameFinishedError)],
)
def test_event_messages(api: SportAPI, mock: respx.MockRouter, message: str, exc: type) -> None:
    mock.get("/v1/event/123/group/line/en").mock(
        return_value=ok({"message": message}, page="/v1/event")
    )
    with pytest.raises(exc) as info:
        api.event(123, LINE)
    assert info.value.game_id == 123
    assert info.value.message == message


def test_server_error_is_retryable(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/menu/live/en").mock(return_value=httpx.Response(502, text="Bad gateway"))
    with pytest.raises(HTTPStatusError) as info:
        api.menu(LIVE)
    assert info.value.http_status == 502 and info.value.retryable


def test_client_error_without_error_code(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/menu/live/en").mock(return_value=httpx.Response(404, json={"detail": "x"}))
    with pytest.raises(HTTPStatusError) as info:
        api.menu(LIVE)
    assert not info.value.retryable


def test_invalid_json(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/menu/live/en").mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(UnexpectedResponseError):
        api.menu(LIVE)


def test_unknown_envelope(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/menu/live/en").mock(return_value=httpx.Response(200, json={"foo": 1}))
    with pytest.raises(UnexpectedResponseError):
        api.menu(LIVE)


def test_body_of_wrong_type(api: SportAPI, mock: respx.MockRouter) -> None:
    mock.get("/v1/menu/live/en").mock(return_value=ok({"unexpected": True}))
    with pytest.raises(UnexpectedResponseError):
        api.menu(LIVE)


@pytest.mark.parametrize("error", [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")])
def test_network_errors(api: SportAPI, mock: respx.MockRouter, error: Exception) -> None:
    mock.get("/v1/menu/live/en").mock(side_effect=error)
    with pytest.raises(TransportError) as info:
        api.menu(LIVE)
    assert info.value.retryable


@pytest.mark.parametrize(
    "call",
    [
        lambda a: a.menu("prematch"),
        lambda a: a.events(1, "LIVE"),
        lambda a: a.events(1, LIVE, full_line=True),
        lambda a: a.events(1, LINE, tournament_id=5, full_line=True),
        lambda a: a.events_by_period(1, hours=3),
        lambda a: a.events_by_period(1, days=6),
        lambda a: a.event(-1, LIVE),
        lambda a: a.event("123", LIVE),
        lambda a: a.search("  ", LIVE),
        lambda a: a.menu(LIVE, lang=""),
    ],
)
def test_invalid_arguments_fail_before_any_request(api: SportAPI, call: Any) -> None:
    with respx.mock(assert_all_mocked=True) as router, pytest.raises(ValueError):
        call(api)
    assert not router.calls


def test_custom_http_client_is_not_closed() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda r: ok([])))
    with SportAPI(api_key=API_KEY, base_url=BASE_URL, http_client=http) as api:
        assert api.sports(LIVE) == []
    assert not http.is_closed
    http.close()
