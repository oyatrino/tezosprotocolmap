#!/usr/bin/env python3
"""Scrape Tezos protocol names and update tezos.gpx with new city waypoints."""

import argparse
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

DEFAULT_NAMING_URL = "https://octez.tezos.com/docs/protocols/naming.html"
GPX_PATH = "tezos.gpx"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Protocol names that don't geocode directly to the intended city.
CITY_OVERRIDES = {
    "Edo": ("Edo (Tokyo), Japan", "Tokyo"),
    "ParisC": ("Paris, France", "Paris, France"),
    "Quebec": ("Quebec City, Canada", "Quebec City, Canada"),
    "Rio": ("Rio de Janeiro, Brazil", "Rio de Janeiro, Brazil"),
}


def scrape_protocols(naming_url):
    """Return a list of city names from the Tezos naming page (protocol >= 004)."""
    resp = requests.get(naming_url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cities = []
    for li in soup.find_all("li"):
        text = li.get_text(strip=True)
        m = re.match(r"(\d{3})\s+(\S+)", text)
        if m and int(m.group(1)) >= 4:
            cities.append(m.group(2))

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


def main():
    parser = argparse.ArgumentParser(description="Update tezos.gpx with new protocol cities.")
    parser.add_argument("--url", default=DEFAULT_NAMING_URL, help="URL of the Tezos protocol naming page")
    args = parser.parse_args()

    naming_url = args.url
    print(f"Scraping protocol names from {naming_url}...")
    protocols = scrape_protocols(naming_url)
    print(f"  Found {len(protocols)} protocols: {', '.join(protocols)}")

    print("Reading existing GPX...")
    existing_text, existing_names = read_existing_gpx()
    existing_wpts = parse_wpts(existing_text)
    print(f"  {len(existing_names)} cities already in GPX")

    # Determine which protocol names are new.
    new_protocols = []
    for p in protocols:
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
            new_protocols.append(p)

    if not new_protocols:
        print("No new protocol cities to add.")
        return

    print(f"New protocols to geocode: {', '.join(new_protocols)}")

    new_wpts = []
    for p in new_protocols:
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

    if not new_wpts:
        print("No new waypoints could be geocoded.")
        return

    all_wpts = existing_wpts + new_wpts
    write_gpx(existing_text, all_wpts)
    print(f"Updated {GPX_PATH} with {len(new_wpts)} new waypoint(s).")


if __name__ == "__main__":
    main()
