"""Search matches by team name, then open the first result's main odds.

    python examples/search_matches.py                        # "Manchester", Prematch
    python examples/search_matches.py Perth --live

Runs on bundled demo data until SPORTAPI_KEY and SPORTAPI_BASE_URL are set
(the demo data contains the searches "Manchester" (Prematch) and "Perth" (Live)).
"""

from __future__ import annotations

import argparse
import warnings

from sportapi import (
    LINE,
    LIVE,
    DemoDataUnavailableError,
    SportAPI,
    SportAPIDemoWarning,
)

warnings.simplefilter("ignore", SportAPIDemoWarning)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("text", nargs="?", default="Manchester")
    parser.add_argument("--live", action="store_true", help="search Live (default: Prematch)")
    args = parser.parse_args()
    line_type = LIVE if args.live else LINE

    with SportAPI() as api:
        if api.is_demo:
            print("[demo data: example responses from the SportAPI docs, not live]\n")
        results = api.search(args.text, line_type)
        if not results:
            print("No matches found")
            return

        for match in results:
            when = match.start_time.strftime("%d %b %H:%M") if match.start_time else ""
            print(f"{match.game_id}  {when:>12}  {match.name}  ({match.tournament_name})")

        first = results[0]
        print(f"\nOpening {first.name} ...")
        try:
            details = api.event(first.game_id, line_type)
        except DemoDataUnavailableError:
            print("(no bundled demo response for this match)")
            return

    for market_name in ("1X2", "Double Chance", "Both Teams To Score"):
        market = details.market(market_name)
        if market is None:
            continue
        prices = ", ".join(f"{o.name} {o.odds}" for o in market.available_outcomes())
        print(f"  {market.name}: {prices}")


if __name__ == "__main__":
    main()
