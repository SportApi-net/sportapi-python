# sportapi-python

Official Python client for the [SportAPI](https://sportapi.net) Sport Line API — Prematch and Live sports odds, scores and live statistics, with typed models and a demo mode that works without an API key.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/SportApi-net/sportapi-python/blob/main/LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Typed](https://img.shields.io/badge/typing-typed-informational.svg)](https://peps.python.org/pep-0561/)

```python
from sportapi import SportAPI

api = SportAPI()                                  # no key yet? demo data
match = api.event(746146992, "live")
print(match.name, match.score_full)               # Arsenal — Coventry City 3:0
print(match.outcome("Total", "Over 3.5").odds)    # 1.23
```

> The library is free and MIT-licensed. The SportAPI data service it talks to is a commercial
> product: live data needs a personal API key ([how to get one](#get-an-api-key)).

## Features

- **Every documented Sport Line endpoint**: `menu`, `events`, the match calendar, `event`, `search`,
  plus the optional `sports`, `countries`, `tournaments`, `topmatches`, `toplist`,
  `topchampionships` and `account`.
- **Typed models** (`dataclasses`, `py.typed`) for sports, countries, tournaments, matches, markets,
  outcomes, live statistics, sub-events and account keys. The original JSON is kept in `.raw`.
- **Demo mode**: without credentials the client serves the full example responses published in the
  SportAPI documentation, so you can build and test before you have a key.
- **Documented errors as exceptions**: `InvalidKeyError`, `KeyExpiredError`,
  `LanguageNotAvailableError`, `GameFinishedError`… mapped from `error_code` / `error_message`
  and from `event` service messages, not just from HTTP status codes.
- **Odds helpers**: find markets and outcomes by name or `group_id`, decimal odds, blocked
  selections, `oc_pointer` lookups, the API's column layout preserved.
- **Polite polling**: `watch_events()` / `watch_event()` and `poll()` follow the documented
  minimum intervals and back off 5 → 10 → 20 → 40 s on temporary failures only.
- Sync **and** async clients (`SportAPI`, `AsyncSportAPI`) on top of [httpx](https://www.python-httpx.org/).
  Python 3.9+.

## Install

```bash
pip install sportapi
```

## Quick start (60 seconds, no key needed)

With no `SPORTAPI_KEY` / `SPORTAPI_BASE_URL` set, the client runs in demo mode and emits one
`SportAPIDemoWarning`, so demo data is never mistaken for live data.

```python
from sportapi import LIVE, SportAPI

with SportAPI() as api:
    # 1. Navigation: sports -> countries -> tournaments that have matches right now
    for sport in api.menu(LIVE)[:3]:
        print(sport.name, sport.counter)

    # 2. Live football matches, grouped by tournament, with a short list of main markets
    for group in api.events(1, LIVE):
        for match in group.matches:
            print(f"{match.timer // 60:>3}' {match.score_full}  {match.name}")

    # 3. One match with every market, live statistics and sub-events
    match = api.event(746146992, LIVE)
    total = match.market("Total")
    for over, under in zip(*total.column_outcomes):   # columns as arranged by the API
        print(over.name, over.odds, "|", under.name, under.odds)
    print(match.stat(29))                             # Stat(id=29, name='Possession %', ...)
```

Demo mode answers exactly the requests that have a published example response (all in English):

| Call | Example data |
|---|---|
| `menu("live")`, `menu("line")` | full menu snapshots |
| `sports(...)`, `countries(1, ...)`, `tournaments(1, 1, ...)` | navigation snapshots |
| `events(1, "live")`, `events(1, "line")` | Live football (39 matches), Prematch "Top" (50 matches) |
| `event(746146992, "live")`, `event(730321837, "line")` | Arsenal — Coventry City (Live), Manchester City — Bournemouth (Prematch) |
| `search("Perth", "live")`, `search("Manchester", "line")` | search results |
| `topmatches(...)`, `toplist(1)` with or without `full=True` | top selections |

`odds=False` is emulated on top of these files. Any other call raises
`DemoDataUnavailableError` with the list of available calls and how to switch to live data.

## Live data

You get a **personal base URL** and an **API key** from the SportAPI manager. Set them as
environment variables (or pass them to the constructor):

```bash
export SPORTAPI_BASE_URL="https://YOUR_API_DOMAIN"
export SPORTAPI_KEY="your-api-key"
```

```python
from sportapi import SportAPI

api = SportAPI()                     # reads SPORTAPI_KEY and SPORTAPI_BASE_URL
# or: SportAPI(api_key="...", base_url="https://YOUR_API_DOMAIN", lang="en")

print(api.account().current_key.days_left)
print(api.key_expires)               # from the X-Key-Expires header of the last response
```

- The key is sent only in the `Package` HTTP header — never in the URL — and is hidden from
  `repr()` and exception messages. Keep it in environment variables or a secrets manager,
  and call the API from your backend, not from a browser.
- Setting only one of the two variables raises `ConfigurationError`; `SportAPI(demo=False)`
  refuses to fall back to demo data.
- `lang` is any language enabled for your key. The API supports 69 languages with
  SportAPI-specific codes (for example `ua`, `cn`, `br`); see
  [Languages](https://sportapi.net/docs/sport-line/reference/languages.html).

Step-by-step setup: [Authentication and access](https://sportapi.net/docs/sport-line/getting-started/authentication-and-access.html).

## API coverage

| Client method | Endpoint | Documentation |
|---|---|---|
| `menu(line_type, cybersport=)` | `GET /v1/menu/{type}/{lang}` | [menu](https://sportapi.net/docs/sport-line/api-reference/menu.html) |
| `events(sport_id, line_type, tournament_id=0, full_line=, odds=, cybersport=)` | `GET /v1/events/{sportId}/{tournamentId}/sub/50/{type}/{lang}` | [events](https://sportapi.net/docs/sport-line/api-reference/events.html) |
| `events_by_period(sport_id, hours=, days=, tournament_id=, odds=)` | `GET /v1/events/{sportId}/{tournamentId}/sub/50/line/{hours}/{days}/{lang}` | [match calendar](https://sportapi.net/docs/sport-line/api-reference/events-by-period.html) |
| `event(game_id, line_type, odds=)` | `GET /v1/event/{gameId}/group/{type}/{lang}` | [event](https://sportapi.net/docs/sport-line/api-reference/event.html) |
| `search(text, line_type)` | `GET /v1/search/{type}/{lang}/{text}` | [search](https://sportapi.net/docs/sport-line/api-reference/search.html) |
| `sports(line_type, cybersport=)` | `GET /v1/sports/{type}/{lang}` | [sports](https://sportapi.net/docs/sport-line/api-reference/optional-methods/sports.html) |
| `countries(sport_id, line_type)` | `GET /v1/countries/{sportId}/{type}/{lang}` | [countries](https://sportapi.net/docs/sport-line/api-reference/optional-methods/countries.html) |
| `tournaments(sport_id, country_id, line_type, cybersport=)` | `GET /v1/tournaments/{sportId}/{countryId}/{type}/{lang}` | [tournaments](https://sportapi.net/docs/sport-line/api-reference/optional-methods/tournaments.html) |
| `topmatches(line_type, full=, odds=)` | `GET /v1/topmatches/{type}/{lang}` | [topmatches](https://sportapi.net/docs/sport-line/api-reference/optional-methods/topmatches.html) |
| `toplist(sport_id, full=, odds=)` | `GET /v1/toplist/{sportId}/{lang}` | [toplist](https://sportapi.net/docs/sport-line/api-reference/optional-methods/toplist.html) |
| `topchampionships(line_type)` | `GET /v1/topchampionships/{type}/{lang}` | [topchampionships](https://sportapi.net/docs/sport-line/api-reference/optional-methods/topchampionships.html) |
| `account()` | `GET /v1/account` | [account](https://sportapi.net/docs/sport-line/api-reference/optional-methods/account.html) |

`line_type` is `"live"` or `"line"` (Prematch); the constants `LIVE`, `LINE` and `PREMATCH` are
exported. `lang` defaults to the client's `lang` (`"en"`). `AsyncSportAPI` has the same methods
as coroutines.

Helpers: `iter_live_matches()`, `watch_events()`, `watch_event()`, `iter_matches()`,
`poll()` / `apoll()`, `recommended_interval()`, and icon URLs in `sportapi.media`
([media assets](https://sportapi.net/docs/sport-line/reference/media-assets.html)).

## Working with odds

```python
match = api.event(730321837, "line")

w1 = match.outcome("1X2", "W1")          # case-insensitive market and outcome names
w1.odds, w1.odds_decimal                 # 1.525, Decimal('1.525')
w1.blocked                               # oc_block: True means unavailable
w1.pointer                               # oc_pointer: '730321837|1|1|0'

match.market(id=17)                      # by group_id (names are localised)
match.find_markets("Fouls")              # several markets can share a name
match.outcome_by_pointer(w1.pointer)     # track a selection across refreshes
[o.size_value for o in match.market("Total").outcomes]   # oc_size as float (str or int in JSON)
```

- `events` returns a **short** market list per match (`Market.column_outcomes is None`);
  `event` returns **all** markets with columns already arranged and sorted by the API.
- Market sets differ by sport: don't assume `1X2` or a draw exists (tennis has none).
- `oc_pointer` identifies a selection for bet placement with the
  [SportAPI Coupon API](https://sportapi.net/sport-events-api.html); see
  [Bet pointer](https://sportapi.net/docs/coupon/bet-placement/bet-pointer.html).

Data models: [match](https://sportapi.net/docs/sport-line/data-models/match.html) ·
[odds](https://sportapi.net/docs/sport-line/data-models/odds.html) ·
[live statistics](https://sportapi.net/docs/sport-line/data-models/live-statistics.html) ·
[sub-events](https://sportapi.net/docs/sport-line/data-models/sub-events.html) ·
[field reference](https://sportapi.net/docs/sport-line/data-models/field-reference.html).

## Polling and update intervals

The API is REST: each response is a snapshot. The documented minimum intervals are built in:

| Data | Live | Prematch |
|---|---:|---:|
| `menu` | 20 s | 60 s |
| `sports`, `countries`, `tournaments` | 60 s | 120 s |
| `events` | 7 s | 30 s |
| `event` | 5 s | 30 s |
| `topmatches` | 30 s | 120 s |
| `toplist` | — | 120 s |
| `topchampionships` | 60 s | 300 s |
| match calendar | — | 60 s |

```python
from sportapi import LIVE, GameFinishedError, SportAPI

api = SportAPI()
try:
    for match in api.watch_event(746146992, LIVE):     # every 5 s, never overlapping
        print(match.score_full, match.timer // 60)
except GameFinishedError:
    print("No longer in the line under this game_id: refresh the match list")
```

`watch_*` refuses intervals below the documented minimum. Temporary failures (network, HTTP 5xx)
back off 5 → 10 → 20 → 40 s; key, language, sport and parameter errors are raised, not retried.
Update a displayed match clock locally from `timer` instead of polling every second.
Details: [Data update guidelines](https://sportapi.net/docs/sport-line/getting-started/update-guidelines.html).

## Errors

```text
SportAPIError
├── ConfigurationError, DemoDataUnavailableError
├── TransportError                       network error or timeout (retryable)
├── UnexpectedResponseError
│   └── HTTPStatusError                  HTTP 4xx/5xx without error_code (5xx retryable)
├── APIError                             error_code + error_message
│   ├── AuthenticationError              MissingKeyError, InvalidKeyError, KeyExpiredError,
│   │                                    KeyBlockedError, KeyNotActiveError, AccessRestrictedError
│   ├── PermissionDeniedError            AccessDeniedError, LanguageNotAvailableError
│   └── InvalidRequestError              InvalidLanguageError, InvalidLineTypeError
└── EventUnavailableError                GameNotFoundError, GameFinishedError
```

An empty list is not an error: nothing is available for that request right now.
See [Error handling](https://sportapi.net/docs/sport-line/getting-started/error-handling.html).

## Examples

All examples run in demo mode out of the box:

| Script | What it shows |
|---|---|
| [`examples/live_board.py`](https://github.com/SportApi-net/sportapi-python/blob/main/examples/live_board.py) | Live scoreboard with clock and main odds; `--watch` refreshes at the documented interval |
| [`examples/match_odds.py`](https://github.com/SportApi-net/sportapi-python/blob/main/examples/match_odds.py) | Every market of one match in columns, blocked selections, live stats, sub-events |
| [`examples/search_matches.py`](https://github.com/SportApi-net/sportapi-python/blob/main/examples/search_matches.py) | Search by team name, then open the first match's main markets |
| [`examples/menu_tree.py`](https://github.com/SportApi-net/sportapi-python/blob/main/examples/menu_tree.py) | Sports → countries → tournaments with counters and icon URLs |

```bash
python examples/live_board.py
python examples/match_odds.py 730321837 --line
```

## Documentation

- [Quick start](https://sportapi.net/docs/sport-line/getting-started/quick-start.html) ·
  [Core concepts](https://sportapi.net/docs/sport-line/getting-started/core-concepts.html) ·
  [Integration guide](https://sportapi.net/docs/sport-line/integration-guide.html)
- [API methods overview](https://sportapi.net/docs/sport-line/api-reference/overview.html) ·
  [Full JSON responses](https://sportapi.net/docs/sport-line/examples/json-responses/overview.html) ·
  [Sports and `sport_id` values](https://sportapi.net/docs/sport-line/reference/sports.html)
- [SportAPI documentation](https://sportapi.net/docs.html) — Sport Line API, Coupon API and more

## Get an API key

Live data requires a personal base URL and API key. Plans start from $30/month, and there is a
free 2-day trial.

- Request access from the SportAPI manager on Telegram:
  [@sportapinet_bot](https://t.me/sportapinet_bot?start=github_sportapi_python)
- Product page: [Sport Line API on sportapi.net](https://sportapi.net/sport-line-api.html)
- Related: [bet placement and settlement](https://sportapi.net/sport-events-api.html),
  [results](https://sportapi.net/sport-rezult-api.html)

## Contributing

Issues and pull requests are welcome — see [CONTRIBUTING.md](https://github.com/SportApi-net/sportapi-python/blob/main/CONTRIBUTING.md). Please never
include an API key in an issue, log or test fixture.

## License

[MIT](https://github.com/SportApi-net/sportapi-python/blob/main/LICENSE) © 2026 SportAPI
