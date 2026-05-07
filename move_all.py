"""Ad-hoc: drive every hockey player to t=0, then to t=1, concurrently.

Run:  python move_all.py
"""

import asyncio
from viam.robot.client import RobotClient
from viam.components.generic import Generic
from robot.const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID

PLAYERS = [
    "left-defense-hockey-player",
    "left-wing-hockey-player",
    "center-hockey-player",
    "right-defense-hockey-player",
    "right-wing-hockey-player",
]


async def move_one(robot, name, t):
    try:
        c = Generic.from_robot(robot=robot, name=name)
        result = await c.do_command({"t": t})
        print(f"  {name}: t={t} ok ({result})")
    except Exception as e:
        print(f"  {name}: t={t} FAILED -- {type(e).__name__}: {e}")


async def main():
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        print("--- Moving all to t=0 (concurrent) ---")
        await asyncio.gather(*[move_one(robot, n, 0.0) for n in PLAYERS])
        print("--- Moving all to t=1 (concurrent) ---")
        await asyncio.gather(*[move_one(robot, n, 1.0) for n in PLAYERS])
    finally:
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
