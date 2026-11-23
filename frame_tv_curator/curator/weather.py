"""Weather nudge: when the weather is, say, rainy, pictures whose mood fits rain are picked a little more often."""
from . import ha

# Home Assistant's standard weather conditions (every weather integration uses this same set).
DEFAULT_MAP = {
    "sunny": ["joyful", "playful", "energetic", "bold"],
    "clear-night": ["calm", "mysterious", "contemplative", "serene"],
    "partlycloudy": ["serene", "calm", "nostalgic"],
    "cloudy": ["contemplative", "melancholy", "calm"],
    "rainy": ["melancholy", "contemplative", "romantic", "mysterious"],
    "pouring": ["melancholy", "dramatic", "mysterious"],
    "lightning": ["dramatic", "bold", "mysterious"],
    "lightning-rainy": ["dramatic", "bold", "mysterious"],
    "snowy": ["serene", "calm", "nostalgic", "contemplative"],
    "snowy-rainy": ["melancholy", "serene", "contemplative"],
    "fog": ["mysterious", "calm", "melancholy"],
    "hail": ["dramatic", "bold"],
    "windy": ["energetic", "dramatic", "bold"],
    "windy-variant": ["energetic", "dramatic", "bold"],
    "exceptional": ["dramatic", "bold"],
}

def entities():
    out = []
    try:
        states = ha._req("GET", "/states") or []
    except Exception:
        states = []
    for s in states:
        eid = s.get("entity_id", "")
        if eid.startswith("weather."):
            out.append({"entity": eid, "state": s.get("state"), "name": (s.get("attributes") or {}).get("friendly_name") or eid})
    return sorted(out, key=lambda x: x["entity"])

def pick_entity(cfg):
    ent = (cfg.get("entity") or "").strip()
    if ent:
        return ent
    es = [e["entity"] for e in entities()]
    for pref in ("weather.weather_home", "weather.home"):
        if pref in es:
            return pref
    return es[0] if es else ""

def current(cfg):
    """(condition, moods) or (None, [])."""
    try:
        ent = pick_entity(cfg)
        if not ent:
            return None, []
        st = (ha.get_state(ent, quiet=True) or {}).get("state")
        if not st or st in ("unknown", "unavailable"):
            return st, []
        m = dict(DEFAULT_MAP); m.update(cfg.get("map") or {})
        return st, [x.strip().lower() for x in (m.get(st) or []) if x and x.strip()]
    except Exception:
        return None, []

def prefer(settings):
    """(set_of_moods, probability) for the picker, or None when the nudge is off or nothing applies."""
    cfg = settings.get("weather") or {}
    if not cfg.get("enabled"):
        return None
    _c, moods = current(cfg)
    p = max(0, min(100, int(cfg.get("strength") or 0))) / 100.0
    return (set(moods), p) if moods and p > 0 else None
