# tests/test_module_model.py
"""Module model lifecycle: validate_config deps, do_command start/stop/status."""

import asyncio

from viam.components.generic import Generic as GenericComponent
from viam.proto.app.robot import ComponentConfig
from viam.services.vision import Vision
from viam.utils import dict_to_struct

from module.constants import DEFAULT_PLAYER_COMPONENTS, DEFAULT_VISION_SERVICE
from module.models.rod_hockey_game import RodHockeyGame


def _config(name="game", attrs=None):
    cfg = ComponentConfig(name=name)
    cfg.attributes.CopyFrom(dict_to_struct(attrs or {}))
    return cfg


class FakePlayer:
    def __init__(self, name):
        self.name = name
        self.commands = []

    async def do_command(self, command, **kwargs):
        self.commands.append(dict(command))
        return {}


class FakeVision:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    async def get_detections_from_camera(self, camera_name, **kwargs):
        self.calls += 1
        return []  # never sees a puck


def _dependencies(attrs=None):
    attrs = attrs or {}
    deps = {}
    players = {}
    for key, default in DEFAULT_PLAYER_COMPONENTS.items():
        name = attrs.get(key, default)
        fake = FakePlayer(name)
        deps[GenericComponent.get_resource_name(name)] = fake
        players[key] = fake
    vision_name = attrs.get("vision_service", DEFAULT_VISION_SERVICE)
    vision = FakeVision(vision_name)
    deps[Vision.get_resource_name(vision_name)] = vision
    return deps, players, vision


def test_validate_config_default_deps():
    required, optional = RodHockeyGame.validate_config(_config())
    assert set(required) == set(DEFAULT_PLAYER_COMPONENTS.values()) | {DEFAULT_VISION_SERVICE}
    assert optional == []


def test_validate_config_respects_overrides():
    attrs = {"center": "my-center", "vision_service": "my-detector"}
    required, _ = RodHockeyGame.validate_config(_config(attrs=attrs))
    assert "my-center" in required
    assert "my-detector" in required
    assert "center-hockey-player" not in required
    assert DEFAULT_VISION_SERVICE not in required


def test_start_stop_status():
    async def scenario():
        attrs = {"poll_interval": 0.01, "stability_delay": 0.01}
        deps, players, vision = _dependencies(attrs)
        game = RodHockeyGame.new(_config(attrs=attrs), deps)

        assert (await game.do_command({"cmd": "status"})) == {"running": False}

        result = await game.do_command({"cmd": "start"})
        assert result["running"] is True

        # Already-running start is a no-op
        result = await game.do_command({"cmd": "start"})
        assert result["status"] == "already running"

        # Let the loop poll vision a few times
        await asyncio.sleep(0.1)
        assert vision.calls > 0
        assert (await game.do_command({"cmd": "status"})) == {"running": True}

        result = await game.do_command({"cmd": "stop"})
        assert result["running"] is False
        assert (await game.do_command({"cmd": "status"})) == {"running": False}

        # Stopping sends every player back to home pose
        for fake in players.values():
            assert any(c.get("t") == 0 and c.get("r") == 0 for c in fake.commands), \
                f"{fake.name} was not sent home"

        # Stop when not running is a no-op
        result = await game.do_command({"cmd": "stop"})
        assert result["status"] == "not running"

    asyncio.run(scenario())


def test_close_stops_loop():
    async def scenario():
        deps, _, _ = _dependencies()
        game = RodHockeyGame.new(_config(attrs={"poll_interval": 0.01}), deps)
        await game.do_command({"cmd": "start"})
        await game.close()
        assert (await game.do_command({"cmd": "status"})) == {"running": False}

    asyncio.run(scenario())


def test_unknown_command_raises():
    async def scenario():
        deps, _, _ = _dependencies()
        game = RodHockeyGame.new(_config(), deps)
        try:
            await game.do_command({"cmd": "bogus"})
        except ValueError as e:
            assert "bogus" in str(e)
        else:
            raise AssertionError("expected ValueError")

    asyncio.run(scenario())
