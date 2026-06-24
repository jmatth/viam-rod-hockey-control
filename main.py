"""
Main entry point for the bubble hockey robot.

Pipeline:
  1. Vision   — detect puck position from camera
  2. Playbook — look up calibrated instruction sequence
  3. Execution — send motor commands to the robot

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

Loop mode (polls vision every 2 seconds):
  python main.py --loop
"""

import asyncio
import argparse

from robot.vision import get_puck_camera_coordinates
from robot.playbook import get_rw_sequence, select_playbook, _CENTER_PLAYBOOK, _RIGHT_D_PLAYBOOK, _LEFT_D_PLAYBOOK, _LEFT_WING_PLAYBOOK
from robot.execution import execute_sequence
from engine.constants import PlayerID


def parse_args():
    parser = argparse.ArgumentParser(description="Bubble hockey robot")

    parser.add_argument("--loop", action="store_true", help="Poll vision every 2 seconds and act when puck is detected")

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


async def get_puck_coordinates():
    """Return (camera_x, camera_y) from vision, or (None, None) if no puck detected."""
    return await get_puck_camera_coordinates()


async def run_playbook_from_puck_position():
    """Detect puck, select playbook, and execute. Returns True if an action was taken."""
    puck_x, puck_y = await get_puck_coordinates()
    if puck_x is None:
        print("No puck detected.")
        return False
    print(f"Puck detected at: x={puck_x:.1f}, y={puck_y:.1f}")

    player, sequence = select_playbook(puck_x, puck_y)
    if not sequence:
        print("No playbook for this position.")
        return False

    await execute_with_coordination(player, sequence)
    return True


async def execute_with_coordination(player, sequence):
    """Execute a playbook sequence, with any multi-player coordination."""
    if player == PlayerID.LEFT_D and sequence is _LEFT_D_PLAYBOOK["right"]:
        await asyncio.gather(
            execute_sequence(sequence, player),
            execute_sequence([{"t": 0.25}], PlayerID.LEFT_WING, post_delay=3),
        )
    elif player == PlayerID.LEFT_WING and sequence in (
        _LEFT_WING_PLAYBOOK["bottom_left"], _LEFT_WING_PLAYBOOK["bottom_right"]
    ):
        await asyncio.gather(
            execute_sequence(sequence, player),
            execute_sequence([{"t": 0.75}], PlayerID.RIGHT_WING, skip_reset=True),
        )
    else:
        await execute_sequence(sequence, player)


async def run_loop(poll_interval=0.25, stability_threshold=15, stability_delay=0.15):
    """Continuously poll the puck and run playbooks.

    Takes two readings separated by stability_delay seconds. Only fires if the
    puck hasn't moved more than stability_threshold pixels between them, so
    playbooks don't trigger while the puck is in motion.

    Multiple players can run in parallel. If the detected player already has a
    playbook running, that trigger is skipped until the player is free.
    """
    _VISION_TIMEOUT  = 15.0
    _EXECUTE_TIMEOUT = 30.0
    _ERROR_SLEEP     = 1.0

    _FORWARDS = {PlayerID.CENTER, PlayerID.LEFT_WING, PlayerID.RIGHT_WING}

    player_tasks: dict = {}

    async def _fire(player, sequence):
        try:
            await asyncio.wait_for(execute_with_coordination(player, sequence), timeout=_EXECUTE_TIMEOUT)
        except Exception as e:
            print(f"{player.name} playbook error: {e}")

    print(f"Loop mode — polling every {poll_interval}s. Press Ctrl+C to stop.")
    while True:
        try:
            x1, y1 = await asyncio.wait_for(get_puck_coordinates(), timeout=_VISION_TIMEOUT)
            if x1 is None:
                print("No puck detected.")
                await asyncio.sleep(poll_interval)
                continue

            await asyncio.sleep(stability_delay)

            x2, y2 = await asyncio.wait_for(get_puck_coordinates(), timeout=_VISION_TIMEOUT)
            if x2 is None:
                await asyncio.sleep(poll_interval)
                continue

            dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            if dist > stability_threshold:
                print(f"Puck moving ({dist:.1f}px delta) — skipping.")
                await asyncio.sleep(poll_interval)
                continue

            puck_x = (x1 + x2) / 2
            puck_y = (y1 + y2) / 2
            print(f"Puck stable at: x={puck_x:.1f}, y={puck_y:.1f}")

            player, sequence = select_playbook(puck_x, puck_y)
            if not sequence:
                print("No playbook for this position.")
            elif player in _FORWARDS:
                task = player_tasks.get(player)
                if task and not task.done():
                    print(f"{player.name} busy — skipping.")
                else:
                    player_tasks[player] = asyncio.create_task(_fire(player, sequence))
            else:  # defense
                task = player_tasks.get(player)
                if task and not task.done():
                    print(f"{player.name} busy — skipping.")
                else:
                    player_tasks[player] = asyncio.create_task(_fire(player, sequence))

            await asyncio.sleep(poll_interval)
        except BaseException as e:
            print(f"Error: {e} — retrying in {_ERROR_SLEEP:.0f}s.")
            await asyncio.sleep(_ERROR_SLEEP)


async def run_once(args):
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
        print(f"Manual override: player={player.name}")
        await execute_sequence(sequence, player)
        return True

    return await run_playbook_from_puck_position()


async def main():
    args = parse_args()

    if args.loop:
        await run_loop()
    else:
        await run_once(args)


if __name__ == "__main__":
    asyncio.run(main())
