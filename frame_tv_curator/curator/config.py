import os, json

MEDIA = os.environ.get("FC_MEDIA", "/media")
ROOT = os.path.join(MEDIA, "frame")
DATA = os.environ.get("FC_DATA", "/data")
RENDER_DIR = os.path.join(ROOT, "_rendered")
EPAPER_DIR = os.path.join(ROOT, "_epaper")
IMG_EXT = (".jpg", ".jpeg", ".png")


def options():
    o = {"log_level": "info", "tv_ip": "", "dry_run": False, "smithsonian_key": ""}
    p = os.path.join(DATA, "options.json")
    if os.path.exists(p):
        try:
            o.update(json.load(open(p)))
        except Exception:
            pass
    if os.environ.get("FC_DRY_RUN"):
        o["dry_run"] = True
    return o


def apply_log_level(setting):
    """Runtime log level: the Settings-tab choice wins; blank falls back to the add-on option."""
    import logging
    lvl = (setting or options().get("log_level") or "info").upper()
    logging.getLogger().setLevel(getattr(logging, lvl, logging.INFO))
    return lvl
