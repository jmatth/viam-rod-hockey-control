# tests/test_game_loop.py
"""GameLoop fires a playbook for a stable puck and cleans up on cancel."""

import asyncio
from types import SimpleNamespace

from engine.constants import PlayerID
from robot.game_loop import GameLoop
from robot.playbook import select_playbook
from robot.vision import _PUCK_CLASS
from robot.zones import _default_zones


class FakePlayer:
    def __init__(self, name):
        self.name = name
        self.commands = []

    async def do_command(self, command, **kwargs):
        self.commands.append(dict(command))
        return {}


class FakeVision:
    """Always reports a puck at a fixed normalized (u, v)."""

    def __init__(self, u, v):
        self.name = "fake-vision"
        self.u, self.v = u, v

    async def get_detections_from_camera(self, camera_name, **kwargs):
        d = SimpleNamespace(
            class_name=_PUCK_CLASS,
            x_min_normalized=self.u, x_max_normalized=self.u,
            y_min_normalized=self.v, y_max_normalized=self.v,
        )
        return [d]


def _players():
    return {pid: FakePlayer(pid.name.lower()) for pid in PlayerID}


def _point_in_some_zone():
    """Centroid of the first real zone in robot/zones.json that has a playbook."""
    for _, _, polygon in _default_zones():
        u = sum(p[0] for p in polygon) / len(polygon)
        v = sum(p[1] for p in polygon) / len(polygon)
        player, sequence = select_playbook(u, v)
        if sequence:
            return u, v, player
    raise AssertionError("no zone in zones.json maps to a playbook")


def test_loop_fires_playbook_and_resets_on_cancel():
    async def scenario():
        u, v, expected_player = _point_in_some_zone()
        players = _players()
        loop = GameLoop(
            players, FakeVision(u, v),
            poll_interval=0.01, stability_delay=0.01,
        )
        task = asyncio.create_task(loop.run())
        # Let it poll, pass the stability check, and fire the playbook
        for _ in range(100):
            await asyncio.sleep(0.01)
            if players[expected_player].commands:
                break
        assert players[expected_player].commands, \
            f"{expected_player.name} never received a command"

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert task.done()

        # Shutdown sends every player home
        for fake in players.values():
            assert any(c.get("t") == 0 and c.get("r") == 0 for c in fake.commands), \
                f"{fake.name} was not sent home"

    asyncio.run(scenario())


def test_loop_survives_vision_errors():
    async def scenario():
        class ExplodingVision:
            name = "boom"

            async def get_detections_from_camera(self, camera_name, **kwargs):
                raise RuntimeError("camera offline")

        players = _players()
        loop = GameLoop(players, ExplodingVision(), poll_interval=0.01)
        task = asyncio.create_task(loop.run())
        await asyncio.sleep(0.05)
        assert not task.done(), "loop died on a vision error instead of retrying"
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
