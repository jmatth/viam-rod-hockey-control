import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
#  Robot connection
# ============================================================

# Primary part, right wing player + camera. All other parts are configured as
# remotes w/ prefixes.
ROBOT_ADDRESS    = os.getenv('ROBOT_ADDRESS')
ROBOT_API_KEY    = os.getenv('ROBOT_API_KEY')
ROBOT_API_KEY_ID = os.getenv('ROBOT_API_KEY_ID')

# ============================================================
#  Camera → game coordinate mapping
# ============================================================

# Real camera pixel range for the puck's x and y
CAMERA_X_MIN = 143.5
CAMERA_X_MAX = 206.5
CAMERA_Y_MIN = 196.0
CAMERA_Y_MAX = 295.0

# ============================================================
#  Motor config
# ============================================================

# Encoder ticks per full motor rotation (set in Viam motor config)
TICKS_PER_ROTATION = 200

# Lateral slide tick limits (0 = home position)
CENTER_SLIDE_MAX_TICKS = 500   # TODO: calibrate full travel
RW_SLIDE_MAX_TICKS     = 500   # TODO: calibrate full travel

# ============================================================
#  Player → Viam component name
# ============================================================

from engine.constants import PlayerID

PLAYER_TO_COMPONENT = {
    PlayerID.CENTER:     "center-hockey-player",
    PlayerID.RIGHT_WING: "right-wing-hockey-player",
    PlayerID.LEFT_WING:  "left-wing-hockey-player",
    PlayerID.RIGHT_D:    "right-defense-hockey-player",
    PlayerID.LEFT_D:     "left-defense-hockey-player",
}
