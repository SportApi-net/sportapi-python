from __future__ import annotations

from typing import Any, List

import httpx
import pytest
import respx

from sportapi import (
    LINE,
    LIVE,
    GameFinishedError,
    KeyExpiredError,
    SportAPI,
    TransportError,
    poll,
    recommended_interval,
)
from sportapi.errors import HTTPStatusError
from sportapi.polling import RECOMMENDED_INTERVALS

from .conftest import API_KEY, BASE_URL


def test_documented_intervals() -> None:
    assert recommended_interval("menu", LIVE) == 20
    assert recommended_interval("menu", LINE) == 60
    assert recommended_interval("events", LIVE) == 7
    assert recommended_interval("event", LIVE) == 5
    assert recommended_interval("event", LINE) == 30
    assert recommended_interval("topchampionships", LINE) == 300
    with pytest.raises(ValueError):
        recommended_interval("toplist", LIVE)  # not used in Live
    with pytest.raises(ValueError):
        recommended_interval("search", LIVE)  # on user action, not polled
    assert set(RECOMMENDED_INTERVALS) >= {"menu", "events", "event", "topmatches"}


class Script:
    """A fetch() that replays results/exceptions in order."""

    def __init__(self, *steps: Any) -> None:
        self.steps = list(steps)
        self.calls = 0

    def __call__(self) -> Any:
        self.calls += 1
        step = self.steps.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def test_poll_waits_interval_between_successes() -> None:
    sleeps: List[float] = []
    results = list(poll(Script("a", "b", "c"), 7, max_polls=3, sleep=sleeps.append))
    assert results == ["a", "b", "c"]
    assert sleeps == [7, 7]  # no sleep after the last result


def test_poll_backs_off_on_temporary_errors_then_resets() -> None:
    sleeps: List[float] = []
    fetch = Script(
        TransportError("down"),
        HTTPStatusError("bad gateway", http_status=502),
        TransportError("down"),
        TransportError("down"),
        TransportError("down"),
        "ok",
        TransportError("down"),
        "ok again",
    )
    results = list(poll(fetch, 30, max_polls=2, sleep=sleeps.append))
    assert results == ["ok", "ok again"]
    assert sleeps == [5, 10, 20, 40, 40, 30, 5]


def test_poll_raises_errors_that_waiting_cannot_fix() -> None:
    fetch = Script("first", KeyExpiredError(100, "Package has expired"))
    gen = poll(fetch, 5, sleep=lambda _: None)
    assert next(gen) == "first"
    with pytest.raises(KeyExpiredError):
        next(gen)
    fetch = Script(HTTPStatusError("not found", http_status=404))
    with pytest.raises(HTTPStatusError):
        next(poll(fetch, 5, sleep=lambda _: None))


def test_poll_rejects_non_positive_interval() -> None:
    with pytest.raises(ValueError):
        next(poll(lambda: 1, 0))


def test_watch_events_refuses_faster_than_documented() -> None:
    api = SportAPI(demo=True)
    with pytest.raises(ValueError, match="7 s"):
        api.watch_events(1, LIVE, interval=1)
    with pytest.raises(ValueError, match="30 s"):
        api.watch_event(1, LINE, interval=10)


def test_watch_event_stops_when_game_is_finished(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sportapi.polling.time.sleep", lambda _: None)
    replies = iter(
        [
            {"status": 1, "page": "/v1/event", "body": {"game_id": 9, "score_full": "0:0"}},
            {"status": 1, "page": "/v1/event", "body": {"game_id": 9, "score_full": "1:0"}},
            {"status": 1, "page": "/v1/event", "body": {"message": "Game id finished"}},
        ]
    )
    with respx.mock(base_url=BASE_URL) as router:
        router.get("/v1/event/9/group/live/en").mock(
            side_effect=lambda request: httpx.Response(200, json=next(replies))
        )
        api = SportAPI(api_key=API_KEY, base_url=BASE_URL)
        scores = []
        with pytest.raises(GameFinishedError):
            for match in api.watch_event(9, LIVE):
                scores.append(match.score_full)
    assert scores == ["0:0", "1:0"]


@pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")
def test_watch_events_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sportapi.polling.time.sleep", lambda _: None)
    snapshots = list(SportAPI().watch_events(1, LIVE, max_polls=2))
    assert len(snapshots) == 2 and len(snapshots[0]) == 33
