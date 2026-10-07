"""README code samples that need no credentials must keep working in demo mode."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCKS = re.findall(r"```python\n(.*?)```", README.read_text(encoding="utf-8"), re.S)


def runnable(block: str) -> bool:
    # Skip samples that need live credentials or poll forever.
    return "account()" not in block and "watch_event(" not in block


@pytest.mark.filterwarnings("ignore::sportapi.SportAPIDemoWarning")
@pytest.mark.parametrize("block", [b for b in BLOCKS if runnable(b)])
def test_readme_sample_runs(block: str, capsys: pytest.CaptureFixture[str]) -> None:
    namespace: dict = {}
    exec("from sportapi import SportAPI\napi = SportAPI()\n" + block, namespace)


def test_readme_has_runnable_samples() -> None:
    assert len([b for b in BLOCKS if runnable(b)]) >= 3
