"""MQTT discovery entities (uses the Mosquitto broker via the Supervisor services API)."""
import os, json, logging, urllib.request
log = logging.getLogger("mqtt")
NODE = "frame_tv_curator"

def broker():
    tok = os.environ.get("SUPERVISOR_TOKEN")
    if os.environ.get("FC_MQTT_HOST"):
        return {"host": os.environ["FC_MQTT_HOST"], "port": 1883, "username": None, "password": None}
    r = urllib.request.Request("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {tok}"})
    return json.load(urllib.request.urlopen(r, timeout=10))["data"]

class Entities:
    def __init__(self, engine):
        self.e = engine
        self.c = None

    def start(self):
        import paho.mqtt.client as mqtt
        try:
            b = broker()
        except Exception as ex:
            log.warning("MQTT broker unavailable (%s); entities disabled", ex)
            return
        try:
            self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except Exception:
            self.c = mqtt.Client()
        if b.get("username"):
            self.c.username_pw_set(b["username"], b.get("password"))
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message
        self.c.will_set(f"{NODE}/availability", "offline", retain=True)
        self.c.connect_async(b["host"], int(b.get("port", 1883)))
        self.c.loop_start()
        self.e.listeners.append(self.publish)

    def _dev(self):
        return {"identifiers": [NODE], "name": "Frame TV Curator", "manufacturer": "Local", "model": "Add-on"}

    def _disc(self, comp, key, name, extra):
        cfg = {"name": name, "unique_id": f"{NODE}_{key}", "device": self._dev(),
               "availability_topic": f"{NODE}/availability", **extra}
        self.c.publish(f"homeassistant/{comp}/{NODE}/{key}/config", json.dumps(cfg), retain=True)

    def _on_connect(self, c, *a, **k):
        c.publish(f"{NODE}/availability", "online", retain=True)
        self._disc("sensor", "title", "Current Title", {"state_topic": f"{NODE}/title", "icon": "mdi:palette"})
        self._disc("sensor", "artist", "Current Artist", {"state_topic": f"{NODE}/artist", "icon": "mdi:account-edit"})
        self._disc("sensor", "image", "Current Image", {"state_topic": f"{NODE}/image"})
        self._disc("switch", "rotation", "Rotation", {"state_topic": f"{NODE}/rotation",
                   "command_topic": f"{NODE}/rotation/set", "icon": "mdi:image-multiple"})
        self._disc("button", "next", "Next", {"command_topic": f"{NODE}/next/set", "icon": "mdi:skip-next"})
        self._disc("button", "previous", "Previous", {"command_topic": f"{NODE}/previous/set", "icon": "mdi:skip-previous"})
        self._disc("select", "folder", "Source Folder", {"state_topic": f"{NODE}/folder",
                   "command_topic": f"{NODE}/folder/set", "options": self._folders()})
        self._disc("number", "interval", "Interval (minutes)", {"state_topic": f"{NODE}/interval",
                   "command_topic": f"{NODE}/interval/set", "min": 1, "max": 10080, "step": 1, "mode": "box"})
        c.subscribe(f"{NODE}/+/set")
        self.publish(self.e.status())

    def _folders(self):
        from . import library
        return [f["name"] for f in library.folders()] or ["art"]

    def _on_message(self, c, u, m):
        t, p = m.topic.split("/")[1], m.payload.decode()
        try:
            if t == "next": self.e.next()
            elif t == "previous": self.e.previous()
            elif t == "rotation": self.e.settings.update({"enabled": p == "ON"}); self.publish(self.e.status())
            elif t == "folder": self.e.settings.update({"source": {"mode": "folder", "folder": p}}); self.publish(self.e.status())
            elif t == "interval": self.e.settings.update({"rotation": {"value": float(p), "unit": "minutes"}}); self.publish(self.e.status())
        except Exception:
            log.exception("command %s", t)

    def publish(self, st):
        if not self.c:
            return
        s = self.e.settings.get()
        P = lambda k, v: self.c.publish(f"{NODE}/{k}", "" if v is None else str(v), retain=True)
        P("title", st.get("title")); P("artist", st.get("artist")); P("image", st.get("current"))
        P("rotation", "ON" if st["enabled"] else "OFF")
        P("folder", s["source"].get("folder", "art"))
        r = s["rotation"]; P("interval", int(float(r["value"]) * {"minutes": 1, "hours": 60, "days": 1440}[r["unit"]]))
