"""Read a hockey-player rod's current state via the module's get_position command.

The hockey-player module returns {"t", "r", "t_moving", "r_moving"} for
{"cmd": "get_position"}. Phase A uses this for observability; B/C consume it to
steer plays.
"""

import asyncio
import logging
import sys

from viam.robot.client import RobotClient
from viam.components.generic import Generic

from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID, PLAYER_TO_COMPONENT
from engine.constants import PlayerID

log = logging.getLogger(__name__)


async def get_player_position(player_id: PlayerID) -> dict:
    """Return {"t", "r", "t_moving", "r_moving"} for the given player's rod."""
    component_name = PLAYER_TO_COMPONENT[player_id]
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        player = Generic.from_robot(robot=robot, name=component_name)
        return await player.do_command({"cmd": "get_position"})
    finally:
        await robot.close()


# Smoke test:  .venv/bin/python -m robot.state center
_ARG_TO_PLAYER = {
    "center": PlayerID.CENTER, "right_wing": PlayerID.RIGHT_WING,
    "left_wing": PlayerID.LEFT_WING, "right_d": PlayerID.RIGHT_D, "left_d": PlayerID.LEFT_D,
}

if __name__ == "__main__":
    from .logging_setup import configure
    configure()
    name = sys.argv[1] if len(sys.argv) > 1 else "center"
    pos = asyncio.run(get_player_position(_ARG_TO_PLAYER[name]))
    log.info("%s: %s", name, pos)
