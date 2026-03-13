"""Shared pytest fixtures for jskim tests."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Return the path to the test fixtures directory."""
    return FIXTURES_DIR


def load_fixture(name):
    """Load a Java fixture file by name and return its content as a string."""
    path = FIXTURES_DIR / name
    return path.read_text(encoding="utf-8")


def fixture_path(name):
    """Return the full path to a fixture file."""
    return FIXTURES_DIR / name
