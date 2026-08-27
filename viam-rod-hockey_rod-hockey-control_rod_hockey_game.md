# Model viam-rod-hockey:rod-hockey-control:rod_hockey_game

Generic service that runs the rod-hockey control loop (vision → playbook →
execution) on the machine. Start and stop the loop with `DoCommand`.

## Configuration

All attributes are optional — the defaults match the standard machine config.

```json
{
  "center": "center-hockey-player",
  "left_wing": "left-wing-hockey-player",
  "right_wing": "right-wing-hockey-player",
  "left_d": "left-defense-hockey-player",
  "right_d": "right-defense-hockey-player",
  "center_gantry": "center-gantry",
  "left_wing_gantry": "left-wing-gantry",
  "right_wing_gantry": "right-wing-gantry",
  "left_d_gantry": "left-defense-gantry",
  "right_d_gantry": "right-defense-gantry",
  "vision_service": "green-puck-detector",
  "camera": "dynamic-crop",
  "poll_interval": 0.25,
  "stability_threshold": 0.03,
  "stability_delay": 0.15,
  "log_level": "info"
}
```

### Attributes

| Name                  | Type   | Required | Description                                                          |
| --------------------- | ------ | -------- | -------------------------------------------------------------------- |
| `center` … `right_d`  | string | no       | Name of each hockey-player Generic component (declared as deps)      |
| `center_gantry` … `right_d_gantry` | string | no | Name of each player's gantry component (declared as deps; homed on start) |
| `vision_service`      | string | no       | Name of the puck-detector vision service (declared as a dep)         |
| `camera`              | string | no       | Camera name the vision service reads detections from                 |
| `poll_interval`       | float  | no       | Seconds between vision polls (default 0.25)                          |
| `stability_threshold` | float  | no       | Max normalized puck movement between the two stability readings      |
| `stability_delay`     | float  | no       | Seconds between the two stability readings (default 0.15)            |
| `log_level`           | string | no       | Level for the game-loop logs: `debug`/`info`/`warning`/`error` (default `info`) |

## DoCommand

| Command             | Effect                                                                  | Returns                                  |
| ------------------- | ----------------------------------------------------------------------- | ---------------------------------------- |
| `{"cmd": "start"}`  | Home all player gantries, then start the control loop (no-op if already running). Pass `"home": false` to skip homing. | `{"running": true, "status": "started (homing gantries first)"}` |
| `{"cmd": "stop"}`   | Cancel the loop and in-flight plays, send every rod to home pose        | `{"running": false, "status": "stopped"}`|
| `{"cmd": "status"}` | Report loop state                                                       | `{"running": true/false}`                |
| `{"cmd": "home"}`   | Home all player gantries without starting the loop (refused while the loop is running) | `{"homed": true/false}`  |

`start` returns immediately; homing (and then the loop) runs in the background.
If any gantry fails to home, the loop does not start — the failure is logged
and `status` reports `running: false`.

The loop also stops (with the same cleanup) when the service is closed, and
restarts automatically across a reconfigure if it was running.

## Logging

Game-loop logs (puck detections, playbook selection/execution, errors) are
forwarded to viam-server and show up in the machine's logs under the `robot.*`
logger names. Set `"log_level": "debug"` to also see per-poll detail
(no-puck polls, puck-moving skips, per-step DoCommand results).
