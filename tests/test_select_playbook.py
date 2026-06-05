# tests/test_select_playbook.py
# Tests select_playbook's mapping logic (player+side -> sequence) independently of
# the shipped zones.json geometry, which is hand-drawn and expected to change. The
# geometry itself is covered by test_zones_json_resolves (every shipped zone's
# centroid resolves) and the robot.zones unit tests.
import robot.playbook as pb
from engine.constants import PlayerID


def test_maps_center_left_to_sequence(monkeypatch):
    monkeypatch.setattr(pb.zones, "select", lambda u, v: (PlayerID.CENTER, "left"))
    player, seq = pb.select_playbook(0.5, 0.5)
    assert player == PlayerID.CENTER
    assert seq is pb._CENTER_PLAYBOOK["left"]


def test_maps_center_middle_left_to_sequence(monkeypatch):
    # The middle bands (Travis's calibration) are now reachable via polygons.
    monkeypatch.setattr(pb.zones, "select", lambda u, v: (PlayerID.CENTER, "middle_left"))
    player, seq = pb.select_playbook(0.5, 0.5)
    assert player == PlayerID.CENTER
    assert seq is pb._CENTER_PLAYBOOK["middle_left"]


def test_right_wing_goes_through_get_rw_sequence(monkeypatch):
    monkeypatch.setattr(pb.zones, "select", lambda u, v: (PlayerID.RIGHT_WING, "left"))
    player, seq = pb.select_playbook(0.5, 0.5)
    assert player == PlayerID.RIGHT_WING
    assert seq == pb.get_rw_sequence("left", "shot")


def test_no_zone_returns_none(monkeypatch):
    monkeypatch.setattr(pb.zones, "select", lambda u, v: (None, None))
    assert pb.select_playbook(0.5, 0.5) == (None, None)
