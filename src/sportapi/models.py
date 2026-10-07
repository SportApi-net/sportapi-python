"""Typed models for Sport Line API responses.

Every model keeps the original JSON object in ``raw``, so fields that are not
modelled here (legacy, reserved or newly added ones) stay accessible.

Field names follow the API where that keeps the docs easy to cross-reference
(``game_id``, ``opp_1_name``, ``score_full``…). Odds-related objects use
shorter Python names and document the JSON field they come from.

Data model docs:

* Match: https://sportapi.net/docs/sport-line/data-models/match.html
* Odds: https://sportapi.net/docs/sport-line/data-models/odds.html
* Live statistics: https://sportapi.net/docs/sport-line/data-models/live-statistics.html
* Sub-events: https://sportapi.net/docs/sport-line/data-models/sub-events.html
* Field reference: https://sportapi.net/docs/sport-line/data-models/field-reference.html
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Iterator, List, Optional, Union

from . import media

__all__ = [
    "Sport",
    "Country",
    "Tournament",
    "TournamentEvents",
    "Match",
    "Market",
    "Outcome",
    "Stat",
    "SubGame",
    "EventPlanEntry",
    "TopChampionship",
    "Account",
    "AccountKey",
    "DailyUsage",
    "iter_matches",
]

JSON = Dict[str, Any]


def _int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _opt_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _opt_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 UTC timestamp such as ``2026-11-03T14:34:23.479Z``."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        # Python < 3.11 only accepts 3 or 6 fractional digits.
        if "." in text:
            head, _, tail = text.partition(".")
            digits = "".join(ch for ch in tail if ch.isdigit())
            zone = tail[len(digits) :]
            try:
                return datetime.fromisoformat(f"{head}.{digits[:6].ljust(6, '0')}{zone}")
            except ValueError:
                return None
        return None


# --- Navigation ---------------------------------------------------------------


@dataclass
class Tournament:
    """A tournament from ``menu`` or ``tournaments``.

    ``country_id`` comes from the JSON field ``countryId`` (capital ``I``).
    ``name`` may be an empty string; do not invent one.
    """

    id: int
    name: str
    counter: int
    sport_id: int
    country_id: int
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Tournament:
        return cls(
            id=_int(data.get("id")),
            name=_str(data.get("name")),
            counter=_int(data.get("counter")),
            sport_id=_int(data.get("sport_id")),
            country_id=_int(data.get("countryId")),
            raw=data,
        )

    @property
    def icon_url(self) -> str:
        """Standard SportAPI tournament icon (WebP)."""
        return media.tournament_icon_url(self.id)


@dataclass
class Country:
    """A country from ``menu`` (with ``tournaments``) or ``countries`` (without)."""

    id: int
    name: str
    counter: int
    sport_id: int
    tournaments: List[Tournament] = field(default_factory=list)
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Country:
        return cls(
            id=_int(data.get("id")),
            name=_str(data.get("name")),
            counter=_int(data.get("counter")),
            sport_id=_int(data.get("sport_id")),
            tournaments=[Tournament.from_dict(t) for t in _list(data.get("sub"))],
            raw=data,
        )

    @property
    def flag_url(self) -> str:
        """Standard SportAPI country flag (WebP)."""
        return media.country_flag_url(self.id)


@dataclass
class Sport:
    """A sport from ``menu`` (with ``countries``) or ``sports`` (without).

    ``counter`` is the number of matches available right now for the requested
    line type; it changes continuously.
    """

    id: int
    name: str
    counter: int
    countries: List[Country] = field(default_factory=list)
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Sport:
        return cls(
            id=_int(data.get("id")),
            name=_str(data.get("name")),
            counter=_int(data.get("counter")),
            countries=[Country.from_dict(c) for c in _list(data.get("sub"))],
            raw=data,
        )

    @property
    def icon_url(self) -> str:
        """Standard SportAPI sport icon (WebP)."""
        return media.sport_icon_url(self.id)

    def iter_tournaments(self) -> Iterator[Tournament]:
        """Iterate over all tournaments of all countries (``menu`` responses only)."""
        for country in self.countries:
            yield from country.tournaments


# --- Odds ---------------------------------------------------------------------


@dataclass
class Outcome:
    """One betting selection (an object of ``oc_list``).

    Attributes:
        name: ``oc_name`` — display name in the requested language (``W1``, ``Over 2.5``…).
        odds: ``oc_rate`` — current decimal odds as a float.
        size: ``oc_size`` — handicap/total/parameter exactly as returned; the API
            uses both numbers (``0``) and strings (``"-3.5"``). See :attr:`size_value`.
        pointer: ``oc_pointer`` — opaque selection code. Compare it as a whole
            string to track the same selection between updates; never build it yourself.
        blocked: ``oc_block`` — ``True`` means the selection is unavailable even
            if ``odds`` still holds a number.
        player_id: ``op_id`` — player/participant for player-specific selections.
        market_name: ``oc_group_name`` — market name in the requested language.
    """

    name: str
    odds: float
    size: Union[str, int, float, None]
    pointer: str
    blocked: bool
    player_id: Optional[int] = None
    market_name: str = ""
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Outcome:
        rate = data.get("oc_rate")
        try:
            odds = float(rate) if rate is not None else 0.0
        except (TypeError, ValueError):
            odds = 0.0
        return cls(
            name=_str(data.get("oc_name")),
            odds=odds,
            size=data.get("oc_size"),
            pointer=_str(data.get("oc_pointer")),
            blocked=bool(data.get("oc_block")),
            player_id=_opt_int(data.get("op_id")),
            market_name=_str(data.get("oc_group_name")),
            raw=data,
        )

    @property
    def available(self) -> bool:
        """``True`` when the selection is not blocked (``oc_block`` is ``false``)."""
        return not self.blocked

    @property
    def odds_decimal(self) -> Decimal:
        """The odds as :class:`decimal.Decimal`, for exact arithmetic and formatting."""
        rate = self.raw.get("oc_rate", self.odds)
        try:
            return Decimal(str(rate))
        except (InvalidOperation, ValueError):
            return Decimal(str(self.odds))

    @property
    def size_value(self) -> Optional[float]:
        """``oc_size`` converted to a float, or ``None`` if it is not numeric."""
        if self.size is None or isinstance(self.size, bool):
            return None
        try:
            return float(self.size)
        except (TypeError, ValueError):
            return None


@dataclass
class Market:
    """A betting market (an object of ``game_oc_list``).

    The structure of ``oc_list`` depends on the method:

    * ``events``, ``topmatches?full=true``, ``toplist?full=true``: a flat list of
      selections. :attr:`column_outcomes` is ``None``.
    * ``event`` (``group`` format): a list of columns, each a list of selections,
      already arranged and sorted by the API. :attr:`column_outcomes` keeps that
      layout; :attr:`outcomes` is the same selections flattened in API order.

    Attributes:
        id: ``group_id`` — use it for program logic (names are localised).
        name: ``group_name``.
        columns: recommended number of display columns; it does not have to equal
            ``len(column_outcomes)``.
    """

    id: int
    name: str
    columns: int
    outcomes: List[Outcome]
    column_outcomes: Optional[List[List[Outcome]]] = None
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Market:
        oc_list = _list(data.get("oc_list"))
        columns: Optional[List[List[Outcome]]] = None
        if any(isinstance(item, list) for item in oc_list):
            columns = [
                [Outcome.from_dict(o) for o in _list(column) if isinstance(o, dict)]
                for column in oc_list
            ]
            outcomes = [o for column in columns for o in column]
        else:
            outcomes = [Outcome.from_dict(o) for o in oc_list if isinstance(o, dict)]
        return cls(
            id=_int(data.get("group_id")),
            name=_str(data.get("group_name")),
            columns=_int(data.get("columns")),
            outcomes=outcomes,
            column_outcomes=columns,
            raw=data,
        )

    def outcome(self, name: str, *, include_blocked: bool = True) -> Optional[Outcome]:
        """Return the first selection whose ``oc_name`` equals ``name`` (case-insensitive)."""
        wanted = name.strip().casefold()
        for outcome in self.outcomes:
            if outcome.name.strip().casefold() == wanted and (
                include_blocked or not outcome.blocked
            ):
                return outcome
        return None

    def available_outcomes(self) -> List[Outcome]:
        """Selections that are not blocked."""
        return [o for o in self.outcomes if not o.blocked]

    def best(self) -> Optional[Outcome]:
        """The available selection with the highest odds, or ``None``."""
        candidates = self.available_outcomes()
        return max(candidates, key=lambda o: o.odds) if candidates else None


# --- Match ----------------------------------------------------------------------


@dataclass
class Stat:
    """A live statistic (an object of ``stat_list``).

    ``opp1``/``opp2`` are strings as returned by the API (``"61"``, ``"1.45"``) and
    belong to ``opp_1_name``/``opp_2_name``. Use ``id`` for program logic.
    """

    id: int
    name: str
    opp1: str
    opp2: str
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Stat:
        return cls(
            id=_int(data.get("id")),
            name=_str(data.get("name")),
            opp1=_str(data.get("opp1")),
            opp2=_str(data.get("opp2")),
            raw=data,
        )


@dataclass
class SubGame:
    """A link to a sub-event (an object of ``sub_games``): halves, corners, cards…

    It has no odds; request them with ``event(sub_game.game_id, …)`` using the
    same line type as the main match.
    """

    game_id: Optional[int]
    name: Optional[str]
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> SubGame:
        return cls(
            game_id=_opt_int(data.get("game_id")),
            name=_opt_str(data.get("game_name")),
            raw=data,
        )


@dataclass
class EventPlanEntry:
    """One pair of teams in a group match (an object of ``event_plan``)."""

    opp_1_name: str
    opp_2_name: str
    opp_1_id: Optional[int] = None
    opp_2_id: Optional[int] = None
    opp_1_country_id: Optional[int] = None
    opp_2_country_id: Optional[int] = None
    opp_1_icon: str = ""
    opp_2_icon: str = ""
    opp_1_date: Optional[int] = None
    opp_2_date: Optional[int] = None
    game_start: Optional[int] = None
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> EventPlanEntry:
        return cls(
            opp_1_name=_str(data.get("opp_1_name")),
            opp_2_name=_str(data.get("opp_2_name")),
            opp_1_id=_opt_int(data.get("opp_1_id")),
            opp_2_id=_opt_int(data.get("opp_2_id")),
            opp_1_country_id=_opt_int(data.get("opp_1_country_id")),
            opp_2_country_id=_opt_int(data.get("opp_2_country_id")),
            opp_1_icon=_str(data.get("opp_1_icon")),
            opp_2_icon=_str(data.get("opp_2_icon")),
            opp_1_date=_opt_int(data.get("opp_1_date")),
            opp_2_date=_opt_int(data.get("opp_2_date")),
            game_start=_opt_int(data.get("game_start")),
            raw=data,
        )


@dataclass
class Match:
    """A match (or sub-event) object.

    The same class is used for every method that returns matches. Short
    summaries (``search``, ``topmatches``/``toplist`` without ``full``) do not
    contain every field: missing numbers are ``None``, missing lists are empty.

    Prematch and Live versions of the same fixture have **different**
    ``game_id`` values; do not link them by ID.

    Notable fields:
        game_start: Unix timestamp in seconds (see :attr:`start_time`).
        timer: elapsed match time in seconds (``0`` in Prematch). Update a
            displayed clock locally instead of polling every second.
        markets: parsed ``game_oc_list``. Short list in ``events``; the complete
            list in ``event``. Empty when requested with ``odds=False``.
        game_oc_counter: the API's outcome counter; it may differ from the
            number of selections actually returned.
        stats: parsed ``stat_list`` (Live only). An empty list means "not
            provided", not zero.
        sub_games: sub-event links (only filled by ``event``).
        zp: Live 3D Tracker ID (pass as the tracker's ``gameid``), ``vi``: video
            stream ID, ``va``: ``1`` when video is available.
    """

    game_id: int
    opp_1_name: str
    opp_2_name: str
    game_start: int = 0
    game_mid: Optional[int] = None
    sport_id: Optional[int] = None
    sport_name: str = ""
    country_id: Optional[int] = None
    country_name: str = ""
    tournament_id: Optional[int] = None
    tournament_name: str = ""
    opp_1_id: Optional[int] = None
    opp_2_id: Optional[int] = None
    opp_1_ids: List[int] = field(default_factory=list)
    opp_2_ids: List[int] = field(default_factory=list)
    opp_1_icon: str = ""
    opp_2_icon: str = ""
    timer: int = 0
    score_full: str = ""
    score_period: str = ""
    score_extra: str = ""
    period_name: str = ""
    extra_time: str = ""
    finale: Optional[bool] = None
    pitch: str = ""
    game_dop_name: str = ""
    game_desk: str = ""
    game_oc_counter: Optional[int] = None
    markets: List[Market] = field(default_factory=list)
    stats: List[Stat] = field(default_factory=list)
    sub_games: List[SubGame] = field(default_factory=list)
    event_plan: List[EventPlanEntry] = field(default_factory=list)
    va: Optional[int] = None
    vi: Optional[str] = None
    zp: Optional[int] = None
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Match:
        return cls(
            game_id=_int(data.get("game_id")),
            opp_1_name=_str(data.get("opp_1_name")),
            opp_2_name=_str(data.get("opp_2_name")),
            game_start=_int(data.get("game_start")),
            game_mid=_opt_int(data.get("game_mid")),
            sport_id=_opt_int(data.get("sport_id")),
            sport_name=_str(data.get("sport_name")),
            country_id=_opt_int(data.get("country_id")),
            country_name=_str(data.get("country_name")),
            tournament_id=_opt_int(data.get("tournament_id")),
            tournament_name=_str(data.get("tournament_name")),
            opp_1_id=_opt_int(data.get("opp_1_id")),
            opp_2_id=_opt_int(data.get("opp_2_id")),
            opp_1_ids=[_int(i) for i in _list(data.get("opp_1_ids"))],
            opp_2_ids=[_int(i) for i in _list(data.get("opp_2_ids"))],
            opp_1_icon=_str(data.get("opp_1_icon")),
            opp_2_icon=_str(data.get("opp_2_icon")),
            timer=_int(data.get("timer")),
            score_full=_str(data.get("score_full")),
            score_period=_str(data.get("score_period")),
            score_extra=_str(data.get("score_extra")),
            period_name=_str(data.get("period_name")),
            extra_time=_str(data.get("extra_time")),
            finale=data.get("finale") if isinstance(data.get("finale"), bool) else None,
            pitch=_str(data.get("pitch")),
            game_dop_name=_str(data.get("game_dop_name")),
            game_desk=_str(data.get("game_desk")),
            game_oc_counter=_opt_int(data.get("game_oc_counter")),
            markets=[
                Market.from_dict(m) for m in _list(data.get("game_oc_list")) if isinstance(m, dict)
            ],
            stats=[Stat.from_dict(s) for s in _list(data.get("stat_list")) if isinstance(s, dict)],
            sub_games=[
                SubGame.from_dict(s) for s in _list(data.get("sub_games")) if isinstance(s, dict)
            ],
            event_plan=[
                EventPlanEntry.from_dict(p)
                for p in _list(data.get("event_plan"))
                if isinstance(p, dict)
            ],
            va=_opt_int(data.get("va")),
            vi=_opt_str(data.get("vi")),
            zp=_opt_int(data.get("zp")),
            raw=data,
        )

    # -- convenience -------------------------------------------------------------

    @property
    def name(self) -> str:
        """``"<opp_1_name> — <opp_2_name>"``."""
        return f"{self.opp_1_name} — {self.opp_2_name}"

    @property
    def start_time(self) -> Optional[datetime]:
        """``game_start`` as a timezone-aware UTC :class:`~datetime.datetime`."""
        if not self.game_start:
            return None
        return datetime.fromtimestamp(self.game_start, tz=timezone.utc)

    @property
    def is_sub_game(self) -> bool:
        """``True`` for a sub-event (its ``game_mid`` points to another match)."""
        return self.game_mid is not None and self.game_mid != self.game_id

    @property
    def has_tracker(self) -> bool:
        """``True`` when a Live 3D Tracker ID (``zp``) is present."""
        return self.zp is not None

    @property
    def has_video(self) -> bool:
        """``True`` when ``va`` is ``1`` (video available)."""
        return self.va == 1

    @property
    def opp_1_icon_url(self) -> Optional[str]:
        """Standard SportAPI icon of the first participant, if an icon name is present."""
        return media.team_icon_url(self.opp_1_icon) if self.opp_1_icon else None

    @property
    def opp_2_icon_url(self) -> Optional[str]:
        """Standard SportAPI icon of the second participant, if an icon name is present."""
        return media.team_icon_url(self.opp_2_icon) if self.opp_2_icon else None

    def market(self, name: Optional[str] = None, *, id: Optional[int] = None) -> Optional[Market]:
        """Return the first market matching ``name`` (``group_name``, case-insensitive)
        and/or ``id`` (``group_id``). Market names are localised; prefer ``id``
        when you know it. Several markets can share a name.
        """
        if name is None and id is None:
            raise ValueError("pass a market name, an id, or both")
        for market in self.find_markets(name, id=id):
            return market
        return None

    def find_markets(self, name: Optional[str] = None, *, id: Optional[int] = None) -> List[Market]:
        """All markets matching ``name`` and/or ``id``, in API order."""
        wanted = name.strip().casefold() if name is not None else None
        return [
            m
            for m in self.markets
            if (wanted is None or m.name.strip().casefold() == wanted)
            and (id is None or m.id == id)
        ]

    def outcome(
        self, market: Union[str, int], outcome: str, *, include_blocked: bool = True
    ) -> Optional[Outcome]:
        """Find a selection by market (name or ``group_id``) and selection name.

        Example: ``match.outcome("1X2", "W1")``.
        """
        markets = (
            self.find_markets(id=market) if isinstance(market, int) else self.find_markets(market)
        )
        for m in markets:
            found = m.outcome(outcome, include_blocked=include_blocked)
            if found is not None:
                return found
        return None

    def iter_outcomes(self) -> Iterator[Outcome]:
        """Iterate over every selection of every market, in API order."""
        for market in self.markets:
            yield from market.outcomes

    def outcome_by_pointer(self, pointer: str) -> Optional[Outcome]:
        """Find a selection by its full ``oc_pointer`` (e.g. after a refresh).

        For player-specific selections the same pointer may appear with
        different ``op_id`` values; this returns the first one.
        """
        for outcome in self.iter_outcomes():
            if outcome.pointer == pointer:
                return outcome
        return None

    def stat(self, id: int) -> Optional[Stat]:
        """Return the live statistic with this ``id`` (for example ``45`` = attacks)."""
        for stat in self.stats:
            if stat.id == id:
                return stat
        return None


@dataclass
class TournamentEvents:
    """A tournament group of the ``events`` response (``body[]``)."""

    tournament_id: int
    tournament_name: str
    matches: List[Match]
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> TournamentEvents:
        return cls(
            tournament_id=_int(data.get("tournament_id")),
            tournament_name=_str(data.get("tournament_name")),
            matches=[
                Match.from_dict(m) for m in _list(data.get("events_list")) if isinstance(m, dict)
            ],
            raw=data,
        )


def iter_matches(groups: Iterable[TournamentEvents]) -> Iterator[Match]:
    """Flatten an ``events`` response into matches, keeping API order."""
    for group in groups:
        yield from group.matches


@dataclass
class TopChampionship:
    """An item of ``topchampionships``."""

    position: int
    tournament_id: int
    tournament_name: str
    sport_id: int
    sport_name: str
    country_id: int
    country_name: str
    counter: int
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> TopChampionship:
        return cls(
            position=_int(data.get("position")),
            tournament_id=_int(data.get("tournament_id")),
            tournament_name=_str(data.get("tournament_name")),
            sport_id=_int(data.get("sport_id")),
            sport_name=_str(data.get("sport_name")),
            country_id=_int(data.get("country_id")),
            country_name=_str(data.get("country_name")),
            counter=_int(data.get("counter")),
            raw=data,
        )


# --- Account ------------------------------------------------------------------


@dataclass
class DailyUsage:
    """Successful requests on one UTC day (``usage_7d[]``)."""

    date: str
    requests: int

    @classmethod
    def from_dict(cls, data: JSON) -> DailyUsage:
        return cls(date=_str(data.get("date")), requests=_int(data.get("requests")))


@dataclass
class AccountKey:
    """One of the client's keys, as returned by ``account`` (``keys[]``).

    ``key`` holds only the last 4 characters; the full key is never returned.
    ``sports`` is the string ``"all"`` or a list of sport IDs.
    """

    key: str
    current: bool
    type: str
    status: str
    label: Optional[str]
    starts_at: Optional[str]
    expires_at: Optional[str]
    days_left: int
    active: bool
    sports: Union[str, List[int]]
    languages: List[str]
    last_used_at: Optional[str]
    access_mode: str
    allowed_ips: List[str]
    allowed_domains: List[str]
    usage_7d: List[DailyUsage]
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> AccountKey:
        sports = data.get("sports")
        return cls(
            key=_str(data.get("key")),
            current=bool(data.get("current")),
            type=_str(data.get("type")),
            status=_str(data.get("status")),
            label=_opt_str(data.get("label")),
            starts_at=_opt_str(data.get("starts_at")),
            expires_at=_opt_str(data.get("expires_at")),
            days_left=_int(data.get("days_left")),
            active=bool(data.get("active")),
            sports=[_int(s) for s in sports] if isinstance(sports, list) else _str(sports),
            languages=[_str(lang) for lang in _list(data.get("languages"))],
            last_used_at=_opt_str(data.get("last_used_at")),
            access_mode=_str(data.get("access_mode")),
            allowed_ips=[_str(i) for i in _list(data.get("allowed_ips"))],
            allowed_domains=[_str(d) for d in _list(data.get("allowed_domains"))],
            usage_7d=[DailyUsage.from_dict(u) for u in _list(data.get("usage_7d"))],
            raw=data,
        )

    @property
    def expires(self) -> Optional[datetime]:
        """``expires_at`` as an aware UTC datetime."""
        return _parse_iso8601(self.expires_at)

    @property
    def starts(self) -> Optional[datetime]:
        """``starts_at`` as an aware UTC datetime (``None``: active since issue)."""
        return _parse_iso8601(self.starts_at)

    @property
    def last_used(self) -> Optional[datetime]:
        """``last_used_at`` as an aware UTC datetime (``None``: never used)."""
        return _parse_iso8601(self.last_used_at)


@dataclass
class Account:
    """Response of the ``account`` method: all keys of the client."""

    client_public_id: str
    client_name: str
    your_ip: str
    keys: List[AccountKey]
    raw: JSON = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: JSON) -> Account:
        raw_client = data.get("client")
        client: JSON = raw_client if isinstance(raw_client, dict) else {}
        return cls(
            client_public_id=_str(client.get("public_id")),
            client_name=_str(client.get("name")),
            your_ip=_str(data.get("your_ip")),
            keys=[AccountKey.from_dict(k) for k in _list(data.get("keys"))],
            raw=data,
        )

    @property
    def current_key(self) -> Optional[AccountKey]:
        """The key used for this request (``current: true``)."""
        for key in self.keys:
            if key.current:
                return key
        return None
