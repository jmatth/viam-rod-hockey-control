# Bubble Hockey Robot

An autonomous bubble hockey robot that uses computer vision and physics simulation to play the game.

## Overview

The robot uses a camera to detect the puck position, runs a physics-based simulation to find the optimal player action, and sends motor commands via the Viam robotics platform.

## Project Structure

```
├── main.py          # Robot entry point
├── simulate.py      # CLI simulator for testing
├── move.py          # Ad-hoc script: drive all players to a (t, r) pose
├── engine/          # Python game engine
│   ├── constants.py     # Numeric constants, zone boundaries, PlayerID enum
│   ├── entities.py      # Player, CurvedPlayer, Puck classes + player instances
│   ├── planner.py       # Action planning and physics simulation
│   └── display.py       # pygame rendering (field, episode playback)
└── robot/           # Viam hardware integration
    ├── const.py         # Robot credentials, camera bounds, motor constants
    ├── vision.py        # Camera-based puck detection
    ├── playbook.py      # Calibrated DoCommand sequences per player/zone
    └── execution.py     # Sends DoCommands to hockey-player components
```

### Hockey-player module

Motor control is delegated to a per-player **hockey-player Viam module** configured on the robot (one Generic component per player: `center-hockey-player`, `left-wing-hockey-player`, `right-wing-hockey-player`, `left-defense-hockey-player`, `right-defense-hockey-player`). Python only sends high-level `DoCommand` payloads — the module handles the actual motor encoder math and slide/rotation limits.

**DoCommand payload** (all fields optional; omit an axis to skip it):

| Field              | Type   | Range    | Meaning                                                              |
| ------------------ | ------ | -------- | -------------------------------------------------------------------- |
| `t`                | float  | `[0, 1]` | Translation target, normalized over `[min_translation_mm, max_translation_mm]` |
| `r`                | float  | `[0, 360]` | Rotation target, in degrees                                        |
| `rpm`              | float  | —        | Rotation speed (defaults from module config)                         |
| `speed_mm_per_sec` | float  | —        | Translation speed (defaults from module config)                      |

Calibrated sequences live in `robot/playbook.py`; `robot/execution.py` walks a sequence and forwards each step to the right player's component.

## How It Works

1. **Vision** — the camera detects the puck position and scales it to game coordinates
2. **Planning** — `plan_action` selects the best player for the puck's zone and searches for the optimal action using a physics simulation
3. **Execution** — motor commands are sent to the robot via Viam

### Action Planning (`engine/planner.py`)

| Function                           | Description                                                      |
| ---------------------------------- | ---------------------------------------------------------------- |
| `plan_action(puck_x, puck_y)`      | Top-level: picks player by zone, returns `(action, PlayerID)`    |
| `find_best_action_for_player(...)` | Two-phase search (guided + random) for a given player and target |
| `simulate_action_for_player(...)`  | Runs a single 100-frame physics simulation and returns a score   |

## Requirements

- Python 3.x
- pygame
- viam-sdk

## Setup

1. Install dependencies with `uv`:

```bash
uv sync
```

2. Configure credentials, camera bounds, and motor constants in `robot/const.py`

## Usage

### Run the robot

Detects the puck, plans the best action, and executes it:

```bash
python main.py
```

### Simulate a shot (with visualization)

```bash
python simulate.py --puck_x 225 --puck_y 400
```

### Loop mode — feed each final puck position back as the next start

```bash
python simulate.py --puck_x 225 --puck_y 400 --loop
```

### Headless mode — no pygame window, just prints the action

```bash
python simulate.py --puck_x 225 --puck_y 400 --headless
```

### Headless loop

```bash
python simulate.py --puck_x 225 --puck_y 400 --loop --headless
```

### Drive all players to a pose (smoke test)

Sends the same `(t, r)` to every hockey-player component concurrently — useful for verifying connectivity and rough calibration:

```bash
python move.py 0.5 90
```

## Built With

- [Viam](https://www.viam.com/) - Robotics platform for hardware control
- [Pygame](https://www.pygame.org/) - Physics simulation and visualization

## License

MIT
