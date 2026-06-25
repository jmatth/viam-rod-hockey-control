# tests/test_seed_zones.py
from tools.seed_zones_from_legacy import LEGACY_ZONES, box_to_normalized_polygon, REF_W, REF_H


def test_box_to_normalized_polygon_corners():
    poly = box_to_normalized_polygon(0, 538, 0, 284)
    assert poly == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def test_legacy_zone_count_and_order():
    # 16 legacy zones; first is the LEFT_WING behind-goal priority zone.
    assert len(LEGACY_ZONES) == 16
    assert LEGACY_ZONES[0]["player"] == "left_wing"


def test_normalized_values_in_unit_range():
    for z in LEGACY_ZONES:
        poly = box_to_normalized_polygon(z["x_min"], z["x_max"], z["y_min"], z["y_max"])
        for x, y in poly:
            assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
