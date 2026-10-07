"""Standard SportAPI icon URLs (WebP) built from IDs in API responses.

See https://sportapi.net/docs/sport-line/reference/media-assets.html
"""

from __future__ import annotations

__all__ = [
    "sport_icon_url",
    "country_flag_url",
    "tournament_icon_url",
    "team_icon_url",
]

_CDN = "https://cdn.sportapi.net"


def sport_icon_url(sport_id: int) -> str:
    """Icon for a ``sport_id``."""
    return f"{_CDN}/sports/v1/color/{int(sport_id)}.webp"


def country_flag_url(country_id: int) -> str:
    """Flag for a ``country_id``."""
    return f"{_CDN}/flags/v1/color/{int(country_id)}.webp"


def tournament_icon_url(tournament_id: int) -> str:
    """Icon for a ``tournament_id``."""
    return f"{_CDN}/tournaments/v1/color/{int(tournament_id)}.webp"


def team_icon_url(icon_name: str) -> str:
    """Icon for a team or participant from ``opp_1_icon`` / ``opp_2_icon``.

    The API returns a file name such as ``8bd073a686a067e6732d8d1688a517c0.png``;
    the original extension is removed and ``.webp`` is used.
    """
    name = icon_name.strip().rsplit("/", 1)[-1]
    if "." in name:
        name = name.rsplit(".", 1)[0]
    if not name:
        raise ValueError("icon_name is empty")
    return f"{_CDN}/opp/v1/color/{name}.webp"
