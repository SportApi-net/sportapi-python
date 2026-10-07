# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-07

### Added

- `SportAPI` (sync) and `AsyncSportAPI` (async) clients for every documented Sport Line API
  method: `menu`, `events`, `events_by_period` (match calendar), `event`, `search`, `sports`,
  `countries`, `tournaments`, `topmatches`, `toplist`, `topchampionships`, `account`.
- Typed models: `Sport`, `Country`, `Tournament`, `TournamentEvents`, `Match`, `Market`, `Outcome`,
  `Stat`, `SubGame`, `EventPlanEntry`, `TopChampionship`, `Account`, `AccountKey`.
- Odds helpers: market/outcome lookup by name or `group_id`, `oc_pointer` lookup, decimal odds,
  blocked selections, `oc_size` as a number.
- Demo mode on the English example responses from the SportAPI documentation, with a one-time
  `SportAPIDemoWarning` and `DemoDataUnavailableError` for requests without bundled data.
- Exceptions for every documented error message and for `event` service messages
  (`Game not found`, `Game id finished`).
- Polling helpers (`poll`, `apoll`, `watch_events`, `watch_event`) with the documented minimum
  intervals and 5 → 10 → 20 → 40 s back-off for temporary failures.
- `X-Key-Expires` tracking (`client.key_expires`) and icon URL helpers (`sportapi.media`).
- Runnable examples: live board, match odds, search, menu tree.

[0.1.0]: https://github.com/SportApi-net/sportapi-python/releases/tag/v0.1.0
