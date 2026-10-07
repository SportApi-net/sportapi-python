"""Live matches board: scores, match clock and main odds for one sport.

    python examples/live_board.py               # football, one snapshot
    python examples/live_board.py --watch       # refresh every 7 s (documented minimum)

Runs on bundled demo data until SPORTAPI_KEY and SPORTAPI_BASE_URL are set.
"""

from __future__ import annotations

import argparse
import contextlib
import warnings
from typing import List

from sportapi import LIVE, Match, SportAPI, SportAPIDemoWarning, TournamentEvents

warnings.simplefilter("ignore", SportAPIDemoWarning)  # we print our own banner


def format_clock(match: Match) -> str:
    """The API gives elapsed seconds; show minutes (update locally between polls)."""
    if not match.timer:
        return match.period_name or "--"
    minute = f"{match.timer // 60}'"
    return f"{minute} {match.period_name}".strip()


def main_market(match: Match) -> str:
    """The first market of the short list (1X2 in football, winner in tennis…)."""
    if not match.markets:
        return ""
    market = match.markets[0]
    prices = "  ".join(
        f"{o.name} {'--' if o.blocked else f'{o.odds:.2f}'}" for o in market.outcomes
    )
    return f"{market.name}: {prices}"


def render(groups: List[TournamentEvents]) -> None:
    total = sum(len(g.matches) for g in groups)
    print(f"{total} live matches in {len(groups)} tournaments\n")
    for group in groups:
        print(group.tournament_name or f"Tournament {group.tournament_id}")
        for match in group.matches:
            print(
                f"  {format_clock(match):>14}  {match.score_full:>5}  "
                f"{match.opp_1_name} - {match.opp_2_name}"
            )
            odds = main_market(match)
            if odds:
                print(f"  {'':>14}  {'':>5}  {odds}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sport", type=int, default=1, help="sport_id (1 = football)")
    parser.add_argument("--watch", action="store_true", help="keep refreshing")
    args = parser.parse_args()

    with SportAPI() as api:
        if api.is_demo:
            print("[demo data: example responses from the SportAPI docs, not live]\n")
        if not args.watch:
            render(api.events(args.sport, LIVE))
            return
        # watch_events() uses the documented minimum interval and backs off on
        # temporary errors; key or parameter errors are raised.
        for groups in api.watch_events(args.sport, LIVE):
            print("\033[2J\033[H", end="")  # clear the terminal
            render(groups)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        main()
