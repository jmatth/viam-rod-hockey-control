"""Client-mode connection helpers.

Used by the standalone CLI entry points (main.py, run_play.py, tools/) that dial
the robot over the network with API-key credentials from .env. The Viam module
path does NOT use this — inside viam-server, resources arrive via dependency
injection (see module/models/rod_hockey_game.py).
"""

import logging

from viam.robot.client import RobotClient
from viam.components.generic import Generic
from viam.services.vision import VisionClient

from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID, PLAYER_TO_COMPONENT

log = logging.getLogger(__name__)

VISION_SERVICE_NAME = "green-puck-detector"
CAMERA_NAME = "dynamic-crop"


async def connect() -> RobotClient:
    """Dial the robot using API-key credentials from the environment."""
    opts = RobotClient.Options.with_api_key(api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID)
    return await RobotClient.at_address(ROBOT_ADDRESS, opts)


def players_from_robot(robot: RobotClient) -> dict:
    """Return {PlayerID: Generic component} for every hockey-player rod."""
    return {
        player_id: Generic.from_robot(robot=robot, name=component_name)
        for player_id, component_name in PLAYER_TO_COMPONENT.items()
    }


def vision_from_robot(robot: RobotClient, name: str = VISION_SERVICE_NAME) -> VisionClient:
    """Return the puck-detector vision service."""
    return VisionClient.from_robot(robot, name)
