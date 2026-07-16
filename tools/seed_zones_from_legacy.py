# tools/seed_zones_from_legacy.py
"""One-shot: convert the legacy axis-aligned zone boxes into a normalized
polygon zones.json. Run once to bootstrap robot/zones.json; refine afterward
with tools/annotate_zones.py.

    .venv/bin/python -m tools.seed_zones_from_legacy
"""

import json
import logging
import os

from robot.logging_setup import configure as configure_logging

log = logging.getLogger(__name__)

# Reference crop size (sample dynamic-crop frame) the legacy pixel boxes assume.
REF_W = 538
REF_H = 284

# Snapshot of the legacy robot/playbook.py _ZONES, in original order (first match wins).
LEGACY_ZONES = [
    {"player": "left_wing",  "side": "bottom_right", "x_min": 75,    "x_max": 155,   "y_min": 230, "y_max": 255},
    {"player": "left_wing",  "side": "bottom_right", "x_min": 45,    "x_max": 75,    "y_min": 110, "y_max": 230},
    {"player": "left_wing",  "side": "bottom_left",  "x_min": 75,    "x_max": 155,   "y_min": 255, "y_max": 280},
    {"player": "left_wing",  "side": "bottom_right", "x_min": 0,     "x_max": 45,    "y_min": 110, "y_max": 280},
    {"player": "left_wing",  "side": "right",        "x_min": 120,   "x_max": 210,   "y_min": 230, "y_max": 255},
    {"player": "left_wing",  "side": "left",         "x_min": 120,   "x_max": 210,   "y_min": 255, "y_max": 280},
    {"player": "right_wing", "side": "left",         "x_min": 155,   "x_max": 315,   "y_min": 25,  "y_max": 75},
    {"player": "right_wing", "side": "right",        "x_min": 155,   "x_max": 315,   "y_min": 0,   "y_max": 25},
    {"player": "right_wing", "side": "bottom_left",  "x_min": 0,     "x_max": 155,   "y_min": 25,  "y_max": 75},
    {"player": "right_wing", "side": "bottom_right", "x_min": 0,     "x_max": 155,   "y_min": 0,   "y_max": 25},
    {"player": "right_d",    "side": "right",        "x_min": 335,   "x_max": 470,   "y_min": 65,  "y_max": 90},
    {"player": "right_d",    "side": "left",         "x_min": 335,   "x_max": 470,   "y_min": 90,  "y_max": 115},
    {"player": "center",     "side": "right",        "x_min": 150,   "x_max": 300,   "y_min": 85,  "y_max": 135},
    {"player": "center",     "side": "left",         "x_min": 150,   "x_max": 300,   "y_min": 135, "y_max": 185},
    {"player": "left_d",     "side": "right",        "x_min": 278.5, "x_max": 485.5, "y_min": 185, "y_max": 210},
    {"player": "left_d",     "side": "left",         "x_min": 278.5, "x_max": 485.5, "y_min": 210, "y_max": 235},
]


def box_to_normalized_polygon(x_min, x_max, y_min, y_max):
    """Return a 4-point normalized polygon (CW from top-left) for a pixel box."""
    return [
        [round(x_min / REF_W, 4), round(y_min / REF_H, 4)],
        [round(x_max / REF_W, 4), round(y_min / REF_H, 4)],
        [round(x_max / REF_W, 4), round(y_max / REF_H, 4)],
        [round(x_min / REF_W, 4), round(y_max / REF_H, 4)],
    ]


def build_zones():
    out = []
    for z in LEGACY_ZONES:
        out.append({
            "player": z["player"],
            "side": z["side"],
            "polygon": box_to_normalized_polygon(z["x_min"], z["x_max"], z["y_min"], z["y_max"]),
        })
    return out


if __name__ == "__main__":
    configure_logging()
    out_path = os.path.join(os.path.dirname(__file__), "..", "robot", "zones.json")
    out_path = os.path.abspath(out_path)
    with open(out_path, "w") as f:
        json.dump(build_zones(), f, indent=2)
    log.info("Wrote %d zones to %s", len(LEGACY_ZONES), out_path)
