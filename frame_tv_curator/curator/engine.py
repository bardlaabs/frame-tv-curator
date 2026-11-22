"""Core: choose -> render -> push (TV + e-paper) -> state. Plus the rotation scheduler."""
import os, time, json, threading, logging, urllib.request, urllib.error
from . import config, library, picker, render, epaper, store, schedule
from .tv import TV
log = logging.getLogger("engine")
UNIT = {"minutes": 60, "hours": 3600, "days": 86400}

class Engine:
    def __init__(self, dry_run=False):
        self.opts = config.options()
        self.dry = dry_run or self.opts.get("dry_run")
        self.settings = store.settings()
        self.state = store.state()
        self.tv = TV(self.settings.get()["tv"], self.dry)
        from .ambient import Ambient
        self.ambient = Ambient(self)
        self.lock = threading.RLock()
        self.listeners = []
        self.last_error = None
        self._stop = threading.Event()
        self.activity = {"phase": "idle", "detail": "", "since": time.time()}
        self._tvc = (0, "")

    def _act(self, phase, detail=""):
        self.activity = {"phase": phase, "detail": detail, "since": time.time()}

    # ---- rendering
    def render_image(self, img_id, force=False):
        s = self.settings.get()
        sc = library.load_sidecar(img_id)
        return render.render(library.abspath(img_id), sc, settings=s["display"],
                             cache_dir=config.RENDER_DIR, force=force)

    # ---- display
    def show(self, img_id, record=True, force_push=False, bird=False):
        try:
            return self._show(img_id, record, force_push, bird)
        finally:
            self._act("idle")

    def _show(self, img_id, record=True, force_push=False, bird=False):
        with self.lock:
            s = self.settings.get()
            name = library.display_info(img_id).get("name") or img_id
            self._act("checking", "Checking the TV")
            ok, why = self.tv.ready()
            library.ensure_sidecar(img_id)
            if ok or force_push:        # the e-paper is slow: start it now, in parallel with the TV render/upload
                threading.Thread(target=self._epaper, args=(s["epaper"], library.load_sidecar(img_id)), daemon=True).start()
            self._act("rendering", "Preparing \u201c%s\u201d (rendering 4K)" % name)
            t0 = time.time()
            jpg = self.render_image(img_id)
            log.info("rendered %s in %.1fs", img_id, time.time() - t0)
            sc = library.load_sidecar(img_id)
            result = {"image": img_id, "rendered": jpg, "tv": why}
            if ok:
                try:
                    st = self.state.get()
                    self._act("pushing", "Sending \u201c%s\u201d to the TV" % name)
                    t0 = time.time()
                    cid = self.tv.push(jpg, st.get("tv_ids", []))
                    log.info("pushed %s in %.1fs", img_id, time.time() - t0)
                    d = self.state.get(); d["tv_ids"] = [cid]; self.state.data = d; self.state.save()
                    result["tv"] = "pushed"
                    self.last_error = None
                except Exception as e:
                    log.exception("push failed")
                    self.last_error = str(e)
                    result["tv"] = f"error: {e}"
                    return result
            else:
                log.info("skip TV push: %s", why)
                if not force_push:
                    self._note_pending(img_id)
                    return result
            self._record(img_id, record, bird)
            self._notify()
            try:
                self._peek_next()
            except Exception:
                log.exception("peek next")
            return result

    def _epaper(self, cfg, sc):
        try:
            epaper.push(cfg, sc, dry_run=self.dry)
        except Exception:
            log.exception("e-paper push")

    def _note_pending(self, img_id):
        d = self.state.get(); d["pending"] = img_id; self.state.data = d; self.state.save()

    def _record(self, img_id, record, bird=False):
        d = self.state.get()
        d["current"] = img_id
        d["showing"] = {"kind": "image"}
        if record and not bird:
            d["since_bird"] = d.get("since_bird", 0) + 1
        d["pending"] = None
        d["last_change"] = time.time()
        if record:
            h = d["history"][: d["pos"] + 1] if d["pos"] >= 0 else d["history"]
            h.append(img_id)
            d["history"] = h[-100:]
            d["pos"] = len(d["history"]) - 1
        self.state.data = d; self.state.save()

    def _push_pattern(self, kind, name, img, detail):
        with self.lock:
            ok, why = self.tv.ready()
            if not ok:
                return {"error": why}
            try:
                self._act("pushing", detail)
                os.makedirs(config.RENDER_DIR, exist_ok=True)
                path = os.path.join(config.RENDER_DIR, name)
                img.save(path, "JPEG", quality=95, subsampling=0)
                cid = self.tv.push(path, self.state.get().get("tv_ids", []))
                d = self.state.get(); d["tv_ids"] = [cid]; d["last_change"] = time.time(); d["showing"] = {"kind": kind}
                self.state.data = d; self.state.save()
                return {"tv": "pushed"}
            finally:
                self._act("idle")

    def calibrate(self):
        """Push the overscan test grid to the TV (rotation is held off for one interval)."""
        return self._push_pattern("calibration", "_calibration.jpg", render.render_calibration(), "Sending the calibration grid to the TV")

    def colorbars(self):
        """Push SMPTE color bars (rotation is held off for one interval; use Resend to go back)."""
        return self._push_pattern("colorbars", "_colorbars.jpg", render.render_colorbars(), "Sending SMPTE color bars to the TV")

    def resend(self):
        """Render and push the current image again without changing the rotation history."""
        cur = self.state.get().get("current")
        if not cur:
            return {"error": "nothing is showing yet"}
        return self.show(cur, record=False)

    def next(self):
        with self.lock:
            self._act("choosing", "Choosing the next image")
            d = self.state.get()
            if d["pos"] < len(d["history"]) - 1:      # redo after previous
                img = d["history"][d["pos"] + 1]
                r = self.show(img, record=False)
                d = self.state.get(); d["pos"] += 1; self.state.data = d; self.state.save()
                return r
            img = self._peek_next()
            if not img:
                self._act("idle")
                return {"error": "no eligible images in source"}
            d = self.state.get(); d["next"] = None; self.state.data = d; self.state.save()
            if img == d.get("current") and (d.get("showing") or {}).get("kind", "image") == "image":
                d["last_change"] = time.time(); self.state.data = d; self.state.save()      # only one image to show: nothing to resend
                self._safe_peek()
                return {"image": img, "tv": "unchanged (only one image in this source)"}
            return self.show(img)

    def active_source(self):
        """(source, rule) - the active schedule rule's source, else the normal rotation source."""
        s = self.settings.get()
        r = schedule.active_rule(s.get("schedules"))
        return (schedule.source_of(r), r) if r else (s["source"], None)

    def _peek_next(self):
        """Choose the next image ahead of time (so the UI can show it); the choice is kept until it is used."""
        with self.lock:
            src, _r = self.active_source()
            d = self.state.get()
            key = picker.source_key(src)
            nid = d.get("next")
            if nid and d.get("next_key") == key and os.path.exists(library.abspath(nid)) \
                    and not (library.load_sidecar(nid).get("flags") or {}).get("exclude"):
                return nid
            nid = picker.next_id(src, d, avoid=d.get("current"))
            d["next"], d["next_key"] = nid, key
            self.state.data = d; self.state.save()
            return nid

    def invalidate_next(self):
        d = self.state.get(); d["next"] = None; self.state.data = d; self.state.save()
        threading.Thread(target=self._safe_peek, daemon=True).start()

    def _safe_peek(self):
        try:
            self._peek_next()
        except Exception:
            log.exception("peek next")

    def previous(self):
        with self.lock:
            d = self.state.get()
            if d["pos"] <= 0:
                return {"error": "no earlier image"}
            img = d["history"][d["pos"] - 1]
            r = self.show(img, record=False)
            d = self.state.get(); d["pos"] -= 1; self.state.data = d; self.state.save()
            return r

    # ---- scheduler
    def interval_s(self):
        r = self.settings.get()["rotation"]
        return max(60, int(float(r["value"]) * UNIT.get(r["unit"], 60)))

    def in_quiet_hours(self):
        q = self.settings.get()["rotation"].get("quiet_hours")
        if not q or "-" not in q:
            return False
        a, b = q.split("-")
        now = time.strftime("%H:%M")
        return (a <= now < b) if a < b else (now >= a or now < b)

    def forget(self, img_id):
        """Remove a deleted image from the history and shuffle bags."""
        with self.lock:
            d = self.state.get()
            h, pos = d.get("history", []), d.get("pos", -1)
            keep = [x for x in h if x != img_id]
            d["pos"] = max(-1, pos - sum(1 for x in h[:pos + 1] if x == img_id))
            d["history"] = keep
            for k, b in (d.get("bags") or {}).items():
                d["bags"][k] = [x for x in b if x != img_id]
            self.state.data = d; self.state.save()

    # ---- Bird Frame interleave
    def _bird_due(self, d, bf):
        if not bf.get("enabled"):
            return False
        n, m = int(bf.get("every_n") or 0), float(bf.get("every_minutes") or 0)
        return (n > 0 and d.get("since_bird", 0) >= n) or (m > 0 and time.time() - d.get("last_bird_ts", 0) >= m * 60)

    def show_bird(self):
        """Show the bird image now for `duration_minutes`, then the normal rotation resumes. Live mode asks the Bird Frame add-on to render and push its collage."""
        with self.lock:
            bf = self.settings.get()["birdframe"]
            dur = float(bf.get("duration_minutes") or 0) * 60 or self.interval_s()
            d = self.state.get(); d["since_bird"] = 0; d["last_bird_ts"] = time.time(); self.state.data = d; self.state.save()
            if bf.get("source") == "folder":
                img = picker.next_id({"mode": "folder", "folder": bf.get("folder") or "birds"}, d)
                self.state.data = d; self.state.save()
                if not img:
                    return {"error": "no images in the bird folder"}
                r = self.show(img, bird=True)
            else:
                ok, why = self.tv.ready()
                if not ok:
                    return {"error": why}
                base = "http://%s:%s" % (bf.get("host") or "local-birdframe-local", bf.get("port") or 8099)
                try:
                    self._act("pushing", "Asking Bird Frame to render and show the bird collage")
                    t0 = json.load(urllib.request.urlopen(base + "/status", timeout=10)).get("last_push_ts", 0)
                    urllib.request.urlopen(urllib.request.Request(base + "/push-now", data=b"", method="POST"), timeout=10)
                    for _ in range(60):
                        time.sleep(2)
                        if json.load(urllib.request.urlopen(base + "/status", timeout=10)).get("last_push_ts", 0) > t0:
                            break
                    else:
                        raise RuntimeError("Bird Frame did not finish in 2 minutes")
                    d = self.state.get(); d["showing"] = {"kind": "birdframe"}; d["last_change"] = time.time()
                    self.state.data = d; self.state.save(); self._notify()
                    r = {"tv": "pushed", "image": "birdframe"}
                except Exception as e:
                    log.warning("bird frame failed: %s", e)
                    if isinstance(e, urllib.error.URLError):
                        msg = ("the Bird Frame add-on is not running (%s). Start it under Settings > Add-ons, and give it a long update "
                               "interval so it does not change the TV itself \u2014 or switch Bird source to \u201cImage from a folder\u201d." % base)
                    else:
                        msg = str(e)
                    self.last_error = "Bird Frame: %s" % msg
                    return {"error": self.last_error}
                finally:
                    self._act("idle")
            d = self.state.get(); d["bird_until"] = time.time() + dur; self.state.data = d; self.state.save()
            return r

    def loop(self):
        while not self._stop.wait(5):
            try:
                s = self.settings.get()
                if not s["enabled"] or self.in_quiet_hours():
                    continue
                d = self.state.get()
                now = time.time()
                if d.get("bird_until"):
                    if now < d["bird_until"]:
                        continue                                   # bird image is up; hold normal rotation
                    d["bird_until"] = None; self.state.data = d; self.state.save()
                    self.next()                                    # duration over: back to the art
                    continue
                _src, rule = self.active_source()
                rid = (rule.get("id") or rule.get("name")) if rule else None
                if rid != d.get("active_rule"):                   # a schedule started or ended: change right away
                    d["active_rule"] = rid; d["next"] = None; self.state.data = d; self.state.save()
                    log.info("schedule %s", ("started: " + rule.get("name", rid)) if rule else "ended")
                    self.next()
                    continue
                due = now - d.get("last_change", 0) >= self.interval_s()
                if d.get("pending"):      # wanted to change while the TV wasn't in Art Mode
                    self.show(d["pending"])
                elif due:
                    if self._bird_due(d, s.get("birdframe") or {}):
                        r = self.show_bird()
                        if r.get("error"):
                            log.warning("bird interleave skipped: %s", r["error"])
                            d = self.state.get(); d["last_bird_ts"] = now; self.state.data = d; self.state.save()
                            self.next()
                    else:
                        self.next()
            except Exception:
                log.exception("scheduler")

    def start(self):
        def prep():
            library.ensure_all()
            self._safe_peek()
            library.fill_location_names()
        def scanner():          # pick up files added from outside (SMB share, scripts); never blocks the scheduler
            while not self._stop.wait(60):
                try:
                    library.scan()
                    library.warm_facts()
                    b = library.list_backups()
                    if not b or time.time() - b[0]["mtime"] > 86400:       # automatic daily backup of sidecars + settings
                        log.info("backup: %s", library.backup_all())
                except Exception:
                    log.exception("library scan / backup")
        threading.Thread(target=prep, daemon=True).start()
        threading.Thread(target=scanner, daemon=True).start()
        threading.Thread(target=self.loop, daemon=True).start()

    def status(self):
        d = self.state.get()
        info = library.display_info(d["current"]) if d.get("current") else {}
        return {"current": d.get("current"), "title": info.get("name"), "artist": info.get("artist"),
                "folder": info.get("folder"), "file": info.get("file"),
                "last_change": d.get("last_change"), "interval_s": self.interval_s(),
                "enabled": self.settings.get()["enabled"], "pending": d.get("pending"),
                "dry_run": self.dry, "last_error": self.last_error,
                "tv": self._tv_text(), "activity": dict(self.activity, elapsed=time.time() - self.activity["since"]),
                "due_in": (d.get("last_change", 0) + self.interval_s()) - time.time(), "server_time": time.time(),
                "showing": (d.get("showing") or {"kind": "image"}), "schedule": (self.active_source()[1] or {}).get("name"), "bird_until": d.get("bird_until"), "next": self._next_info(d), "ambient": self.ambient.status()}

    def _next_info(self, d):
        h, pos = d.get("history", []), d.get("pos", -1)
        nid = h[pos + 1] if pos < len(h) - 1 else d.get("next")
        if not nid or not os.path.exists(library.abspath(nid)):
            return None
        return {"id": nid, "name": library.display_info(nid).get("name")}

    def _tv_text(self):
        busy = self.activity["phase"] != "idle"
        if busy or time.time() - self._tvc[0] < 8:
            return self._tvc[1] or "checking…"
        self._tvc = (time.time(), self.tv.ready()[1])
        return self._tvc[1]

    def _notify(self):
        for f in self.listeners:
            try: f(self.status())
            except Exception: pass
