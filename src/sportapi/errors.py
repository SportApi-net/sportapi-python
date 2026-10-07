"""Exception classes raised by the SportAPI client.

The Sport Line API reports access and parameter errors as a JSON object with
``error_code`` and ``error_message`` (not always with a matching HTTP status),
and reports some ``event`` states as ``body.message`` inside a successful
envelope. Both are turned into the exceptions below.

See https://sportapi.net/docs/sport-line/getting-started/error-handling.html
"""

from __future__ import annotations

from typing import Any, Optional

__all__ = [
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

GET_KEY_URL = "https://t.me/sportapinet_bot?start=github_sportapi_python"


class SportAPIError(Exception):
    """Base class for every error raised by this library."""

    #: Whether retrying the same request later can succeed without changing it.
    #: Used by :func:`sportapi.poll` to decide between back-off and giving up.
    retryable: bool = False


class ConfigurationError(SportAPIError):
    """The client is configured inconsistently (for example a key without a base URL)."""


class DemoDataUnavailableError(SportAPIError):
    """Demo mode has no bundled example response for this request."""


class TransportError(SportAPIError):
    """The request did not reach the API or no response was received (network, timeout)."""

    retryable = True


class UnexpectedResponseError(SportAPIError):
    """The API returned something that is neither data nor a documented error."""

    def __init__(
        self, message: str, *, http_status: Optional[int] = None, payload: Any = None
    ) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.payload = payload


class HTTPStatusError(UnexpectedResponseError):
    """HTTP 4xx/5xx response without a documented ``error_code`` body.

    Server-side (5xx) failures are marked as retryable.
    """

    def __init__(self, message: str, *, http_status: int, payload: Any = None) -> None:
        super().__init__(message, http_status=http_status, payload=payload)
        self.retryable = http_status >= 500


class APIError(SportAPIError):
    """A documented API error: the response contained ``error_code`` and ``error_message``.

    Attributes:
        code: the numeric ``error_code`` (for example ``100`` or ``90``).
        message: the ``error_message`` text returned by the API.
        http_status: the HTTP status of the response, if any.
    """

    def __init__(
        self,
        code: Optional[int],
        message: str,
        *,
        http_status: Optional[int] = None,
        payload: Any = None,
    ) -> None:
        super().__init__(f"SportAPI error {code}: {message}")
        self.code = code
        self.message = message
        self.http_status = http_status
        self.payload = payload


# --- 1. API key errors -------------------------------------------------------


class AuthenticationError(APIError):
    """The API key is missing, unknown, inactive or used from a disallowed address."""


class MissingKeyError(AuthenticationError):
    """``Missing Package header``: the key was not sent in the ``Package`` header."""


class InvalidKeyError(AuthenticationError):
    """``Invalid Package``: the key was not found."""


class KeyExpiredError(AuthenticationError):
    """``Package has expired``: the access period has ended. Contact the SportAPI manager."""


class KeyBlockedError(AuthenticationError):
    """``Package is blocked``: the key is temporarily paused."""


class KeyNotActiveError(AuthenticationError):
    """``Package is not active yet``: the access period has not started yet."""


class AccessRestrictedError(AuthenticationError):
    """``Access from IP/site … is not allowed for this Package``.

    The key is restricted to the client's IP addresses or websites; the message
    contains the address the request came from.
    """


# --- 2. Subscription and permission errors -----------------------------------


class PermissionDeniedError(APIError):
    """The key does not include the requested sport, language or data."""


class AccessDeniedError(PermissionDeniedError):
    """``Access denied``: for example a ``sport_id`` outside the subscription."""


class LanguageNotAvailableError(PermissionDeniedError):
    """``The language is not available in your package.``"""


# --- 3. Request parameter errors ---------------------------------------------


class InvalidRequestError(APIError):
    """A request parameter is invalid."""


class InvalidLanguageError(InvalidRequestError):
    """``Invalid language``: the language code is not supported."""


class InvalidLineTypeError(InvalidRequestError):
    """``Wrong data type (accept only live or line)`` (``error_code`` 90)."""


# --- 4. States of the ``event`` method ---------------------------------------


class EventUnavailableError(SportAPIError):
    """``event`` returned a service message in ``body.message`` instead of a match.

    Attributes:
        game_id: the requested ``game_id``.
        message: the message text returned by the API.
    """

    def __init__(self, game_id: int, message: str) -> None:
        super().__init__(f"Match {game_id}: {message}")
        self.game_id = game_id
        self.message = message


class GameNotFoundError(EventUnavailableError):
    """``Game not found``: no match exists for this ``game_id`` in this line type."""


class GameFinishedError(EventUnavailableError):
    """``Game id finished``: the match is no longer available under this ``game_id``.

    The reason is not reported: it may have moved from Prematch to Live under a
    new ``game_id``, been cancelled, or ended. Stop polling this ID and refresh
    the match list with ``events``.
    """


class SportAPIDemoWarning(UserWarning):
    """Emitted once when the client serves bundled demo data instead of live data."""


_EXACT_MESSAGES = {
    "Missing Package header": MissingKeyError,
    "Invalid Package": InvalidKeyError,
    "Package has expired": KeyExpiredError,
    "Package is blocked": KeyBlockedError,
    "Package is not active yet": KeyNotActiveError,
    "Access denied": AccessDeniedError,
    "The language is not available in your package.": LanguageNotAvailableError,
    "Invalid language": InvalidLanguageError,
    "Wrong data type (accept only live or line)": InvalidLineTypeError,
}


def api_error_from_payload(payload: dict[str, Any], http_status: Optional[int] = None) -> APIError:
    """Build the most specific :class:`APIError` subclass for an error payload."""
    raw_code = payload.get("error_code")
    try:
        code: Optional[int] = int(raw_code) if raw_code is not None else None
    except (TypeError, ValueError):
        code = None
    message = str(payload.get("error_message") or "Unknown error")
    normalized = message.strip()

    cls: type[APIError] = _EXACT_MESSAGES.get(normalized, APIError)
    if cls is APIError:
        if normalized.startswith("Access from ") and normalized.endswith(
            "is not allowed for this Package"
        ):
            cls = AccessRestrictedError
        elif code == 90:
            cls = InvalidLineTypeError
    return cls(code, message, http_status=http_status, payload=payload)


def event_error_from_message(game_id: int, message: str) -> EventUnavailableError:
    """Build the exception for an ``event`` ``body.message`` state."""
    normalized = message.strip()
    if normalized == "Game not found":
        return GameNotFoundError(game_id, message)
    if normalized == "Game id finished":
        return GameFinishedError(game_id, message)
    return EventUnavailableError(game_id, message)
