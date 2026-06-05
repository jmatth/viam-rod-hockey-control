import asyncio

from viam.robot.client import RobotClient
from viam.components.generic import Generic

from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID
from engine.constants import PlayerID


_PLAYER_TO_COMPONENT = {
    PlayerID.CENTER:     "center-hockey-player",
    PlayerID.RIGHT_WING: "right-wing-hockey-player",
    PlayerID.LEFT_WING:  "left-wing-hockey-player",
    PlayerID.RIGHT_D:    "right-defense-hockey-player",
    PlayerID.LEFT_D:     "left-defense-hockey-player",
}

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


async def execute_sequence(sequence, player_id=PlayerID.CENTER, post_delay=0):
    """Send each step in `sequence` to the player's hockey-player component via DoCommand.

    Each step is a dict matching the DoCommand payload (t, r, rpm,
    speed_mm_per_sec -- all optional). After the sequence finishes (or errors
    mid-run), the player is returned to home pose (t=0, r=0).
    Reuses a persistent robot connection; reconnects automatically on error.
    """
    if not sequence:
        print("Empty sequence.")
        return

    component_name = _PLAYER_TO_COMPONENT[player_id]
    print(f"Executing sequence ({len(sequence)} steps, player={player_id.name}, component={component_name})")

    reset_cmd = {"t": 0, "r": 0}
    if player_id in (PlayerID.LEFT_WING, PlayerID.RIGHT_WING):
        reset_cmd["speed_mm_per_sec"] = 10000

    try:
        robot = await _get_robot()
        player = Generic.from_robot(robot=robot, name=component_name)
        for step in sequence:
            await player.do_command(step)
        if post_delay:
            await asyncio.sleep(post_delay)
        await player.do_command(reset_cmd)
    except Exception:
        await _reset_robot()
        try:
            robot = await _get_robot()
            await Generic.from_robot(robot=robot, name=component_name).do_command(reset_cmd)
            print(f"Returned {component_name} to home pose after error.")
        except Exception as e:
            print(f"Failed to reset {component_name} to home: {e}")
        raise

    print("Done.")
