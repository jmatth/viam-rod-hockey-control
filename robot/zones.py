# robot/zones.py
"""Polygon zone geometry and player selection for the bubble hockey robot.

Polygons live in normalized field coordinates (u, v) in [0, 1], image-space
origin top-left. Loaded from robot/zones.json (authored by tools/annotate_zones.py).
"""

import json
import os

from engine.constants import PlayerID

_ZONES_PATH = os.path.join(os.path.dirname(__file__), "zones.json")

_NAME_TO_PLAYER = {
    "center":     PlayerID.CENTER,
    "right_wing": PlayerID.RIGHT_WING,
    "left_wing":  PlayerID.LEFT_WING,
    "right_d":    PlayerID.RIGHT_D,
    "left_d":     PlayerID.LEFT_D,
}

_ZONES_CACHE = None


def point_in_polygon(u: float, v: float, polygon) -> bool:
    """Ray-casting point-in-polygon test. `polygon` is a list of (u, v) tuples."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > v) != (yj > v)) and (u < (xj - xi) * (v - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def normalize_point(px: float, py: float, width: int, height: int):
    """Convert a pixel coordinate to normalized (u, v) in [0, 1]."""
    return (px / width, py / height)


def load_zones(path: str = _ZONES_PATH):
    """Load zones as a list of (PlayerID, side, polygon) tuples, in file order."""
    with open(path) as f:
        raw = json.load(f)
    zones = []
    for z in raw:
        player = _NAME_TO_PLAYER[z["player"]]
        polygon = [tuple(pt) for pt in z["polygon"]]
        zones.append((player, z["side"], polygon))
    return zones


def _default_zones():
    global _ZONES_CACHE
    if _ZONES_CACHE is None:
        _ZONES_CACHE = load_zones()
    return _ZONES_CACHE


def select(u: float, v: float, zones=None):
    """Return (PlayerID, side) for the first zone containing (u, v), else (None, None)."""
    if zones is None:
        zones = _default_zones()
    for player, side, polygon in zones:
        if point_in_polygon(u, v, polygon):
            return player, side
    return None, None
