"""Tests for scripts/generate_map.py pure functions."""

from scripts.generate_map import match_protocols, short_label


# ---------- short_label ----------

def test_short_label_strips_country():
    assert short_label("Athens, Greece") == "Athens"


def test_short_label_edo():
    assert short_label("Edo (Tokyo), Japan") == "Edo"


def test_short_label_quebec():
    assert short_label("Quebec City, Canada") == "Quebec"


def test_short_label_rio():
    assert short_label("Rio de Janeiro, Brazil") == "Rio"


def test_short_label_no_country():
    assert short_label("Athens") == "Athens"


def test_short_label_multi_part():
    assert short_label("Lima, Peru") == "Lima"


# ---------- match_protocols ----------

def test_match_protocols_basic():
    waypoints = [
        ("Athens, Greece", 37.9838, 23.7275),
        ("Babylon, Iraq", 32.5439, 44.4208),
    ]
    protocols = {
        "Athens": {"number": 4, "hash": "PtAthens", "mainnet": True},
        "Babylon": {"number": 5, "hash": "PsBabylon", "mainnet": True},
    }
    matched = match_protocols(waypoints, protocols)
    assert "Athens" in matched
    assert "Babylon" in matched
    assert matched["Athens"]["number"] == 4


def test_match_protocols_parisc_alias():
    waypoints = [("Paris, France", 48.8566, 2.3522)]
    protocols = {
        "ParisC": {"number": 20, "hash": "PsParis", "mainnet": True},
    }
    matched = match_protocols(waypoints, protocols)
    assert "Paris" in matched
    assert matched["Paris"]["number"] == 20


def test_match_protocols_unmatched_waypoint():
    waypoints = [("Unknown City, Nowhere", 0.0, 0.0)]
    protocols = {"Athens": {"number": 4}}
    matched = match_protocols(waypoints, protocols)
    assert len(matched) == 0


def test_match_protocols_empty():
    matched = match_protocols([], {})
    assert matched == {}
