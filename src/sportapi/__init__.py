"""Official Python client for the SportAPI Sport Line API.

Prematch and Live sports data — sports, tournaments, matches, scores, live
statistics and betting odds — from https://sportapi.net.

Quick start (works without an API key, on bundled demo data)::

    from sportapi import SportAPI

    api = SportAPI()
    match = api.event(746146992, "live")
    print(match.name, match.score_full, match.outcome("Total", "Over 3.5"))

Documentation: https://sportapi.net/docs/sport-line/getting-started/quick-start.html
"""

from ._core import LINE, LIVE
from ._version import __version__
from .async_client import AsyncSportAPI
from .client import SportAPI
from .errors import (
    AccessDeniedError,
    AccessRestrictedError,
    APIError,
    AuthenticationError,
    ConfigurationError,
    DemoDataUnavailableError,
    EventUnavailableError,
    GameFinishedError,
    GameNotFoundError,
    HTTPStatusError,
    InvalidKeyError,
    InvalidLanguageError,
    InvalidLineTypeError,
    InvalidRequestError,
    KeyBlockedError,
    KeyExpiredError,
    KeyNotActiveError,
    LanguageNotAvailableError,
    MissingKeyError,
    PermissionDeniedError,
    SportAPIDemoWarning,
    SportAPIError,
    TransportError,
    UnexpectedResponseError,
)
from .models import (
    Account,
    AccountKey,
    Country,
    DailyUsage,
    EventPlanEntry,
    Market,
    Match,
    Outcome,
    Sport,
    Stat,
    SubGame,
    TopChampionship,
    Tournament,
    TournamentEvents,
    iter_matches,
)
from .polling import RECOMMENDED_INTERVALS, apoll, poll, recommended_interval

PREMATCH = LINE
"""Alias of ``"line"``: matches that have not started yet."""

__all__ = [
    "__version__",
    "SportAPI",
    "AsyncSportAPI",
    "LIVE",
    "LINE",
    "PREMATCH",
    # models
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
    # polling
    "RECOMMENDED_INTERVALS",
    "recommended_interval",
    "poll",
    "apoll",
    # errors
    "SportAPIError",
    "ConfigurationError",
    "DemoDataUnavailableError",
    "TransportError",
    "UnexpectedResponseError",
    "HTTPStatusError",
    "APIError",
    "AuthenticationError",
    "MissingKeyError",
    "InvalidKeyError",
    "KeyExpiredError",
    "KeyBlockedError",
    "KeyNotActiveError",
    "AccessRestrictedError",
    "PermissionDeniedError",
    "AccessDeniedError",
    "LanguageNotAvailableError",
    "InvalidRequestError",
    "InvalidLanguageError",
    "InvalidLineTypeError",
    "EventUnavailableError",
    "GameNotFoundError",
    "GameFinishedError",
    "SportAPIDemoWarning",
]
