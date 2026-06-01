#!/usr/bin/env python3
"""Render tezos.gpx waypoints onto a world map using cartopy + matplotlib."""

import argparse
import xml.etree.ElementTree as ET

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# Manual label offsets (dx, dy in points) for cities that would overlap.
# Positive dx = right, positive dy = up.
LABEL_OFFSETS = {
    "Athens": (6, -8),
    "Babylon": (6, 0),
    "Carthage": (-6, 6),
    "Delphi": (-6, 6),
    "Florence": (-6, 6),
    "Granada": (-6, -8),
    "Ithaca": (-6, -8),
    "Paris": (6, 6),
    "Oxford": (-6, -8),
    "Tallinn": (6, 0),
    "Nairobi": (6, 0),
}

DEFAULT_OFFSET = (6, -4)


def parse_gpx(gpx_path):
    """Parse GPX file and return list of (name, lat, lon)."""
    tree = ET.parse(gpx_path)
    root = tree.getroot()
    ns = ""
    # Handle default GPX namespace if present
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    waypoints = []
    for wpt in root.findall(f"{ns}wpt"):
        lat = float(wpt.get("lat"))
        lon = float(wpt.get("lon"))
        name_el = wpt.find(f"{ns}name")
        name = name_el.text if name_el is not None else ""
        waypoints.append((name, lat, lon))
    return waypoints


def short_label(name):
    """Strip country suffix and shorten known long names."""
    label = name.split(",")[0].strip()
    if label == "Edo (Tokyo)":
        label = "Edo"
    if label == "Quebec City":
        label = "Quebec"
    if label == "Rio de Janeiro":
        label = "Rio"
    return label


def generate_map(waypoints, output_path, dpi):
    """Render waypoints on a Robinson-projection world map."""
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

    ax.set_global()
    ax.add_feature(cfeature.OCEAN, facecolor="#ddeeff")
    ax.add_feature(cfeature.LAND, facecolor="#f0f0f0", edgecolor="none")
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="#cccccc")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor="#aaaaaa")
    ax.spines["geo"].set_linewidth(0.5)

    for name, lat, lon in waypoints:
        ax.plot(
            lon,
            lat,
            marker="o",
            color="#d62728",
            markersize=5,
            transform=ccrs.PlateCarree(),
            zorder=5,
        )

        label = short_label(name)
        dx, dy = LABEL_OFFSETS.get(label, DEFAULT_OFFSET)

        ax.annotate(
            label,
            xy=(lon, lat),
            xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=6,
            fontweight="bold",
            color="#333333",
            zorder=6,
        )

    plt.tight_layout(pad=0.5)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Map saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate map from GPX waypoints")
    parser.add_argument("--gpx", default="tezos.gpx", help="Path to GPX file")
    parser.add_argument("--output", default="map.png", help="Output PNG path")
    parser.add_argument("--dpi", type=int, default=150, help="Output DPI")
    args = parser.parse_args()

    waypoints = parse_gpx(args.gpx)
    print(f"Parsed {len(waypoints)} waypoints from {args.gpx}")
    generate_map(waypoints, args.output, args.dpi)


if __name__ == "__main__":
    main()
