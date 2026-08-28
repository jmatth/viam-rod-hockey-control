from engine.constants import PlayerID

# Config attribute key → PlayerID, in the order deps are declared.
ATTR_TO_PLAYER = {
    "center":     PlayerID.CENTER,
    "left_wing":  PlayerID.LEFT_WING,
    "right_wing": PlayerID.RIGHT_WING,
    "left_d":     PlayerID.LEFT_D,
    "right_d":    PlayerID.RIGHT_D,
}

# Default component name per config attribute key (overridable in config).
DEFAULT_PLAYER_COMPONENTS = {
    "center":     "center-hockey-player",
    "left_wing":  "left-wing-hockey-player",
    "right_wing": "right-wing-hockey-player",
    "left_d":     "left-defense-hockey-player",
    "right_d":    "right-defense-hockey-player",
}

# Default gantry component name per config attribute key (overridable in
# config). One gantry per player rod; homed before the game loop starts.
DEFAULT_PLAYER_GANTRIES = {
    "center_gantry":     "center-gantry",
    "left_wing_gantry":  "left-wing-gantry",
    "right_wing_gantry": "right-wing-gantry",
    "left_d_gantry":     "left-defense-gantry",
    "right_d_gantry":    "right-defense-gantry",
}

# Player attr keys (from ATTR_TO_PLAYER) whose gantries are mounted inverted
# and must home to the far end of travel: their home() call gets
# {"home_position_mm": "max"} as the extra argument. Overridable via the
# "inverted_gantries" config attribute.
DEFAULT_INVERTED_GANTRIES = ["center"]

DEFAULT_VISION_SERVICE = "green-puck-detector"
DEFAULT_CAMERA         = "manual-crop"

PLAYERS = list(DEFAULT_PLAYER_COMPONENTS.values())
