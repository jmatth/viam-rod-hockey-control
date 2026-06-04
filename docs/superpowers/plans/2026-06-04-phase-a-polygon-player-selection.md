# Phase A — Polygon-Based Player Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace axis-aligned zone bounding boxes with normalized polygons in a corner-anchored field frame, and start observing rod state via `get_position`, as future-proofing groundwork for Phases B and C.

**Architecture:** Puck position arrives as normalized `(u,v) ∈ [0,1]²` (read from Viam detections' built-in normalized fields). A new `robot/zones.py` loads per-`(player,side)` polygons from `robot/zones.json` and selects the owning player via point-in-polygon. `robot/playbook.py` delegates geometry to it and maps `(player,side) → sequence`. A matplotlib tool (`tools/annotate_zones.py`) authors the polygons on a saved frame; an initial `zones.json` is auto-seeded from today's boxes for behavioral continuity. `robot/state.py` adds a `get_position` helper (the B-seam); `execution.py` stops discarding the `t_final`/`r_final` moves already return.

**Tech Stack:** Python 3.13, `viam-sdk` 0.71, `matplotlib` (tool only), `pytest`. Run tests with `.venv/bin/python -m pytest` from the repo root (puts the repo root on `sys.path` so `import robot.*` resolves).

**Branch:** `phase-a-polygon-zones` (already created; the approved spec lives at `docs/superpowers/specs/2026-06-04-phase-a-polygon-player-selection-design.md`).

**Coordinate conventions used throughout:** image-space origin top-left, `u` to the right, `v` down, both normalized to `[0,1]`. Legacy boxes are in `dynamic-crop` pixels; the reference crop size for converting them is the sample frame `dynamic-crop-2026-06-04_16_56_57.jpeg` = **538×284** (`REF_W=538`, `REF_H=284`).

**One intentional behavior change (approved):** CENTER's side was previously computed from a sloped line (`_center_line_y`). After this plan, CENTER's side comes from its polygons, with the boundary at the seam between the two seeded CENTER zones (`v≈135/284`). All other players are behaviorally equivalent to today for interior points.

---

### Task 1: Pure geometry primitives in `robot/zones.py`

**Files:**
- Create: `robot/zones.py`
- Test: `tests/test_zones_geometry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_zones_geometry.py
from robot.zones import point_in_polygon, normalize_point


SQUARE = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
# A concave "C"/L shape to catch naive bounding-box logic.
CONCAVE = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.4), (0.4, 0.4), (0.4, 1.0), (0.0, 1.0)]


def test_point_inside_square():
    assert point_in_polygon(0.5, 0.5, SQUARE) is True


def test_point_outside_square():
    assert point_in_polygon(1.5, 0.5, SQUARE) is False


def test_point_in_concavity_is_outside():
    # (0.7, 0.7) is inside the bounding box but inside the cut-out notch.
    assert point_in_polygon(0.7, 0.7, CONCAVE) is False


def test_point_in_solid_part_of_concave():
    assert point_in_polygon(0.2, 0.2, CONCAVE) is True


def test_normalize_point():
    assert normalize_point(269.0, 142.0, 538, 284) == (269.0 / 538, 142.0 / 284)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_zones_geometry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'robot.zones'`

- [ ] **Step 3: Write minimal implementation**

```python
# robot/zones.py
"""Polygon zone geometry and player selection for the bubble hockey robot.

Polygons live in normalized field coordinates (u, v) in [0, 1], image-space
origin top-left. Loaded from robot/zones.json (authored by tools/annotate_zones.py).
"""


def point_in_polygon(u: float, v: float, polygon) -> bool:
    """Ray-casting point-in-polygon test. `polygon` is a list of (u, v) tuples."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > v) != (yj > v)) and (u < (xj - xi) * (v - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def normalize_point(px: float, py: float, width: int, height: int):
    """Convert a pixel coordinate to normalized (u, v) in [0, 1]."""
    return (px / width, py / height)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_zones_geometry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add robot/zones.py tests/test_zones_geometry.py
git commit -m "feat(zones): add point-in-polygon and normalize geometry primitives"
```

---

### Task 2: Zone loading and selection in `robot/zones.py`

**Files:**
- Modify: `robot/zones.py`
- Test: `tests/test_zones_select.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_zones_select.py
import json

from engine.constants import PlayerID
from robot.zones import load_zones, select


def _write(tmp_path, data):
    p = tmp_path / "zones.json"
    p.write_text(json.dumps(data))
    return str(p)


# Two overlapping squares; the first listed must win (first-match priority).
OVERLAP = [
    {"player": "left_wing", "side": "bottom_right",
     "polygon": [[0.0, 0.0], [0.6, 0.0], [0.6, 0.6], [0.0, 0.6]]},
    {"player": "left_d", "side": "left",
     "polygon": [[0.4, 0.4], [1.0, 0.4], [1.0, 1.0], [0.4, 1.0]]},
]


def test_load_zones_maps_player_names(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert zones[0][0] == PlayerID.LEFT_WING
    assert zones[0][1] == "bottom_right"
    assert zones[0][2][0] == (0.0, 0.0)


def test_select_first_match_wins(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    # (0.5, 0.5) is inside BOTH squares; first listed (left_wing) wins.
    assert select(0.5, 0.5, zones) == (PlayerID.LEFT_WING, "bottom_right")


def test_select_second_zone(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert select(0.8, 0.8, zones) == (PlayerID.LEFT_D, "left")


def test_select_no_match_returns_none(tmp_path):
    zones = load_zones(_write(tmp_path, OVERLAP))
    assert select(0.99, 0.05, zones) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_zones_select.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_zones'`

- [ ] **Step 3: Write minimal implementation**

Append to `robot/zones.py`:

```python
import json
import os

from engine.constants import PlayerID

_ZONES_PATH = os.path.join(os.path.dirname(__file__), "zones.json")

_NAME_TO_PLAYER = {
    "center":     PlayerID.CENTER,
    "right_wing": PlayerID.RIGHT_WING,
    "left_wing":  PlayerID.LEFT_WING,
    "right_d":    PlayerID.RIGHT_D,
    "left_d":     PlayerID.LEFT_D,
}

_ZONES_CACHE = None


def load_zones(path: str = _ZONES_PATH):
    """Load zones as a list of (PlayerID, side, polygon) tuples, in file order."""
    with open(path) as f:
        raw = json.load(f)
    zones = []
    for z in raw:
        player = _NAME_TO_PLAYER[z["player"]]
        polygon = [tuple(pt) for pt in z["polygon"]]
        zones.append((player, z["side"], polygon))
    return zones


def _default_zones():
    global _ZONES_CACHE
    if _ZONES_CACHE is None:
        _ZONES_CACHE = load_zones()
    return _ZONES_CACHE


def select(u: float, v: float, zones=None):
    """Return (PlayerID, side) for the first zone containing (u, v), else (None, None)."""
    if zones is None:
        zones = _default_zones()
    for player, side, polygon in zones:
        if point_in_polygon(u, v, polygon):
            return player, side
    return None, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_zones_select.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add robot/zones.py tests/test_zones_select.py
git commit -m "feat(zones): load zones.json and select player by point-in-polygon"
```

---

### Task 3: Seed `robot/zones.json` from today's boxes

Produces an initial `zones.json` (normalized rectangle-polygons) so the loop runs with behavior continuous with today's, before any hand-annotation. Order is preserved so first-match priority is unchanged.

**Files:**
- Create: `tools/seed_zones_from_legacy.py`
- Create (generated): `robot/zones.json`
- Test: `tests/test_seed_zones.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_zones.py
from tools.seed_zones_from_legacy import LEGACY_ZONES, box_to_normalized_polygon, REF_W, REF_H


def test_box_to_normalized_polygon_corners():
    poly = box_to_normalized_polygon(0, 538, 0, 284)
    assert poly == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]


def test_legacy_zone_count_and_order():
    # 16 legacy zones; first is the LEFT_WING behind-goal priority zone.
    assert len(LEGACY_ZONES) == 16
    assert LEGACY_ZONES[0]["player"] == "left_wing"


def test_normalized_values_in_unit_range():
    for z in LEGACY_ZONES:
        poly = box_to_normalized_polygon(z["x_min"], z["x_max"], z["y_min"], z["y_max"])
        for x, y in poly:
            assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_seed_zones.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.seed_zones_from_legacy'`

- [ ] **Step 3: Write minimal implementation**

```python
# tools/seed_zones_from_legacy.py
"""One-shot: convert the legacy axis-aligned zone boxes into a normalized
polygon zones.json. Run once to bootstrap robot/zones.json; refine afterward
with tools/annotate_zones.py.

    .venv/bin/python -m tools.seed_zones_from_legacy
"""

import json
import os

# Reference crop size (sample dynamic-crop frame) the legacy pixel boxes assume.
REF_W = 538
REF_H = 284

# Snapshot of the legacy robot/playbook.py _ZONES, in original order (first match wins).
LEGACY_ZONES = [
    {"player": "left_wing",  "side": "bottom_right", "x_min": 75,    "x_max": 155,   "y_min": 230, "y_max": 255},
    {"player": "left_wing",  "side": "bottom_right", "x_min": 45,    "x_max": 75,    "y_min": 110, "y_max": 230},
    {"player": "left_wing",  "side": "bottom_left",  "x_min": 75,    "x_max": 155,   "y_min": 255, "y_max": 280},
    {"player": "left_wing",  "side": "bottom_right", "x_min": 0,     "x_max": 45,    "y_min": 110, "y_max": 280},
    {"player": "left_wing",  "side": "right",        "x_min": 120,   "x_max": 210,   "y_min": 230, "y_max": 255},
    {"player": "left_wing",  "side": "left",         "x_min": 120,   "x_max": 210,   "y_min": 255, "y_max": 280},
    {"player": "right_wing", "side": "left",         "x_min": 155,   "x_max": 315,   "y_min": 25,  "y_max": 75},
    {"player": "right_wing", "side": "right",        "x_min": 155,   "x_max": 315,   "y_min": 0,   "y_max": 25},
    {"player": "right_wing", "side": "bottom_left",  "x_min": 0,     "x_max": 155,   "y_min": 25,  "y_max": 75},
    {"player": "right_wing", "side": "bottom_right", "x_min": 0,     "x_max": 155,   "y_min": 0,   "y_max": 25},
    {"player": "right_d",    "side": "right",        "x_min": 335,   "x_max": 470,   "y_min": 65,  "y_max": 90},
    {"player": "right_d",    "side": "left",         "x_min": 335,   "x_max": 470,   "y_min": 90,  "y_max": 115},
    {"player": "center",     "side": "right",        "x_min": 150,   "x_max": 300,   "y_min": 85,  "y_max": 135},
    {"player": "center",     "side": "left",         "x_min": 150,   "x_max": 300,   "y_min": 135, "y_max": 185},
    {"player": "left_d",     "side": "right",        "x_min": 278.5, "x_max": 485.5, "y_min": 185, "y_max": 210},
    {"player": "left_d",     "side": "left",         "x_min": 278.5, "x_max": 485.5, "y_min": 210, "y_max": 235},
]


def box_to_normalized_polygon(x_min, x_max, y_min, y_max):
    """Return a 4-point normalized polygon (CW from top-left) for a pixel box."""
    return [
        [round(x_min / REF_W, 4), round(y_min / REF_H, 4)],
        [round(x_max / REF_W, 4), round(y_min / REF_H, 4)],
        [round(x_max / REF_W, 4), round(y_max / REF_H, 4)],
        [round(x_min / REF_W, 4), round(y_max / REF_H, 4)],
    ]


def build_zones():
    out = []
    for z in LEGACY_ZONES:
        out.append({
            "player": z["player"],
            "side": z["side"],
            "polygon": box_to_normalized_polygon(z["x_min"], z["x_max"], z["y_min"], z["y_max"]),
        })
    return out


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(__file__), "..", "robot", "zones.json")
    out_path = os.path.abspath(out_path)
    with open(out_path, "w") as f:
        json.dump(build_zones(), f, indent=2)
    print(f"Wrote {len(LEGACY_ZONES)} zones to {out_path}")
```

- [ ] **Step 4: Run test to verify it passes, then generate zones.json**

Run: `.venv/bin/python -m pytest tests/test_seed_zones.py -v`
Expected: PASS (3 passed)

Run: `.venv/bin/python -m tools.seed_zones_from_legacy`
Expected: `Wrote 16 zones to /home/nick/rod-hockey-robot/robot/zones.json`

Verify it loads through the real loader:
Run: `.venv/bin/python -c "from robot.zones import load_zones; print(len(load_zones()))"`
Expected: `16`

- [ ] **Step 5: Commit**

```bash
git add tools/seed_zones_from_legacy.py tests/test_seed_zones.py robot/zones.json
git commit -m "feat(zones): seed zones.json from legacy boxes as normalized polygons"
```

---

### Task 4: Delegate `select_playbook` to `zones`, remove legacy zone logic

**Files:**
- Modify: `robot/playbook.py` (imports at `:16-23`; `select_playbook` at `:291-303`; remove `_ZONES` `:30-54`, `_center_side` `:226-227`, `get_instructions` `:230-262`, `_center_line_y` + `_CENTER_X*` `:265-273`, `_select_zone` `:284-288`)
- Test: `tests/test_select_playbook.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_select_playbook.py
# Uses the seeded robot/zones.json from Task 3.
from engine.constants import PlayerID
from robot.playbook import select_playbook, RIGHT_WING_LEFT, CENTER_LEFT


def test_right_wing_left_zone():
    # Legacy right_wing/left box was px x[155,315] y[25,75] on a 538x284 crop.
    # Center of that box -> normalized ~ (0.437, 0.176).
    player, seq = select_playbook(235.0 / 538, 50.0 / 284)
    assert player == PlayerID.RIGHT_WING
    # RW sequence starts with the position block for that side.
    assert seq[0] == RIGHT_WING_LEFT[0]


def test_center_left_zone():
    # Legacy center/left box px x[150,300] y[135,185] -> center normalized.
    player, seq = select_playbook(225.0 / 538, 160.0 / 284)
    assert player == PlayerID.CENTER
    assert seq is CENTER_LEFT


def test_no_zone_returns_none():
    player, seq = select_playbook(0.99, 0.99)
    assert (player, seq) == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_select_playbook.py -v`
Expected: FAIL — current `select_playbook` takes pixel coords and calls `_select_zone`; `(0.437, 0.176)` falls in no legacy *pixel* box, so assertions fail.

- [ ] **Step 3: Rewrite `select_playbook` and delete legacy logic**

In `robot/playbook.py`, change the import block at the top (`:16-23`) from:

```python
from engine.constants import (
    PlayerID,
    center_x,
    left_d_x,
    LEFT_WING_SEG_B_X_MID,
    right_d_x,
    right_wing_x,
)
```

to:

```python
from engine.constants import PlayerID
from . import zones
```

Delete these now-unused blocks entirely: `_ZONES` (`:30-54`), `_center_side` (`:226-227`), `get_instructions` (`:230-262`), the `_CENTER_X*`/`_CENTER_Y*` constants and `_center_line_y` (`:265-273`), and `_select_zone` (`:284-288`). Keep `_PLAYBOOK_MAP`.

Replace the body of `select_playbook` (`:291-303`) with:

```python
def select_playbook(u: float, v: float):
    """Return (PlayerID, sequence) for the puck at normalized (u, v), or (None, None)."""
    player_id, side = zones.select(u, v)
    if player_id is None:
        return None, None
    print(f"{player_id.name} side: {side}  (u={u:.3f}, v={v:.3f})")
    if player_id == PlayerID.RIGHT_WING:
        return player_id, get_rw_sequence(side, "shot")
    return player_id, _PLAYBOOK_MAP[player_id][side]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_select_playbook.py -v`
Expected: PASS (3 passed)

Sanity-check nothing else imported the deleted names:
Run: `.venv/bin/python -c "import robot.playbook, main, run_play"`
Expected: no error (imports succeed)

- [ ] **Step 5: Commit**

```bash
git add robot/playbook.py tests/test_select_playbook.py
git commit -m "refactor(playbook): select_playbook delegates to polygon zones"
```

---

### Task 5: Vision returns normalized `(u, v)`

**Files:**
- Modify: `robot/vision.py` (add pure extractor + new async function; keep existing functions)
- Test: `tests/test_vision_puck.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_vision_puck.py
from types import SimpleNamespace

from robot.vision import puck_uv_from_detections


def _det(cls, xmn, ymn, xmx, ymx):
    return SimpleNamespace(
        class_name=cls,
        x_min_normalized=xmn, y_min_normalized=ymn,
        x_max_normalized=xmx, y_max_normalized=ymx,
    )


def test_no_orange_returns_none():
    dets = [_det("lime-green", 0.1, 0.1, 0.2, 0.2)]
    assert puck_uv_from_detections(dets) == (None, None)


def test_single_orange_center():
    dets = [_det("orange", 0.4, 0.6, 0.6, 0.8)]
    assert puck_uv_from_detections(dets) == (0.5, 0.7)


def test_averages_multiple_orange():
    dets = [_det("orange", 0.0, 0.0, 0.2, 0.2), _det("orange", 0.8, 0.8, 1.0, 1.0)]
    # centers (0.1,0.1) and (0.9,0.9) -> mean (0.5, 0.5)
    u, v = puck_uv_from_detections(dets)
    assert round(u, 6) == 0.5 and round(v, 6) == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_vision_puck.py -v`
Expected: FAIL — `ImportError: cannot import name 'puck_uv_from_detections'`

- [ ] **Step 3: Add the extractor and the async field-coordinate function**

In `robot/vision.py`, add the pure extractor near `get_center` (after `:27`):

```python
def puck_uv_from_detections(detections):
    """Average the normalized centers of all orange (puck) detections.

    Returns (u, v) in [0, 1], or (None, None) if no puck detected. Uses Viam's
    server-computed *_normalized bbox fields, so no image size is needed.
    """
    pucks = [d for d in detections if d.class_name == _PUCK_CLASS]
    if not pucks:
        return None, None
    us = [(d.x_min_normalized + d.x_max_normalized) / 2 for d in pucks]
    vs = [(d.y_min_normalized + d.y_max_normalized) / 2 for d in pucks]
    return sum(us) / len(us), sum(vs) / len(vs)
```

Add the async wrapper after `get_puck_camera_coordinates` (after `:93`):

```python
async def get_puck_field_coordinates():
    """Connect, detect the puck, and return its normalized (u, v) field position.

    Returns (u, v) in [0, 1], or (None, None) if no puck is detected.
    """
    machine = await _connect()
    try:
        vision1 = VisionClient.from_robot(machine, "vision-1")
        detections = await vision1.get_detections_from_camera("dynamic-crop")
        u, v = puck_uv_from_detections(detections)
        if u is not None:
            print(f"Puck field coords: u={u:.3f}, v={v:.3f}")
        return u, v
    finally:
        await machine.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_vision_puck.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add robot/vision.py tests/test_vision_puck.py
git commit -m "feat(vision): add normalized (u,v) puck field coordinates"
```

---

### Task 6: Wire `main.py` to normalized coordinates

**Files:**
- Modify: `main.py` (import `:34`; `get_puck_coordinates` `:80-82`; `run_loop` signature/prints `:114-149`; `run_playbook_from_puck_position` print `:91`)

No new automated test (this path needs hardware); verified by import + manual run.

- [ ] **Step 1: Update the vision import**

In `main.py`, change line 34 from:

```python
from robot.vision import get_puck_camera_coordinates
```

to:

```python
from robot.vision import get_puck_field_coordinates
```

- [ ] **Step 2: Update the `get_puck_coordinates` wrapper**

Replace `get_puck_coordinates` (`:80-82`) with:

```python
async def get_puck_coordinates():
    """Return normalized (u, v) from vision, or (None, None) if no puck detected."""
    return await get_puck_field_coordinates()
```

- [ ] **Step 3: Normalize the stability threshold and prints**

In `run_loop` (`:114`), change the signature default:

```python
async def run_loop(poll_interval=0.25, stability_threshold=0.03, stability_delay=0.15):
```

In `run_loop`, update the stable-puck print (`:149`) to:

```python
            print(f"Puck stable at: u={puck_x:.3f}, v={puck_y:.3f}")
```

In `run_playbook_from_puck_position`, update the detected print (`:91`) to:

```python
    print(f"Puck detected at: u={puck_x:.3f}, v={puck_y:.3f}")
```

Also update the docstring of `run_loop` (`:118-119`) so the threshold reads in normalized units:

```python
    puck hasn't moved more than stability_threshold (normalized, ~0.03 ≈ 16px on a
    538-wide crop) between them, so playbooks don't trigger while the puck moves.
```

- [ ] **Step 4: Verify imports and arg parsing still work**

Run: `.venv/bin/python -c "import main"`
Expected: no error

Run: `.venv/bin/python main.py --help`
Expected: argparse help prints, listing `--loop` and the manual flags (no traceback)

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat(main): drive loop with normalized puck coordinates"
```

---

### Task 7: Rod-state plumbing — `robot/state.py` and `execution.py` logging

**Files:**
- Modify: `robot/const.py` (add shared `PLAYER_TO_COMPONENT`)
- Modify: `robot/execution.py` (use shared map; log `do_command` results)
- Create: `robot/state.py`
- Test: `tests/test_player_component_map.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_player_component_map.py
from engine.constants import PlayerID
from robot.const import PLAYER_TO_COMPONENT


def test_every_player_has_a_component():
    for player in PlayerID:
        assert player in PLAYER_TO_COMPONENT
        assert isinstance(PLAYER_TO_COMPONENT[player], str)


def test_center_component_name():
    assert PLAYER_TO_COMPONENT[PlayerID.CENTER] == "center-hockey-player"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_player_component_map.py -v`
Expected: FAIL — `ImportError: cannot import name 'PLAYER_TO_COMPONENT'`

- [ ] **Step 3: Add shared map, use it in execution, add state.py**

Append to `robot/const.py`:

```python
# ============================================================
#  Player → Viam component name
# ============================================================

from engine.constants import PlayerID

PLAYER_TO_COMPONENT = {
    PlayerID.CENTER:     "center-hockey-player",
    PlayerID.RIGHT_WING: "right-wing-hockey-player",
    PlayerID.LEFT_WING:  "left-wing-hockey-player",
    PlayerID.RIGHT_D:    "right-defense-hockey-player",
    PlayerID.LEFT_D:     "left-defense-hockey-player",
}
```

In `robot/execution.py`, replace the local `_PLAYER_TO_COMPONENT` map by importing the shared one. Replace the `.const` import line (`:4`) — leave the `from engine.constants import PlayerID` line (`:5`) intact, it's still used by the `player_id=PlayerID.CENTER` default:

```python
from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID, PLAYER_TO_COMPONENT
```

Delete the local `_PLAYER_TO_COMPONENT = {...}` block (`:8-14`), and update the lookup in `execute_sequence` (`:29`) from `_PLAYER_TO_COMPONENT[player_id]` to `PLAYER_TO_COMPONENT[player_id]`.

In `execute_sequence`, change the step loop (`:38-39`) from:

```python
        for step in sequence:
            await player.do_command(step)
```

to (stop discarding the reported final pose):

```python
        for step in sequence:
            result = await player.do_command(step)
            print(f"  step {step} -> {result}")
```

Create `robot/state.py`:

```python
"""Read a hockey-player rod's current state via the module's get_position command.

The hockey-player module returns {"t", "r", "t_moving", "r_moving"} for
{"cmd": "get_position"}. Phase A uses this for observability; B/C consume it to
steer plays.
"""

import asyncio
import sys

from viam.robot.client import RobotClient
from viam.components.generic import Generic

from .const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID, PLAYER_TO_COMPONENT
from engine.constants import PlayerID


async def get_player_position(player_id: PlayerID) -> dict:
    """Return {"t", "r", "t_moving", "r_moving"} for the given player's rod."""
    component_name = PLAYER_TO_COMPONENT[player_id]
    opts = RobotClient.Options.with_api_key(
        api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID,
    )
    robot = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        player = Generic.from_robot(robot=robot, name=component_name)
        return await player.do_command({"cmd": "get_position"})
    finally:
        await robot.close()


# Smoke test:  .venv/bin/python -m robot.state center
_ARG_TO_PLAYER = {
    "center": PlayerID.CENTER, "right_wing": PlayerID.RIGHT_WING,
    "left_wing": PlayerID.LEFT_WING, "right_d": PlayerID.RIGHT_D, "left_d": PlayerID.LEFT_D,
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "center"
    pos = asyncio.run(get_player_position(_ARG_TO_PLAYER[name]))
    print(f"{name}: {pos}")
```

- [ ] **Step 4: Run test and verify imports**

Run: `.venv/bin/python -m pytest tests/test_player_component_map.py -v`
Expected: PASS (2 passed)

Run: `.venv/bin/python -c "import robot.execution, robot.state"`
Expected: no error

- [ ] **Step 5: Commit**

```bash
git add robot/const.py robot/execution.py robot/state.py tests/test_player_component_map.py
git commit -m "feat(state): add get_position helper; log move results; share component map"
```

---

### Task 8: Annotation tool `tools/annotate_zones.py`

**Files:**
- Create: `tools/annotate_zones.py`
- Test: `tests/test_annotate_build_zone.py`

The GUI glue is verified manually; its pure helper (`build_zone`) is unit-tested.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_annotate_build_zone.py
from tools.annotate_zones import build_zone


def test_build_zone_normalizes_vertices():
    verts_px = [(0, 0), (538, 0), (538, 284), (0, 284)]
    z = build_zone("center", "left", verts_px, 538, 284)
    assert z == {
        "player": "center",
        "side": "left",
        "polygon": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
    }


def test_build_zone_rounds_to_4dp():
    z = build_zone("left_d", "right", [(269, 142), (270, 143), (269, 143)], 538, 284)
    assert z["polygon"][0] == [round(269 / 538, 4), round(142 / 284, 4)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_annotate_build_zone.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.annotate_zones'`

- [ ] **Step 3: Write the tool**

```python
# tools/annotate_zones.py
"""Draw player zone polygons on a saved dynamic-crop frame and export zones.json.

    .venv/bin/python tools/annotate_zones.py --image <frame.jpeg> --out robot/zones.json

Reference overlays (faint) help you trace today's behavior:
  - any existing zones.json polygons (edit mode)
  - the legacy boxes from tools/seed_zones_from_legacy.LEGACY_ZONES

Interaction (single polygon at a time):
  - Click vertices on the image; close the polygon (click near the first point).
  - Press Enter (in this terminal) to name it: you'll be prompted for player+side.
  - Press 'w' on the figure to write the JSON; 'q' to quit without further saving.
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import PolygonSelector

from tools.seed_zones_from_legacy import LEGACY_ZONES

PLAYERS = ["center", "right_wing", "left_wing", "right_d", "left_d"]
SIDES = ["left", "right", "bottom_left", "bottom_right"]


def build_zone(player, side, verts_px, width, height):
    """Return a zone dict with the vertices normalized to [0, 1] (rounded 4dp)."""
    polygon = [[round(x / width, 4), round(y / height, 4)] for (x, y) in verts_px]
    return {"player": player, "side": side, "polygon": polygon}


def _prompt(label, options):
    while True:
        val = input(f"  {label} {options}: ").strip()
        if val in options:
            return val
        print(f"  '{val}' not in {options}")


def _overlay_reference(ax, width, height, out_path):
    # Legacy boxes (faint blue), drawn in pixel space scaled to this image.
    from tools.seed_zones_from_legacy import REF_W, REF_H
    sx, sy = width / REF_W, height / REF_H
    for z in LEGACY_ZONES:
        x0, y0 = z["x_min"] * sx, z["y_min"] * sy
        w, h = (z["x_max"] - z["x_min"]) * sx, (z["y_max"] - z["y_min"]) * sy
        ax.add_patch(plt.Rectangle((x0, y0), w, h, fill=False, edgecolor="cyan",
                                   alpha=0.35, linewidth=0.8))
    # Existing zones.json (faint yellow), if present.
    if os.path.exists(out_path):
        with open(out_path) as f:
            for z in json.load(f):
                pts = [(u * width, v * height) for u, v in z["polygon"]]
                ax.add_patch(plt.Polygon(pts, closed=True, fill=False,
                                         edgecolor="yellow", alpha=0.4, linewidth=1.0))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="/home/nick/Downloads/dynamic-crop-2026-06-04_16_56_57.jpeg")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "robot", "zones.json"))
    args = parser.parse_args()
    out_path = os.path.abspath(args.out)

    img = mpimg.imread(args.image)
    height, width = img.shape[:2]

    fig, ax = plt.subplots()
    ax.imshow(img)
    ax.set_title("draw polygon, Enter=name it, w=write json, q=quit")
    _overlay_reference(ax, width, height, out_path)

    zones = []
    state = {"verts": []}

    def on_select(verts):
        state["verts"] = list(verts)

    selector = PolygonSelector(ax, on_select)

    def on_key(event):
        if event.key == "enter":
            if len(state["verts"]) < 3:
                print("  need at least 3 vertices before naming")
                return
            player = _prompt("player", PLAYERS)
            side = _prompt("side", SIDES)
            zones.append(build_zone(player, side, state["verts"], width, height))
            print(f"  added {player}/{side} ({len(zones)} total). Draw the next polygon.")
            selector.clear()
            state["verts"] = []
        elif event.key == "w":
            with open(out_path, "w") as f:
                json.dump(zones, f, indent=2)
            print(f"  wrote {len(zones)} zones to {out_path}")
        elif event.key == "q":
            plt.close(fig)

    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_annotate_build_zone.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tools/annotate_zones.py tests/test_annotate_build_zone.py
git commit -m "feat(tools): add matplotlib zone annotation tool"
```

---

### Task 9: Dev deps, docs, and full verification

**Files:**
- Modify: `pyproject.toml` (dev deps)
- Modify: `README.md` (document the new pieces)

- [ ] **Step 1: Add dev dependencies**

In `pyproject.toml`, change the `[dependency-groups]` `dev` list from:

```toml
dev = [
    "pyinstaller>=6.20.0",
]
```

to:

```toml
dev = [
    "pyinstaller>=6.20.0",
    "pytest>=9.0.0",
    "matplotlib>=3.10.0",
]
```

- [ ] **Step 2: Document the new workflow in README.md**

Under the "Hockey-player module" section in `README.md`, add this subsection:

```markdown
### Zones (Phase A)

Player selection uses normalized polygon zones in `robot/zones.json` (coordinates
in `[0,1]`, image-space, on the `dynamic-crop` frame). To (re)draw them on a saved
frame:

    .venv/bin/python tools/annotate_zones.py --image <frame.jpeg> --out robot/zones.json

`robot/zones.py` loads the polygons and `select(u, v)` returns `(PlayerID, side)`
via point-in-polygon; `robot/playbook.py` maps that to a motor sequence. Rod state
is readable via `robot/state.py` (`{"cmd": "get_position"}`):

    .venv/bin/python -m robot.state center
```

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS — all tests from Tasks 1–8 green (point-in-polygon, select, seed, select_playbook, vision puck, component map, build_zone).

- [ ] **Step 4: Final import smoke test**

Run: `.venv/bin/python -c "import main, run_play, robot.vision, robot.zones, robot.state, robot.execution, robot.playbook; print('all imports OK')"`
Expected: `all imports OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml README.md
git commit -m "docs: document Phase A zones workflow; pin dev deps"
```

---

## Manual (hardware) verification

These require the live robot and are done after the automated tasks, on the bench:

- [ ] **Annotation tool:** `.venv/bin/python tools/annotate_zones.py` — confirm the saved frame loads with the cyan legacy boxes overlaid, a polygon can be drawn, Enter prompts for player/side, and `w` writes `robot/zones.json`.
- [ ] **Vision normalization sanity:** run a one-shot detection and confirm the logged `(u, v)` are sane for the known puck in the sample frame (lower-center-right ⇒ roughly `u≈0.66, v≈0.66`), **not** near `(0, 0)`. If they come back ≈0, the detector isn't populating `*_normalized` fields — switch `puck_uv_from_detections` to pixel centers divided by image size (use `normalize_point` with dims from `get_images`).
- [ ] **`get_position`:** `.venv/bin/python -m robot.state center` prints `{'t': ..., 'r': ..., 't_moving': ..., 'r_moving': ...}`.
- [ ] **Loop:** `.venv/bin/python main.py --loop` selects a sensible player for a placed puck and logs per-step `t_final`/`r_final` during execution.

---

## Spec coverage map

| Spec section | Task(s) |
| --- | --- |
| 4.1 `zones.json` format | 2, 3 |
| 4.2 annotation tool | 8 |
| 4.3 `zones.py` select geometry | 1, 2 |
| 4.4 playbook wiring + remove `_center_line_y` | 4 |
| 4.5 vision normalized `(u,v)` | 5, 6 |
| 4.6 `get_position` plumbing + log `t_final` | 7 |
| §5 runtime data flow (threshold normalized) | 6 |
| §6 error handling (no-match, missing json) | 2, 4 |
| §7 testing | 1–5, 7, 8 |
