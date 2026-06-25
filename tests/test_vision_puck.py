# tests/test_vision_puck.py
from types import SimpleNamespace

from robot.vision import puck_uv_from_detections


def _det(cls, xmn, ymn, xmx, ymx):
    return SimpleNamespace(
        class_name=cls,
        x_min_normalized=xmn, y_min_normalized=ymn,
        x_max_normalized=xmx, y_max_normalized=ymx,
    )


def test_no_orange_returns_none():
    dets = [_det("lime-green", 0.1, 0.1, 0.2, 0.2)]
    assert puck_uv_from_detections(dets) == (None, None)


def test_single_orange_center():
    dets = [_det("orange", 0.4, 0.6, 0.6, 0.8)]
    assert puck_uv_from_detections(dets) == (0.5, 0.7)


def test_averages_multiple_orange():
    dets = [_det("orange", 0.0, 0.0, 0.2, 0.2), _det("orange", 0.8, 0.8, 1.0, 1.0)]
    # centers (0.1,0.1) and (0.9,0.9) -> mean (0.5, 0.5)
    u, v = puck_uv_from_detections(dets)
    assert round(u, 6) == 0.5 and round(v, 6) == 0.5
