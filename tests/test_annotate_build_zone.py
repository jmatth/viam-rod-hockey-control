# tests/test_annotate_build_zone.py
from tools.annotate_zones import build_zone


def test_build_zone_normalizes_vertices():
    verts_px = [(0, 0), (538, 0), (538, 284), (0, 284)]
    z = build_zone("center", "left", verts_px, 538, 284)
    assert z == {
        "player": "center",
        "side": "left",
        "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    }


def test_build_zone_rounds_to_4dp():
    z = build_zone("left_d", "right", [(269, 142), (270, 143), (269, 143)], 538, 284)
    assert z["polygon"][0] == [round(269 / 538, 4), round(142 / 284, 4)]
