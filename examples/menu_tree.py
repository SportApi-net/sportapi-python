"""Navigation tree: sports -> countries -> tournaments with match counters.

    python examples/menu_tree.py                  # Live menu
    python examples/menu_tree.py --line --top 3   # Prematch, 3 biggest sports

Runs on bundled demo data until SPORTAPI_KEY and SPORTAPI_BASE_URL are set.
"""

from __future__ import annotations

import argparse
import warnings

from sportapi import LINE, LIVE, SportAPI, SportAPIDemoWarning

warnings.simplefilter("ignore", SportAPIDemoWarning)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--line", action="store_true", help="Prematch menu (default: Live)")
    parser.add_argument("--top", type=int, default=5, help="sports to expand")
    parser.add_argument("--countries", type=int, default=3, help="countries per sport")
    args = parser.parse_args()
    line_type = LINE if args.line else LIVE

    with SportAPI() as api:
        if api.is_demo:
            print("[demo data: example responses from the SportAPI docs, not live]\n")
        sports = api.menu(line_type)

    total = sum(s.counter for s in sports)
    print(f"{line_type}: {len(sports)} sports, {total} matches\n")
    for sport in sorted(sports, key=lambda s: s.counter, reverse=True)[: args.top]:
        print(f"{sport.name} ({sport.counter})  id={sport.id}  {sport.icon_url}")
        countries = sorted(sport.countries, key=lambda c: c.counter, reverse=True)
        for country in countries[: args.countries]:
            print(f"  {country.name} ({country.counter})")
            for tournament in country.tournaments:
                # Tournament names can be empty; never invent one.
                label = tournament.name or f"tournament {tournament.id}"
                print(f"    {label} ({tournament.counter})  tournament_id={tournament.id}")
        print()
    print("Next: api.events(sport_id, line_type, tournament_id=...) for the matches.")


if __name__ == "__main__":
    main()
