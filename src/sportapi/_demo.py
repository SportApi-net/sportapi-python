"""Demo mode: serves the example responses published in the SportAPI documentation.

The files in ``_demo_data`` are the English full JSON responses from
https://sportapi.net/docs/sport-line/examples/json-responses/overview.html,
copied without changes. They are snapshots from August–October 2026, not live data.
"""

from __future__ import annotations

import copy
import json
import warnings
from functools import cache
from importlib import resources
from typing import Any, Dict, Optional, Tuple

from .errors import GET_KEY_URL, DemoDataUnavailableError, SportAPIDemoWarning

DEMO_LANG = "en"

# (method, *path parameters, *query options) -> bundled file name
_FILES: Dict[Tuple[Any, ...], str] = {
    ("menu", "live"): "menu.live.en.json",
    ("menu", "line"): "menu.line.en.json",
    ("sports", "live"): "sports.live.en.json",
    ("sports", "line"): "sports.line.en.json",
    ("countries", 1, "live"): "countries.sport-1.live.en.json",
    ("countries", 1, "line"): "countries.sport-1.line.en.json",
    ("tournaments", 1, 1, "live"): "tournaments.sport-1.country-1.live.en.json",
    ("tournaments", 1, 1, "line"): "tournaments.sport-1.country-1.line.en.json",
    ("events", 1, 0, "live"): "events.sport-1.tournament-0.sub-50.live.en.json",
    ("events", 1, 0, "line"): "events.sport-1.tournament-0.sub-50.line.en.json",
    ("event", 746146992, "live"): "event.game-746146992.group.live.en.json",
    ("event", 730321837, "line"): "event.game-730321837.group.line.en.json",
    ("search", "live", "perth"): "search.query-perth.live.en.json",
    ("search", "line", "manchester"): "search.query-manchester.line.en.json",
    ("toplist", 1, False): "toplist.sport-1.line.en.json",
    ("toplist", 1, True): "toplist.full.sport-1.line.en.json",
    ("topmatches", "live", False): "topmatches.live.en.json",
    ("topmatches", "line", False): "topmatches.line.en.json",
    ("topmatches", "live", True): "topmatches.full.live.en.json",
    ("topmatches", "line", True): "topmatches.full.line.en.json",
}

AVAILABLE_CALLS = (
    'menu("live" | "line")',
    'sports("live" | "line")',
    'countries(1, "live" | "line")',
    'tournaments(1, 1, "live" | "line")',
    'events(1, "live" | "line")  # tournament_id=0',
    'event(746146992, "live"), event(730321837, "line")',
    'search("Perth", "live"), search("Manchester", "line")',
    "toplist(1), toplist(1, full=True)",
    'topmatches("live" | "line"), with or without full=True',
)

_warned = False


def warn_once() -> None:
    """Warn (once per process) that responses are bundled demo data."""
    global _warned
    if _warned:
        return
    _warned = True
    warnings.warn(
        "SportAPI demo mode: no SPORTAPI_KEY / SPORTAPI_BASE_URL configured, so the "
        "client returns bundled example responses from the SportAPI documentation "
        "(snapshots, not live data). Get an API key at " + GET_KEY_URL,
        SportAPIDemoWarning,
        stacklevel=5,
    )


def has_file(key: Tuple[Any, ...]) -> bool:
    return key in _FILES


def unavailable(description: str, reason: Optional[str] = None) -> DemoDataUnavailableError:
    lines = [
        f"No bundled demo response for {description}." + (f" {reason}" if reason else ""),
        "Demo mode (no SPORTAPI_KEY / SPORTAPI_BASE_URL set) only serves the example "
        "responses from the SportAPI documentation, in English (lang='en'):",
    ]
    lines.extend(f"  - {call}" for call in AVAILABLE_CALLS)
    lines.append(
        "For live data, get a personal base URL and API key "
        f"({GET_KEY_URL}) and set SPORTAPI_KEY and SPORTAPI_BASE_URL."
    )
    return DemoDataUnavailableError("\n".join(lines))


@cache
def _read_text(filename: str) -> str:
    return (resources.files("sportapi") / "_demo_data" / filename).read_text(encoding="utf-8")


def load(key: Tuple[Any, ...], *, strip_odds: bool = False) -> Any:
    """Return a fresh copy of the bundled payload for ``key``."""
    payload = json.loads(_read_text(_FILES[key]))
    if strip_odds:
        payload = _without_odds(payload)
    return payload


def _without_odds(payload: Any) -> Any:
    """Emulate ``odds=false``: remove ``game_oc_list`` from every match, keep the rest."""
    payload = copy.deepcopy(payload)
    body = payload.get("body") if isinstance(payload, dict) else None

    def strip(match: Any) -> None:
        if isinstance(match, dict):
            match.pop("game_oc_list", None)

    if isinstance(body, dict):
        strip(body)
    elif isinstance(body, list):
        for item in body:
            if isinstance(item, dict) and isinstance(item.get("events_list"), list):
                for match in item["events_list"]:
                    strip(match)
            else:
                strip(item)
    return payload
