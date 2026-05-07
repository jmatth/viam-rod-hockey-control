"""Ad-hoc: check t for each player, drive only those not yet at t=0 to t=0,
then drive all to t=1 concurrently.

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

# About 1% of full travel — wider than the module's translation_arrival_tol
# (~2 mm / max_translation_mm ≈ 0.005) to absorb encoder noise.
T_ZERO_TOL = 0.01


async def get_t(robot, name):
    c = Generic.from_robot(robot=robot, name=name)
    pos = await c.do_command({"cmd": "get_position"})
    return c, float(pos["t"])


async def send(c, name, payload):
    try:
        result = await c.do_command(payload)
        print(f"  {name}: {payload} ok ({result})")
    except Exception as e:
        print(f"  {name}: {payload} FAILED -- {type(e).__name__}: {e}")


async def main():
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        print("--- Reading current t for each player ---")
        results = await asyncio.gather(
            *[get_t(robot, n) for n in PLAYERS],
            return_exceptions=True,
        )

        components = {}
        to_zero = []
        for name, r in zip(PLAYERS, results):
            if isinstance(r, Exception):
                print(f"  {name}: get_position FAILED -- {type(r).__name__}: {r}")
                continue
            c, t = r
            components[name] = c
            print(f"  {name}: t={t:.4f}")
            if abs(t) > T_ZERO_TOL:
                to_zero.append(name)

        if to_zero:
            print(f"--- Moving to t=0 (concurrent): {to_zero} ---")
            await asyncio.gather(*[send(components[n], n, {"t": 0.0}) for n in to_zero])
        else:
            print("--- All players already at t=0; skipping ---")

        print("--- Moving all to t=1 (concurrent) ---")
        await asyncio.gather(
            *[send(components[n], n, {"t": 1.0}) for n in components]
        )
    finally:
        await robot.close()


if __name__ == "__main__":
    asyncio.run(main())
