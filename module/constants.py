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

DEFAULT_VISION_SERVICE = "green-puck-detector"
DEFAULT_CAMERA         = "dynamic-crop"

PLAYERS = list(DEFAULT_PLAYER_COMPONENTS.values())
