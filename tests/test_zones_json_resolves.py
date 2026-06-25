"""Guard: every zone in the shipped robot/zones.json resolves to a real motor
sequence through select_playbook. Catches future zone/playbook drift (e.g. a
zone whose (player, side) has no entry in the playbook tables)."""

from robot.zones import load_zones
from robot.playbook import select_playbook


def _centroid(polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def test_every_shipped_zone_resolves_to_a_sequence():
    zones = load_zones()
    assert zones, "zones.json is empty"
    for player_id, side, polygon in zones:
        u, v = _centroid(polygon)
        got_player, seq = select_playbook(u, v)
        assert got_player is not None, f"no zone matched centroid of {player_id}/{side}"
        assert seq, f"empty sequence for centroid of {player_id}/{side} -> {got_player}"
