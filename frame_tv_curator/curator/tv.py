"""Samsung Frame push: upload -> select -> delete previous (Art Mode API)."""
import os, time, logging, threading
from . import config, ha
log = logging.getLogger("tv")

class TV:
    def __init__(self, cfg, dry_run=False):
        self.cfg, self.dry = cfg, dry_run
        self.lock = threading.Lock()

    def host(self):
        h = self.cfg.get("ip") or config.options().get("tv_ip")
        if not h:
            h = ha.tv_info(self.cfg["entity"]).get("ip")
        return h

    def _art(self):
        from samsungtvws import SamsungTVWS
        tok = os.path.join(config.DATA, "tv_token.txt")
        tv = SamsungTVWS(host=self.host(), port=8002, token_file=tok, name=self.cfg.get("name", "FrameTVCurator"),
                         timeout=30)
        return tv.art()

    def ready(self):
        """Only push while the TV is in Art Mode (selecting art wakes it otherwise)."""
        if self.dry:
            return True, "dry-run"
        info = ha.tv_info(self.cfg["entity"])
        if info.get("art_mode") == "on":
            return True, "ok"
        # HA's attribute can lag; ask the TV itself before giving up
        try:
            if info.get("state") == "on" and str(self._art().get_artmode()).lower() == "on":
                return True, "ok (TV reports Art Mode)"
        except Exception as e:
            log.warning("direct art-mode check failed: %s", e)
        return False, f"TV not in Art Mode (state={info.get('state')}, art_mode={info.get('art_mode')})"

    def push(self, jpeg_path, previous_ids):
        """Returns the new content_id (or None). previous_ids: ids we uploaded earlier, to delete."""
        if self.dry:
            log.info("[dry-run] would upload %s and delete %s", jpeg_path, previous_ids)
            return "DRY-%d" % os.path.getsize(jpeg_path)
        with self.lock:
            art = self._art()
            data = open(jpeg_path, "rb").read()
            cid = art.upload(data, matte="none", portrait_matte="none", file_type="JPEG")
            art.select_image(cid, show=True)
            for old in previous_ids:
                try:
                    art.delete(old)
                except Exception as e:
                    log.warning("delete %s failed: %s", old, e)
            return cid

    def probe(self):
        """Art Mode settings the TV reports: {brightness:{value,min,max}, color_temperature:{...}, sensor}. Cached by the caller."""
        if self.dry:
            return {"brightness": {"value": 5, "min": 1, "max": 10}, "color_temperature": {"value": 0, "min": -5, "max": 5}, "sensor": "off", "dry": True}
        out = {}
        try:
            with self.lock:
                art = self._art()
                raw = art.get_artmode_settings()
                out["raw"] = str(raw)[:600]
                items = raw
                if isinstance(items, dict) and "data" in items:
                    items = items["data"]
                if isinstance(items, str):
                    import json as _j
                    try:
                        items = _j.loads(items)
                    except Exception:
                        items = []
                if isinstance(items, dict):
                    items = [items]
                num = lambda v: (float(v) if v not in (None, "") else None)
                for it in items or []:
                    if not isinstance(it, dict):
                        continue
                    name = it.get("item")
                    if name in ("brightness", "color_temperature"):
                        d = {"value": num(it.get("value"))}
                        if it.get("min") is not None:
                            d["min"] = int(float(it["min"]))
                        if it.get("max") is not None:
                            d["max"] = int(float(it["max"]))
                        out[name] = d
                    elif name == "brightness_sensor_setting":
                        out["sensor"] = it.get("value")
                for name, fn in (("brightness", art.get_brightness), ("color_temperature", art.get_color_temperature)):
                    if name not in out:
                        try:
                            v = fn()
                            if isinstance(v, dict):
                                v = v.get("value", v.get("data"))
                            out[name] = {"value": num(v)}
                        except Exception as ex:
                            out.setdefault("notes", []).append("%s: %s" % (name, ex))
        except Exception as e:
            log.warning("tv probe failed: %s", e)
            out["error"] = str(e)
        return out

    def apply_art(self, brightness=None, color_temp=None, sensor_off=None):
        """Set Art Mode brightness / color tone (TV units) and optionally switch the TV's own brightness sensor off."""
        if self.dry:
            return True, "dry-run"
        try:
            with self.lock:
                art = self._art()
                if sensor_off is not None:
                    art.set_brightness_sensor_setting("off" if sensor_off else "on")
                if brightness is not None:
                    art.set_brightness(int(brightness))
                if color_temp is not None:
                    art.set_color_temperature(int(color_temp))
            return True, "ok"
        except Exception as e:
            log.warning("apply_art failed: %s", e)
            return False, str(e)

    # ---- wake / power helpers -------------------------------------------------------------
    def _up(self):
        """True when the TV answers on its REST port (works even if HA's state is wrong)."""
        import urllib.request, json as _j
        try:
            h = self.host()
            if not h:
                return False
            with urllib.request.urlopen("http://%s:8001/api/v2/" % h, timeout=3) as f:
                return (_j.loads(f.read().decode()).get("device") or {}).get("PowerState", "on") == "on"
        except Exception:
            return False

    def wake(self):
        """Wake-on-LAN. Needs the TV MAC (settings tv.mac). Tries our own UDP packets and HA's wake_on_lan service."""
        import socket, re
        mac = re.sub(r"[^0-9a-fA-F]", "", str(self.cfg.get("mac") or ""))
        if len(mac) != 12:
            return False, "no valid TV MAC address set (TV tab > Connection > MAC address)"
        pkt = b"\xff" * 6 + bytes.fromhex(mac) * 16
        h = self.host() or ""
        dests = ["255.255.255.255"]
        if h.count(".") == 3:
            dests += [h.rsplit(".", 1)[0] + ".255", h]
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sent = 0
        for d in dests:
            for port in (9, 7):
                try:
                    s.sendto(pkt, (d, port)); sent += 1
                except Exception as e:
                    log.debug("WoL to %s:%s failed: %s", d, port, e)
        s.close()
        try:      # HA core runs on the host network, so its packet reaches the LAN even if ours does not (needs the wake_on_lan integration)
            ha.call("wake_on_lan", "send_magic_packet", {"mac": ":".join(mac[i:i + 2] for i in range(0, 12, 2))})
        except Exception as e:
            log.debug("HA wake_on_lan not available: %s", e)
        log.info("sent Wake-on-LAN (%d packets) for %s", sent, mac)
        return True, "Wake-on-LAN sent"

    def _wake_and_wait(self, ent, first_err=None):
        """Try HA turn_on, then Wake-on-LAN; wait until the TV is up. Returns (ok, message)."""
        ha_err = first_err
        if first_err is None:
            try:
                ha.call("media_player", "turn_on", {"entity_id": ent})
            except Exception as e:
                ha_err = e
                log.warning("HA media_player.turn_on failed (%s); using Wake-on-LAN", e)
        for _ in range(3):                      # give HA's own power-on a few seconds first
            time.sleep(2)
            if self._up() or ha.tv_info(ent).get("state") == "on":
                return True, "up"
        ok, why = self.wake()
        for _ in range(25):
            time.sleep(2)
            if self._up() or ha.tv_info(ent).get("state") == "on":
                time.sleep(3)
                return True, "up"
        hint = ""
        if ha_err is not None and "500" in str(ha_err):
            hint = " Home Assistant's own power-on also failed (the samsungtv_smart integration's SmartThings token is probably expired or rejected: re-authorize SmartThings there)."
        log.warning("wake: TV not reachable after Wake-on-LAN (REST up=%s, HA state=%s)", self._up(), ha.tv_info(ent).get("state"))
        return False, "TV did not wake up (%s).%s" % (why, hint)

    def _art_mode_on(self):
        if str(self._art().get_artmode()).lower() != "on":
            self._art().set_artmode(True)

    def _key(self, key):
        from samsungtvws import SamsungTVWS
        tok = os.path.join(config.DATA, "tv_token.txt")
        SamsungTVWS(host=self.host(), port=8002, token_file=tok, name=self.cfg.get("name", "FrameTVCurator"), timeout=15).send_key(key)

    def control(self, action):
        """Remote controls from the web UI. action: art_on | art_off | power_off. Returns (ok, message)."""
        if self.dry:
            return True, "dry-run: would do " + action
        ent = self.cfg["entity"]
        info = ha.tv_info(ent)
        try:
            if action == "art_on":
                if not self._up() and info.get("state") in (None, "off", "unavailable", "standby"):
                    def job():       # waking takes up to a minute: do it in the background so the web request does not time out
                        try:
                            ok, why = self._wake_and_wait(ent)
                            if ok:
                                self._art_mode_on()
                                log.info("art_on: TV woke and Art Mode was set")
                            else:
                                log.warning("art_on: %s", why)
                        except Exception as e:
                            if "ms.channel.client" in str(e):
                                log.info("art_on: TV sent a channel notice; retrying once")
                                try:
                                    time.sleep(3); self._art_mode_on()
                                except Exception as e2:
                                    log.warning("art_on retry failed: %s", e2)
                            else:
                                log.warning("art_on after wake failed: %s", e)
                    threading.Thread(target=job, daemon=True).start()
                    return True, "TV is off: sending Wake-on-LAN. Art Mode will turn on in up to a minute (see the log if it does not)."
                self._art_mode_on()
                return True, "Art Mode on"
            if action == "art_off":
                self._art().set_artmode(False)
                return True, "Art Mode off (TV is showing normal TV)"
            if action == "power_off":
                try:
                    ha.call("media_player", "turn_off", {"entity_id": ent})
                except Exception as e:
                    log.warning("HA media_player.turn_off failed (%s); sending KEY_POWER to the TV", e)
                    self._key("KEY_POWER")
                return True, "Power off sent"
        except Exception as e:
            if "ms.channel.client" in str(e):      # the TV answered with a connect/disconnect notice instead of the reply: the command itself went through
                log.info("tv control %s: TV sent a channel notice (%s); treating as done", action, str(e)[-60:])
                return True, {"art_on": "Art Mode on", "art_off": "Art Mode off", "power_off": "Power off sent"}.get(action, "done") + " (TV sent a connection notice; please confirm on the TV)"
            log.warning("tv control %s failed: %s", action, e)
            return False, "%s failed: %s" % (action, e)
        return False, "unknown action"
