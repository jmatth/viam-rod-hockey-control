# tools/annotate_zones.py
"""Draw player-zone polygons on a saved dynamic-crop frame, in your browser.

    .venv/bin/python tools/annotate_zones.py --image <frame.jpeg> --out robot/zones.json

Starts a tiny local web server (stdlib only — no matplotlib / Qt / tkinter) and
opens a page with the frame on a canvas. The current robot/zones.json is loaded
for editing, and the legacy boxes are shown faintly for reference.

The page is served from tools/annotate_zones.html on every request, so editing
that file and reloading the browser picks up changes — no server restart needed.
(Changing PLAYERS/SIDES below or --scale still needs a restart, since those are
injected server-side.)

Interaction:
  - Click to drop polygon vertices on the image.
  - Pick player + side, click "Finish zone" to commit the polygon.
  - "Undo point" / "Remove last zone" to correct mistakes; per-row x deletes one.
  - "Save" writes robot/zones.json (normalized to [0,1]). Vertices are normalized
    server-side via build_zone, the same function used by the seeded zones.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Allow running directly as `python tools/annotate_zones.py` (not only `-m tools...`):
# put the repo root on sys.path so the `tools` package resolves.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

from tools.seed_zones_from_legacy import LEGACY_ZONES, REF_W, REF_H
from robot.const import ROBOT_ADDRESS, ROBOT_API_KEY, ROBOT_API_KEY_ID
from robot.logging_setup import configure as configure_logging
from viam.robot.client import RobotClient
from viam.components.camera import Camera

log = logging.getLogger(__name__)

PLAYERS = ["center", "right_wing", "left_wing", "right_d", "left_d"]
SIDES = ["left", "middle_left", "middle_right", "right", "bottom_left", "bottom_right"]

_PAGE_PATH = os.path.join(os.path.dirname(__file__), "annotate_zones.html")


def build_zone(player, side, verts_px, width, height):
    """Return a zone dict with the vertices normalized to [0, 1] (rounded 4dp)."""
    polygon = [[round(x / width, 4), round(y / height, 4)] for (x, y) in verts_px]
    return {"player": player, "side": side, "polygon": polygon}


def _legacy_boxes_px(width, height):
    """Legacy zone boxes scaled from the reference crop to this image's pixels."""
    sx, sy = width / REF_W, height / REF_H
    boxes = []
    for z in LEGACY_ZONES:
        boxes.append({
            "player": z["player"], "side": z["side"],
            "x": z["x_min"] * sx, "y": z["y_min"] * sy,
            "w": (z["x_max"] - z["x_min"]) * sx, "h": (z["y_max"] - z["y_min"]) * sy,
        })
    return boxes


def _existing_zones_px(out_path, width, height):
    """Existing zones.json polygons converted to image-pixel vertices for editing."""
    if not os.path.exists(out_path):
        return []
    with open(out_path) as f:
        raw = json.load(f)
    out = []
    for z in raw:
        out.append({
            "player": z["player"], "side": z["side"],
            "points": [[u * width, v * height] for u, v in z["polygon"]],
        })
    return out


def _render_page(scale):
    """Read the HTML template from disk (fresh each call) and inject server config."""
    with open(_PAGE_PATH) as f:
        page = f.read()
    return (page.replace("%PLAYERS%", json.dumps(PLAYERS))
                .replace("%SIDES%", json.dumps(SIDES))
                .replace("%SCALE%", str(scale)))


async def _grab_live_crop_async():
    opts = RobotClient.Options.with_api_key(api_key=ROBOT_API_KEY, api_key_id=ROBOT_API_KEY_ID)
    machine = await RobotClient.at_address(ROBOT_ADDRESS, opts)
    try:
        cam = Camera.from_robot(machine, "dynamic-crop")
        images, _ = await cam.get_images()
        if not images:
            raise RuntimeError("dynamic-crop returned no images")
        return bytes(images[0].data)
    finally:
        await machine.close()


def grab_live_crop():
    """Fetch one fresh frame from the dynamic-crop camera; return (bytes, content_type)."""
    data = asyncio.run(_grab_live_crop_async())
    ctype = "image/png" if data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    return data, ctype


def _make_handler(image_path, out_path, width, height, scale):
    legacy = _legacy_boxes_px(width, height)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet
            pass

        def _send(self, code, body, ctype="application/json"):
            if isinstance(body, str):
                body = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path == "/":
                self._send(200, _render_page(scale), "text/html; charset=utf-8")
            elif path == "/image":
                with open(image_path, "rb") as f:
                    data = f.read()
                ctype = "image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
                self._send(200, data, ctype)
            elif path == "/live-image":
                try:
                    data, ctype = grab_live_crop()
                    self._send(200, data, ctype)
                except Exception as e:
                    self._send(500, f"{type(e).__name__}: {e}", "text/plain")
            elif path == "/data":
                # Re-read zones.json per request so a Save + reload shows the
                # current file, not a snapshot cached at server startup.
                self._send(200, json.dumps({
                    "width": width, "height": height,
                    "legacy": legacy,
                    "zones": _existing_zones_px(out_path, width, height),
                }))
            else:
                self._send(404, json.dumps({"error": "not found"}))

        def do_POST(self):
            if self.path != "/save":
                self._send(404, json.dumps({"error": "not found"}))
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length))
                out = [build_zone(z["player"], z["side"], z["points"], width, height)
                       for z in payload["zones"]]
                with open(out_path, "w") as f:
                    json.dump(out, f, indent=2)
                self._send(200, json.dumps({"ok": True, "count": len(out), "path": out_path}))
            except Exception as e:  # surface the error to the page
                self._send(200, json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="/home/nick/Downloads/dynamic-crop-2026-06-04_16_56_57.jpeg")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "robot", "zones.json"))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--scale", type=float, default=3.0, help="display zoom factor (default 3)")
    args = parser.parse_args()
    out_path = os.path.abspath(args.out)

    width, height = Image.open(args.image).size

    handler = _make_handler(args.image, out_path, width, height, args.scale)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    url = f"http://127.0.0.1:{args.port}/"
    log.info("Annotating %s (%dx%d) -> %s", args.image, width, height, out_path)
    log.info("Open %s  (Ctrl+C to stop)", url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("stopped.")
        server.shutdown()


if __name__ == "__main__":
    configure_logging()
    main()
