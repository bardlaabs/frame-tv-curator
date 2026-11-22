"""Presence: turn the Frame on when someone arrives and off after everyone has been gone a while.

Sources are a chain: the chosen presence sensors (any one 'on' = present), then an optional clock window
(used only when every chosen sensor is unavailable), otherwise nothing happens - a missing sensor can never
switch the TV off or break rotation."""
import time, threading, logging
from . import ha
log = logging.getLogger("presence")
ON = ("on", "home", "detected", "occupied", "true")
OFF = ("off", "not_home", "clear", "unoccupied", "false")


def _mins(t):
    try:
        h, m = str(t).split(":")[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None


def in_window(spec, now=None):
    """'HH:MM-HH:MM' (may wrap midnight). Blank = always."""
    if not spec or "-" not in spec:
        return True
    a, b = [_mins(x.strip()) for x in spec.split("-", 1)]
    if a is None or b is None:
        return True
    t = time.localtime(now or time.time())
    n = t.tm_hour * 60 + t.tm_min
    return a <= n < b if a <= b else (n >= a or n < b)


class Presence:
    def __init__(self, engine):
        self.e = engine
        self.st = {"enabled": False, "present": None, "source": "off", "away_for_s": 0, "last": None, "error": None}
        self.away_since = None      # when sensors first read "nobody" (debounce)
        self.away_done = False      # we already turned the TV off for this absence
        self.was_present = None
        self.last_act = 0

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="presence").start()

    def status(self):
        return dict(self.st)

    def _loop(self):
        time.sleep(20)
        while True:
            try:
                self.tick()
                self.st["error"] = None
            except Exception as ex:
                log.exception("presence tick")
                self.st["error"] = str(ex)
            time.sleep(10)

    def read(self, c):
        """-> (present True/False/None, label)"""
        ents = [x for x in (c.get("entities") or []) if x]
        seen = []
        for ent in ents:
            s = ha.get_state(ent, quiet=True)
            v = (s or {}).get("state")
            if v in ON:
                return True, "%s is on" % ent
            if v in OFF:
                seen.append(ent)
        if seen:
            return False, "%d sensor(s) clear" % len(seen)
        fb = c.get("fallback_hours")
        if fb:
            return in_window(fb), "fallback: clock window %s%s" % (fb, " (sensors unavailable)" if ents else "")
        return None, "no presence sensor available - leaving the TV alone"

    def tick(self):
        s = self.e.settings.get()
        c = s.get("presence") or {}
        self.st["enabled"] = bool(c.get("enabled"))
        if not c.get("enabled"):
            self.st.update(present=None, source="off", away_for_s=0)
            self.away_since, self.away_done, self.was_present = None, False, None
            return
        now = time.time()
        present, src = self.read(c)
        self.st.update(present=present, source=src)
        if present is None:
            return
        info = ha.tv_info(s["tv"]["entity"])
        tv = info.get("state")
        if tv not in ("on", "off", "standby"):
            return                                        # TV unreachable: do nothing
        if present:
            if self.away_since is not None and self.away_done and c.get("on_return", True) and \
                    in_window(c.get("active_hours"), now) and tv != "on" and now - self.last_act > 30:
                ok, msg = self.e.tv.control("art_on")
                self.last_act = now
                self.st["last"] = "%s: welcome back - %s" % (time.strftime("%H:%M:%S"), msg)
                log.info("presence returned: %s", msg)
            self.away_since, self.away_done = None, False
            self.st["away_for_s"] = 0
            self.was_present = True
            return
        # nobody here
        if self.away_since is None:
            self.away_since = now
        gone = now - self.away_since
        self.st["away_for_s"] = int(gone)
        if self.away_done or tv != "on":
            return
        if gone < float(c.get("away_minutes", 10)) * 60:
            return
        if c.get("only_art_mode", True) and info.get("art_mode") != "on":
            return                                        # someone may be watching TV: leave it
        act = c.get("away_action", "power_off")
        ok, msg = self.e.tv.control("art_off" if act == "art_off" else "power_off")
        self.away_done = True
        self.last_act = now
        self.st["last"] = "%s: nobody for %d min - %s" % (time.strftime("%H:%M:%S"), gone // 60, msg)
        log.info("presence away: %s", msg)
