"""Ambient control: art brightness, art color temperature and a companion light that follow the TV.

Every value can come from a chain of sources (the chosen one first, then fallbacks), so a missing or unavailable
entity never stops anything: lux sensor / control entity -> sun position (or the clock) -> manual value."""
import time, math, threading, logging
from . import ha
log = logging.getLogger("ambient")


def _num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _smooth(e0, e1, x):
    t = _clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


class Ambient:
    def __init__(self, engine):
        self.e = engine
        self.st = {"brightness": {}, "color_temp": {}, "light": {}, "tv_state": None, "updated": 0, "error": None}
        self.last = {"tv_on": None, "b": None, "b_ts": 0, "c": None, "c_ts": 0, "lb": None, "lk": None}
        self._wake = threading.Event()
        self._probe = (0, None)

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="ambient").start()

    def poke(self):
        self.last["b"] = self.last["c"] = None          # re-apply on the next pass
        self._wake.set()

    def status(self):
        return dict(self.st)

    def _loop(self):
        time.sleep(15)
        while True:
            try:
                self.tick()
                self.st["error"] = None
            except Exception as ex:
                log.exception("ambient tick")
                self.st["error"] = str(ex)
            self._wake.wait(20)
            self._wake.clear()

    # ---- readings
    def _state(self, ent):
        if not ent:
            return None
        s = ha.get_state(ent, quiet=True)
        if not s or s.get("state") in ("unavailable", "unknown", None, ""):
            return None
        return s

    def sun(self, ent):
        s = self._state(ent or "sun.sun")
        v = _num(((s or {}).get("attributes") or {}).get("elevation"))
        if v is not None:
            return v, "sun %+.0f°" % v
        t = time.localtime()
        h = t.tm_hour + t.tm_min / 60
        v = 55 * math.sin(math.pi * (h - 6.5) / 12) if 6.5 <= h <= 18.5 else -20      # crude clock-based daylight curve
        return v, "clock (no sun entity) %+.0f°" % v

    def _b_chain(self, c):
        def lux():
            s = self._state(c.get("lux_entity"))
            v = _num(s and s["state"])
            if v is None:
                return None
            lo = max(0.1, float(c.get("lux_low", 10)))
            hi = max(float(c.get("lux_high", 400)), lo + 1)
            f = 0.0 if v <= lo else _clamp(math.log10(v / lo) / math.log10(hi / lo))
            return f, "lux sensor %s lx" % round(v)

        def entity():
            ent = c.get("entity")
            s = self._state(ent)
            if not s:
                return None
            a = s.get("attributes") or {}
            p = _num(a.get("brightness_pct"))
            if p is None and ent.startswith("light.") and _num(a.get("brightness")) is not None:
                p = _num(a.get("brightness")) / 255 * 100
            if p is None:
                v = _num(s["state"])
                if v is None:
                    return None
                mx = _num(a.get("max")) or float(c.get("entity_max", 100))
                p = v / mx * 100
            return _clamp(p / 100), "%s = %.0f%%" % (ent, p)

        def sun():
            e, txt = self.sun(c.get("sun_entity"))
            return _smooth(-4, 35, e), txt

        def manual():
            return _clamp(float(c.get("manual", 60)) / 100), "manual %s%%" % c.get("manual", 60)
        return {"lux": [lux, entity, sun, manual], "entity": [entity, lux, sun, manual], "sun": [sun, manual],
                "manual": [manual]}

    @staticmethod
    def _why(ent, noun):
        return "No %s chosen" % noun if not ent else "%s unavailable" % ent

    def _first(self, fns, label, why=None):
        for i, f in enumerate(fns):
            r = f()
            if r:
                if i == 0:
                    return r[0], r[1]
                return r[0], ((why + " \u2014 using " if why else "fallback: ") + r[1])
        return None, "no source available"

    def brightness_pct(self, c, mode):
        why = {"lux": self._why(c.get("lux_entity"), "lux sensor"), "entity": self._why(c.get("entity"), "entity")}.get(mode)
        f, src = self._first(self._b_chain(c).get(mode, []), "brightness", why)
        if f is None:
            return None, src
        lo, hi = float(c.get("min_pct", 10)), float(c.get("max_pct", 100))
        return lo + f * (hi - lo), src

    def kelvin(self, c, mode):
        def entity():
            s = self._state(c.get("entity"))
            if not s:
                return None
            a = s.get("attributes") or {}
            k = _num(a.get("color_temp_kelvin"))
            if k is None and _num(a.get("color_temp")):
                k = 1e6 / _num(a.get("color_temp"))
            if k is None:
                v = _num(s["state"])
                if v:
                    k = v if v > 1000 else 1e6 / v
            return (k, "%s = %d K" % (c.get("entity"), k)) if k else None

        def sun():
            e, txt = self.sun(c.get("sun_entity"))
            night, day = float(c.get("night_k", 2700)), float(c.get("day_k", 6500))
            return night + _smooth(-4, 35, e) * (day - night), txt

        def manual():
            return float(c.get("manual_k", 5000)), "manual %s K" % c.get("manual_k", 5000)
        chain = {"entity": [entity, sun, manual], "sun": [sun, manual], "manual": [manual]}.get(mode, [])
        return self._first(chain, "color temperature", self._why(c.get("entity"), "entity") if mode == "entity" else None)

    # ---- TV ranges (cached)
    def probe(self, force=False):
        if not force and self._probe[1] and time.time() - self._probe[0] < 600:
            return self._probe[1]
        p = self.e.tv.probe()
        if p and not p.get("error"):
            self._probe = (time.time(), p)
        return p

    # ---- main pass
    def tick(self):
        s = self.e.settings.get()
        a = s.get("ambient") or {}
        bc, cc, lc = a.get("brightness", {}), a.get("color_temp", {}), a.get("light", {})
        info = ha.tv_info(s["tv"]["entity"])
        tv_state = info.get("state")
        valid = tv_state in ("on", "off", "standby")
        on = tv_state == "on"
        just_on = on and self.last["tv_on"] is False
        transitioned = valid and self.last["tv_on"] is not None and on != self.last["tv_on"]
        now = time.time()
        self.st.update(tv_state=tv_state, updated=now)

        bmode = bc.get("mode", "off")
        if bmode == "off" and lc.get("follow") and lc.get("sync_brightness"):
            bmode = "sun"
        bpct, bsrc = (None, "off")
        if bmode != "off":
            bpct, bsrc = self.brightness_pct(bc, bmode)
            tau = _num(bc.get("smoothing_s", 120)) or 0.0       # a jittery lux sensor would otherwise flip the TV between steps
            if bpct is not None and tau > 0:
                prev = getattr(self, "_ema", None)
                if prev is None or now - prev[0] > max(600.0, 5 * tau):
                    ema = bpct
                else:
                    ema = prev[1] + (bpct - prev[1]) * (1 - math.exp(-(now - prev[0]) / tau))
                self._ema = (now, ema)
                bpct = ema
        cmode = cc.get("mode", "off")
        kel, ksrc = (None, "off")
        if cmode != "off":
            kel, ksrc = self.kelvin(cc, cmode)
        self.st["brightness"] = {"mode": bmode, "pct": None if bpct is None else round(bpct), "source": bsrc,
                                 "applied": self.last["b"]}
        self.st["color_temp"] = {"mode": cmode, "kelvin": None if kel is None else round(kel), "source": ksrc,
                                 "applied": self.last["c"]}

        # --- push to the TV (only while it is on; again right after it turns on)
        if on and (bc.get("mode", "off") != "off" or cmode != "off"):
            pr = self.probe()
            kw = {}
            if bc.get("mode", "off") != "off" and bpct is not None:
                rng = (pr or {}).get("brightness") or {}
                lo, hi = rng.get("min", 1), rng.get("max", 10)
                lo = max(lo, 1) if hi <= 10 else lo
                raw = lo + bpct / 100 * (hi - lo)
                val = int(round(raw))
                hy = max(0.0, min(1.0, _num(bc.get("hysteresis", 0.3)) or 0.0))
                if self.last["b"] is not None and val != self.last["b"] and abs(raw - self.last["b"]) < 0.5 + hy:
                    val = self.last["b"]        # inside the dead band around the current step: stay put (no flicker)
                if (val != self.last["b"] and now - self.last["b_ts"] >= float(bc.get("min_interval_s", 60))) or just_on or self.last["b"] is None:
                    kw["brightness"] = val
                    if bc.get("disable_sensor", True):
                        kw["sensor_off"] = True
            if cmode != "off" and kel is not None:
                rng = dict({"min": -5, "max": 5}, **((pr or {}).get("color_temperature") or {}))   # Frame scale: -5 (warm) .. +5 (cool)
                if "min" in rng:
                    lo, hi = float(cc.get("low_k", 2700)), float(cc.get("high_k", 6500))
                    t = _clamp((kel - lo) / (hi - lo))
                    if cc.get("flip"):
                        t = 1 - t
                    val = int(round(rng["min"] + t * (rng["max"] - rng["min"])))
                    if (val != self.last["c"] and now - self.last["c_ts"] >= float(cc.get("min_interval_s", 300))) or just_on or self.last["c"] is None:
                        kw["color_temp"] = val
            if kw:
                ok, msg = self.e.tv.apply_art(**kw)
                log.info("TV art settings %s -> %s", kw, msg)
                if ok:
                    if "brightness" in kw:
                        self.last["b"], self.last["b_ts"] = kw["brightness"], now
                    if "color_temp" in kw:
                        self.last["c"], self.last["c_ts"] = kw["color_temp"], now
                    self.st["brightness"]["applied"], self.st["color_temp"]["applied"] = self.last["b"], self.last["c"]
                else:
                    self.st["error"] = msg

        # --- companion light
        ent = lc.get("entity")
        self.st["light"] = {"entity": ent, "follow": bool(lc.get("follow"))}
        if ent and lc.get("follow") and valid:
            dom = ent.split(".")[0]
            if transitioned:
                svc = "turn_on" if on else "turn_off"
                data = {"entity_id": ent}
                if on and dom == "light":
                    data.update(self._light_params(lc, bpct, kel))
                try:
                    ha.call(dom, svc, data)
                    self.st["light"]["last"] = "%s at %s" % (svc, time.strftime("%H:%M:%S"))
                    self.last["lb"], self.last["lk"] = data.get("brightness_pct"), data.get("color_temp_kelvin")
                except Exception as ex:
                    self.st["light"]["last"] = "failed: %s" % ex
            elif on and dom == "light" and (lc.get("sync_brightness") or lc.get("sync_color_temp")):
                ls = self._state(ent)
                if ls and ls["state"] == "on":
                    par = self._light_params(lc, bpct, kel)
                    db = abs((par.get("brightness_pct") or 0) - (self.last["lb"] or 0)) >= 5 if "brightness_pct" in par else False
                    dk = abs((par.get("color_temp_kelvin") or 0) - (self.last["lk"] or 0)) >= 150 if "color_temp_kelvin" in par else False
                    if db or dk or (self.last["lb"] is None and self.last["lk"] is None):
                        try:
                            ha.call("light", "turn_on", dict(par, entity_id=ent))
                            self.last["lb"], self.last["lk"] = par.get("brightness_pct"), par.get("color_temp_kelvin")
                            self.st["light"]["last"] = "synced at %s" % time.strftime("%H:%M:%S")
                        except Exception as ex:
                            self.st["light"]["last"] = "failed: %s" % ex
        if valid:
            self.last["tv_on"] = on

    def _light_params(self, lc, bpct, kel):
        out = {}
        if lc.get("sync_brightness") and bpct is not None:
            lo, hi = float(lc.get("light_min_pct", 10)), float(lc.get("light_max_pct", 100))
            out["brightness_pct"] = int(round(lo + bpct / 100 * (hi - lo)))
        if lc.get("sync_color_temp") and kel is not None:
            out["color_temp_kelvin"] = int(round(kel))
        return out
