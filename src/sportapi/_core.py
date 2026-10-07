"""Transport-independent parts of the client: configuration, request specs and
response handling. Shared by :class:`sportapi.SportAPI` and
:class:`sportapi.AsyncSportAPI`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Mapping, Optional, Tuple, TypeVar
from urllib.parse import quote, urlsplit

from . import _demo
from ._version import __version__
from .errors import (
    GET_KEY_URL,
    ConfigurationError,
    HTTPStatusError,
    UnexpectedResponseError,
    api_error_from_payload,
    event_error_from_message,
)
from .models import (
    Account,
    Country,
    Match,
    Sport,
    TopChampionship,
    Tournament,
    TournamentEvents,
    _parse_iso8601,
)

T = TypeVar("T")

LIVE = "live"
LINE = "line"
LINE_TYPES = (LIVE, LINE)

ENV_KEY = "SPORTAPI_KEY"
ENV_BASE_URL = "SPORTAPI_BASE_URL"
DEFAULT_TIMEOUT = 15.0
USER_AGENT = f"sportapi-python/{__version__}"

# `count` path segment of `events`: the limit was removed, the docs say "always pass 50".
_EVENTS_COUNT = 50
_PERIOD_HOURS = (0, 2, 4, 6, 12)
_PERIOD_MAX_DAYS = 5


@dataclass(frozen=True)
class Config:
    api_key: Optional[str]
    base_url: Optional[str]
    demo: bool

    def __repr__(self) -> str:  # never print the key
        if self.demo:
            return "Config(demo=True)"
        return f"Config(base_url={self.base_url!r}, api_key='***', demo=False)"


def resolve_config(api_key: Optional[str], base_url: Optional[str], demo: Optional[bool]) -> Config:
    """Combine constructor arguments with ``SPORTAPI_KEY`` / ``SPORTAPI_BASE_URL``."""
    key = api_key if api_key is not None else os.environ.get(ENV_KEY)
    url = base_url if base_url is not None else os.environ.get(ENV_BASE_URL)
    key = (key or "").strip() or None
    url = (url or "").strip().rstrip("/") or None

    if demo:
        return Config(api_key=None, base_url=None, demo=True)
    if key and url:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ConfigurationError(
                f"{ENV_BASE_URL} must be an absolute http(s) URL such as "
                "'https://YOUR_API_DOMAIN' (the base URL provided by the SportAPI manager)."
            )
        return Config(api_key=key, base_url=url, demo=False)
    if demo is False or key or url:
        missing = [name for name, value in ((ENV_KEY, key), (ENV_BASE_URL, url)) if not value]
        raise ConfigurationError(
            "Live mode needs both an API key and your personal base URL; missing: "
            + ", ".join(missing)
            + ". Both are issued by the SportAPI manager: "
            + GET_KEY_URL
        )
    return Config(api_key=None, base_url=None, demo=True)


@dataclass(frozen=True)
class RequestSpec(Generic[T]):
    """Everything needed to perform one API call, in live or demo mode."""

    name: str
    path: str
    parse: Callable[[Any], T]
    params: Mapping[str, str] = field(default_factory=dict)
    description: str = ""
    demo_key: Optional[Tuple[Any, ...]] = None
    demo_strip_odds: bool = False
    demo_reason: Optional[str] = None
    game_id: Optional[int] = None


# --- validation helpers -------------------------------------------------------


def _line_type(value: str) -> str:
    if value not in LINE_TYPES:
        raise ValueError(f"line_type must be 'live' or 'line' (Prematch), got {value!r}")
    return value


def _id(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {value!r}")
    return value


def _lang(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("lang must be a non-empty language code such as 'en'")
    return quote(value.strip(), safe="")


def _no_esports_demo(cybersport: bool) -> Optional[str]:
    return "cybersport=True is not in the demo data." if cybersport else None


def _demo_check(
    key: Tuple[Any, ...],
    lang: str,
    *,
    unsupported: Optional[str] = None,
) -> Tuple[Optional[Tuple[Any, ...]], Optional[str]]:
    if unsupported:
        return None, unsupported
    if lang != _demo.DEMO_LANG:
        return None, f"Demo responses are only bundled for lang='en' (got {lang!r})."
    if not _demo.has_file(key):
        return None, None
    return key, None


# --- parsers ------------------------------------------------------------------


def _list_parser(item: Callable[[Dict[str, Any]], T]) -> Callable[[Any], List[T]]:
    def parse(body: Any) -> List[T]:
        if not isinstance(body, list):
            raise UnexpectedResponseError(
                f"Expected a list in 'body', got {type(body).__name__}", payload=body
            )
        return [item(entry) for entry in body if isinstance(entry, dict)]

    return parse


def _object_parser(item: Callable[[Dict[str, Any]], T]) -> Callable[[Any], T]:
    def parse(body: Any) -> T:
        if not isinstance(body, dict):
            raise UnexpectedResponseError(
                f"Expected an object in 'body', got {type(body).__name__}", payload=body
            )
        return item(body)

    return parse


# --- request specs ------------------------------------------------------------


def menu_spec(line_type: str, lang: str, cybersport: bool) -> RequestSpec[List[Sport]]:
    lt = _line_type(line_type)
    lg = _lang(lang)
    demo_key, reason = _demo_check(("menu", lt), lg, unsupported=_no_esports_demo(cybersport))
    return RequestSpec(
        name="menu",
        path=f"/v1/menu/{lt}/{lg}",
        params={"cybersport": "true"} if cybersport else {},
        parse=_list_parser(Sport.from_dict),
        description=f"menu({lt!r}, lang={lg!r}, cybersport={cybersport})",
        demo_key=demo_key,
        demo_reason=reason,
    )


def sports_spec(line_type: str, lang: str, cybersport: bool) -> RequestSpec[List[Sport]]:
    lt = _line_type(line_type)
    lg = _lang(lang)
    demo_key, reason = _demo_check(("sports", lt), lg, unsupported=_no_esports_demo(cybersport))
    return RequestSpec(
        name="sports",
        path=f"/v1/sports/{lt}/{lg}",
        params={"cybersport": "true"} if cybersport else {},
        parse=_list_parser(Sport.from_dict),
        description=f"sports({lt!r}, lang={lg!r}, cybersport={cybersport})",
        demo_key=demo_key,
        demo_reason=reason,
    )


def countries_spec(sport_id: int, line_type: str, lang: str) -> RequestSpec[List[Country]]:
    sid = _id("sport_id", sport_id)
    lt = _line_type(line_type)
    lg = _lang(lang)
    demo_key, reason = _demo_check(("countries", sid, lt), lg)
    return RequestSpec(
        name="countries",
        path=f"/v1/countries/{sid}/{lt}/{lg}",
        parse=_list_parser(Country.from_dict),
        description=f"countries({sid}, {lt!r}, lang={lg!r})",
        demo_key=demo_key,
        demo_reason=reason,
    )


def tournaments_spec(
    sport_id: int, country_id: int, line_type: str, lang: str, cybersport: bool
) -> RequestSpec[List[Tournament]]:
    sid = _id("sport_id", sport_id)
    cid = _id("country_id", country_id)
    lt = _line_type(line_type)
    lg = _lang(lang)
    demo_key, reason = _demo_check(
        ("tournaments", sid, cid, lt),
        lg,
        unsupported=_no_esports_demo(cybersport),
    )
    return RequestSpec(
        name="tournaments",
        path=f"/v1/tournaments/{sid}/{cid}/{lt}/{lg}",
        params={"cybersport": "true"} if cybersport else {},
        parse=_list_parser(Tournament.from_dict),
        description=f"tournaments({sid}, {cid}, {lt!r}, lang={lg!r}, cybersport={cybersport})",
        demo_key=demo_key,
        demo_reason=reason,
    )


def events_spec(
    sport_id: int,
    line_type: str,
    tournament_id: int,
    lang: str,
    cybersport: bool,
    full_line: bool,
    odds: bool,
) -> RequestSpec[List[TournamentEvents]]:
    sid = _id("sport_id", sport_id)
    tid = _id("tournament_id", tournament_id)
    lt = _line_type(line_type)
    lg = _lang(lang)
    if full_line and (lt != LINE or tid != 0):
        raise ValueError(
            "full_line=True (match=all) only applies to Prematch ('line') with tournament_id=0"
        )
    params: Dict[str, str] = {}
    if cybersport:
        params["cybersport"] = "true"
    if full_line:
        params["match"] = "all"
    if not odds:
        params["odds"] = "false"
    unsupported = _no_esports_demo(cybersport)
    if full_line:
        unsupported = "The demo Prematch file is the default 50-match 'Top', not match=all."
    demo_key, reason = _demo_check(("events", sid, tid, lt), lg, unsupported=unsupported)
    return RequestSpec(
        name="events",
        path=f"/v1/events/{sid}/{tid}/sub/{_EVENTS_COUNT}/{lt}/{lg}",
        params=params,
        parse=_list_parser(TournamentEvents.from_dict),
        description=f"events({sid}, {lt!r}, tournament_id={tid}, lang={lg!r})",
        demo_key=demo_key,
        demo_strip_odds=not odds,
        demo_reason=reason,
    )


def events_by_period_spec(
    sport_id: int, tournament_id: int, hours: int, days: int, lang: str, odds: bool
) -> RequestSpec[List[TournamentEvents]]:
    sid = _id("sport_id", sport_id)
    tid = _id("tournament_id", tournament_id)
    if hours not in _PERIOD_HOURS or isinstance(hours, bool):
        raise ValueError(f"hours must be one of {_PERIOD_HOURS}, got {hours!r}")
    if isinstance(days, bool) or not isinstance(days, int) or not 0 <= days <= _PERIOD_MAX_DAYS:
        raise ValueError(f"days must be between 0 (today) and {_PERIOD_MAX_DAYS}, got {days!r}")
    lg = _lang(lang)
    return RequestSpec(
        name="events_by_period",
        path=f"/v1/events/{sid}/{tid}/sub/{_EVENTS_COUNT}/{LINE}/{hours}/{days}/{lg}",
        params={} if odds else {"odds": "false"},
        parse=_list_parser(TournamentEvents.from_dict),
        description=f"events_by_period({sid}, tournament_id={tid}, hours={hours}, days={days})",
        demo_reason="The match calendar has no example response in the documentation.",
    )


def event_spec(game_id: int, line_type: str, lang: str, odds: bool) -> RequestSpec[Match]:
    gid = _id("game_id", game_id)
    lt = _line_type(line_type)
    lg = _lang(lang)
    demo_key, reason = _demo_check(("event", gid, lt), lg)
    return RequestSpec(
        name="event",
        path=f"/v1/event/{gid}/group/{lt}/{lg}",
        params={} if odds else {"odds": "false"},
        parse=_object_parser(Match.from_dict),
        description=f"event({gid}, {lt!r}, lang={lg!r})",
        demo_key=demo_key,
        demo_strip_odds=not odds,
        demo_reason=reason,
        game_id=gid,
    )


def search_spec(text: str, line_type: str, lang: str) -> RequestSpec[List[Match]]:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("search text must be a non-empty string")
    lt = _line_type(line_type)
    lg = _lang(lang)
    query = text.strip()
    demo_key, reason = _demo_check(("search", lt, query.casefold()), lg)
    return RequestSpec(
        name="search",
        path=f"/v1/search/{lt}/{lg}/{quote(query, safe='')}",
        parse=_list_parser(Match.from_dict),
        description=f"search({query!r}, {lt!r}, lang={lg!r})",
        demo_key=demo_key,
        demo_reason=reason,
    )


def toplist_spec(sport_id: int, lang: str, full: bool, odds: bool) -> RequestSpec[List[Match]]:
    sid = _id("sport_id", sport_id)
    lg = _lang(lang)
    params: Dict[str, str] = {}
    if full:
        params["full"] = "true"
        if not odds:
            params["odds"] = "false"
    demo_key, reason = _demo_check(("toplist", sid, bool(full)), lg)
    return RequestSpec(
        name="toplist",
        path=f"/v1/toplist/{sid}/{lg}",
        params=params,
        parse=_list_parser(Match.from_dict),
        description=f"toplist({sid}, lang={lg!r}, full={full})",
        demo_key=demo_key,
        demo_strip_odds=full and not odds,
        demo_reason=reason,
    )


def topmatches_spec(line_type: str, lang: str, full: bool, odds: bool) -> RequestSpec[List[Match]]:
    lt = _line_type(line_type)
    lg = _lang(lang)
    params: Dict[str, str] = {}
    if full:
        params["full"] = "true"
        if not odds:
            params["odds"] = "false"
    demo_key, reason = _demo_check(("topmatches", lt, bool(full)), lg)
    return RequestSpec(
        name="topmatches",
        path=f"/v1/topmatches/{lt}/{lg}",
        params=params,
        parse=_list_parser(Match.from_dict),
        description=f"topmatches({lt!r}, lang={lg!r}, full={full})",
        demo_key=demo_key,
        demo_strip_odds=full and not odds,
        demo_reason=reason,
    )


def topchampionships_spec(line_type: str, lang: str) -> RequestSpec[List[TopChampionship]]:
    lt = _line_type(line_type)
    lg = _lang(lang)
    return RequestSpec(
        name="topchampionships",
        path=f"/v1/topchampionships/{lt}/{lg}",
        parse=_list_parser(TopChampionship.from_dict),
        description=f"topchampionships({lt!r}, lang={lg!r})",
        demo_reason="topchampionships has no full example response in the documentation.",
    )


def account_spec() -> RequestSpec[Account]:
    return RequestSpec(
        name="account",
        path="/v1/account",
        parse=_object_parser(Account.from_dict),
        description="account()",
        demo_reason="account describes your own keys, so it needs a real key.",
    )


# --- execution helpers -----------------------------------------------------------


def request_headers(api_key: str) -> Dict[str, str]:
    return {"Package": api_key, "Accept": "application/json", "User-Agent": USER_AGENT}


def demo_payload(spec: RequestSpec[Any]) -> Any:
    if spec.demo_key is None:
        raise _demo.unavailable(spec.description, spec.demo_reason)
    _demo.warn_once()
    return _demo.load(spec.demo_key, strip_odds=spec.demo_strip_odds)


def decode_json(text: str, http_status: int) -> Any:
    import json

    try:
        return json.loads(text)
    except ValueError:
        if http_status >= 400:
            raise HTTPStatusError(
                f"SportAPI returned HTTP {http_status} with a non-JSON body",
                http_status=http_status,
            ) from None
        raise UnexpectedResponseError(
            f"SportAPI returned invalid JSON (HTTP {http_status})",
            http_status=http_status,
        ) from None


def handle_payload(spec: RequestSpec[T], payload: Any, http_status: int = 200) -> T:
    """Turn a decoded response into data, following the documented parsing order:
    API error → envelope → ``event`` message → method schema.
    """
    if isinstance(payload, dict) and "error_code" in payload:
        raise api_error_from_payload(payload, http_status)
    if http_status >= 400:
        raise HTTPStatusError(
            f"SportAPI returned HTTP {http_status}", http_status=http_status, payload=payload
        )
    if not (
        isinstance(payload, dict)
        and "status" in payload
        and isinstance(payload.get("page"), str)
        and "body" in payload
    ):
        raise UnexpectedResponseError(
            "Unknown SportAPI response format", http_status=http_status, payload=payload
        )
    body = payload["body"]
    if spec.game_id is not None and isinstance(body, dict) and isinstance(body.get("message"), str):
        raise event_error_from_message(spec.game_id, body["message"])
    return spec.parse(body)


def parse_key_expires(value: Optional[str]) -> Optional[datetime]:
    return _parse_iso8601(value)
