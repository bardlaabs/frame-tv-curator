"""E-paper card via open_epaper_link.drawcustom."""
import os, logging, threading
from . import config, ha, render
log = logging.getLogger("epaper")
_lock = threading.Lock()

def push(cfg, sidecar, dry_run=False):
    if not cfg.get("enabled"):
        return None
    with _lock:
        return _push(cfg, sidecar, dry_run)

def _push(cfg, sidecar, dry_run):
    size = tuple(cfg.get("size") or render.EPAPER["size"])
    im = render.render_epaper(sidecar, style=cfg.get("style", "gallery"), size=size)
    os.makedirs(config.EPAPER_DIR, exist_ok=True)
    dest = os.path.join(config.EPAPER_DIR, "card.png")
    im.save(dest)
    payload = {"device_id": [cfg["device_id"]], "background": "white", "rotate": 0, "dither": "0",
               "ttl": cfg.get("ttl", 60), "refresh_type": cfg.get("refresh_type", "0"), "dry-run": dry_run,
               "payload": [{"type": "dlimg", "url": "/media/frame/_epaper/card.png", "x": 0, "y": 0,
                            "xsize": size[0], "ysize": size[1]}]}
    try:
        ha.call("open_epaper_link", "drawcustom", payload)
    except Exception as e:
        log.warning("drawcustom failed: %s", e)
    return dest
