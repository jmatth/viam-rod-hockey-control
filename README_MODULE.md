# Module rod-hockey-control

Runs the autonomous rod-hockey control loop as a Viam module. The service polls
the puck-detector vision service, waits for the puck to be stable, selects a
calibrated playbook for the zone it landed in, and drives the hockey-player rod
components — all on the machine, with resources injected by viam-server (no API
keys or dialing).

Start/stop the loop from the app's **DoCommand** panel (or any SDK client):

```json
{"cmd": "start"}
{"cmd": "stop"}
{"cmd": "status"}
```

## Models

This module provides the following model(s):

- [`viam-rod-hockey:rod-hockey-control:rod_hockey_game`](viam-rod-hockey_rod-hockey-control_rod_hockey_game.md) - the vision → playbook → execution control loop, start/stoppable via DoCommand

## Local development

Build the module binary and archive:

```bash
./build-module.sh    # → dist/module, dist/archive.tar.gz
```

To test on a machine before publishing, add it to the machine config as a
[local module](https://docs.viam.com/operate/get-started/other-hardware/#test-your-module-locally)
pointing at `dist/module`, then add the service:

```json
{
  "name": "rod-hockey-control",
  "api": "rdk:service:generic",
  "model": "viam-rod-hockey:rod-hockey-control:rod_hockey_game"
}
```

Component/service names and loop tuning are configurable via attributes — see
the [model docs](viam-rod-hockey_rod-hockey-control_rod_hockey_game.md).
