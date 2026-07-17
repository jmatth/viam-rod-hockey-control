"""The vision → playbook → execution control loop, decoupled from any connection.

GameLoop takes injected resource handles (hockey-player components + vision
service), so it runs identically inside the Viam module (dependencies) and from
the CLI (robot.connection). `run()` is cancellation-safe: cancelling the task
running it stops polling, cancels in-flight playbooks, and returns every player
to home pose.
"""

import asyncio
import logging
from typing import Mapping

from viam.components.generic import Generic
from viam.services.vision import Vision

from engine.constants import PlayerID
from .execution import execute_sequence, home_command
from .playbook import select_playbook, _LEFT_D_PLAYBOOK, _LEFT_WING_PLAYBOOK
from .vision import get_puck_field_coordinates

log = logging.getLogger(__name__)

_VISION_TIMEOUT  = 15.0
_EXECUTE_TIMEOUT = 30.0
_ERROR_SLEEP     = 1.0


class GameLoop:
    """Continuously polls the puck and fires calibrated playbooks."""

    def __init__(
        self,
        players: Mapping[PlayerID, Generic],
        vision: Vision,
        camera_name: str = "dynamic-crop",
        poll_interval: float = 0.25,
        stability_threshold: float = 0.03,
        stability_delay: float = 0.15,
    ):
        self.players = players
        self.vision = vision
        self.camera_name = camera_name
        self.poll_interval = poll_interval
        self.stability_threshold = stability_threshold
        self.stability_delay = stability_delay
        self._player_tasks: dict = {}

    async def get_puck_coordinates(self):
        """Return normalized (u, v) from vision, or (None, None) if no puck detected."""
        return await get_puck_field_coordinates(self.vision, self.camera_name)

    async def execute_with_coordination(self, player, sequence):
        """Execute a playbook sequence, with any multi-player coordination."""
        if player == PlayerID.LEFT_D and sequence is _LEFT_D_PLAYBOOK["right"]:
            await asyncio.gather(
                execute_sequence(sequence, player, self.players),
                execute_sequence([{"t": 0.25}], PlayerID.LEFT_WING, self.players, post_delay=3),
            )
        elif player == PlayerID.LEFT_WING and sequence in (
            _LEFT_WING_PLAYBOOK["bottom_left"], _LEFT_WING_PLAYBOOK["bottom_right"]
        ):
            await asyncio.gather(
                execute_sequence(sequence, player, self.players),
                execute_sequence([{"t": 0.75}], PlayerID.RIGHT_WING, self.players, skip_reset=True),
            )
        else:
            await execute_sequence(sequence, player, self.players)

    async def run_once(self) -> bool:
        """Detect puck, select playbook, and execute. Returns True if an action was taken."""
        puck_x, puck_y = await self.get_puck_coordinates()
        if puck_x is None:
            log.info("No puck detected.")
            return False
        log.info("Puck detected at: u=%.3f, v=%.3f", puck_x, puck_y)

        player, sequence = select_playbook(puck_x, puck_y)
        if not sequence:
            log.info("No playbook for this position.")
            return False

        await self.execute_with_coordination(player, sequence)
        return True

    async def run(self):
        """Continuously poll the puck and run playbooks until cancelled.

        Takes two readings separated by stability_delay seconds. Only fires if the
        puck hasn't moved more than stability_threshold (normalized, ~0.03 ≈ 16px on
        a 538-wide crop) between them, so playbooks don't trigger while the puck
        moves.

        Multiple players can run in parallel. If the detected player already has a
        playbook running, that trigger is skipped until the player is free.
        """
        log.info("Loop mode — polling every %ss.", self.poll_interval)
        try:
            while True:
                try:
                    await self._poll_and_fire()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("Error — retrying in %.0fs.", _ERROR_SLEEP)
                    await asyncio.sleep(_ERROR_SLEEP)
        finally:
            await self._shutdown()

    async def _poll_and_fire(self):
        x1, y1 = await asyncio.wait_for(self.get_puck_coordinates(), timeout=_VISION_TIMEOUT)
        if x1 is None:
            log.debug("No puck detected.")
            await asyncio.sleep(self.poll_interval)
            return

        await asyncio.sleep(self.stability_delay)

        x2, y2 = await asyncio.wait_for(self.get_puck_coordinates(), timeout=_VISION_TIMEOUT)
        if x2 is None:
            await asyncio.sleep(self.poll_interval)
            return

        dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        if dist > self.stability_threshold:
            log.debug("Puck moving (%.3f delta) — skipping.", dist)
            await asyncio.sleep(self.poll_interval)
            return

        puck_x = (x1 + x2) / 2
        puck_y = (y1 + y2) / 2
        log.info("Puck stable at: u=%.3f, v=%.3f", puck_x, puck_y)

        player, sequence = select_playbook(puck_x, puck_y)
        if not sequence:
            log.info("No playbook for this position.")
        else:
            task = self._player_tasks.get(player)
            if task and not task.done():
                log.info("%s busy — skipping.", player.name)
            else:
                self._player_tasks[player] = asyncio.create_task(self._fire(player, sequence))

        await asyncio.sleep(self.poll_interval)

    async def _fire(self, player, sequence):
        try:
            await asyncio.wait_for(self.execute_with_coordination(player, sequence), timeout=_EXECUTE_TIMEOUT)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("%s playbook error", player.name)

    async def _shutdown(self):
        """Cancel in-flight playbooks and return every player to home pose."""
        pending = [t for t in self._player_tasks.values() if not t.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._player_tasks.clear()

        async def _reset(player_id, component):
            try:
                await asyncio.wait_for(component.do_command(home_command(player_id)), timeout=10)
            except Exception:
                log.exception("Failed to reset %s to home.", component.name)

        await asyncio.gather(*[_reset(pid, c) for pid, c in self.players.items()])
        log.info("Loop stopped — all players sent home.")
