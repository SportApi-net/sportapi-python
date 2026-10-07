"""Synchronous SportAPI client."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Any, Iterable, Iterator, List, Optional, Type, TypeVar

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
    iter_matches,
)
from .polling import checked_interval, poll

__all__ = ["SportAPI"]

T = TypeVar("T")


class SportAPI:
    """Client for the SportAPI Sport Line API (Prematch and Live odds, scores, stats).

    Configuration, in order of precedence:

    * ``api_key`` / ``base_url`` arguments;
    * ``SPORTAPI_KEY`` / ``SPORTAPI_BASE_URL`` environment variables.

    Both values are issued by the SportAPI manager (the base URL is personal).
    With neither configured, the client runs in **demo mode** and returns the
    example responses bundled from the SportAPI documentation (a
    :class:`~sportapi.SportAPIDemoWarning` is emitted once). Pass ``demo=True``
    to force demo mode or ``demo=False`` to require live credentials.

    The key is sent only in the ``Package`` HTTP header and never appears in
    URLs, ``repr()`` or exception messages.

    Each response is a snapshot: poll with the documented minimum intervals
    (see :mod:`sportapi.polling` and :meth:`watch_events`), never faster.

    Example::

        from sportapi import SportAPI

        with SportAPI() as api:              # demo mode without env vars
            for group in api.events(1, "live"):
                for match in group.matches:
                    print(match.name, match.score_full)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        *,
        lang: str = "en",
        timeout: float = _core.DEFAULT_TIMEOUT,
        demo: Optional[bool] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._config = _core.resolve_config(api_key, base_url, demo)
        self.lang = lang
        self.timeout = timeout
        self._owns_http = http_client is None
        self._http = http_client
        self.key_expires: Optional[datetime] = None
        """Expiration of the key from the last ``X-Key-Expires`` response header."""

    # -- lifecycle -------------------------------------------------------------

    @property
    def is_demo(self) -> bool:
        """``True`` when responses come from bundled demo data."""
        return self._config.demo

    @property
    def base_url(self) -> Optional[str]:
        return self._config.base_url

    def __repr__(self) -> str:
        if self.is_demo:
            return "SportAPI(demo=True)"
        return f"SportAPI(base_url={self.base_url!r}, lang={self.lang!r})"

    def close(self) -> None:
        """Close the underlying HTTP connection pool (if the client created it)."""
        if self._http is not None and self._owns_http:
            self._http.close()
            self._http = None

    def __enter__(self) -> SportAPI:
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        self.close()

    def _client(self) -> httpx.Client:
        if self._http is None:
            self._http = httpx.Client(timeout=self.timeout)
            self._owns_http = True
        return self._http

    def _send(self, spec: _core.RequestSpec[T]) -> T:
        if self._config.demo:
            return _core.handle_payload(spec, _core.demo_payload(spec))
        assert self._config.api_key is not None and self._config.base_url is not None
        try:
            response = self._client().get(
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

    # -- navigation --------------------------------------------------------------

    def menu(
        self, line_type: str, *, lang: Optional[str] = None, cybersport: bool = False
    ) -> List[Sport]:
        """Sports → countries → tournaments that currently have matches.

        ``GET /v1/menu/{type}/{lang}``. Poll no more often than every 20 s
        (Live) / 60 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/menu.html

        Args:
            line_type: ``"live"`` or ``"line"`` (Prematch).
            lang: language code; defaults to the client's ``lang``.
            cybersport: return the esports menu.
        """
        return self._send(_core.menu_spec(line_type, self._lang(lang), cybersport))

    def sports(
        self, line_type: str, *, lang: Optional[str] = None, cybersport: bool = False
    ) -> List[Sport]:
        """Sports that currently have matches (``countries`` is empty).

        ``GET /v1/sports/{type}/{lang}``. Usually :meth:`menu` is more convenient.
        Poll no more often than every 60 s (Live) / 120 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/sports.html
        """
        return self._send(_core.sports_spec(line_type, self._lang(lang), cybersport))

    def countries(
        self, sport_id: int, line_type: str, *, lang: Optional[str] = None
    ) -> List[Country]:
        """Countries with matches for one sport (``tournaments`` is empty).

        ``GET /v1/countries/{sportId}/{type}/{lang}``. Poll no more often than
        every 60 s (Live) / 120 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/countries.html
        """
        return self._send(_core.countries_spec(sport_id, line_type, self._lang(lang)))

    def tournaments(
        self,
        sport_id: int,
        country_id: int,
        line_type: str,
        *,
        lang: Optional[str] = None,
        cybersport: bool = False,
    ) -> List[Tournament]:
        """Tournaments with matches for one sport and country.

        ``GET /v1/tournaments/{sportId}/{countryId}/{type}/{lang}``. Poll no more
        often than every 60 s (Live) / 120 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/tournaments.html
        """
        return self._send(
            _core.tournaments_spec(sport_id, country_id, line_type, self._lang(lang), cybersport)
        )

    # -- matches -----------------------------------------------------------------

    def events(
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
        """Matches of a sport (or one tournament), grouped by tournament.

        ``GET /v1/events/{sportId}/{tournamentId}/sub/50/{type}/{lang}``.
        Each match carries a *short* list of main markets; use :meth:`event`
        for the complete odds of one match. Take ``sport_id``/``tournament_id``
        from a current :meth:`menu` response.

        For Prematch with ``tournament_id=0`` the API returns a 50-match "Top"
        selection; ``full_line=True`` (``match=all``) returns the whole line.
        Poll no more often than every 7 s (Live) / 30 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/events.html

        Args:
            tournament_id: ``0`` = all tournaments of the sport.
            full_line: Prematch only, with ``tournament_id=0``.
            odds: ``False`` omits ``game_oc_list`` (2–5× smaller responses).
        """
        return self._send(
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

    def events_by_period(
        self,
        sport_id: int,
        *,
        tournament_id: int = 0,
        hours: int = 0,
        days: int = 0,
        lang: Optional[str] = None,
        odds: bool = True,
    ) -> List[TournamentEvents]:
        """Prematch match calendar.

        ``GET /v1/events/{sportId}/{tournamentId}/sub/50/line/{hours}/{days}/{lang}``.

        * ``hours`` = 2, 4, 6 or 12: matches starting within that many hours;
        * ``hours=0, days=0``: today (until the end of the day, Kyiv time);
        * ``hours=0, days=1..5``: that calendar day (``1`` = tomorrow).

        Poll no more often than every 60 s.
        Docs: https://sportapi.net/docs/sport-line/api-reference/events-by-period.html
        """
        return self._send(
            _core.events_by_period_spec(
                sport_id, tournament_id, hours, days, self._lang(lang), odds
            )
        )

    def event(
        self,
        game_id: int,
        line_type: str,
        *,
        lang: Optional[str] = None,
        odds: bool = True,
    ) -> Match:
        """Full data of one match or sub-event: all markets (``group`` format),
        live statistics and ``sub_games``.

        ``GET /v1/event/{gameId}/group/{type}/{lang}``. Use the line type the
        ``game_id`` came from. Poll no more often than every 5 s (Live) /
        30 s (Prematch), and only for matches the user is looking at.
        Docs: https://sportapi.net/docs/sport-line/api-reference/event.html

        Raises:
            GameFinishedError: ``Game id finished`` — stop polling this ID.
            GameNotFoundError: ``Game not found``.
        """
        return self._send(_core.event_spec(game_id, line_type, self._lang(lang), odds))

    def search(self, text: str, line_type: str, *, lang: Optional[str] = None) -> List[Match]:
        """Find matches by team or participant name (short summaries, no odds).

        ``GET /v1/search/{type}/{lang}/{text}`` — the text is URL-encoded for
        you. Live and Prematch are searched separately. An empty list means
        nothing was found. Call it on user action, not in a loop.
        Docs: https://sportapi.net/docs/sport-line/api-reference/search.html
        """
        return self._send(_core.search_spec(text, line_type, self._lang(lang)))

    # -- curated selections ----------------------------------------------------------

    def topmatches(
        self,
        line_type: str,
        *,
        lang: Optional[str] = None,
        full: bool = False,
        odds: bool = True,
    ) -> List[Match]:
        """Up to 10 top matches across all sports of the key.

        ``GET /v1/topmatches/{type}/{lang}``. ``full=True`` returns extended
        match objects with a short odds list (``odds=False`` drops it).
        Poll no more often than every 30 s (Live) / 120 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/topmatches.html
        """
        return self._send(_core.topmatches_spec(line_type, self._lang(lang), full, odds))

    def toplist(
        self,
        sport_id: int,
        *,
        lang: Optional[str] = None,
        full: bool = False,
        odds: bool = True,
    ) -> List[Match]:
        """Up to 10 top Prematch matches of one sport.

        ``GET /v1/toplist/{sportId}/{lang}``. Prematch only. Poll no more often
        than every 120 s.
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/toplist.html
        """
        return self._send(_core.toplist_spec(sport_id, self._lang(lang), full, odds))

    def topchampionships(
        self, line_type: str, *, lang: Optional[str] = None
    ) -> List[TopChampionship]:
        """Up to 12 popular championships (no matches; use :meth:`events` with
        their ``tournament_id``).

        ``GET /v1/topchampionships/{type}/{lang}``. Esports are not included.
        Poll no more often than every 60 s (Live) / 300 s (Prematch).
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/topchampionships.html
        """
        return self._send(_core.topchampionships_spec(line_type, self._lang(lang)))

    def account(self) -> Account:
        """All keys of the client: expiration, sports, languages, restrictions,
        7-day usage, and the caller's IP (``your_ip``).

        ``GET /v1/account``. Not available in demo mode.
        Docs: https://sportapi.net/docs/sport-line/api-reference/optional-methods/account.html
        """
        return self._send(_core.account_spec())

    # -- helpers -----------------------------------------------------------------

    def iter_live_matches(
        self, sport_ids: Optional[Iterable[int]] = None, *, lang: Optional[str] = None
    ) -> Iterator[Match]:
        """Yield every Live match, sport by sport.

        Without ``sport_ids`` the current Live sports are taken from
        :meth:`sports`, then :meth:`events` is requested once per sport (lazily,
        as you iterate). In demo mode only sports with bundled data are visited.
        """
        if sport_ids is None:
            ids = [sport.id for sport in self.sports(_core.LIVE, lang=lang)]
            if self.is_demo:
                ids = [i for i in ids if _demo.has_file(("events", i, 0, _core.LIVE))]
        else:
            ids = list(sport_ids)
        for sport_id in ids:
            yield from iter_matches(self.events(sport_id, _core.LIVE, lang=lang))

    def watch_events(
        self,
        sport_id: int,
        line_type: str,
        *,
        interval: Optional[float] = None,
        max_polls: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[List[TournamentEvents]]:
        """Poll :meth:`events` at the documented interval and yield each snapshot.

        ``interval`` defaults to the documented minimum (7 s Live, 30 s
        Prematch); smaller values raise :class:`ValueError`. Temporary errors
        back off 5 → 10 → 20 → 40 s; other errors are raised. Extra keyword
        arguments go to :meth:`events`.
        """
        every = checked_interval("events", line_type, interval)
        return poll(
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
    ) -> Iterator[Match]:
        """Poll :meth:`event` at the documented interval (5 s Live, 30 s Prematch).

        Iteration ends with :class:`~sportapi.GameFinishedError` once the match
        is no longer available under this ``game_id``.
        """
        every = checked_interval("event", line_type, interval)
        return poll(
            lambda: self.event(game_id, line_type, **kwargs),
            every,
            max_polls=max_polls,
        )
