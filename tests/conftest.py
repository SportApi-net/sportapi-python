from __future__ import annotations

import json
from collections.abc import Iterator
from importlib import resources
from typing import Any

import pytest

from sportapi import _demo

BASE_URL = "https://api.example.test"
API_KEY = "test-key-0000"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Each test starts without credentials and with the demo warning not yet shown."""
    monkeypatch.delenv("SPORTAPI_KEY", raising=False)
    monkeypatch.delenv("SPORTAPI_BASE_URL", raising=False)
    monkeypatch.setattr(_demo, "_warned", False)
    yield


def example(filename: str) -> Any:
    """Load one of the documentation JSON responses bundled with the package."""
    text = (resources.files("sportapi") / "_demo_data" / filename).read_text(encoding="utf-8")
    return json.loads(text)
