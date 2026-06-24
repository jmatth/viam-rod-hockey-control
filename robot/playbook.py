"""Calibrated instruction playbooks for each player.

Each step is a dict matching the hockey-player module's DoCommand payload:
  {"t": 0.5, "r": 90, "rpm": 30, "speed_mm_per_sec": 100}

Fields (all optional; omit to skip an axis or use config defaults):
  t                 : translation target, normalized over [min_translation_mm,
                      max_translation_mm]. Range [0, 1].
  r                 : rotation target in degrees. Range [0, 360].
  rpm               : rotation speed (defaults from component config).
  speed_mm_per_sec  : translation speed (defaults from component config).

All values below are placeholders -- calibrate on hardware.
"""

from engine.constants import (
    PlayerID,
    center_x,
    left_d_x,
    LEFT_WING_SEG_B_X_MID,
    right_d_x,
    right_wing_x,
)

# Puck zone boundaries — adjust these to tune which player handles each region.
# All values in game pixels (x: 0–450 width, y: 0–838 length).
# Zones are checked in order; first match wins.
# LEFT_WING entries are first because their y range covers the behind-goal
# area that would otherwise fall inside the LEFT_D x range.
_ZONES = [
    # LEFT_WING — behind goal (checked first; y overrides x-based zones below)
    {"player": PlayerID.LEFT_WING,  "side": "bottom_right",  "x_min":  45, "x_max": 155, "y_min": 230, "y_max": 255},
    {"player": PlayerID.LEFT_WING,  "side": "bottom_right",  "x_min":  45, "x_max": 75, "y_min": 110, "y_max": 230},
    {"player": PlayerID.LEFT_WING,  "side": "bottom_left",  "x_min":  45, "x_max": 155, "y_min": 255, "y_max": 280},
    {"player": PlayerID.LEFT_WING,  "side": "bottom_left",  "x_min":  0, "x_max": 45, "y_min": 110, "y_max": 280},
    # LEFT_WING — normal play (near left goal; tune x bounds to match physical reach)
    {"player": PlayerID.LEFT_WING,  "side": "right",        "x_min": 120, "x_max": 210, "y_min": 230, "y_max": 255},
    {"player": PlayerID.LEFT_WING,  "side": "left",         "x_min": 120, "x_max": 210, "y_min": 255, "y_max": 280},
    # RIGHT_WING — normal play
    {"player": PlayerID.RIGHT_WING, "side": "left",         "x_min": 155, "x_max": 320, "y_min": 25, "y_max": 75},
    {"player": PlayerID.RIGHT_WING, "side": "right",        "x_min": 155, "x_max": 320, "y_min": 0, "y_max": 25},
    # RIGHT_WING — bottom
    {"player": PlayerID.RIGHT_WING, "side": "bottom_left",  "x_min": 0, "x_max": 155, "y_min": 25, "y_max": 75},
    {"player": PlayerID.RIGHT_WING, "side": "bottom_right", "x_min": 0, "x_max": 155, "y_min": 0, "y_max": 25},
    # RIGHT_D
    {"player": PlayerID.RIGHT_D,    "side": "right",        "x_min": 320, "x_max": 485, "y_min": 65, "y_max": 90},
    {"player": PlayerID.RIGHT_D,    "side": "left",         "x_min": 320, "x_max": 485, "y_min": 90, "y_max": 115},
    # CENTER
    {"player": PlayerID.CENTER,     "side": "right",        "x_min": 130, "x_max": 320, "y_min":  85, "y_max": 135},
    {"player": PlayerID.CENTER,     "side": "left",         "x_min": 130, "x_max": 320, "y_min": 135, "y_max": 165},
    # LEFT_D
    {"player": PlayerID.LEFT_D,     "side": "right",        "x_min": 278.5, "x_max": 530, "y_min":   185, "y_max": 210},
    {"player": PlayerID.LEFT_D,     "side": "left",         "x_min": 278.5, "x_max": 530, "y_min":   210, "y_max": 235},
]



# ── Center player playbook ─────────────────────────────────────────────────────
#
# X-axis: right (puck_x < center_x, closer to 0) vs left (puck_x >= center_x).

CENTER_LEFT = [
    {"t": 0.95, "r": 100},  # TODO: calibrate -- center, puck on left
    {"r": 300, "rpm": 400, "direction": "ccw"},
]

CENTER_MIDDLE_LEFT = [
    {"t": 0.95, "r": 100},
    {"r": 220, "rpm": 20, "direction": "ccw"},
    {"r": 0, "rpm": 250, "direction": "cw"},
    {"r": 90, "rpm": 1000, "direction": "cw"},
]

CENTER_MIDDLE_RIGHT = [
    {"t": 0.95, "r": 260},
    {"r": 150, "rpm": 20, "direction": "cw"},
    {"r": 0, "rpm": 250, "direction": "ccw"},
    {"r": 270, "rpm": 1000, "direction": "ccw"},
]

CENTER_RIGHT = [
    {"t": 0.95, "r": 260},  # TODO: calibrate -- center, puck on right
    {"r": 60, "rpm": 400, "direction": "cw"},
]

_CENTER_PLAYBOOK = {
    "left":         CENTER_LEFT,
    "middle_left":  CENTER_MIDDLE_LEFT,
    "middle_right": CENTER_MIDDLE_RIGHT,
    "right":        CENTER_RIGHT,
}


# ── Right wing playbook ────────────────────────────────────────────────────────
#
# Two-phase: position sequence + action sequence, concatenated at runtime.
# e.g. RIGHT_WING_LEFT + RIGHT_WING_SHOT.

# Position sequences -- move puck to sweet spot
RIGHT_WING_LEFT = [
    {"t": 0.5, "r": 125, "speed_mm_per_sec": 10000},  # TODO: calibrate -- right wing position, puck on left
    {"t": 0.485, "r": 180, "direction": "ccw", "speed_mm_per_sec": 10000},
    {"r": 0, "rpm": 150},
]

RIGHT_WING_RIGHT = [
    {"t": 0.5, "r": 265, "speed_mm_per_sec": 10000},  # TODO: calibrate -- right wing position, puck on right
    {"r": 60, "rpm": 300, "direction": "ccw"},
]

RIGHT_WING_BOTTOM_LEFT = [
    {"t": 1, "r": 0.0, "speed_mm_per_sec": 10000},  # TODO: calibrate -- right wing position, puck bottom-left
    {"r": 80, "direction": "ccw"},
    {"t": 0.5, "speed_mm_per_sec": 10000},
    {"t": 0.525, "r": 270, "direction": "cw", "speed_mm_per_sec": 10000},
    {"t": 0.5, "r": 180, "rpm": 400, "direction": "cw", "speed_mm_per_sec": 10000},
]

RIGHT_WING_BOTTOM_RIGHT = [
    {"t": 1, "r": 0.0, "speed_mm_per_sec": 10000},  # TODO: calibrate -- right wing position, puck bottom-right
    {"r": 295, "direction": "cw"},
    {"t": 0.50, "speed_mm_per_sec": 10000},
    {"r": 60, "rpm": 260},
]

# Action sequences -- execute the play
RIGHT_WING_SHOT = [
    {"t": 0.0, "r": 0.0},  # TODO: calibrate -- right wing shot
]

RIGHT_WING_PASS = [
    {"t": 0.0, "r": 0.0},  # TODO: calibrate -- right wing pass
]

RIGHT_WING_BOTTOM_SHOT = [
    {"t": 0.0, "r": 0.0},  # TODO: calibrate -- right wing bottom shot
]

RIGHT_WING_BOTTOM_PASS = [
    {"t": 0.0, "r": 0.0},  # TODO: calibrate -- right wing bottom pass
]

_RIGHT_WING_POSITIONS = {
    "left":         RIGHT_WING_LEFT,
    "right":        RIGHT_WING_RIGHT,
    "bottom_left":  RIGHT_WING_BOTTOM_LEFT,
    "bottom_right": RIGHT_WING_BOTTOM_RIGHT,
}

_RIGHT_WING_ACTIONS = {
    "shot":        RIGHT_WING_SHOT,
    "pass":        RIGHT_WING_PASS,
    "bottom_shot": RIGHT_WING_BOTTOM_SHOT,
    "bottom_pass": RIGHT_WING_BOTTOM_PASS,
}


def get_rw_sequence(side: str, action: str) -> list:
    """Combine a position and action sequence for the right wing."""
    return _RIGHT_WING_POSITIONS[side] + _RIGHT_WING_ACTIONS[action]


# ── Right defenseman playbook ──────────────────────────────────────────────────

RIGHT_D_LEFT = [
    {"r": 100},              # rotate to position first
    {"t": 0.95},             # then translate
    {"r": 300, "direction": "cw", "rpm": 220},
]

RIGHT_D_RIGHT = [
    {"t": 1, "r": 260},  # TODO: calibrate -- right D, puck on left
    {"r": 60, "direction": "ccw", "rpm": 200},
]

_RIGHT_D_PLAYBOOK = {
    "left":  RIGHT_D_LEFT,
    "right": RIGHT_D_RIGHT,
}


# ── Left defenseman playbook ───────────────────────────────────────────────────

LEFT_D_LEFT = [
    {"t": 0.8, "r": 115},  # TODO: calibrate -- left D, puck on left (pass to center)
    {"r": 300, "direction": "cw", "rpm": 220},
]

LEFT_D_RIGHT = [
    {"t": 0.8, "r": 255, "direction": "ccw"},  # TODO: calibrate -- left D, puck on right (pass to center)
    {"r": 60, "direction": "ccw", "rpm": 220},
]

_LEFT_D_PLAYBOOK = {
    "left":  LEFT_D_LEFT,
    "right": LEFT_D_RIGHT,
}


# ── Left wing playbook ─────────────────────────────────────────────────────────
#
# Zones are 2D (x + y), but playbook uses simple left/right for now.

LEFT_WING_LEFT = [
    {"t": 0.2, "r": 120, "speed_mm_per_sec": 10000},  # TODO: calibrate -- left wing, puck on left
    {"r": 300, "rpm": 400, "direction": "cw"},
]

LEFT_WING_RIGHT = [  # TODO: calibrate -- left wing, puck on right
    {"t": 0.35, "r": 260, "speed_mm_per_sec": 10000},
    {"t": 0.34, "r": 90, "direction": "cw", "speed_mm_per_sec": 10000},
    {"r": 300, "rpm": 1000, "direction": "cw"},
]

LEFT_WING_BOTTOM_LEFT = [
    {"t": 0.5, "r": 110, "speed_mm_per_sec": 10000},  # TODO: calibrate -- left wing, puck bottom-left
    {"t": 0.75, "r": 150, "speed_mm_per_sec": 10000},
    {"t": 1, "r": 120, "direction": "ccw", "speed_mm_per_sec": 10000},
    {"r": 100, "direction": "ccw"},
    {"r": 300, "rpm": 200, "direction": "cw"},
]

LEFT_WING_BOTTOM_RIGHT = [
    {"t": 0.5, "r": 270, "speed_mm_per_sec": 10000},  # TODO: calibrate -- left wing, puck bottom-right
    {"t": 1, "r": 320, "direction": "cw", "speed_mm_per_sec": 10000},
    {"r": 100, "rpm": 300, "direction": "ccw"},
]

_LEFT_WING_PLAYBOOK = {
    "left":         LEFT_WING_LEFT,
    "right":        LEFT_WING_RIGHT,
    "bottom_left":  LEFT_WING_BOTTOM_LEFT,
    "bottom_right": LEFT_WING_BOTTOM_RIGHT,
}


# ── Public API ─────────────────────────────────────────────────────────────────

def _center_side(puck_x: float) -> str:
    return "right" if puck_x < center_x else "left"  # x closer to 0 = right


def get_instructions(puck_x: float, puck_y: float, player_id: PlayerID = PlayerID.CENTER):  # noqa: ARG001
    """Return the calibrated instruction sequence for the given player and puck position."""
    if player_id == PlayerID.CENTER:
        side = _center_side(puck_x)
        print(f"Center side: {side}  (puck_x={puck_x:.0f})")
        return _CENTER_PLAYBOOK[side]

    if player_id == PlayerID.RIGHT_WING:
        side = "left" if puck_x < right_wing_x else "right"
        action = "shot"  # default; caller can override via get_rw_sequence directly
        print(f"Right wing side: {side}  (puck_x={puck_x:.0f})")
        return get_rw_sequence(side, action)

    if player_id == PlayerID.RIGHT_D:
        side = "right" if puck_x < right_d_x else "left"
        print(f"Right D side: {side}  (puck_x={puck_x:.0f})")
        return _RIGHT_D_PLAYBOOK[side]

    if player_id == PlayerID.LEFT_D:
        side = "right" if puck_x < left_d_x else "left"
        print(f"Left D side: {side}  (puck_x={puck_x:.0f})")
        return _LEFT_D_PLAYBOOK[side]

    if player_id == PlayerID.LEFT_WING:
        lw_zone = next(z for z in _ZONES if z["player"] == PlayerID.LEFT_WING)
        if puck_y >= lw_zone["y_min"]:
            side = "bottom_right" if puck_x < LEFT_WING_SEG_B_X_MID else "bottom_left"
        else:
            side = "right" if puck_x < LEFT_WING_SEG_B_X_MID else "left"
        print(f"Left Wing side: {side}  (puck_x={puck_x:.0f}, puck_y={puck_y:.0f})")
        return _LEFT_WING_PLAYBOOK[side]

    return None


# Center rod angle — two calibration points in camera pixel space.
# Tune these to match the physical angle of the center rod.
_CENTER_X1, _CENTER_Y1 = 150, 140
_CENTER_X2, _CENTER_Y2 = 300, 125

def _center_line_y(puck_x: float) -> float:
    """Y midpoint of the center rod at a given camera x (linear interpolation)."""
    slope = (_CENTER_Y2 - _CENTER_Y1) / (_CENTER_X2 - _CENTER_X1)
    return _CENTER_Y1 + slope * (puck_x - _CENTER_X1)


# Four measured points along the left wing's curved rod section.
_LW_CURVE_POINTS = [(20.5, 118.0), (21.5, 204.5), (34.5, 238.0), (81.5, 256.5)]


def _left_wing_curve_y(puck_x: float) -> float:
    """Y midpoint of the left wing rod at a given camera x (piecewise linear)."""
    pts = _LW_CURVE_POINTS
    if puck_x <= pts[0][0]:
        return pts[0][1]
    if puck_x >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= puck_x <= x1:
            t = (puck_x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return pts[-1][1]


_PLAYBOOK_MAP = {
    PlayerID.CENTER:    _CENTER_PLAYBOOK,
    PlayerID.RIGHT_D:   _RIGHT_D_PLAYBOOK,
    PlayerID.LEFT_D:    _LEFT_D_PLAYBOOK,
    PlayerID.LEFT_WING: _LEFT_WING_PLAYBOOK,
}


def _select_zone(puck_x: float, puck_y: float):
    for zone in _ZONES:
        if zone["x_min"] <= puck_x < zone["x_max"] and zone["y_min"] <= puck_y < zone["y_max"]:
            return zone
    return None


def select_playbook(puck_x: float, puck_y: float):
    """Return (PlayerID, sequence) for the given puck position, or (None, None)."""
    zone = _select_zone(puck_x, puck_y)
    if zone is None:
        return None, None
    player_id = zone["player"]
    side = zone["side"]
    if player_id == PlayerID.CENTER:
        mid = _center_line_y(puck_x)
        if puck_y < mid - 15:
            side = "right"
        elif puck_y < mid - 3:
            side = "middle_right"
        elif puck_y < mid + 10:
            side = "middle_left"
        else:
            side = "left"
    if player_id == PlayerID.LEFT_WING and side in ("bottom_left", "bottom_right"):
        curve_y = _left_wing_curve_y(puck_x)
        side = "bottom_right" if puck_y < curve_y else "bottom_left"
    print(f"{player_id.name} side: {side}  (puck_x={puck_x:.0f}, puck_y={puck_y:.0f})")
    if player_id == PlayerID.RIGHT_WING:
        return player_id, get_rw_sequence(side, "shot")
    return player_id, _PLAYBOOK_MAP[player_id][side]
