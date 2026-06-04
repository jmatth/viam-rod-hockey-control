# robot/zones.py
"""Polygon zone geometry and player selection for the bubble hockey robot.

Polygons live in normalized field coordinates (u, v) in [0, 1], image-space
origin top-left. Loaded from robot/zones.json (authored by tools/annotate_zones.py).
"""


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
