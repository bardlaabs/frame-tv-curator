"""Small thread-safe JSON stores for settings and runtime state."""
import os, json, copy, threading
from . import config

DEFAULT_SETTINGS = {
    "enabled": True,
    "source": {"mode": "folder", "folder": "art", "mix": {"art": 70, "photos": 30}},
    "rotation": {"value": 30, "unit": "minutes", "at_time": "06:00", "quiet_hours": ""},
    # global display defaults; merged under render.DEFAULTS and under each sidecar's own "display"
    "display": {
        "mat": {"enabled": False},
        "placard": {"enabled": True, "template": "modern_minimal", "placement": "overlay",
                    "position": "bottom-right", "scale": 1.0, "margin_pct": 2.2, "mat_layout": "two_line"},
        "overscan": {"top": 0, "right": 0, "bottom": 0, "left": 0, "mode": "placard"},
        "srgb": True,
    },
    "ambient": {
        "brightness": {"mode": "off", "manual": 60, "lux_entity": "", "lux_low": 10, "lux_high": 400, "entity": "",
                       "entity_max": 100, "sun_entity": "sun.sun", "min_pct": 15, "max_pct": 100,
                       "disable_sensor": True, "min_interval_s": 60},
        "color_temp": {"mode": "off", "manual_k": 5000, "entity": "", "sun_entity": "sun.sun", "night_k": 2700,
                       "day_k": 6500, "low_k": 2700, "high_k": 6500, "flip": False, "min_interval_s": 300},
        "light": {"entity": "", "follow": False, "sync_brightness": False, "sync_color_temp": False,
                  "light_min_pct": 10, "light_max_pct": 100},
    },
    "epaper": {"enabled": False, "device_id": "55385339f31a217b95bf7190366e9989", "style": "gallery",
               "size": [522, 152], "ttl": 60, "refresh_type": "0"},
    "schedules": [],
    "log_level": "",
    "birdframe": {"enabled": False, "every_n": 10, "every_minutes": 0, "duration_minutes": 10, "source": "live",
                  "folder": "birds", "host": "local-birdframe-local", "port": 8099},
    "tv": {"ip": "", "entity": "media_player.frametv", "name": "FrameTVCurator", "keep_uploads": 1, "mac": ""},
}


def deep_merge(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class JsonStore:
    def __init__(self, name, default):
        self.path = os.path.join(config.DATA, name)
        self.lock = threading.RLock()
        self.data = copy.deepcopy(default)
        if os.path.exists(self.path):
            try:
                self.data = deep_merge(default, json.load(open(self.path)))
            except Exception:
                pass

    def save(self):
        with self.lock:
            os.makedirs(config.DATA, exist_ok=True)
            tmp = self.path + ".tmp"
            json.dump(self.data, open(tmp, "w"), indent=1)
            os.replace(tmp, self.path)

    def update(self, patch):
        with self.lock:
            self.data = deep_merge(self.data, patch)
            self.save()
            return copy.deepcopy(self.data)

    def get(self):
        with self.lock:
            return copy.deepcopy(self.data)


def settings():
    return JsonStore("settings.json", DEFAULT_SETTINGS)


def state():
    return JsonStore("state.json", {"bags": {}, "history": [], "pos": -1, "current": None,
                                    "tv_ids": [], "since_bird": 0, "last_change": 0})
