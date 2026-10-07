"""The scripts in examples/ must run in demo mode without credentials."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@pytest.mark.parametrize(
    ("script", "args", "expected"),
    [
        ("live_board.py", [], "live matches in"),
        ("match_odds.py", [], "Arsenal"),
        ("match_odds.py", ["730321837", "--line", "--markets", "1"], "Manchester City"),
        ("search_matches.py", [], "1X2: W1 1.525"),
        ("search_matches.py", ["Perth", "--live"], "Perth RedStar"),
        ("menu_tree.py", ["--line", "--top", "2"], "tournament_id="),
    ],
)
def test_example_runs_in_demo_mode(script: str, args: list, expected: str) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith("SPORTAPI_")}
    result = subprocess.run(
        [sys.executable, str(EXAMPLES / script), *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "[demo data" in result.stdout
    assert expected in result.stdout
