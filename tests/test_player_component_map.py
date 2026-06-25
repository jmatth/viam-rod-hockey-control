# tests/test_player_component_map.py
from engine.constants import PlayerID
from robot.const import PLAYER_TO_COMPONENT


def test_every_player_has_a_component():
    for player in PlayerID:
        assert player in PLAYER_TO_COMPONENT
        assert isinstance(PLAYER_TO_COMPONENT[player], str)


def test_center_component_name():
    assert PLAYER_TO_COMPONENT[PlayerID.CENTER] == "center-hockey-player"
