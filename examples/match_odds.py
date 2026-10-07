"""All odds of one match: markets in columns, blocked selections, live stats, sub-events.

    python examples/match_odds.py                       # demo Live match 746146992
    python examples/match_odds.py 730321837 --line      # demo Prematch match
    python examples/match_odds.py 746146992 --markets 0 # every market

Runs on bundled demo data until SPORTAPI_KEY and SPORTAPI_BASE_URL are set.
"""

from __future__ import annotations

import argparse
import warnings

from sportapi import LINE, LIVE, GameFinishedError, Market, SportAPI, SportAPIDemoWarning

warnings.simplefilter("ignore", SportAPIDemoWarning)


def print_market(market: Market) -> None:
    print(f"\n{market.name}  (group_id={market.id})")
    # In the `event` response the API already arranged selections into columns
    # and sorted them; keep that order.
    columns = market.column_outcomes or [market.outcomes]
    for row in range(max(len(c) for c in columns) if columns else 0):
        cells = []
        for column in columns:
            if row < len(column):
                o = column[row]
                price = "blocked" if o.blocked else f"{o.odds:.3f}"
                cells.append(f"{o.name[:24]:<24} {price:>7}")
            else:
                cells.append(" " * 32)
        print("  " + " | ".join(cells))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("game_id", type=int, nargs="?", default=746146992)
    parser.add_argument("--line", action="store_true", help="Prematch match (default: Live)")
    parser.add_argument("--markets", type=int, default=6, help="markets to show (0 = all)")
    args = parser.parse_args()
    line_type = LINE if args.line else LIVE

    with SportAPI() as api:
        if api.is_demo:
            print("[demo data: example responses from the SportAPI docs, not live]\n")
        try:
            match = api.event(args.game_id, line_type)
        except GameFinishedError:
            print("This game_id is no longer in the line; refresh the match list.")
            return

    start = match.start_time.strftime("%Y-%m-%d %H:%M UTC") if match.start_time else "?"
    print(f"{match.name}  {match.score_full}")
    print(f"{match.sport_name} / {match.tournament_name} / start {start}")
    if match.period_name:
        print(f"{match.period_name}, {match.timer // 60}'  periods: {match.score_period}")
    print(
        f"{len(match.markets)} markets, {sum(1 for _ in match.iter_outcomes())} selections "
        f"(game_oc_counter={match.game_oc_counter})"
    )

    if match.stats:
        print("\nLive statistics")
        for stat in match.stats:
            print(f"  {stat.opp1:>6}  {stat.name:<22} {stat.opp2}")

    shown = match.markets if args.markets == 0 else match.markets[: args.markets]
    for market in shown:
        print_market(market)

    over = match.outcome("Total", "Over 2.5")
    if over is not None:
        print(f"\nTotal Over 2.5 -> {over.odds_decimal} (oc_pointer {over.pointer})")

    if match.sub_games:
        print("\nSub-events (request with api.event(sub.game_id, line_type)):")
        for sub in match.sub_games:
            print(f"  {sub.game_id}  {sub.name}")
    if match.has_tracker:
        print(f"\nLive 3D Tracker available: gameid={match.zp}")


if __name__ == "__main__":
    main()
