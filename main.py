"""
Client-mode entry point for the bubble hockey robot (dials in with .env creds).

Pipeline:
  1. Vision   — detect puck position from camera
  2. Playbook — look up calibrated instruction sequence
  3. Execution — send motor commands to the robot

The same loop also runs on the machine itself as a Viam module (see module.py);
this CLI is kept for bench testing and calibration.

Manual override (skips vision — useful for calibration):
  python main.py --center-left
  python main.py --center-right
  python main.py --rw-shot --left
  python main.py --rw-shot --right
  python main.py --rw-shot --bottom-left
  python main.py --rw-shot --bottom-right
  python main.py --rw-pass --left
  python main.py --rw-pass --right
  python main.py --rw-pass --bottom-left
  python main.py --rw-pass --bottom-right
  python main.py --rd-left
  python main.py --rd-right
  python main.py --ld-left
  python main.py --ld-right
  python main.py --lw-left
  python main.py --lw-right

Loop mode (polls vision continuously):
  python main.py --loop

Add -v/--verbose to any of the above for per-poll vision and per-step motor detail.
"""

import asyncio
import argparse
import logging

from robot.connection import connect, players_from_robot, vision_from_robot
from robot.game_loop import GameLoop
from robot.playbook import get_rw_sequence, _CENTER_PLAYBOOK, _RIGHT_D_PLAYBOOK, _LEFT_D_PLAYBOOK, _LEFT_WING_PLAYBOOK
from robot.execution import execute_sequence
from robot.logging_setup import configure as configure_logging
from engine.constants import PlayerID

log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Bubble hockey robot")

    parser.add_argument("--loop", action="store_true", help="Poll vision continuously and act when puck is detected")
    parser.add_argument("-v", "--verbose", action="store_true", help="Log per-poll vision and per-step motor detail")

    side_group = parser.add_mutually_exclusive_group()
    side_group.add_argument("--left",         action="store_true")
    side_group.add_argument("--right",        action="store_true")
    side_group.add_argument("--bottom-left",  action="store_true")
    side_group.add_argument("--bottom-right", action="store_true")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--center-left",  action="store_true")
    group.add_argument("--center-right", action="store_true")
    group.add_argument("--rw-shot", action="store_true")
    group.add_argument("--rw-pass", action="store_true")
    group.add_argument("--rd-left",  action="store_true")
    group.add_argument("--rd-right", action="store_true")
    group.add_argument("--ld-left",  action="store_true")
    group.add_argument("--ld-right", action="store_true")
    group.add_argument("--lw-left",  action="store_true")
    group.add_argument("--lw-right", action="store_true")

    return parser.parse_args()


def _rw_side(args) -> str:
    if args.right:        return "right"
    if args.bottom_left:  return "bottom_left"
    if args.bottom_right: return "bottom_right"
    return "left"


def _rw_action(args, base: str) -> str:
    """Return the action key, using bottom variant when a bottom side is selected."""
    if args.bottom_left or args.bottom_right:
        return f"bottom_{base}"
    return base


async def run_once(args, loop: GameLoop) -> bool:
    """Run one vision → plan → execute cycle. Returns True if an action was taken."""
    # Manual override — skip vision, infer player from flag
    sequence = None
    player = None
    if args.center_left:  player = PlayerID.CENTER;     sequence = _CENTER_PLAYBOOK["left"]
    if args.center_right: player = PlayerID.CENTER;     sequence = _CENTER_PLAYBOOK["right"]
    if args.rw_shot: player = PlayerID.RIGHT_WING; sequence = get_rw_sequence(_rw_side(args), _rw_action(args, "shot"))
    if args.rw_pass: player = PlayerID.RIGHT_WING; sequence = get_rw_sequence(_rw_side(args), _rw_action(args, "pass"))
    if args.rd_left:  player = PlayerID.RIGHT_D; sequence = _RIGHT_D_PLAYBOOK["left"]
    if args.rd_right: player = PlayerID.RIGHT_D; sequence = _RIGHT_D_PLAYBOOK["right"]
    if args.ld_left:  player = PlayerID.LEFT_D;  sequence = _LEFT_D_PLAYBOOK["left"]
    if args.ld_right: player = PlayerID.LEFT_D;  sequence = _LEFT_D_PLAYBOOK["right"]
    if args.lw_left:  player = PlayerID.LEFT_WING; sequence = _LEFT_WING_PLAYBOOK["left"]
    if args.lw_right: player = PlayerID.LEFT_WING; sequence = _LEFT_WING_PLAYBOOK["right"]

    if sequence:
        log.info("Manual override: player=%s", player.name)
        await execute_sequence(sequence, player, loop.players)
        return True

    return await loop.run_once()


async def main():
    args = parse_args()
    configure_logging(level=logging.DEBUG if args.verbose else logging.INFO)

    robot = await connect()
    try:
        loop = GameLoop(players_from_robot(robot), vision_from_robot(robot))
        if args.loop:
            log.info("Press Ctrl+C to stop.")
            await loop.run()
        else:
            await run_once(args, loop)
    finally:
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
