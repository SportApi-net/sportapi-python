from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from sportapi import (
    Account,
    Market,
    Match,
    Outcome,
    Sport,
    Tournament,
    TournamentEvents,
    iter_matches,
)
from sportapi.media import country_flag_url, sport_icon_url, team_icon_url, tournament_icon_url

from .conftest import example


@pytest.fixture(scope="module")
def live_event() -> Match:
    return Match.from_dict(example("event.game-746146992.group.live.en.json")["body"])


@pytest.fixture(scope="module")
def prematch_event() -> Match:
    return Match.from_dict(example("event.game-730321837.group.line.en.json")["body"])


def test_event_market_keeps_api_columns(prematch_event: Match) -> None:
    market = prematch_event.market("1X2")
    assert market is not None
    assert market.id == 1 and market.columns == 3
    assert market.column_outcomes is not None and len(market.column_outcomes) == 3
    assert [o.name for o in market.outcomes] == ["W1", "X", "W2"]
    assert [c[0].name for c in market.column_outcomes] == ["W1", "X", "W2"]


def test_events_market_is_flat() -> None:
    groups = [
        TournamentEvents.from_dict(t)
        for t in example("events.sport-1.tournament-0.sub-50.live.en.json")["body"]
    ]
    match = next(iter_matches(groups))
    assert match.markets
    assert all(m.column_outcomes is None for m in match.markets)
    assert match.markets[0].outcomes


def test_outcome_lookup(prematch_event: Match) -> None:
    w1 = prematch_event.outcome("1x2", "w1")  # case-insensitive
    assert w1 is not None
    assert w1.odds == 1.525
    assert w1.odds_decimal == Decimal("1.525")
    assert w1.pointer == "730321837|1|1|0"
    assert w1.size == 0 and w1.size_value == 0.0
    assert w1.available and not w1.blocked
    assert prematch_event.outcome(1, "W1") == w1  # by group_id
    assert prematch_event.outcome("1X2", "draw") is None
    assert prematch_event.outcome_by_pointer("730321837|1|1|0") == w1


def test_oc_size_string_and_number(prematch_event: Match) -> None:
    handicap = next(o for o in prematch_event.iter_outcomes() if o.size == "-3.5")
    assert isinstance(handicap.size, str)
    assert handicap.size_value == -3.5


def test_player_specific_outcomes(prematch_event: Match) -> None:
    scorers = prematch_event.market("Who Will Score Goal")
    assert scorers is not None
    assert any(o.player_id is not None for o in scorers.outcomes)


def test_duplicate_market_names(prematch_event: Match) -> None:
    fouls = prematch_event.find_markets("Fouls")
    assert len(fouls) == 2
    assert prematch_event.market("Fouls") is fouls[0]
    with pytest.raises(ValueError):
        prematch_event.market()


def test_stats_and_sub_games(live_event: Match) -> None:
    attacks = live_event.stat(45)
    assert attacks is not None and (attacks.opp1, attacks.opp2) == ("61", "54")
    assert live_event.stat(9999) is None
    corners = next(s for s in live_event.sub_games if s.name == "Corners")
    assert corners.game_id == 746147010
    assert live_event.has_tracker and not live_event.has_video
    assert not live_event.is_sub_game


def test_start_time_and_icons(live_event: Match) -> None:
    assert live_event.start_time == datetime.fromtimestamp(1787338800, tz=timezone.utc)
    assert live_event.opp_1_icon_url is not None
    assert live_event.opp_1_icon_url.endswith(".webp")
    assert ".png" not in live_event.opp_1_icon_url


def test_blocked_outcomes_are_excluded_from_best() -> None:
    market = Market.from_dict(
        {
            "group_id": 1,
            "group_name": "1X2",
            "columns": 3,
            "oc_list": [
                {"oc_name": "W1", "oc_rate": 9.0, "oc_pointer": "1|1|1|0", "oc_block": True},
                {"oc_name": "X", "oc_rate": 3.2, "oc_pointer": "1|1|2|0", "oc_block": False},
            ],
        }
    )
    best = market.best()
    assert best is not None and best.name == "X"
    assert market.outcome("W1", include_blocked=False) is None
    assert [o.name for o in market.available_outcomes()] == ["X"]


def test_outcome_tolerates_missing_fields() -> None:
    outcome = Outcome.from_dict({"oc_name": "W1"})
    assert outcome.odds == 0.0 and outcome.size is None and outcome.size_value is None


def test_menu_tree_and_country_id_spelling() -> None:
    sports = [Sport.from_dict(s) for s in example("menu.line.en.json")["body"]]
    tournament = next(sports[0].iter_tournaments())
    assert tournament.country_id == tournament.raw["countryId"]
    assert tournament.sport_id == sports[0].id
    assert Tournament.from_dict({"id": 5, "name": ""}).name == ""


def test_account_parsing() -> None:
    body = {
        "client": {"public_id": "f47ad380-39e2-4549-ac76-aa422df628ea", "name": "Example"},
        "your_ip": "203.0.113.7",
        "keys": [
            {
                "key": "…c55f",
                "current": True,
                "type": "test",
                "status": "active",
                "label": "demo 12 days",
                "starts_at": None,
                "expires_at": "2026-11-03T14:34:23.479Z",
                "days_left": 30,
                "active": True,
                "sports": "all",
                "languages": ["en"],
                "last_used_at": "2026-10-04T15:20:07.843Z",
                "access_mode": "enforce",
                "allowed_ips": ["203.0.113.7", "198.51.100.0/24"],
                "allowed_domains": ["example.com", "*.example.com"],
                "usage_7d": [{"date": "2026-10-04", "requests": 7}],
            },
            {"key": "…a1b2", "current": False, "sports": [1, 3], "expires_at": None},
        ],
    }
    account = Account.from_dict(body)
    assert account.client_name == "Example" and account.your_ip == "203.0.113.7"
    key = account.current_key
    assert key is not None and key.sports == "all"
    assert key.expires == datetime(2026, 11, 3, 14, 34, 23, 479000, tzinfo=timezone.utc)
    assert key.starts is None
    assert key.usage_7d[0].requests == 7
    assert account.keys[1].sports == [1, 3]
    assert account.keys[1].expires is None


def test_media_urls() -> None:
    assert sport_icon_url(1) == "https://cdn.sportapi.net/sports/v1/color/1.webp"
    assert country_flag_url(218) == "https://cdn.sportapi.net/flags/v1/color/218.webp"
    assert tournament_icon_url(118737) == (
        "https://cdn.sportapi.net/tournaments/v1/color/118737.webp"
    )
    assert team_icon_url("8bd073a686a067e6732d8d1688a517c0.png") == (
        "https://cdn.sportapi.net/opp/v1/color/8bd073a686a067e6732d8d1688a517c0.webp"
    )
    with pytest.raises(ValueError):
        team_icon_url(".png")
