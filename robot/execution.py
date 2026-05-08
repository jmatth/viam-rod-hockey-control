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


async def execute_sequence(sequence, player_id=PlayerID.CENTER):
    """Send each step in `sequence` to the player's hockey-player component via DoCommand.

    Each step is a dict matching the DoCommand payload (t, r, rpm,
    speed_mm_per_sec -- all optional). After the sequence finishes (or errors
    mid-run), the player that ran is returned to home pose (t=0, r=0). Other
    rods are not touched.
    """
    if not sequence:
        print("Empty sequence.")
        return

    component_name = _PLAYER_TO_COMPONENT[player_id]
    print(f"Executing sequence ({len(sequence)} steps, player={player_id.name}, component={component_name})")

    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        player = Generic.from_robot(robot=robot, name=component_name)
        for step in sequence:
            await player.do_command(step)
    finally:
        # Return the active rod to home pose, even on mid-sequence error
        print(f"Returning {component_name} to home pose.")
        await Generic.from_robot(robot=robot, name=component_name).do_command({"t": 0.0, "r": 0.0})
        await robot.close()

    print("Done.")
