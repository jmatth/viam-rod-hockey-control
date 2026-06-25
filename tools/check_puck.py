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

# Quiet Viam's routine INFO connection logs (warnings/errors still show). A global
# disable beats per-logger levels, which the SDK reconfigures at connect time.
logging.disable(logging.INFO)

# Allow running directly as `python tools/check_puck.py`: repo root on sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from robot.vision import get_puck_field_coordinates, _reset_machine
from robot.zones import select


async def main():
    try:
        u, v = await get_puck_field_coordinates()
    except Exception as e:
        print(f"Error reaching robot/vision: {type(e).__name__}: {e}")
        return
    finally:
        await _reset_machine()

    if u is None:
        print("No puck detected.")
        return

    print(f"Puck found at  u={u:.3f}  v={v:.3f}")
    player, side = select(u, v)
    if player is None:
        print("Puck is in NO zone — no player would act on it.")
    else:
        print(f"  player: {player.name}")
        print(f"  zone:   {side}")


if __name__ == "__main__":
    asyncio.run(main())
