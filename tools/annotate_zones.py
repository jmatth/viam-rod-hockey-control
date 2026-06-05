# tools/annotate_zones.py
"""Draw player zone polygons on a saved dynamic-crop frame and export zones.json.

    .venv/bin/python tools/annotate_zones.py --image <frame.jpeg> --out robot/zones.json

Reference overlays (faint) help you trace today's behavior:
  - any existing zones.json polygons (edit mode)
  - the legacy boxes from tools/seed_zones_from_legacy.LEGACY_ZONES

Interaction (single polygon at a time):
  - Click vertices on the image; close the polygon (click near the first point).
  - Press Enter (in this terminal) to name it: you'll be prompted for player+side.
  - Press 'w' on the figure to write the JSON; 'q' to quit without further saving.
"""

import argparse
import json
import os
import sys

# Allow running directly as `python tools/annotate_zones.py` (not only `-m tools...`):
# put the repo root on sys.path so the `tools` package resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import PolygonSelector

from tools.seed_zones_from_legacy import LEGACY_ZONES

PLAYERS = ["center", "right_wing", "left_wing", "right_d", "left_d"]
SIDES = ["left", "right", "bottom_left", "bottom_right"]


def build_zone(player, side, verts_px, width, height):
    """Return a zone dict with the vertices normalized to [0, 1] (rounded 4dp)."""
    polygon = [[round(x / width, 4), round(y / height, 4)] for (x, y) in verts_px]
    return {"player": player, "side": side, "polygon": polygon}


def _prompt(label, options):
    while True:
        val = input(f"  {label} {options}: ").strip()
        if val in options:
            return val
        print(f"  '{val}' not in {options}")


def _overlay_reference(ax, width, height, out_path):
    # Legacy boxes (faint blue), drawn in pixel space scaled to this image.
    from tools.seed_zones_from_legacy import REF_W, REF_H
    sx, sy = width / REF_W, height / REF_H
    for z in LEGACY_ZONES:
        x0, y0 = z["x_min"] * sx, z["y_min"] * sy
        w, h = (z["x_max"] - z["x_min"]) * sx, (z["y_max"] - z["y_min"]) * sy
        ax.add_patch(plt.Rectangle((x0, y0), w, h, fill=False, edgecolor="cyan",
                                   alpha=0.35, linewidth=0.8))
    # Existing zones.json (faint yellow), if present.
    if os.path.exists(out_path):
        with open(out_path) as f:
            for z in json.load(f):
                pts = [(u * width, v * height) for u, v in z["polygon"]]
                ax.add_patch(plt.Polygon(pts, closed=True, fill=False,
                                         edgecolor="yellow", alpha=0.4, linewidth=1.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="/home/nick/Downloads/dynamic-crop-2026-06-04_16_56_57.jpeg")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "robot", "zones.json"))
    args = parser.parse_args()
    out_path = os.path.abspath(args.out)

    img = mpimg.imread(args.image)
    height, width = img.shape[:2]

    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.set_title("draw polygon, Enter=name it, w=write json, q=quit")
    _overlay_reference(ax, width, height, out_path)

    zones = []
    state = {"verts": []}

    def on_select(verts):
        state["verts"] = list(verts)

    selector = PolygonSelector(ax, on_select)

    def on_key(event):
        if event.key == "enter":
            if len(state["verts"]) < 3:
                print("  need at least 3 vertices before naming")
                return
            player = _prompt("player", PLAYERS)
            side = _prompt("side", SIDES)
            zones.append(build_zone(player, side, state["verts"], width, height))
            print(f"  added {player}/{side} ({len(zones)} total). Draw the next polygon.")
            selector.clear()
            state["verts"] = []
        elif event.key == "w":
            with open(out_path, "w") as f:
                json.dump(zones, f, indent=2)
            print(f"  wrote {len(zones)} zones to {out_path}")
        elif event.key == "q":
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()


if __name__ == "__main__":
    main()
