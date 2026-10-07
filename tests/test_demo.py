from __future__ import annotations

import warnings

import pytest

from sportapi import (
    LINE,
    LIVE,
    DemoDataUnavailableError,
    Match,
    SportAPI,
    SportAPIDemoWarning,
    iter_matches,
)


@pytest.fixture
def api() -> SportAPI:
    return SportAPI()


def test_warns_once_per_process(api: SportAPI) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        api.sports(LIVE)
        api.sports(LINE)
        SportAPI().menu(LIVE)
    demo_warnings = [w for w in caught if issubclass(w.category, SportAPIDemoWarning)]
    assert len(demo_warnings) == 1
    message = str(demo_warnings[0].message)
    assert "not live data" in message
    assert "t.me/sportapinet_bot?start=github_sportapi_python" in message


def test_warning_points_at_caller(api: SportAPI) -> None:
    with pytest.warns(SportAPIDemoWarning) as record:
        api.sports(LIVE)
    assert record[0].filename == __file__


@pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")
class TestBundledResponses:
    def test_menu(self, api: SportAPI) -> None:
        live = api.menu(LIVE)
        assert len(live) == 31
        football = next(s for s in live if s.id == 1)
        assert football.name == "Football"
        assert football.countries and football.countries[0].tournaments
        assert sum(c.counter for c in football.countries) == football.counter
        assert len(api.menu(LINE)) == 34

    def test_sports_countries_tournaments(self, api: SportAPI) -> None:
        assert len(api.sports(LIVE)) == 22
        assert len(api.sports(LINE)) == 32
        assert len(api.countries(1, LIVE)) == 15
        assert len(api.countries(1, LINE)) == 99
        tournaments = api.tournaments(1, 1, LINE)
        assert tournaments and all(t.country_id == 1 for t in tournaments)

    def test_events(self, api: SportAPI) -> None:
        live = api.events(1, LIVE)
        assert len(live) == 33
        assert len(list(iter_matches(live))) == 39
        prematch = api.events(1, LINE)
        assert len(list(iter_matches(prematch))) == 50

    def test_events_without_odds_drops_markets(self, api: SportAPI) -> None:
        matches = list(iter_matches(api.events(1, LIVE, odds=False)))
        assert all(m.markets == [] for m in matches)
        assert all("game_oc_list" not in m.raw for m in matches)
        assert all(m.game_oc_counter is not None for m in matches)

    def test_event_live_and_prematch(self, api: SportAPI) -> None:
        live = api.event(746146992, LIVE)
        assert live.name == "Arsenal — Coventry City"
        assert len(live.markets) == 49
        assert len(live.sub_games) == 13
        assert len(live.stats) == 15
        assert live.zp == 746146992
        prematch = api.event(730321837, LINE)
        assert len(prematch.markets) == 204
        assert sum(1 for _ in prematch.iter_outcomes()) == 1294
        assert prematch.game_oc_counter == 1337

    def test_event_odds_false(self, api: SportAPI) -> None:
        match = api.event(746146992, LIVE, odds=False)
        assert match.markets == []
        assert match.stats  # everything else is kept

    @pytest.mark.parametrize(
        ("text", "line_type", "count"),
        [
            ("Perth", LIVE, 10),
            (" perth ", LIVE, 10),
            ("MANCHESTER", LINE, 17),
        ],
    )
    def test_search(self, api: SportAPI, text: str, line_type: str, count: int) -> None:
        results = api.search(text, line_type)
        assert len(results) == count
        assert all(isinstance(r, Match) and r.markets == [] for r in results)

    def test_top_selections(self, api: SportAPI) -> None:
        assert len(api.topmatches(LIVE)) == 10
        assert len(api.topmatches(LINE, full=True)) == 10
        short = api.toplist(1)
        assert short[0].country_id is None  # short summary has no country
        full = api.toplist(1, full=True)
        assert full[0].country_id is not None
        assert any(m.markets for m in full)
        assert all(m.markets == [] for m in api.toplist(1, full=True, odds=False))


@pytest.mark.parametrize(
    "call",
    [
        lambda api: api.event(1, LIVE),
        lambda api: api.event(746146992, LINE),  # right id, wrong line type
        lambda api: api.search("Arsenal", LIVE),
        lambda api: api.countries(2, LIVE),
        lambda api: api.events(1, LIVE, tournament_id=88637),
        lambda api: api.events(1, LINE, full_line=True),
        lambda api: api.menu(LIVE, cybersport=True),
        lambda api: api.menu(LIVE, lang="de"),
        lambda api: api.events_by_period(1, hours=2),
        lambda api: api.topchampionships(LINE),
        lambda api: api.account(),
    ],
)
def test_unavailable_demo_calls_explain_how_to_get_a_key(api: SportAPI, call) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(DemoDataUnavailableError) as info:
        call(api)
    message = str(info.value)
    assert "SPORTAPI_KEY" in message and "SPORTAPI_BASE_URL" in message
    assert "https://t.me/sportapinet_bot?start=github_sportapi_python" in message
    assert "event(746146992" in message  # lists what *is* available


@pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")
def test_iter_live_matches_visits_only_bundled_sports(api: SportAPI) -> None:
    matches = list(api.iter_live_matches())
    assert len(matches) == 39
    assert {m.sport_id for m in matches} == {1}


@pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")
def test_each_call_returns_fresh_objects(api: SportAPI) -> None:
    first = api.event(746146992, LIVE)
    first.raw["opp_1_name"] = "changed"
    assert api.event(746146992, LIVE).opp_1_name == "Arsenal"
