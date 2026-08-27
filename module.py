import asyncio

from viam import logging as viam_logging
from viam.module.module import Module

from module.models.rod_hockey_game import RodHockeyGame as RodHockeyGameModel

# Register the package-root loggers with the SDK so records from the robot/,
# engine/, and module/ packages are forwarded to viam-server once the module
# connects (Module calls viam.logging.setParent, which installs the forwarding
# handler on every registered logger). Child loggers like robot.game_loop
# propagate their records up to these. Without this, nothing configures std
# logging inside the module process and the game loop's logs are dropped.
for _pkg in ("robot", "engine", "module"):
    viam_logging.getLogger(_pkg).propagate = False  # SDK handler is the sole sink


if __name__ == '__main__':
    asyncio.run(Module.run_from_registry())
