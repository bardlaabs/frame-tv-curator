"""Samsung Frame push: upload -> select -> delete previous (Art Mode API)."""
import os, time, logging, threading, hashlib, random
from contextlib import contextmanager
from . import config, ha
log = logging.getLogger("tv")

class TV:
    def __init__(self, cfg, dry_run=False):
        self.cfg, self.dry = cfg, dry_run
        self.lock = threading.RLock()     # one art-channel connection at a time (see _session)
        self.unknown_since = None         # when Art Mode status first became unreadable while the TV is on
        self.last_heal = 0
        self._unk_n = 0
        self._rc = (0, False, "")         # cached direct Art Mode verdict: (valid until, ok, why)

    def host(self):
        h = self.cfg.get("ip") or config.options().get("tv_ip")
        if not h:
            h = ha.tv_info(self.cfg["entity"]).get("ip")
        return h

    @staticmethod
    def _is_notice(e):
        """The TV tells every connected client when another client joins or leaves (ms.channel.clientConnect / clientDisconnect).
        samsungtvws treats such a notice, arriving where it expects the handshake, as a failed connection. No command was sent
        yet, so trying again is safe."""
        return "ms.channel.client" in str(e)

    @staticmethod
    def _brief(e):
        if TV._is_notice(e):
            return "the TV was busy with another connection (join/leave notice)"
        return str(e)[:100] or e.__class__.__name__

    def _art(self, tries=6):
        """A connected Art API object. A join/leave notice from another client during the handshake is retried."""
        from samsungtvws import SamsungTVWS
        tok = os.path.join(config.DATA, "tv_token.txt")
        for i in range(tries):
            art = SamsungTVWS(host=self.host(), port=8002, token_file=tok, name=self.cfg.get("name", "FrameTVCurator"),
                              timeout=30).art()
            try:
                art.open()
                return art
            except Exception as e:
                try:
                    art.close()
                except Exception:
                    pass
                if not self._is_notice(e) or i == tries - 1:
                    raise
                time.sleep(0.5 * (i + 1) + random.random() * 0.5)

    @contextmanager
    def _session(self, wait=90):
        """The only way the add-on talks to the TV's art channel: one connection at a time, always closed afterwards.
        Overlapping connections (this add-on's own threads, Home Assistant's) make the TV broadcast join/leave notices
        that break each other's handshakes."""
        if not self.lock.acquire(timeout=wait):
            raise TimeoutError("the TV connection is busy")
        art = None
        try:
            art = self._art()
            yield art
        finally:
            try:
                if art is not None:
                    art.close()
            except Exception:
                pass
            time.sleep(0.3)               # let the TV announce our leaving before anyone else connects
            self.lock.release()

    def stuck_for(self):
        """Seconds the TV has been on with an Art Mode status we cannot read (0 = fine)."""
        return 0 if self.unknown_since is None else time.time() - self.unknown_since

    def ready(self):
        """Only push while the TV is in Art Mode (selecting art wakes it otherwise).
        Home Assistant's art_mode_status attribute can lag, and is missing for as long as its own Art connection is stuck, so
        when it does not say "on" we ask the TV itself. A question the TV could not answer is "unknown", never "not in Art Mode"."""
        if self.dry:
            return True, "dry-run"
        info = ha.tv_info(self.cfg["entity"])
        st = info.get("state")
        if info.get("art_mode") == "on":
            self.unknown_since, self._unk_n = None, 0
            return True, "ok"
        if st != "on":
            self.unknown_since, self._unk_n = None, 0
            return False, f"TV not in Art Mode (state={st}, art_mode={info.get('art_mode')})"
        now = time.time()
        if self._rc[2] and now < self._rc[0]:         # recent answer: do not open a connection every few seconds
            return self._rc[1], self._rc[2]
        try:
            with self._session(wait=10) as art:
                mode = str(art.get_artmode()).lower()
        except Exception as e:
            self._unk_n += 1
            if self.unknown_since is None:
                self.unknown_since = now
            why = "Art Mode status unknown: %s" % self._brief(e)
            if self._unk_n <= 3 or self._unk_n % 10 == 0:
                log.warning("direct art-mode check failed (%d in a row): %s", self._unk_n, self._brief(e))
            self._rc = (now + min(15 * self._unk_n, 60), False, why)
            return False, why
        self.unknown_since, self._unk_n = None, 0
        res = (True, "ok (TV reports Art Mode)") if mode == "on" else (False, f"TV not in Art Mode (state=on, art_mode={mode})")
        self._rc = (now + 15, res[0], res[1])
        return res

    def heal(self):
        """Reload Home Assistant's Samsung integration: clears an Art connection that stopped answering. -> (ok, message)"""
        ent = self.cfg["entity"]
        try:
            ha.call("homeassistant", "reload_config_entry", {"entity_id": ent})
            self._rc = (0, False, "")
            return True, "reloaded the integration behind %s" % ent
        except Exception as e:
            return False, "could not reload the integration behind %s: %s" % (ent, e)

    def push(self, jpeg_path, previous_ids):
        """Returns the new content_id (or None). previous_ids: ids we uploaded earlier, to delete."""
        if self.dry:
            log.info("[dry-run] would upload %s and delete %s", jpeg_path, previous_ids)
            return "DRY-%d" % os.path.getsize(jpeg_path)
        with self._session() as art:
            data = open(jpeg_path, "rb").read()
            cid = art.upload(data, matte="none", portrait_matte="none", file_type="JPEG")
            art.select_image(cid, show=True)
            for old in previous_ids:
                try:
                    art.delete(old)
                except Exception as e:
                    log.warning("delete %s failed: %s", old, e)
            return cid

    def push_cached(self, jpeg_path, img_id, fav, cache, cc, legacy_ids=()):
        """Like push(), but keeps recent (and favorite) pictures on the TV and reuses them: a picture already on the TV with
        the same rendered bytes is just selected again. Returns (content_id, new_cache, info)."""
        data = open(jpeg_path, "rb").read()
        sha = hashlib.sha1(data).hexdigest()
        now = time.time()
        if self.dry:
            log.info("[dry-run] would cache-push %s (%d cached)", img_id, len(cache))
            return "DRY-%d" % len(data), cache, {"reused": False, "deleted": 0, "cached": len(cache)}
        with self._session() as art:
            try:
                on_tv = {x.get("content_id") for x in (art.available() or [])}
            except Exception as e:
                log.warning("could not list the TV's pictures: %s", e)
                on_tv = None
            cache = [e for e in cache if on_tv is None or e.get("cid") in on_tv]
            hit = next((e for e in cache if e["id"] == img_id and e.get("sha") == sha), None)
            stale = [e for e in cache if e["id"] == img_id and e is not hit]
            reused = False
            if hit:
                try:
                    art.select_image(hit["cid"], show=True)
                    cid, reused = hit["cid"], True
                    hit["ts"], hit["fav"] = now, bool(fav)
                except Exception as e:
                    log.warning("cached picture would not show (%s); uploading again", e)
                    cache.remove(hit)
                    hit = None
            if not hit:
                cid = art.upload(data, matte="none", portrait_matte="none", file_type="JPEG")
                art.select_image(cid, show=True)
                cache.append({"id": img_id, "cid": cid, "sha": sha, "ts": now, "fav": bool(fav)})
            drop = [e["cid"] for e in stale] + [c for c in legacy_ids if c != cid]
            cache = [e for e in cache if e not in stale]
            keep_fav = int(cc.get("max_favorites") or 0) if cc.get("keep_favorites", True) else 0
            favs = sorted([e for e in cache if e.get("fav") and e["cid"] != cid], key=lambda e: -e["ts"])[:keep_fav]
            rest = sorted([e for e in cache if e not in favs and e["cid"] != cid], key=lambda e: -e["ts"])
            recent = rest[:max(0, int(cc.get("keep_recent") or 1) - 1)]
            keep = [e for e in cache if e["cid"] == cid] + favs + recent
            drop += [e["cid"] for e in cache if e not in keep]
            for old in drop:
                try:
                    art.delete(old)
                except Exception as e:
                    log.warning("delete %s failed: %s", old, e)
            return cid, keep, {"reused": reused, "deleted": len(drop), "cached": len(keep)}

    def clear_cache(self, cids):
        if self.dry or not cids:
            return 0
        n = 0
        with self._session() as art:
            for c in cids:
                try:
                    art.delete(c); n += 1
                except Exception as e:
                    log.warning("delete %s failed: %s", c, e)
        return n

    def probe(self):
        """Art Mode settings the TV reports: {brightness:{value,min,max}, color_temperature:{...}, sensor}. Cached by the caller."""
        if self.dry:
            return {"brightness": {"value": 5, "min": 1, "max": 10}, "color_temperature": {"value": 0, "min": -5, "max": 5}, "sensor": "off", "dry": True}
        out = {}
        try:
            with self._session() as art:
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
            with self._session() as art:
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
        with self._session() as art:
            if str(art.get_artmode()).lower() != "on":
                art.set_artmode(True)

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
                with self._session() as art:
                    art.set_artmode(False)
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
