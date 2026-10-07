from __future__ import annotations

from typing import List

import httpx
import pytest
import respx

from sportapi import (
    LIVE,
    AsyncSportAPI,
    DemoDataUnavailableError,
    GameFinishedError,
    InvalidKeyError,
    TransportError,
    apoll,
)

from .conftest import API_KEY, BASE_URL, example

pytestmark = pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")


async def test_demo_mode() -> None:
    async with AsyncSportAPI() as api:
        assert api.is_demo
        match = await api.event(746146992, LIVE)
        assert match.opp_2_name == "Coventry City"
        assert len(await api.menu(LIVE)) == 31
        matches = [m async for m in api.iter_live_matches()]
        assert len(matches) == 39
        with pytest.raises(DemoDataUnavailableError):
            await api.account()


async def test_live_request_and_errors() -> None:
    async with respx.mock(base_url=BASE_URL) as router:
        route = router.get("/v1/events/1/0/sub/50/live/en").mock(
            return_value=httpx.Response(
                200, json=example("events.sport-1.tournament-0.sub-50.live.en.json")
            )
        )
        router.get("/v1/menu/live/en").mock(
            return_value=httpx.Response(
                200, json={"error_code": 100, "error_message": "Invalid Package"}
            )
        )
        router.get("/v1/event/7/group/live/en").mock(
            return_value=httpx.Response(
                200,
                json={"status": 1, "page": "/v1/event", "body": {"message": "Game id finished"}},
            )
        )
        router.get("/v1/sports/live/en").mock(side_effect=httpx.ConnectError("refused"))

        async with AsyncSportAPI(api_key=API_KEY, base_url=BASE_URL) as api:
            groups = await api.events(1, LIVE)
            assert len(groups) == 33
            assert route.calls.last.request.headers["Package"] == API_KEY
            with pytest.raises(InvalidKeyError):
                await api.menu(LIVE)
            with pytest.raises(GameFinishedError):
                await api.event(7, LIVE)
            with pytest.raises(TransportError):
                await api.sports(LIVE)


async def test_apoll_backoff() -> None:
    sleeps: List[float] = []
    steps = [TransportError("down"), "a", "b"]

    async def fetch() -> str:
        step = steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    results = [r async for r in apoll(fetch, 7, max_polls=2, sleep=fake_sleep)]
    assert results == ["a", "b"]
    assert sleeps == [5, 7]


async def test_async_watch_rejects_fast_interval() -> None:
    api = AsyncSportAPI()
    with pytest.raises(ValueError):
        api.watch_events(1, LIVE, interval=2)
    await api.aclose()
