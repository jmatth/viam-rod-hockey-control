# tests/test_zones_geometry.py
from robot.zones import point_in_polygon, normalize_point


SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
# A concave "C"/L shape to catch naive bounding-box logic.
CONCAVE = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.4), (0.4, 0.4), (0.4, 1.0), (0.0, 1.0)]


def test_point_inside_square():
    assert point_in_polygon(0.5, 0.5, SQUARE) is True


def test_point_outside_square():
    assert point_in_polygon(1.5, 0.5, SQUARE) is False


def test_point_in_concavity_is_outside():
    # (0.7, 0.7) is inside the bounding box but inside the cut-out notch.
    assert point_in_polygon(0.7, 0.7, CONCAVE) is False


def test_point_in_solid_part_of_concave():
    assert point_in_polygon(0.2, 0.2, CONCAVE) is True


def test_normalize_point():
    assert normalize_point(269.0, 142.0, 538, 284) == (269.0 / 538, 142.0 / 284)
