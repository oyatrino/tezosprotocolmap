"""Shared fixtures for the test suite."""

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def naming_html():
    """Minimal HTML with protocol list items."""
    return (FIXTURES / "naming_page.html").read_text(encoding="utf-8")


@pytest.fixture()
def sample_gpx_text():
    """GPX text with 4 sample waypoints."""
    return (FIXTURES / "tezos_sample.gpx").read_text(encoding="utf-8")


@pytest.fixture()
def sample_gpx_path():
    """Path to the sample GPX fixture."""
    return str(FIXTURES / "tezos_sample.gpx")
