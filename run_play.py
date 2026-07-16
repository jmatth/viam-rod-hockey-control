"""Run a specific playbook for a single player.

Usage:
  python3 run_play.py --player center --side left
  python3 run_play.py --player left_d --side right
  python3 run_play.py --player right_wing --side left --action shot

Players: center, left_d, right_d, left_wing, right_wing
Sides:   left, right
Actions: shot, pass, bottom_shot, bottom_pass  (right_wing only)
"""

import argparse
import asyncio

from engine.constants import PlayerID
from robot.execution import execute_sequence
from robot.logging_setup import configure as configure_logging
from robot.playbook import (
    _CENTER_PLAYBOOK,
    _LEFT_D_PLAYBOOK,
    _RIGHT_D_PLAYBOOK,
    _LEFT_WING_PLAYBOOK,
    get_rw_sequence,
)

_PLAYER_MAP = {
    "center":     PlayerID.CENTER,
    "left_d":     PlayerID.LEFT_D,
    "right_d":    PlayerID.RIGHT_D,
    "left_wing":  PlayerID.LEFT_WING,
    "right_wing": PlayerID.RIGHT_WING,
}

_PLAYBOOKS = {
    "center":    _CENTER_PLAYBOOK,
    "left_d":    _LEFT_D_PLAYBOOK,
    "right_d":   _RIGHT_D_PLAYBOOK,
    "left_wing": _LEFT_WING_PLAYBOOK,
}


def get_sequence(player: str, side: str, action: str):
    if player == "right_wing":
        if side in ("bottom_left", "bottom_right"):
            return get_rw_sequence(side, "bottom_shot")
        return get_rw_sequence(side, action)
    return _PLAYBOOKS[player][side]


async def main():
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--player", required=True, choices=_PLAYER_MAP.keys())
    parser.add_argument("--side", required=True, choices=["left", "right", "bottom_left", "bottom_right"])
    parser.add_argument("--action", default="shot", choices=["shot", "pass", "bottom_shot", "bottom_pass"])
    args = parser.parse_args()

    sequence = get_sequence(args.player, args.side, args.action)
    player_id = _PLAYER_MAP[args.player]

    if args.player == "left_d" and args.side == "right":
        await asyncio.gather(
            execute_sequence(sequence, player_id),
            execute_sequence([{"t": 0.6}], PlayerID.LEFT_WING),
        )
        await execute_sequence([{"t": 0}], PlayerID.LEFT_WING)
    else:
        await execute_sequence(sequence, player_id)


if __name__ == "__main__":
    asyncio.run(main())
