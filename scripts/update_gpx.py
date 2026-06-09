#!/usr/bin/env python3
"""Scrape Tezos protocol names and update tezos.gpx with new city waypoints."""

import argparse
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

DEFAULT_NAMING_URL = "https://octez.tezos.com/docs/protocols/naming.html"
GPX_PATH = "tezos.gpx"
PROTOCOLS_JSON_PATH = "protocols.json"
PROTOCOL_COUNT_JSON_PATH = "protocol-count.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
TZKT_API = "https://api.tzkt.io/v1"
TEZTNETS_URL = "https://teztnets.com/teztnets.json"

# Protocol names that don't geocode directly to the intended city.
CITY_OVERRIDES = {
    "Edo": ("Edo (Tokyo), Japan", "Tokyo"),
    "ParisC": ("Paris, France", "Paris, France"),
    "Quebec": ("Quebec City, Canada", "Quebec City, Canada"),
    "Rio": ("Rio de Janeiro, Brazil", "Rio de Janeiro, Brazil"),
}

# Map scraped names to TzKT extras.alias where they differ.
TZKT_ALIAS_MAP = {
    "ParisC": "Paris C",
}


def scrape_protocols(naming_url):
    """Return a list of (number, city_name) tuples from the Tezos naming page (protocol >= 004)."""
    resp = requests.get(naming_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cities = []
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        m = re.match(r"(\d{3})\s+(\S+)", text)
        if m and int(m.group(1)) >= 4:
            cities.append((int(m.group(1)), m.group(2)))

    if not cities:
        print("ERROR: Found zero protocols on the naming page. Page structure may have changed.", file=sys.stderr)
        sys.exit(1)

    return cities


def read_existing_gpx():
    """Parse tezos.gpx and return (full text, set of city display names)."""
    with open(GPX_PATH, encoding="utf-8") as f:
        text = f.read()

    names = set()
    for m in re.finditer(r"<name>(.*?)</name>", text):
        names.add(m.group(1))

    return text, names


def geocode(query):
    """Geocode a city name via Nominatim. Returns (lat, lon) or None."""
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "TezosProtocolMap/1.0"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


def display_name_for(protocol_name, lat, lon):
    """Build the <name> text for a protocol city."""
    if protocol_name in CITY_OVERRIDES:
        return CITY_OVERRIDES[protocol_name][0]

    # Reverse-geocode to get the country from Nominatim.
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": protocol_name, "format": "json", "limit": 1, "accept-language": "en"},
        headers={"User-Agent": "TezosProtocolMap/1.0"},
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json()
    if results and "display_name" in results[0]:
        parts = results[0]["display_name"].split(", ")
        country = parts[-1]
        return f"{protocol_name}, {country}"

    return protocol_name


def desc_for(display_name):
    """Generate a <desc> string matching existing conventions."""
    # Existing entries use "Capital of X" or "City in X" or "Ancient city in X".
    # Default to "City in <country>".
    parts = display_name.split(", ")
    if len(parts) >= 2:
        return f"City in {parts[-1]}"
    return display_name


def format_coord(value):
    """Format a coordinate to 4 decimal places."""
    return f"{value:.4f}"


def build_wpt(display_name, lat, lon):
    """Build a GPX <wpt> block as a string."""
    return (
        f'  <wpt lat="{format_coord(lat)}" lon="{format_coord(lon)}">\n'
        f"    <name>{display_name}</name>\n"
        f"    <desc>{desc_for(display_name)}</desc>\n"
        f"  </wpt>"
    )


def parse_wpts(text):
    """Extract all <wpt>...</wpt> blocks from GPX text."""
    return re.findall(r"  <wpt .*?</wpt>", text, re.DOTALL)


def sort_key(wpt_block):
    """Sort waypoints alphabetically by <name>."""
    m = re.search(r"<name>(.*?)</name>", wpt_block)
    return m.group(1).lower() if m else ""


def write_gpx(existing_text, wpt_blocks):
    """Write the GPX file with sorted waypoints, preserving header/footer."""
    header = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
    header += '<gpx version="1.1" creator="Tezos Protocols Maps (by Copolycube)">\n'
    footer = "</gpx>\n"

    sorted_blocks = sorted(wpt_blocks, key=sort_key)
    body = "\n".join(sorted_blocks)

    with open(GPX_PATH, "w", encoding="utf-8") as f:
        f.write(header + body + "\n" + footer)


def fetch_tzkt_protocols():
    """Fetch protocol metadata from TzKT API. Returns dict keyed by alias."""
    try:
        resp = requests.get(f"{TZKT_API}/protocols", timeout=30)
        resp.raise_for_status()
        raw = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  WARNING: TzKT API unreachable ({exc}), skipping enrichment.", file=sys.stderr)
        return {}

    protocols = {}
    levels = []
    for p in raw:
        alias = (p.get("extras") or {}).get("alias")
        if not alias:
            continue
        first_level = p.get("firstLevel", 0)
        protocols[alias] = {
            "hash": p.get("hash"),
            "firstLevel": first_level,
        }
        if first_level > 0:
            levels.append(first_level)

    # Batch-fetch activation timestamps.
    if levels:
        try:
            level_str = ",".join(str(lv) for lv in levels)
            resp = requests.get(
                f"{TZKT_API}/blocks",
                params={"level.in": level_str, "select": "level,timestamp"},
                timeout=30,
            )
            resp.raise_for_status()
            ts_map = {b["level"]: b["timestamp"] for b in resp.json()}
        except (requests.RequestException, ValueError):
            ts_map = {}
    else:
        ts_map = {}

    for data in protocols.values():
        data["activationDate"] = ts_map.get(data["firstLevel"])

    return protocols


def fetch_testnet_protocols():
    """Fetch protocol testnets from teztnets.com. Returns dict: city_name -> {rpc_url, ...}."""
    try:
        resp = requests.get(TEZTNETS_URL, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  WARNING: teztnets.com unreachable ({exc}).", file=sys.stderr)
        return {}

    protocols = {}
    seen = set()
    for entry in data.values():
        if entry.get("category") != "Protocol Teztnets":
            continue
        human_name = entry.get("human_name") or ""
        if not human_name.endswith("net"):
            continue
        city = human_name[:-3]  # "Ushuaianet" -> "Ushuaia"
        if city in seen:
            continue
        seen.add(city)
        protocols[city] = {"rpc_url": entry.get("rpc_url")}

    return protocols


def fetch_protocol_hash(rpc_url):
    """Get the current protocol hash from a testnet RPC endpoint."""
    try:
        url = f"{rpc_url.rstrip('/')}/chains/main/blocks/head/protocols"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("protocol") if isinstance(data, dict) else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def gpx_coords_for_protocols(scraped, gpx_text):
    """Match GPX waypoints to protocol names. Returns dict: name -> (lat, lon)."""
    wpt_data = []
    for m in re.finditer(
        r'<wpt lat="([^"]+)" lon="([^"]+)">\s*<name>([^<]+)</name>', gpx_text
    ):
        wpt_data.append((m.group(3), float(m.group(1)), float(m.group(2))))

    coords = {}
    for _, name in scraped:
        override_display = CITY_OVERRIDES[name][0] if name in CITY_OVERRIDES else None
        for wpt_name, lat, lon in wpt_data:
            if override_display and wpt_name == override_display:
                coords[name] = (lat, lon)
                break
            if wpt_name.startswith(name):
                coords[name] = (lat, lon)
                break
    return coords


def build_protocols_json(scraped, tzkt_data, gpx_coords, testnet_info=None):
    """Merge scraped numbers, TzKT data, and GPX coords into protocols dict."""
    has_tzkt = bool(tzkt_data)
    testnet_info = testnet_info or {}
    result = {}
    for number, name in scraped:
        tzkt_alias = TZKT_ALIAS_MAP.get(name, name)
        tzkt = tzkt_data.get(tzkt_alias, {})
        coords = gpx_coords.get(name)

        proto_hash = tzkt.get("hash")
        # For testnet-only protocols, try the testnet RPC.
        if not proto_hash and name in testnet_info:
            rpc_url = testnet_info[name].get("rpc_url")
            if rpc_url:
                print(f"  Fetching hash for {name} from testnet RPC...")
                proto_hash = fetch_protocol_hash(rpc_url)

        result[name] = {
            "number": number,
            "hash": proto_hash,
            "activationDate": tzkt.get("activationDate"),
            "mainnet": bool(tzkt.get("hash")) if has_tzkt else None,
            "lat": coords[0] if coords else None,
            "lon": coords[1] if coords else None,
        }

    return result


def write_protocols_json(protocols_data):
    """Write protocols.json and protocol-count.json."""
    with open(PROTOCOLS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(protocols_data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {PROTOCOLS_JSON_PATH} with {len(protocols_data)} protocols.")

    count_data = {
        "schemaVersion": 1,
        "label": "protocols",
        "message": str(len(protocols_data)),
        "color": "blue",
    }
    with open(PROTOCOL_COUNT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(count_data, f, indent=2)
        f.write("\n")
    print(f"Wrote {PROTOCOL_COUNT_JSON_PATH}.")


def main():
    parser = argparse.ArgumentParser(description="Update tezos.gpx with new protocol cities.")
    parser.add_argument("--url", default=DEFAULT_NAMING_URL, help="URL of the Tezos protocol naming page")
    args = parser.parse_args()

    naming_url = args.url
    print(f"Scraping protocol names from {naming_url}...")
    scraped = scrape_protocols(naming_url)
    print(f"  Found {len(scraped)} protocols: {', '.join(name for _, name in scraped)}")

    # Merge testnet-only protocols not yet on the naming page.
    print("Fetching testnet protocols from teztnets.com...")
    testnet_protocols = fetch_testnet_protocols()
    scraped_names = {name for _, name in scraped}
    testnet_info = {}
    if testnet_protocols:
        next_number = max(num for num, _ in scraped) + 1
        for city in sorted(testnet_protocols):
            if city not in scraped_names:
                scraped.append((next_number, city))
                testnet_info[city] = testnet_protocols[city]
                print(f"  Added testnet-only protocol: {next_number:03d} {city}")
                next_number += 1
        if not testnet_info:
            print("  No new testnet-only protocols found.")
    else:
        print("  No testnet data available.")

    print("Reading existing GPX...")
    existing_text, existing_names = read_existing_gpx()
    existing_wpts = parse_wpts(existing_text)
    print(f"  {len(existing_names)} cities already in GPX")

    # Determine which protocol names are new.
    new_protocols = []
    for num, p in scraped:
        if p in CITY_OVERRIDES:
            display = CITY_OVERRIDES[p][0]
        else:
            display = None
        # Check if any existing name starts with the protocol name or matches the override.
        found = False
        for name in existing_names:
            if display and name == display:
                found = True
                break
            if name.startswith(p):
                found = True
                break
        if not found:
            new_protocols.append((num, p))

    if new_protocols:
        print(f"New protocols to geocode: {', '.join(name for _, name in new_protocols)}")

        new_wpts = []
        for _, p in new_protocols:
            geocode_query = CITY_OVERRIDES[p][1] if p in CITY_OVERRIDES else p
            print(f"  Geocoding '{geocode_query}'...")
            coords = geocode(geocode_query)
            if coords is None:
                print(f"    WARNING: Could not geocode '{geocode_query}', skipping.")
                continue

            lat, lon = coords
            display = display_name_for(p, lat, lon)
            print(f"    {display} -> ({format_coord(lat)}, {format_coord(lon)})")

            new_wpts.append(build_wpt(display, lat, lon))
            time.sleep(1)  # Nominatim usage policy: max 1 request/second

        if new_wpts:
            all_wpts = existing_wpts + new_wpts
            write_gpx(existing_text, all_wpts)
            print(f"Updated {GPX_PATH} with {len(new_wpts)} new waypoint(s).")
        else:
            print("No new waypoints could be geocoded.")
    else:
        print("No new protocol cities to add.")

    # Re-read GPX to get final coords (including any newly added cities).
    final_text, _ = read_existing_gpx()

    # Enrich with TzKT metadata.
    print("Fetching protocol metadata from TzKT...")
    tzkt_data = fetch_tzkt_protocols()
    if tzkt_data:
        print(f"  Got metadata for {len(tzkt_data)} protocols from TzKT.")
    else:
        print("  No TzKT data available; protocols.json will have null hashes/dates.")

    gpx_coords = gpx_coords_for_protocols(scraped, final_text)
    protocols_data = build_protocols_json(scraped, tzkt_data, gpx_coords, testnet_info)
    write_protocols_json(protocols_data)


if __name__ == "__main__":
    main()
