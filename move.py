"""Ad-hoc: drive every hockey player to a given (t, r) concurrently.

Usage:  python move.py <t> <r>
Example: python move.py 0.5 90
"""

import asyncio
import logging
import sys
from viam.robot.client import RobotClient
from viam.components.generic import Generic
from robot.const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID
from robot.logging_setup import configure as configure_logging
from module.constants import PLAYERS

log = logging.getLogger(__name__)


async def move_one(robot, name, payload):
    try:
        c = Generic.from_robot(robot=robot, name=name)
        result = await c.do_command(payload)
        log.info("  %s: %s ok (%s)", name, payload, result)
    except Exception as e:
        log.error("  %s: %s FAILED -- %s: %s", name, payload, type(e).__name__, e)


async def main(t, r):
    payload = {"t": t, "r": r}
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        log.info("--- Moving all to %s (concurrent) ---", payload)
        await asyncio.gather(*[move_one(robot, n, payload) for n in PLAYERS])
    finally:
        await robot.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python move.py <t> <r>", file=sys.stderr)
        sys.exit(2)
    configure_logging()
    t = float(sys.argv[1])
    r = float(sys.argv[2])
    asyncio.run(main(t, r))
