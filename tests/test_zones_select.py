# tests/test_zones_select.py
import json

from engine.constants import PlayerID
from robot.zones import load_zones, select


def _write(tmp_path, data):
    p = tmp_path / "zones.json"
    p.write_text(json.dumps(data))
    return str(p)


# Two overlapping squares; the first listed must win (first-match priority).
OVERLAP = [
    {"player": "left_wing", "side": "bottom_right",
     "polygon": [[0.0, 0.0], [0.6, 0.0], [0.6, 0.6], [0.0, 0.6]]},
    {"player": "left_d", "side": "left",
     "polygon": [[0.4, 0.4], [1.0, 0.4], [1.0, 1.0], [0.4, 1.0]]},
]


def test_load_zones_maps_player_names(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert zones[0][0] == PlayerID.LEFT_WING
    assert zones[0][1] == "bottom_right"
    assert zones[0][2][0] == (0.0, 0.0)


def test_select_first_match_wins(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    # (0.5, 0.5) is inside BOTH squares; first listed (left_wing) wins.
    assert select(0.5, 0.5, zones) == (PlayerID.LEFT_WING, "bottom_right")


def test_select_second_zone(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert select(0.8, 0.8, zones) == (PlayerID.LEFT_D, "left")


def test_select_no_match_returns_none(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert select(0.99, 0.05, zones) == (None, None)
