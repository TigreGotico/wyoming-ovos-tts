"""Shared fixtures for wyoming-ovos-tts tests."""

from __future__ import annotations

from pathlib import Path

import pytest

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return _FIXTURES
