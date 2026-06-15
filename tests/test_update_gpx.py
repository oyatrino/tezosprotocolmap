"""Tests for scripts/update_gpx.py pure functions."""

from unittest.mock import MagicMock, patch

from scripts.update_gpx import (
    build_protocols_json,
    build_wpt,
    desc_for,
    format_coord,
    gpx_coords_for_protocols,
    parse_wpts,
    scrape_protocols,
    sort_key,
)


# ---------- format_coord ----------

def test_format_coord_rounds_to_four_decimals():
    assert format_coord(37.98384) == "37.9838"


def test_format_coord_pads_short_decimals():
    assert format_coord(10.1) == "10.1000"


def test_format_coord_negative():
    assert format_coord(-77.0428) == "-77.0428"


# ---------- desc_for ----------

def test_desc_for_city_country():
    assert desc_for("Athens, Greece") == "City in Greece"


def test_desc_for_no_country():
    assert desc_for("Athens") == "Athens"


def test_desc_for_multiple_parts():
    assert desc_for("Quebec City, Quebec, Canada") == "City in Canada"


# ---------- build_wpt ----------

def test_build_wpt_structure():
    wpt = build_wpt("Athens, Greece", 37.9838, 23.7275)
    assert '<wpt lat="37.9838" lon="23.7275">' in wpt
    assert "<name>Athens, Greece</name>" in wpt
    assert "<desc>City in Greece</desc>" in wpt
    assert wpt.startswith("  <wpt")
    assert wpt.endswith("</wpt>")


# ---------- parse_wpts ----------

def test_parse_wpts_extracts_blocks(sample_gpx_text):
    blocks = parse_wpts(sample_gpx_text)
    assert len(blocks) == 4
    assert "<name>Athens, Greece</name>" in blocks[0]


# ---------- sort_key ----------

def test_sort_key_extracts_lowercase_name():
    block = '  <wpt lat="37.9838" lon="23.7275">\n    <name>Athens, Greece</name>\n    <desc>Capital</desc>\n  </wpt>'
    assert sort_key(block) == "athens, greece"


def test_sort_key_no_name():
    assert sort_key("<wpt></wpt>") == ""


# ---------- gpx_coords_for_protocols ----------

def test_gpx_coords_for_protocols_basic(sample_gpx_text):
    scraped = [(4, "Athens"), (5, "Babylon"), (6, "Carthage")]
    coords = gpx_coords_for_protocols(scraped, sample_gpx_text)
    assert coords["Athens"] == (37.9838, 23.7275)
    assert coords["Babylon"] == (32.5439, 44.4208)
    assert coords["Carthage"] == (36.8508, 10.1833)


def test_gpx_coords_for_protocols_overrides(sample_gpx_text):
    scraped = [(8, "Edo")]
    coords = gpx_coords_for_protocols(scraped, sample_gpx_text)
    assert coords["Edo"] == (35.6895, 139.6917)


def test_gpx_coords_for_protocols_missing(sample_gpx_text):
    scraped = [(10, "Granada")]
    coords = gpx_coords_for_protocols(scraped, sample_gpx_text)
    assert "Granada" not in coords


# ---------- build_protocols_json ----------

def test_build_protocols_json_mainnet():
    scraped = [(4, "Athens"), (5, "Babylon")]
    tzkt_data = {
        "Athens": {"hash": "PtAthens", "firstLevel": 1, "activationDate": "2019-05-30T00:58:55Z"},
        "Babylon": {"hash": "PsBabylon", "firstLevel": 2, "activationDate": "2019-10-18T08:18:28Z"},
    }
    gpx_coords = {"Athens": (37.9838, 23.7275), "Babylon": (32.5439, 44.4208)}
    result = build_protocols_json(scraped, tzkt_data, gpx_coords)
    assert result["Athens"]["number"] == 4
    assert result["Athens"]["hash"] == "PtAthens"
    assert result["Athens"]["mainnet"] is True
    assert result["Athens"]["lat"] == 37.9838
    assert result["Babylon"]["mainnet"] is True


def test_build_protocols_json_testnet_only():
    scraped = [(25, "Ushuaia")]
    # TzKT is reachable (non-empty) but doesn't contain this protocol.
    tzkt_data = {"Athens": {"hash": "PtAthens", "firstLevel": 1, "activationDate": "2019-05-30T00:58:55Z"}}
    gpx_coords = {"Ushuaia": (-54.8073, -68.3084)}
    testnet_info = {"Ushuaia": {"rpc_url": "https://rpc.ushuaianet.teztnets.com"}}

    with patch("scripts.update_gpx.fetch_protocol_hash", return_value="PsUshuaia"):
        result = build_protocols_json(scraped, tzkt_data, gpx_coords, testnet_info)
    assert result["Ushuaia"]["mainnet"] is False
    assert result["Ushuaia"]["hash"] == "PsUshuaia"


def test_build_protocols_json_no_tzkt():
    scraped = [(4, "Athens")]
    tzkt_data = {}
    gpx_coords = {"Athens": (37.9838, 23.7275)}
    result = build_protocols_json(scraped, tzkt_data, gpx_coords)
    assert result["Athens"]["mainnet"] is None
    assert result["Athens"]["hash"] is None


def test_build_protocols_json_no_coords():
    scraped = [(4, "Athens")]
    tzkt_data = {"Athens": {"hash": "PtAthens", "firstLevel": 1, "activationDate": "2019-05-30T00:58:55Z"}}
    gpx_coords = {}
    result = build_protocols_json(scraped, tzkt_data, gpx_coords)
    assert result["Athens"]["lat"] is None
    assert result["Athens"]["lon"] is None


def test_build_protocols_json_alias_map():
    scraped = [(20, "ParisC")]
    tzkt_data = {
        "Paris C": {"hash": "PsParis", "firstLevel": 100, "activationDate": "2024-06-25T07:30:25Z"},
    }
    gpx_coords = {"ParisC": (48.8566, 2.3522)}
    result = build_protocols_json(scraped, tzkt_data, gpx_coords)
    assert result["ParisC"]["hash"] == "PsParis"
    assert result["ParisC"]["mainnet"] is True


# ---------- scrape_protocols ----------

def test_scrape_protocols_with_fixture(naming_html):
    mock_resp = MagicMock()
    mock_resp.text = naming_html
    mock_resp.raise_for_status = MagicMock()

    with patch("scripts.update_gpx.requests.get", return_value=mock_resp):
        result = scrape_protocols("https://example.com/naming.html")

    assert result == [(4, "Athens"), (5, "Babylon"), (6, "Carthage"), (7, "Delphi")]


def test_scrape_protocols_skips_below_004(naming_html):
    mock_resp = MagicMock()
    mock_resp.text = naming_html
    mock_resp.raise_for_status = MagicMock()

    with patch("scripts.update_gpx.requests.get", return_value=mock_resp):
        result = scrape_protocols("https://example.com/naming.html")

    names = [name for _, name in result]
    assert "Genesis" not in names
    assert "Demo_noops" not in names
