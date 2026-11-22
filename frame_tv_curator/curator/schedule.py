"""Time-of-day / day-of-week / season (date range) schedules: an active rule replaces the normal source."""
import time

def _md(s):
    try:
        m, d = str(s).strip().split("-")[-2:]
        return int(m), int(d)
    except Exception:
        return None

def _hm(s):
    try:
        h, m = str(s).strip().split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None

def matches(rule, t=None):
    t = t or time.localtime()
    if not rule.get("enabled", True):
        return False
    days = rule.get("days") or []
    if days and t.tm_wday not in [int(x) for x in days]:
        return False
    a, b = _md(rule.get("date_from")), _md(rule.get("date_to"))
    if a or b:
        a, b = a or b, b or a                       # one date given = that single day
        cur = (t.tm_mon, t.tm_mday)
        if not ((a <= cur <= b) if a <= b else (cur >= a or cur <= b)):   # a > b: wraps over New Year
            return False
    f, to = _hm(rule.get("time_from")), _hm(rule.get("time_to"))
    if f is not None and to is not None and f != to:
        cur = t.tm_hour * 60 + t.tm_min
        if not ((f <= cur < to) if f < to else (cur >= f or cur < to)):   # f > to: wraps over midnight
            return False
    return True

def active_rule(rules, t=None):
    ok = [r for r in (rules or []) if matches(r, t)]
    return max(ok, key=lambda r: int(r.get("priority") or 0)) if ok else None

def source_of(rule):
    if rule.get("kind") == "images":
        return {"mode": "images", "images": rule.get("images") or [], "rule": rule.get("id") or rule.get("name")}
    return {"mode": "folder", "folder": rule.get("folder") or "Art", "rule": rule.get("id") or rule.get("name")}
