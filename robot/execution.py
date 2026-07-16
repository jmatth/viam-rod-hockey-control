import asyncio
import logging

from viam.robot.client import RobotClient
from viam.components.generic import Generic

from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID, PLAYER_TO_COMPONENT
from engine.constants import PlayerID


log = logging.getLogger(__name__)

_robot = None


async def _get_robot():
    global _robot
    if _robot is None:
        opts = RobotClient.Options.with_api_key(api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID)
        _robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    return _robot


async def _reset_robot():
    global _robot
    if _robot is not None:
        try:
            await _robot.close()
        except Exception:
            pass
        _robot = None


async def execute_sequence(sequence, player_id=PlayerID.CENTER, post_delay=0, skip_reset=False):
    """Send each step in `sequence` to the player's hockey-player component via DoCommand.

    Each step is a dict matching the DoCommand payload (t, r, rpm,
    speed_mm_per_sec -- all optional). After the sequence finishes (or errors
    mid-run), the player is returned to home pose (t=0, r=0).
    Reuses a persistent robot connection; reconnects automatically on error.
    """
    if not sequence:
        log.warning("Empty sequence.")
        return

    component_name = PLAYER_TO_COMPONENT[player_id]
    log.info("Executing sequence (%d steps, player=%s, component=%s)",
             len(sequence), player_id.name, component_name)

    reset_cmd = {"t": 0, "r": 0}
    if player_id in (PlayerID.LEFT_WING, PlayerID.RIGHT_WING):
        reset_cmd["speed_mm_per_sec"] = 10000

    try:
        robot = await _get_robot()
        player = Generic.from_robot(robot=robot, name=component_name)
        for step in sequence:
            result = await player.do_command(step)
            log.debug("step %s -> %s", step, result)
        if post_delay:
            await asyncio.sleep(post_delay)
        if not skip_reset:
            await player.do_command(reset_cmd)
    except Exception:
        await _reset_robot()
        try:
            robot = await _get_robot()
            await Generic.from_robot(robot=robot, name=component_name).do_command(reset_cmd)
            log.warning("Returned %s to home pose after error.", component_name)
        except Exception:
            log.exception("Failed to reset %s to home.", component_name)
        raise

    log.info("Done.")
