"""Polling helpers that follow the SportAPI data update guidelines.

The Sport Line API is REST: every response is a snapshot, so fresh scores and
odds require repeating requests. The guidelines set a *minimum* interval per
method and line type, ask clients not to overlap requests for the same data,
and suggest a growing delay (5 → 10 → 20 → 40 s) after temporary failures only.

See https://sportapi.net/docs/sport-line/getting-started/update-guidelines.html
"""

from __future__ import annotations

import asyncio
import time
from typing import (
    AsyncIterator,
    Awaitable,
    Callable,
    Iterator,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
)

from .errors import SportAPIError

__all__ = [
    "RECOMMENDED_INTERVALS",
    "RETRY_BACKOFF",
    "recommended_interval",
    "poll",
    "apoll",
]

T = TypeVar("T")

#: Minimum seconds between two requests, per method and line type.
#: ``None`` means the combination is not used. If the SportAPI manager gave you
#: different intervals for your connection, use those.
RECOMMENDED_INTERVALS: Mapping[str, Mapping[str, Optional[int]]] = {
    "menu": {"live": 20, "line": 60},
    "sports": {"live": 60, "line": 120},
    "countries": {"live": 60, "line": 120},
    "tournaments": {"live": 60, "line": 120},
    "events": {"live": 7, "line": 30},
    "event": {"live": 5, "line": 30},
    "topmatches": {"live": 30, "line": 120},
    "toplist": {"live": None, "line": 120},
    "topchampionships": {"live": 60, "line": 300},
    "events_by_period": {"live": None, "line": 60},
}

#: Suggested delays (seconds) after consecutive temporary failures.
RETRY_BACKOFF: Sequence[float] = (5, 10, 20, 40)


def recommended_interval(method: str, line_type: str) -> int:
    """Return the documented minimum polling interval in seconds.

    >>> recommended_interval("events", "live")
    7

    Raises:
        ValueError: unknown method, or the method is not used for this line type
            (for example ``toplist`` in Live).
    """
    try:
        value = RECOMMENDED_INTERVALS[method][line_type]
    except KeyError:
        raise ValueError(f"no documented interval for {method!r} / {line_type!r}") from None
    if value is None:
        raise ValueError(f"{method!r} is not used for {line_type!r}")
    return value


def poll(
    fetch: Callable[[], T],
    interval: float,
    *,
    backoff: Sequence[float] = RETRY_BACKOFF,
    max_polls: Optional[int] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Iterator[T]:
    """Call ``fetch`` repeatedly and yield each successful result.

    The cycle is the one recommended by the docs: request → wait for the
    response → let the caller process it → wait ``interval`` → next request.
    Requests never overlap.

    Temporary failures (network errors, HTTP 5xx) are retried after
    ``backoff`` delays (5, 10, 20, 40 s, then 40 s); after a success the normal
    interval resumes. Errors that cannot be fixed by waiting — invalid or
    expired key, unavailable language or sport, bad parameters,
    ``Game id finished`` — are raised immediately.

    Args:
        fetch: zero-argument callable, e.g. ``lambda: client.events(1, "live")``.
        interval: seconds between requests; use at least
            :func:`recommended_interval` for the method.
        max_polls: stop after this many successful results (``None``: forever).
    """
    if interval <= 0:
        raise ValueError("interval must be positive")
    delays = list(backoff) or [interval]
    done = 0
    failures = 0
    while max_polls is None or done < max_polls:
        try:
            result = fetch()
        except SportAPIError as error:
            if not error.retryable:
                raise
            sleep(delays[min(failures, len(delays) - 1)])
            failures += 1
            continue
        failures = 0
        done += 1
        yield result
        if max_polls is not None and done >= max_polls:
            return
        sleep(interval)


async def apoll(
    fetch: Callable[[], Awaitable[T]],
    interval: float,
    *,
    backoff: Sequence[float] = RETRY_BACKOFF,
    max_polls: Optional[int] = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[T]:
    """Async version of :func:`poll`; ``fetch`` returns an awaitable."""
    if interval <= 0:
        raise ValueError("interval must be positive")
    delays = list(backoff) or [interval]
    done = 0
    failures = 0
    while max_polls is None or done < max_polls:
        try:
            result = await fetch()
        except SportAPIError as error:
            if not error.retryable:
                raise
            await sleep(delays[min(failures, len(delays) - 1)])
            failures += 1
            continue
        failures = 0
        done += 1
        yield result
        if max_polls is not None and done >= max_polls:
            return
        await sleep(interval)


def checked_interval(method: str, line_type: str, interval: Optional[float]) -> float:
    """Return ``interval`` or the documented minimum; reject faster polling."""
    minimum = recommended_interval(method, line_type)
    if interval is None:
        return float(minimum)
    if interval < minimum:
        raise ValueError(
            f"{method} ({line_type}) should not be requested more often than every "
            f"{minimum} s (got {interval}). See "
            "https://sportapi.net/docs/sport-line/getting-started/update-guidelines.html"
        )
    return float(interval)
