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
  "vision_service": "green-puck-detector",
  "camera": "dynamic-crop",
  "poll_interval": 0.25,
  "stability_threshold": 0.03,
  "stability_delay": 0.15
}
```

### Attributes

| Name                  | Type   | Required | Description                                                          |
| --------------------- | ------ | -------- | -------------------------------------------------------------------- |
| `center` … `right_d`  | string | no       | Name of each hockey-player Generic component (declared as deps)      |
| `vision_service`      | string | no       | Name of the puck-detector vision service (declared as a dep)         |
| `camera`              | string | no       | Camera name the vision service reads detections from                 |
| `poll_interval`       | float  | no       | Seconds between vision polls (default 0.25)                          |
| `stability_threshold` | float  | no       | Max normalized puck movement between the two stability readings      |
| `stability_delay`     | float  | no       | Seconds between the two stability readings (default 0.15)            |

## DoCommand

| Command             | Effect                                                                  | Returns                                  |
| ------------------- | ----------------------------------------------------------------------- | ---------------------------------------- |
| `{"cmd": "start"}`  | Start the control loop (no-op if already running)                       | `{"running": true, "status": "started"}` |
| `{"cmd": "stop"}`   | Cancel the loop and in-flight plays, send every rod to home pose        | `{"running": false, "status": "stopped"}`|
| `{"cmd": "status"}` | Report loop state                                                       | `{"running": true/false}`                |

The loop also stops (with the same cleanup) when the service is closed, and
restarts automatically across a reconfigure if it was running.
