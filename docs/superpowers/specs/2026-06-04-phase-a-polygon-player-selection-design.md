# Phase A — Polygon-based, position-aware player selection

**Date:** 2026-06-04
**Status:** Approved design, pre-implementation
**Roadmap:** Phase A (this doc) → Phase B (per-rod `(t,r)` homography) → Phase C (closed-loop dynamic play). Each phase gets its own spec → plan → build.

## 1. Motivation

Today the loop (`python main.py --loop`) decides which rod to move by testing the
puck's pixel position against axis-aligned **bounding boxes** (`_ZONES` in
`robot/playbook.py`), in raw `dynamic-crop` pixel coordinates. This works, but is
brittle in three ways we want to retire as groundwork for B and C:

- **Rectangles can't follow the real geometry** of each rod's reachable region;
  overlaps are resolved only by fragile list ordering.
- **Zones are absolute pixels** tied to one crop size, so a camera bump that
  changes the crop scale shifts every boundary.
- **The rod's true state is invisible to us.** The module already reports it, and
  even `doMotion` returns `t_final`/`r_final` on every move — but `execution.py`
  discards the return value.

Phase A is **future-proofing, not a bug fix**: it replaces boxes with polygons in
a normalized field frame, and starts *observing* rod state — laying the seams B
and C plug into — without changing how plays are chosen for a given position.

## 2. Key facts this design rests on (verified)

- **`dynamic-crop` already produces a corner-anchored field frame.**
  `~/dynamicDetections/module.go` (`computeCropBounds`, `Images`) takes a C270
  frame, runs **vision-2** which must return **exactly 4 detections** (the corner
  markers), computes the **axis-aligned bounding box of their 4 centers**, and
  crops C270 to it. **vision-1** then detects the orange puck (`#fb7838`) *inside
  that crop*. The crop is recomputed every frame, so it self-corrects for camera
  translation and scale drift.
- **Therefore puck coordinates are already in field space.** Today's `_ZONES`
  (x ≤ ~485, y ≤ ~280) are simply that crop's pixel size — the reference frame
  `dynamic-crop-2026-06-04_16_56_57.jpeg` is **538×284**. The "game pixels"
  comment at `playbook.py:27` is stale; the real units are dynamic-crop pixels.
- **A needs no homography.** Because the puck and the polygons both live in the
  `dynamic-crop` frame, any perspective keystoning is identical for both and
  cancels out in a point-in-polygon test. Metric rectification only matters when
  we need true angles — that is **Phase B**.
- **`{"cmd":"get_position"}` is implemented and deployed.** `hockey-player`
  (`do_command.go:doGetPosition`, routed in `module.go:139-148`) returns
  `{"t", "r", "t_moving", "r_moving"}`. No Go change is required in any phase A/B/C
  capability we depend on here.

## 3. Coordinate system

All Phase A geometry is in **normalized field coordinates** `(u, v)`, image-space
origin (top-left), `u` to the right, `v` down:

```
u = puck_x_px / crop_width_px      v = puck_y_px / crop_height_px      u, v ∈ [0, 1]
```

Normalizing by the *live* crop size makes zones invariant to crop-scale changes
(camera bump → corners move → crop resizes → polygons scale with it).

## 4. Components

### 4.1 Zone data format — `robot/zones.json`

An **ordered** list (first match wins, preserving today's LEFT_WING-before-LEFT_D
priority). One polygon per `(player, side)` — so **side comes straight from the
polygon**, which lets us delete CENTER's special sloped-line logic
(`_center_line_y`, `_center_side`). Coordinates are normalized `[0,1]`.

```json
[
  { "player": "left_wing", "side": "bottom_right", "polygon": [[0.14,0.39],[0.29,0.39],[0.29,0.90],[0.14,0.90]] },
  { "player": "center",    "side": "left",         "polygon": [[...],[...]] }
]
```

- Players: `center, right_wing, left_wing, right_d, left_d`.
- Sides: `left, right, bottom_left, bottom_right` (the `bottom_*` sides are only
  used by `right_wing` and `left_wing`, matching the existing playbooks).

### 4.2 Annotation tool — `tools/annotate_zones.py`

A matplotlib tool (uses `PolygonSelector`; no robot connection required — works on
a saved frame):

- **Input:** path to a saved `dynamic-crop` frame (default:
  `/home/nick/Downloads/dynamic-crop-2026-06-04_16_56_57.jpeg`, overridable via
  `--image`). Output path overridable via `--out` (default `robot/zones.json`).
- **Reference overlay:** the current `_ZONES` rectangles drawn faintly **directly
  in the loaded image's pixel space** (they are already in dynamic-crop pixels, so
  no rescaling is attempted). They are a rough visual guide only — exact alignment
  is not required — letting the user trace/extend existing behavior rather than
  start blind.
- **Workflow:** draw a polygon → a **terminal prompt** asks for `player` then
  `side` (validated against the allowed values) → repeat. Keys on the canvas: new
  polygon, undo last, save, quit.
- **Output:** writes `robot/zones.json`, converting every clicked vertex to
  normalized coords by dividing by the loaded image width/height.

This frame-capture + overlay harness is intentionally reusable as Phase B's
per-rod calibration UI.

### 4.3 Selection geometry — `robot/zones.py` (new)

Owns geometry only; knows nothing about motor sequences.

- `load_zones(path="robot/zones.json")` — parse once, cache at module load; raise
  a clear error if the file is missing or malformed.
- `select(u, v) -> (PlayerID, side) | (None, None)` — iterate zones in order,
  return the first whose polygon contains `(u, v)`.
- `_point_in_polygon(u, v, polygon) -> bool` — small ray-casting implementation,
  **no new runtime dependency** (matplotlib is only imported by the tool).

### 4.4 Playbook wiring — `robot/playbook.py`

- `select_playbook(u, v)` keeps its name and `(PlayerID, sequence)` return, but now
  takes **normalized** coords, delegates the geometry to `zones.select(u, v)`, and
  maps `(player, side) → sequence` via the existing `_PLAYBOOK_MAP` /
  `get_rw_sequence(side, "shot")`.
- **Removed:** `_ZONES`, `_select_zone`, `_center_line_y`, `_center_side`, and the
  CENTER side special-case. The playbook *sequence* tables
  (`_CENTER_PLAYBOOK`, etc.) are unchanged.

### 4.5 Vision — `robot/vision.py`

- New `get_puck_field_coordinates() -> (u, v) | (None, None)`:
  1. Fetch the `dynamic-crop` image **and** run detections on that same image
     (`camera.get_image` + `vision1.get_detections(img)`), so the puck center and
     the crop size come from **one coherent frame**.
  2. Average the orange detections' centers → `(puck_x, puck_y)` px.
  3. Normalize by `img.size` → `(u, v)`.
- The raw `get_puck_camera_coordinates()` is retained for debugging.
- `main.py`'s `get_puck_coordinates()` wrapper now calls the field-coordinate
  function; both the loop and the single-shot `run_playbook_from_puck_position`
  path therefore speak normalized coords end to end.

### 4.6 Rod-state plumbing — `robot/state.py` (new, the B-seam)

- `get_player_position(player_id) -> {t, r, t_moving, r_moving}` — sends
  `{"cmd":"get_position"}` to the player's `hockey-player` component.
- `robot/execution.py`: stop discarding `do_command(step)`'s return; **log** the
  `t_final`/`r_final` each step reports.
- Phase A use is **observability only** — logging. No control-flow change. B is
  where this starts steering plays; C polls it mid-play.

## 5. Runtime data flow (loop, after Phase A)

1. **Vision** → `(u, v)` normalized, or `None`.
2. **Stability gate** (unchanged in concept) — two readings; act only if they
   agree. Threshold is redefined in **normalized units**, default `0.03`
   (≈16 px on a 538-wide crop; documents the old `15 px`).
3. **Select** → `select_playbook(u, v)` → `(player, sequence)` or `(None, None)`.
4. **Execute** → `execute_with_coordination` → `execute_sequence` (now logs
   reported `t_final`/`r_final`).

`main.py`'s loop structure, timeouts, and error handling are otherwise untouched.

## 6. Error handling

- **Vision / dynamic-crop failure** (e.g. vision-2 ≠ 4 corners → module errors):
  propagates as today; the loop's existing `try/except` sleeps 5 s and retries.
- **`zones.json` missing or malformed:** raise a clear error at load (fail fast —
  the loop cannot select without zones).
- **No polygon matches `(u, v)`:** `select` returns `(None, None)` → existing
  "No playbook for this position." behavior.
- **`get_position` failure:** log a warning and continue — it is observability
  only and must never break the control loop.

## 7. Testing

Pure-function units (no hardware), under `tests/`:

- `_point_in_polygon`: inside, outside, on-edge, concave-polygon, and
  outside-bounding-box-but-inside-concavity cases.
- `zones.select`: against a synthetic `zones.json` — points map to the expected
  `(player, side)`; first-match-wins on deliberately overlapping polygons;
  `(None, None)` outside all polygons.
- Normalization math: px ↔ `(u, v)` round-trips.

Hardware-dependent paths (annotation tool, live vision, `get_position`) are
verified manually: run the tool against the saved frame, draw zones, run the loop,
and confirm the logged `(u,v)`/player/`t_final` values are sane.

## 8. Scope guardrails (non-goals)

- **No homography / metric rectification** — Phase B.
- **No continuous `(t,r)` interpolation**; sides stay discrete — Phase B.
- **No closed-loop control or opponent sensing** — Phase C.
- **No Go module changes** (`hockey-player`, `dynamic-crop`).
- **No change to the puck-stability concept** (rod motion ≠ puck motion).
- Selection for a given puck position should stay behaviorally equivalent to
  today's, modulo deliberate re-drawing of zone boundaries.

## 9. Seams for B and C

- **Normalized `(u, v)` from vision** — B attaches a per-zone homography mapping
  `(u, v)` → metric field → target `(t, r)`.
- **`robot/zones.py` geometry separate from `playbook.py` sequences** — B can hang
  a per-zone `(t,r)` box / correspondence set off each zone without touching
  selection.
- **`get_player_position` exists** — B consumes it to compute moves from current
  state; C polls it during a play to track a moving puck.

## 10. File summary

| File | Change |
| --- | --- |
| `robot/zones.json` | **new** — generated by the annotation tool |
| `tools/annotate_zones.py` | **new** — matplotlib annotation tool |
| `robot/zones.py` | **new** — polygon load + point-in-polygon `select` |
| `robot/state.py` | **new** — `get_player_position` (`{"cmd":"get_position"}`) |
| `robot/vision.py` | `get_puck_field_coordinates()` returning normalized `(u,v)` |
| `robot/playbook.py` | `select_playbook(u,v)` delegates to `zones`; remove `_ZONES`/`_center_line_y` |
| `robot/execution.py` | log reported `t_final`/`r_final` instead of discarding |
| `main.py` | wrapper calls field-coord vision; stability threshold normalized |
| `tests/` | unit tests for point-in-polygon, `select`, normalization |
