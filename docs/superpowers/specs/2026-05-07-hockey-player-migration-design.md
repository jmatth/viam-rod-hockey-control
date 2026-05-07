# Hockey-player module migration — design

**Date:** 2026-05-07
**Scope:** `robot/playbook.py`, `robot/execution.py` only.

## Context

Today, `execute_sequence` drives two raw `Motor` components per player (`{prefix}-movement`, `{prefix}-rotation`) using relative `motor.go_for(rpm, revolutions)` calls. Playbook entries are tuples of `(motor, ticks, rpm)` — incremental moves. After each sequence, the executor reverses the net delta to "go home."

We are migrating to the `nfranczak:generic:hockey-player` Viam module. It exposes one `Generic` component per player and accepts `DoCommand` payloads with **absolute** axes:

- `t` ∈ `[0, 1]` — gantry position (normalized over `min_translation_mm` … `max_translation_mm`)
- `r` ∈ `[0, 360]` — rotation in degrees
- `rpm` — rotation speed (optional; falls back to `default_rpm_rotation`)
- `speed_mm_per_sec` — translation speed (optional; falls back to `default_speed_mm_per_sec`)
- `wrap`, `power` — out of scope for this migration

All five players have hockey-player components configured across three Viam parts:

| Player        | Component name                  | Part            |
|---------------|---------------------------------|-----------------|
| CENTER        | `center-hockey-player`          | `rig1-5072-3`   |
| RIGHT_WING    | `right-wing-hockey-player`      | `rig1-2270-2`   |
| LEFT_WING     | `left-wing-hockey-player`       | `rig1-2270-main`|
| RIGHT_D       | `right-defense-hockey-player`   | `rig1-2270-2`   |
| LEFT_D        | `left-defense-hockey-player`    | `rig1-2270-main`|

The non-primary parts are configured as remotes of `rig1-2270-main` such that bare component names resolve from a single client connection.

## Out of scope (flagged for the user, not handled here)

1. **Bug** in `rig1-2270-2`: `right-wing-gantry.motor` is set to `right-defense-movement`; should be `right-wing-movement`.
2. **Field name**: configs use `"inverted"`; module README documents `"invert"`. May be silently ignored.
3. `engine/constants.py` `PlayerID.get_prefix()` returns motor-style prefixes inconsistent with new component names. Not touched per scope; `execution.py` carries its own mapping.
4. `main.py`, `robot/const.py`, `robot/vision.py` — untouched.
5. Calibrating actual `(t, r)` values on hardware.

## `playbook.py` design

### Step format

Each step is a `dict` matching the `DoCommand` payload shape:

```python
{"t": 0.5, "r": 90, "rpm": 30, "speed_mm_per_sec": 100}
```

Any of `t`, `r`, `rpm`, `speed_mm_per_sec` may be omitted. Omitting `t` ⇒ rotate-only; omitting `r` ⇒ translate-only; omitting speeds ⇒ component defaults.

### Sequence values

Existing `(motor, ticks, rpm)` values were already documented as placeholders and were tuned against a different motor topology and `TICKS_PER_ROTATION` setup. Mechanically translating them to absolute `(t, r)` would produce mechanically-translated placeholders, not useful calibration. **All sequences become single-step placeholders** of the form `[{"t": 0.0, "r": 0.0}]` with a TODO comment carrying forward the original intent (e.g., `# TODO: calibrate — center, puck on left`).

### Public API preserved

`main.py` imports the following — all retained, with the same names and call signatures:

- Module-level dicts: `_CENTER_PLAYBOOK`, `_RIGHT_D_PLAYBOOK`, `_LEFT_D_PLAYBOOK`, `_LEFT_WING_PLAYBOOK`
- Right-wing two-phase pattern: `_RIGHT_WING_POSITIONS`, `_RIGHT_WING_ACTIONS`, and `get_rw_sequence(side, action)` which returns `positions[side] + actions[action]`
- Named sequence constants like `CENTER_LEFT`, `RIGHT_WING_LEFT`, `LEFT_D_LEFT`, etc. — kept for any external imports
- `get_instructions(puck_x, puck_y, player_id)` — same selection logic (uses `puck_x` against per-player x-thresholds from `engine.constants`); returns the new step-dict list

The values inside each list change from tuples to dicts; the list/dict structure does not.

## `execution.py` design

```python
from viam.robot.client import RobotClient
from viam.components.generic import Generic
from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID
from engine.constants import PlayerID

_PLAYER_TO_COMPONENT = {
    PlayerID.CENTER:     "center-hockey-player",
    PlayerID.RIGHT_WING: "right-wing-hockey-player",
    PlayerID.LEFT_WING:  "left-wing-hockey-player",
    PlayerID.RIGHT_D:    "right-defense-hockey-player",
    PlayerID.LEFT_D:     "left-defense-hockey-player",
}


async def execute_sequence(sequence, player_id=PlayerID.CENTER):
    if not sequence:
        print("Empty sequence.")
        return

    component_name = _PLAYER_TO_COMPONENT[player_id]
    print(f"Executing sequence ({len(sequence)} steps, "
          f"player={player_id.name}, component={component_name})")

    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        player = Generic.from_robot(robot=robot, name=component_name)
        for step in sequence:
            await player.do_command(step)
    finally:
        await robot.close()

    print("Done.")
```

### Behavior changes

- One `Generic` component per player instead of two `Motor`s.
- Each step is a single `do_command(dict)` call.
- No `TICKS_PER_ROTATION` math; no `("move", ...)` / `("rotate", ...)` switch.
- **No reset-to-home** (per design decision). Sequences end where they end.
- `_PLAYER_TO_COMPONENT` lives locally because `engine/constants.py` is out of scope and its existing `get_prefix()` returns motor-style prefixes that don't match component names.
- `robot.close()` added in a `finally` so we don't leak connections on errors.

`TICKS_PER_ROTATION` from `robot/const.py` becomes unused inside `execution.py`. The constant in `const.py` itself is left in place (out of scope to delete it).

## Risks

- If remotes don't actually expose bare names from `rig1-2270-main`, all calls except left-side will fail with "resource not found." Verify by listing components from the primary connection.
- If `"inverted": true` is silently ignored on center / right-wing, the hardware will move opposite to what calibrated `t` values prescribe. Verify by sending `{"t": 0.0}` and `{"t": 1.0}` and confirming direction.
- The `right-wing-gantry` motor reference bug must be fixed before right-wing calibration begins.

## Test plan

- `python main.py --ld-left` and `--ld-right`: confirm `do_command` reaches `left-defense-hockey-player` and the placeholder step doesn't crash.
- `python main.py --lw-left`: same against left-wing.
- `python main.py --rw-shot --left` etc.: same against right-wing (after gantry-motor fix).
- `python main.py --rd-left`: same against right-defense.
- `python main.py --center-left`: same against center.
- After each, the player rod sits at wherever the last step put it (no reset).
- Calibration of actual `(t, r)` values is follow-on work outside this migration.
