"""
Vision module — detects the puck from the robot's camera.

The loop path (`get_puck_field_coordinates`) returns the puck's position in
normalized field coordinates (u, v) in [0, 1], read from the detections'
server-computed normalized bbox fields. The legacy `get_puck_camera_coordinates`
returns raw camera pixel coordinates and is retained for debugging.
"""

import asyncio
from viam.robot.client import RobotClient
from viam.components.camera import Camera
from viam.services.vision import VisionClient

from .const import (
    ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID,
    CAMERA_X_MIN, CAMERA_X_MAX, CAMERA_Y_MIN, CAMERA_Y_MAX,
)
from engine.constants import WIDTH, HEIGHT

# Class name used by the vision service to label field corner markers
_CORNER_CLASS = "lime-green"
_PUCK_CLASS   = "green"

_machine = None


async def _get_machine():
    global _machine
    if _machine is None:
        opts = RobotClient.Options.with_api_key(api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID)
        _machine = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    return _machine


async def _reset_machine():
    global _machine
    if _machine is not None:
        try:
            await _machine.close()
        except Exception:
            pass
        _machine = None


def get_center(bbox):
    """Return the (x, y) center of a bounding box."""
    return ((bbox.x_min + bbox.x_max) / 2, (bbox.y_min + bbox.y_max) / 2)


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


def group_by_y(detections, threshold=30):
    """Group bounding boxes by y-center proximity.

    Returns a sorted list of averaged y-centers, one per cluster.
    Useful for collapsing multiple detections of the same object row.
    """
    y_centers = sorted(get_center(d)[1] for d in detections)
    groups = []
    for y in y_centers:
        for group in groups:
            if abs(y - group['avg']) <= threshold:
                group['vals'].append(y)
                group['avg'] = sum(group['vals']) / len(group['vals'])
                break
        else:
            groups.append({'vals': [y], 'avg': y})
    return [round(g['avg'], 1) for g in groups]


def scale_puck_coords(camera_x, camera_y, cam_x_min=CAMERA_X_MIN, cam_x_max=CAMERA_X_MAX,
                      cam_y_min=CAMERA_Y_MIN, cam_y_max=CAMERA_Y_MAX):
    """Map a puck position from camera space to game pixel space.

    Camera is landscape and rotated 90°: camera_x → game_y (long axis),
    camera_y → game_x (short axis). Clamps to camera bounds before mapping.
    """
    camera_x = max(min(camera_x, cam_x_max), cam_x_min)
    camera_y = max(min(camera_y, cam_y_max), cam_y_min)

    game_x = (cam_y_max - camera_y) / (cam_y_max - cam_y_min) * WIDTH
    game_y = (camera_x - cam_x_min) / (cam_x_max - cam_x_min) * HEIGHT

    return game_x, game_y


async def get_puck_camera_coordinates():
    """Detect the puck and return its raw camera (x, y).

    Reuses a persistent robot connection; reconnects automatically on error.
    Returns the averaged center of all puck detections, or (None, None).
    """
    try:
        machine = await _get_machine()
        vision1 = VisionClient.from_robot(machine, "green-puck-detector")
        puck_detections = await vision1.get_detections_from_camera("dynamic-crop")

        pink = [d for d in puck_detections if d.class_name == _PUCK_CLASS]
        if not pink:
            return None, None

        centers = [get_center(d) for d in pink]
        camera_x = sum(c[0] for c in centers) / len(centers)
        camera_y = sum(c[1] for c in centers) / len(centers)
        print(f"Camera puck: x={camera_x:.1f}, y={camera_y:.1f}")
        return camera_x, camera_y
    except Exception:
        await _reset_machine()
        raise


async def get_puck_field_coordinates():
    """Detect the puck and return its normalized (u, v) field position.

    Reuses a persistent robot connection; reconnects automatically on error.
    Returns (u, v) in [0, 1], or (None, None) if no puck is detected.
    """
    try:
        machine = await _get_machine()
        vision1 = VisionClient.from_robot(machine, "green-puck-detector")
        detections = await vision1.get_detections_from_camera("dynamic-crop")
        u, v = puck_uv_from_detections(detections)
        if u is not None:
            print(f"Puck field coords: u={u:.3f}, v={v:.3f}")
        return u, v
    except Exception:
        await _reset_machine()
        raise


def _field_bounds_from_corners(detections):
    """Extract camera-space field bounds from corner marker detections.

    Returns (x_min, x_max, y_min, y_max) or None if fewer than 2 corners found.
    """
    corners = [d for d in detections if d.class_name == _CORNER_CLASS]
    if len(corners) < 2:
        return None
    xs = [get_center(d)[0] for d in corners]
    ys = [get_center(d)[1] for d in corners]
    return min(xs), max(xs), min(ys), max(ys)


# --- Standalone test ---
async def _main():
    machine = await _get_machine()
    try:
        vision1 = VisionClient.from_robot(machine, "green-puck-detector")
        vision2 = VisionClient.from_robot(machine, "dynamic-crop-detector")

        puck_detections, corner_detections = await asyncio.gather(
            vision1.get_detections_from_camera("dynamic-crop"),
            vision2.get_detections_from_camera("cam"),
        )

        # Report all detections with confidence scores for debugging
        all_detections = puck_detections + corner_detections
        print(f"Raw detections ({len(all_detections)}):")
        for d in all_detections:
            cx, cy = get_center(d)
            print(f"  {d.class_name:12s}  conf={d.confidence:.2f}  center=({cx:.0f}, {cy:.0f})")

        # Derive field bounds from corner markers
        bounds = _field_bounds_from_corners(corner_detections)
        if bounds:
            cam_x_min, cam_x_max, cam_y_min, cam_y_max = bounds
            print(f"Corner-derived camera bounds: x=[{cam_x_min:.1f}, {cam_x_max:.1f}], y=[{cam_y_min:.1f}, {cam_y_max:.1f}]")
        else:
            cam_x_min, cam_x_max = CAMERA_X_MIN, CAMERA_X_MAX
            cam_y_min, cam_y_max = CAMERA_Y_MIN, CAMERA_Y_MAX
            print("No corner markers detected — using hardcoded camera bounds.")

        # Find puck — average all centers for a stable position
        pink = [d for d in puck_detections if d.class_name == _PUCK_CLASS]
        if not pink:
            print("No puck detected.")
            return

        centers = [get_center(d) for d in pink]
        camera_x = sum(c[0] for c in centers) / len(centers)
        camera_y = sum(c[1] for c in centers) / len(centers)
        print(f"Camera puck ({len(pink)} detections):  x={camera_x:.1f}, y={camera_y:.1f}")

        # Map to full game coordinates using field bounds
        game_x = (cam_y_max - camera_y) / (cam_y_max - cam_y_min) * WIDTH
        game_y = (camera_x - cam_x_min) / (cam_x_max - cam_x_min) * HEIGHT
        print(f"Game coordinates: x={game_x:.1f}, y={game_y:.1f}")

    finally:
        await _reset_machine()

if __name__ == '__main__':
    asyncio.run(_main())
