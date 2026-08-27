"""Viam generic service wrapping the rod-hockey control loop.

Runs on the machine inside viam-server. The hockey-player components and the
puck-detector vision service arrive via dependency injection (no dialing, no
API keys). The control loop is started/stopped over DoCommand:

    {"cmd": "start"}   → home all player gantries, then begin polling vision and
                         firing playbooks (pass "home": false to skip homing)
    {"cmd": "stop"}    → cancel the loop, cancel in-flight plays, send rods home
    {"cmd": "status"}  → {"running": true/false}
    {"cmd": "home"}    → home all player gantries without starting the loop

Config attributes (all optional, defaults in module/constants.py):
    center, left_wing, right_wing, left_d, right_d — hockey-player component names
    center_gantry … right_d_gantry — per-rod gantry component names (homed on start)
    vision_service      — puck-detector vision service name
    camera              — camera name the vision service reads from
    poll_interval       — seconds between vision polls
    stability_threshold — max normalized puck movement between the two readings
    log_level           — level for the game-loop loggers: debug/info/warning/error
"""

import asyncio
import logging
from typing import ClassVar, Mapping, Optional, Sequence, Tuple, cast

from typing_extensions import Self
from viam import logging as viam_logging
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.services.generic import Generic
from viam.components.gantry import Gantry
from viam.components.generic import Generic as GenericComponent
from viam.services.vision import Vision
from viam.utils import ValueTypes, struct_to_dict

from engine.constants import PlayerID
from robot.game_loop import GameLoop
from ..constants import (
    ATTR_TO_PLAYER,
    DEFAULT_PLAYER_COMPONENTS,
    DEFAULT_PLAYER_GANTRIES,
    DEFAULT_VISION_SERVICE,
    DEFAULT_CAMERA,
)

_HOME_TIMEOUT = 60.0  # seconds; homing sweeps the full rod travel


class RodHockeyGame(Generic, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(
        ModelFamily("viam-rod-hockey", "rod-hockey-control"), "rod_hockey_game"
    )

    def __init__(self, name: str):
        super().__init__(name)
        self._loop_task: Optional[asyncio.Task] = None
        self._players: Mapping[PlayerID, GenericComponent] = {}
        self._gantries: Mapping[str, Gantry] = {}
        self._vision: Optional[Vision] = None
        self._camera_name: str = DEFAULT_CAMERA
        self._poll_interval: float = 0.25
        self._stability_threshold: float = 0.03

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        self = super().new(config, dependencies)
        self.reconfigure(config, dependencies)
        return self

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """Declare the player components, gantries, and vision service as required deps.

        Component/service names come from config attributes when present, else
        the defaults in module/constants.py.
        """
        attrs = struct_to_dict(config.attributes)
        deps = [
            str(attrs.get(key, default))
            for key, default in DEFAULT_PLAYER_COMPONENTS.items()
        ]
        deps.extend(
            str(attrs.get(key, default))
            for key, default in DEFAULT_PLAYER_GANTRIES.items()
        )
        deps.append(str(attrs.get("vision_service", DEFAULT_VISION_SERVICE)))
        return deps, []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        attrs = struct_to_dict(config.attributes)

        players = {}
        for key, player_id in ATTR_TO_PLAYER.items():
            name = str(attrs.get(key, DEFAULT_PLAYER_COMPONENTS[key]))
            players[player_id] = cast(
                GenericComponent,
                self._dep(dependencies, GenericComponent.get_resource_name(name)),
            )
        gantries = {}
        for key, default in DEFAULT_PLAYER_GANTRIES.items():
            name = str(attrs.get(key, default))
            gantries[name] = cast(
                Gantry, self._dep(dependencies, Gantry.get_resource_name(name))
            )
        self._gantries = gantries
        vision_name = str(attrs.get("vision_service", DEFAULT_VISION_SERVICE))
        self._vision = cast(Vision, self._dep(dependencies, Vision.get_resource_name(vision_name)))
        self._players = players
        self._camera_name = str(attrs.get("camera", DEFAULT_CAMERA))
        self._poll_interval = float(attrs.get("poll_interval", 0.25))
        self._stability_threshold = float(attrs.get("stability_threshold", 0.03))
        self._apply_log_level(attrs.get("log_level", "info"))

        # If the loop is running, restart it on the new handles/settings.
        if self._loop_running():
            self.logger.info("Reconfigured while running — restarting game loop.")
            old = self._loop_task
            old.cancel()
            game_loop = self._new_game_loop()

            async def _restart():
                await asyncio.gather(old, return_exceptions=True)
                await game_loop.run()

            self._loop_task = asyncio.get_running_loop().create_task(_restart())
            self._loop_task.add_done_callback(self._on_loop_done)

    def _apply_log_level(self, value):
        """Set the level on the game-loop package loggers registered in module.py."""
        level = logging.getLevelNamesMapping().get(str(value).upper())
        if level is None:
            self.logger.warning("Unknown log_level %r — keeping INFO.", value)
            level = logging.INFO
        for pkg in ("robot", "engine", "module"):
            viam_logging.update_log_level(viam_logging.getLogger(pkg), level)

    @staticmethod
    def _dep(
        dependencies: Mapping[ResourceName, ResourceBase], resource_name: ResourceName
    ) -> ResourceBase:
        """Look up a dependency, tolerating remote-prefixed names."""
        if resource_name in dependencies:
            return dependencies[resource_name]
        for rn, resource in dependencies.items():
            if rn.name == resource_name.name or rn.name.endswith(":" + resource_name.name):
                return resource
        raise KeyError(
            f"Missing dependency '{resource_name.name}' "
            f"(have: {[rn.name for rn in dependencies]})"
        )

    def _new_game_loop(self) -> GameLoop:
        return GameLoop(
            players=self._players,
            vision=self._vision,
            camera_name=self._camera_name,
            poll_interval=self._poll_interval,
            stability_threshold=self._stability_threshold,
        )

    async def _home_all(self):
        """Home every player gantry in parallel; raise if any fails."""
        self.logger.info("Homing %d gantries: %s", len(self._gantries), list(self._gantries))

        async def _home(name: str, gantry: Gantry) -> Optional[str]:
            try:
                homed = await gantry.home(timeout=_HOME_TIMEOUT)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self.logger.error("Gantry %r failed to home: %r", name, err)
                return name
            if not homed:
                self.logger.error("Gantry %r reported unsuccessful homing.", name)
                return name
            return None

        results = await asyncio.gather(*(_home(n, g) for n, g in self._gantries.items()))
        failed = [name for name in results if name]
        if failed:
            raise RuntimeError(f"Homing failed for gantries: {failed}")
        self.logger.info("All gantries homed.")

    async def _home_then_run(self, game_loop: GameLoop, home: bool):
        if home:
            await self._home_all()
        await game_loop.run()

    def _loop_running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    def _on_loop_done(self, task: asyncio.Task):
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            self.logger.error("Game loop exited with error: %r", exc)

    async def _stop_loop(self):
        task = self._loop_task
        self._loop_task = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs,
    ) -> Mapping[str, ValueTypes]:
        cmd = command.get("cmd") or command.get("command")

        if cmd == "start":
            if self._loop_running():
                return {"running": True, "status": "already running"}
            home = command.get("home", True) is not False
            self._loop_task = asyncio.get_running_loop().create_task(
                self._home_then_run(self._new_game_loop(), home)
            )
            self._loop_task.add_done_callback(self._on_loop_done)
            status = "started (homing gantries first)" if home else "started"
            self.logger.info("Game loop started%s.", " — homing gantries first" if home else "")
            return {"running": True, "status": status}

        if cmd == "stop":
            if not self._loop_running():
                return {"running": False, "status": "not running"}
            await self._stop_loop()
            self.logger.info("Game loop stopped.")
            return {"running": False, "status": "stopped"}

        if cmd == "status":
            return {"running": self._loop_running()}

        if cmd == "home":
            if self._loop_running():
                return {"homed": False, "status": "loop is running — stop it before homing"}
            await self._home_all()
            return {"homed": True}

        raise ValueError(
            f"Unknown command {cmd!r} — expected one of: start, stop, status, home"
        )

    async def close(self):
        await self._stop_loop()
        await super().close()
