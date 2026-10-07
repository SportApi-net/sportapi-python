"""Asynchronous SportAPI client (same methods as :class:`sportapi.SportAPI`)."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, AsyncIterator, Iterable, List, Optional, Type, TypeVar

import httpx

from . import _core, _demo
from .errors import TransportError
from .models import (
    Account,
    Country,
    Match,
    Sport,
    TopChampionship,
    Tournament,
    TournamentEvents,
)
from .polling import apoll, checked_interval

__all__ = ["AsyncSportAPI"]

T = TypeVar("T")


class AsyncSportAPI:
    """Async client for the SportAPI Sport Line API, built on ``httpx.AsyncClient``.

    Configuration, demo mode and method semantics are identical to
    :class:`sportapi.SportAPI`; every method is a coroutine. See that class
    for per-method documentation and polling intervals.

    Example::

        import asyncio
        from sportapi import AsyncSportAPI

        async def main():
            async with AsyncSportAPI() as api:
                match = await api.event(746146992, "live")
                print(match.name, match.score_full)

        asyncio.run(main())
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        *,
        lang: str = "en",
        timeout: float = _core.DEFAULT_TIMEOUT,
        demo: Optional[bool] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = _core.resolve_config(api_key, base_url, demo)
        self.lang = lang
        self.timeout = timeout
        self._owns_http = http_client is None
        self._http = http_client
        self.key_expires: Optional[datetime] = None

    @property
    def is_demo(self) -> bool:
        return self._config.demo

    @property
    def base_url(self) -> Optional[str]:
        return self._config.base_url

    def __repr__(self) -> str:
        if self.is_demo:
            return "AsyncSportAPI(demo=True)"
        return f"AsyncSportAPI(base_url={self.base_url!r}, lang={self.lang!r})"

    async def aclose(self) -> None:
        if self._http is not None and self._owns_http:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> AsyncSportAPI:
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        await self.aclose()

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout)
            self._owns_http = True
        return self._http

    async def _send(self, spec: _core.RequestSpec[T]) -> T:
        if self._config.demo:
            return _core.handle_payload(spec, _core.demo_payload(spec))
        assert self._config.api_key is not None and self._config.base_url is not None
        try:
            response = await self._client().get(
                self._config.base_url + spec.path,
                params=dict(spec.params) or None,
                headers=_core.request_headers(self._config.api_key),
            )
        except httpx.TimeoutException as error:
            raise TransportError(f"SportAPI request timed out: {spec.name}") from error
        except httpx.HTTPError as error:
            raise TransportError(
                f"Could not reach SportAPI ({type(error).__name__}): {spec.name}"
            ) from error
        expires = response.headers.get("X-Key-Expires")
        if expires:
            self.key_expires = _core.parse_key_expires(expires) or self.key_expires
        payload = _core.decode_json(response.text, response.status_code)
        return _core.handle_payload(spec, payload, response.status_code)

    def _lang(self, lang: Optional[str]) -> str:
        return lang if lang is not None else self.lang

    async def menu(
        self, line_type: str, *, lang: Optional[str] = None, cybersport: bool = False
    ) -> List[Sport]:
        """See :meth:`sportapi.SportAPI.menu`."""
        return await self._send(_core.menu_spec(line_type, self._lang(lang), cybersport))

    async def sports(
        self, line_type: str, *, lang: Optional[str] = None, cybersport: bool = False
    ) -> List[Sport]:
        """See :meth:`sportapi.SportAPI.sports`."""
        return await self._send(_core.sports_spec(line_type, self._lang(lang), cybersport))

    async def countries(
        self, sport_id: int, line_type: str, *, lang: Optional[str] = None
    ) -> List[Country]:
        """See :meth:`sportapi.SportAPI.countries`."""
        return await self._send(_core.countries_spec(sport_id, line_type, self._lang(lang)))

    async def tournaments(
        self,
        sport_id: int,
        country_id: int,
        line_type: str,
        *,
        lang: Optional[str] = None,
        cybersport: bool = False,
    ) -> List[Tournament]:
        """See :meth:`sportapi.SportAPI.tournaments`."""
        return await self._send(
            _core.tournaments_spec(sport_id, country_id, line_type, self._lang(lang), cybersport)
        )

    async def events(
        self,
        sport_id: int,
        line_type: str,
        *,
        tournament_id: int = 0,
        lang: Optional[str] = None,
        cybersport: bool = False,
        full_line: bool = False,
        odds: bool = True,
    ) -> List[TournamentEvents]:
        """See :meth:`sportapi.SportAPI.events`."""
        return await self._send(
            _core.events_spec(
                sport_id,
                line_type,
                tournament_id,
                self._lang(lang),
                cybersport,
                full_line,
                odds,
            )
        )

    async def events_by_period(
        self,
        sport_id: int,
        *,
        tournament_id: int = 0,
        hours: int = 0,
        days: int = 0,
        lang: Optional[str] = None,
        odds: bool = True,
    ) -> List[TournamentEvents]:
        """See :meth:`sportapi.SportAPI.events_by_period`."""
        return await self._send(
            _core.events_by_period_spec(
                sport_id, tournament_id, hours, days, self._lang(lang), odds
            )
        )

    async def event(
        self,
        game_id: int,
        line_type: str,
        *,
        lang: Optional[str] = None,
        odds: bool = True,
    ) -> Match:
        """See :meth:`sportapi.SportAPI.event`."""
        return await self._send(_core.event_spec(game_id, line_type, self._lang(lang), odds))

    async def search(self, text: str, line_type: str, *, lang: Optional[str] = None) -> List[Match]:
        """See :meth:`sportapi.SportAPI.search`."""
        return await self._send(_core.search_spec(text, line_type, self._lang(lang)))

    async def topmatches(
        self,
        line_type: str,
        *,
        lang: Optional[str] = None,
        full: bool = False,
        odds: bool = True,
    ) -> List[Match]:
        """See :meth:`sportapi.SportAPI.topmatches`."""
        return await self._send(_core.topmatches_spec(line_type, self._lang(lang), full, odds))

    async def toplist(
        self,
        sport_id: int,
        *,
        lang: Optional[str] = None,
        full: bool = False,
        odds: bool = True,
    ) -> List[Match]:
        """See :meth:`sportapi.SportAPI.toplist`."""
        return await self._send(_core.toplist_spec(sport_id, self._lang(lang), full, odds))

    async def topchampionships(
        self, line_type: str, *, lang: Optional[str] = None
    ) -> List[TopChampionship]:
        """See :meth:`sportapi.SportAPI.topchampionships`."""
        return await self._send(_core.topchampionships_spec(line_type, self._lang(lang)))

    async def account(self) -> Account:
        """See :meth:`sportapi.SportAPI.account`."""
        return await self._send(_core.account_spec())

    async def iter_live_matches(
        self, sport_ids: Optional[Iterable[int]] = None, *, lang: Optional[str] = None
    ) -> AsyncIterator[Match]:
        """See :meth:`sportapi.SportAPI.iter_live_matches`."""
        if sport_ids is None:
            ids = [sport.id for sport in await self.sports(_core.LIVE, lang=lang)]
            if self.is_demo:
                ids = [i for i in ids if _demo.has_file(("events", i, 0, _core.LIVE))]
        else:
            ids = list(sport_ids)
        for sport_id in ids:
            for group in await self.events(sport_id, _core.LIVE, lang=lang):
                for match in group.matches:
                    yield match

    def watch_events(
        self,
        sport_id: int,
        line_type: str,
        *,
        interval: Optional[float] = None,
        max_polls: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[List[TournamentEvents]]:
        """See :meth:`sportapi.SportAPI.watch_events`; use with ``async for``."""
        every = checked_interval("events", line_type, interval)
        return apoll(
            lambda: self.events(sport_id, line_type, **kwargs),
            every,
            max_polls=max_polls,
        )

    def watch_event(
        self,
        game_id: int,
        line_type: str,
        *,
        interval: Optional[float] = None,
        max_polls: Optional[int] = None,
        **kwargs: Any,
    ) -> AsyncIterator[Match]:
        """See :meth:`sportapi.SportAPI.watch_event`; use with ``async for``."""
        every = checked_interval("event", line_type, interval)
        return apoll(
            lambda: self.event(game_id, line_type, **kwargs),
            every,
            max_polls=max_polls,
        )
