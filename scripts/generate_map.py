#!/usr/bin/env python3
"""Render tezos.gpx waypoints onto a world map using cartopy + matplotlib."""

import argparse
import json
import xml.etree.ElementTree as ET

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt


# Manual label offsets (dx, dy in points) for cities that would overlap.
# Positive dx = right, positive dy = up.
LABEL_OFFSETS = {
    "Athens": (8, -8),
    "Babylon": (8, 0),
    "Carthage": (-8, 6),
    "Delphi": (-8, 6),
    "Florence": (-8, 6),
    "Granada": (-8, -8),
    "Ithaca": (-8, -8),
    "Paris": (8, 6),
    "Oxford": (-8, -8),
    "Tallinn": (8, 0),
    "Nairobi": (8, 0),
}

DEFAULT_OFFSET = (8, -4)

# Protocol names that differ from the short label used on the map.
PROTOCOL_TO_LABEL = {
    "ParisC": "Paris",
}

COLOR_MAINNET = "#1f77b4"
COLOR_TESTNET = "#ff7f0e"
COLOR_ARROW = "#888888"
COLOR_FALLBACK = "#d62728"


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


def load_protocols(path):
    """Load protocols.json if it exists. Returns dict or None."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def match_protocols(waypoints, protocols):
    """Build label->protocol mapping from GPX waypoints and protocols.json."""
    label_to_proto = {}
    for proto_name, data in protocols.items():
        label = PROTOCOL_TO_LABEL.get(proto_name, proto_name)
        label_to_proto[label] = data

    matched = {}
    for name, lat, lon in waypoints:
        label = short_label(name)
        if label in label_to_proto:
            matched[label] = label_to_proto[label]
    return matched


def generate_map(waypoints, output_path, dpi, protocols=None):
    """Render waypoints on a Robinson-projection world map."""
    fig = plt.figure(figsize=(12, 6))
    ax = fig.add_subplot(1, 1, 1, projection=ccrs.Robinson())

    ax.set_global()
    ax.add_feature(cfeature.OCEAN, facecolor="#ddeeff")
    ax.add_feature(cfeature.LAND, facecolor="#f0f0f0", edgecolor="none")
    ax.add_feature(cfeature.BORDERS, linewidth=0.3, edgecolor="#cccccc")
    ax.add_feature(cfeature.COASTLINE, linewidth=0.4, edgecolor="#aaaaaa")
    ax.spines["geo"].set_linewidth(0.5)

    matched = match_protocols(waypoints, protocols) if protocols is not None else {}

    # Draw chronological arrows if we have protocol data.
    if matched:
        wpt_by_label = {short_label(n): (lat, lon) for n, lat, lon in waypoints}
        ordered = sorted(
            ((l, d) for l, d in matched.items() if isinstance(d, dict) and "number" in d),
            key=lambda kv: kv[1]["number"],
        )
        trail = [(wpt_by_label[label], label) for label, _ in ordered if label in wpt_by_label]

        for i in range(len(trail) - 1):
            (lat1, lon1), _ = trail[i]
            (lat2, lon2), _ = trail[i + 1]
            ax.annotate(
                "",
                xy=(lon2, lat2),
                xytext=(lon1, lat1),
                xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                textcoords=ccrs.PlateCarree()._as_mpl_transform(ax),
                arrowprops=dict(
                    arrowstyle="->",
                    color=COLOR_ARROW,
                    alpha=0.4,
                    lw=0.5,
                ),
                zorder=3,
            )

    for name, lat, lon in waypoints:
        label = short_label(name)
        proto = matched.get(label)

        if proto and "number" in proto:
            color = COLOR_MAINNET if proto.get("mainnet") else COLOR_TESTNET
            number_str = f"{proto['number']:03d} "
        else:
            color = COLOR_FALLBACK
            number_str = ""

        ax.plot(
            lon, lat,
            marker="o",
            color=color,
            markersize=5,
            transform=ccrs.PlateCarree(),
            zorder=5,
        )

        dx, dy = LABEL_OFFSETS.get(label, DEFAULT_OFFSET)
        ax.annotate(
            f"{number_str}{label}",
            xy=(lon, lat),
            xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=6,
            fontweight="bold",
            color="#333333",
            zorder=6,
        )

    # Legend.
    if matched:
        legend_handles = [
            mpatches.Patch(color=COLOR_MAINNET, label="Mainnet"),
            mpatches.Patch(color=COLOR_TESTNET, label="Testnet only"),
        ]
        ax.legend(handles=legend_handles, loc="lower left", fontsize=6, framealpha=0.8)

    plt.tight_layout(pad=0.5)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    print(f"Map saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate map from GPX waypoints")
    parser.add_argument("--gpx", default="tezos.gpx", help="Path to GPX file")
    parser.add_argument("--output", default="map.png", help="Output PNG path")
    parser.add_argument("--dpi", type=int, default=150, help="Output DPI")
    parser.add_argument(
        "--protocols", default="protocols.json",
        help="Path to protocols.json (empty string to disable enrichment)",
    )
    args = parser.parse_args()

    waypoints = parse_gpx(args.gpx)
    print(f"Parsed {len(waypoints)} waypoints from {args.gpx}")

    protocols = load_protocols(args.protocols)
    if protocols is not None:
        print(f"Loaded {len(protocols)} protocols from {args.protocols}")
    else:
        print("No protocols.json loaded; using fallback style")

    generate_map(waypoints, args.output, args.dpi, protocols)


if __name__ == "__main__":
    main()
