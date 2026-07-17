import asyncio
import logging
from typing import Mapping

from viam.components.generic import Generic

from engine.constants import PlayerID


log = logging.getLogger(__name__)

_WINGS = (PlayerID.LEFT_WING, PlayerID.RIGHT_WING)


def home_command(player_id: PlayerID) -> dict:
    """Return the DoCommand payload that sends a player back to home pose."""
    cmd = {"t": 0, "r": 0}
    if player_id in _WINGS:
        cmd["speed_mm_per_sec"] = 10000
    return cmd


async def execute_sequence(
    sequence,
    player_id: PlayerID,
    players: Mapping[PlayerID, Generic],
    post_delay: float = 0,
    skip_reset: bool = False,
):
    """Send each step in `sequence` to the player's hockey-player component via DoCommand.

    `players` maps PlayerID to the Generic hockey-player component — injected by
    the module (dependencies) or built from a RobotClient (robot.connection).
    Each step is a dict matching the DoCommand payload (t, r, rpm,
    speed_mm_per_sec -- all optional). After the sequence finishes (or errors
    mid-run), the player is returned to home pose (t=0, r=0).
    """
    if not sequence:
        log.warning("Empty sequence.")
        return

    player = players[player_id]
    log.info("Executing sequence (%d steps, player=%s, component=%s)",
             len(sequence), player_id.name, player.name)

    reset_cmd = home_command(player_id)

    try:
        for step in sequence:
            result = await player.do_command(step)
            log.debug("step %s -> %s", step, result)
        if post_delay:
            await asyncio.sleep(post_delay)
        if not skip_reset:
            await player.do_command(reset_cmd)
    except Exception:
        try:
            await player.do_command(reset_cmd)
            log.warning("Returned %s to home pose after error.", player.name)
        except Exception:
            log.exception("Failed to reset %s to home.", player.name)
        raise

    log.info("Done.")
