"""Viam generic service wrapping the rod-hockey control loop.

Runs on the machine inside viam-server. The hockey-player components and the
puck-detector vision service arrive via dependency injection (no dialing, no
API keys). The control loop is started/stopped over DoCommand:

    {"cmd": "start"}   → begin polling vision and firing playbooks
    {"cmd": "stop"}    → cancel the loop, cancel in-flight plays, send rods home
    {"cmd": "status"}  → {"running": true/false}

Config attributes (all optional, defaults in module/constants.py):
    center, left_wing, right_wing, left_d, right_d — hockey-player component names
    vision_service      — puck-detector vision service name
    camera              — camera name the vision service reads from
    poll_interval       — seconds between vision polls
    stability_threshold — max normalized puck movement between the two readings
    stability_delay     — seconds between the two stability readings
"""

import asyncio
from typing import ClassVar, Mapping, Optional, Sequence, Tuple, cast

from typing_extensions import Self
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.services.generic import Generic
from viam.components.generic import Generic as GenericComponent
from viam.services.vision import Vision
from viam.utils import ValueTypes, struct_to_dict

from engine.constants import PlayerID
from robot.game_loop import GameLoop
from ..constants import (
    ATTR_TO_PLAYER,
    DEFAULT_PLAYER_COMPONENTS,
    DEFAULT_VISION_SERVICE,
    DEFAULT_CAMERA,
)


class RodHockeyGame(Generic, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(
        ModelFamily("viam-rod-hockey", "rod-hockey-game"), "rod_hockey_game"
    )

    def __init__(self, name: str):
        super().__init__(name)
        self._loop_task: Optional[asyncio.Task] = None
        self._players: Mapping[PlayerID, GenericComponent] = {}
        self._vision: Optional[Vision] = None
        self._camera_name: str = DEFAULT_CAMERA
        self._poll_interval: float = 0.25
        self._stability_threshold: float = 0.03
        self._stability_delay: float = 0.15

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
        """Declare the player components and vision service as required deps.

        Component/service names come from config attributes when present, else
        the defaults in module/constants.py.
        """
        attrs = struct_to_dict(config.attributes)
        deps = [
            str(attrs.get(key, default))
            for key, default in DEFAULT_PLAYER_COMPONENTS.items()
        ]
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
        vision_name = str(attrs.get("vision_service", DEFAULT_VISION_SERVICE))
        self._vision = cast(Vision, self._dep(dependencies, Vision.get_resource_name(vision_name)))
        self._players = players
        self._camera_name = str(attrs.get("camera", DEFAULT_CAMERA))
        self._poll_interval = float(attrs.get("poll_interval", 0.25))
        self._stability_threshold = float(attrs.get("stability_threshold", 0.03))
        self._stability_delay = float(attrs.get("stability_delay", 0.15))

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
            stability_delay=self._stability_delay,
        )

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
            self._loop_task = asyncio.get_running_loop().create_task(self._new_game_loop().run())
            self._loop_task.add_done_callback(self._on_loop_done)
            self.logger.info("Game loop started.")
            return {"running": True, "status": "started"}

        if cmd == "stop":
            if not self._loop_running():
                return {"running": False, "status": "not running"}
            await self._stop_loop()
            self.logger.info("Game loop stopped.")
            return {"running": False, "status": "stopped"}

        if cmd == "status":
            return {"running": self._loop_running()}

        raise ValueError(
            f"Unknown command {cmd!r} — expected one of: start, stop, status"
        )

    async def close(self):
        await self._stop_loop()
        await super().close()
