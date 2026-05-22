"""Ad-hoc: drive every hockey player to a given (t, r) concurrently.

Usage:  python move.py <t> <r>
Example: python move.py 0.5 90
"""

import asyncio
import sys
from viam.robot.client import RobotClient
from viam.components.generic import Generic
from robot.const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID
from src.common import PLAYERS

async def move_one(robot, name, payload):
    try:
        c = Generic.from_robot(robot=robot, name=name)
        result = await c.do_command(payload)
        print(f"  {name}: {payload} ok ({result})")
    except Exception as e:
        print(f"  {name}: {payload} FAILED -- {type(e).__name__}: {e}")


async def main(t, r):
    payload = {"t": t, "r": r}
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        print(f"--- Moving all to {payload} (concurrent) ---")
        await asyncio.gather(*[move_one(robot, n, payload) for n in PLAYERS])
    finally:
        await robot.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python move.py <t> <r>", file=sys.stderr)
        sys.exit(2)
    t = float(sys.argv[1])
    r = float(sys.argv[2])
    asyncio.run(main(t, r))
