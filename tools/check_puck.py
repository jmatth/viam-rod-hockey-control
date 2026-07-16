# tools/check_puck.py
"""One-shot diagnostic: detect the puck and report which player/zone it falls in.

    make check-puck
    (or: .venv/bin/python tools/check_puck.py)

Vision + zone selection only — does NOT move any rod. Uses the same path the
loop uses: get_puck_field_coordinates() -> zones.select(u, v).
"""

import asyncio
import logging
import os
import sys

# Allow running directly as `python tools/check_puck.py`: repo root on sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot.vision import get_puck_field_coordinates, _reset_machine
from robot.zones import select
from robot.logging_setup import configure as configure_logging

log = logging.getLogger(__name__)


async def main():
    try:
        u, v = await get_puck_field_coordinates()
    except Exception as e:
        log.error("Error reaching robot/vision: %s: %s", type(e).__name__, e)
        return
    finally:
        await _reset_machine()

    if u is None:
        log.info("No puck detected.")
        return

    log.info("Puck found at  u=%.3f  v=%.3f", u, v)
    player, side = select(u, v)
    if player is None:
        log.info("Puck is in NO zone — no player would act on it.")
    else:
        log.info("  player: %s", player.name)
        log.info("  zone:   %s", side)


if __name__ == "__main__":
    # quiet_viam keeps the SDK's routine INFO connection logs out of the report.
    configure_logging(quiet_viam=True)
    asyncio.run(main())
