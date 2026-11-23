"""Identify artwork with Claude (Anthropic Messages API, stdlib only). The key comes from the add-on option
`anthropic_key` (kept by Home Assistant's Supervisor), never from the settings file."""
import base64, io, json, os, time, threading, urllib.request, urllib.error
from . import config, library

API = "https://api.anthropic.com/v1/messages"
_lock = threading.Lock()

# USD per million tokens (input, output). Editable in Settings > AI; used only to estimate spend.
DEFAULT_PRICES = {"claude-haiku-5-5": [1.0, 5.0], "claude-sonnet-5-5": [3.0, 15.0]}
MODELS = {"claude-haiku-5-5": "Haiku 5.5 (cheapest, good for bulk)", "claude-sonnet-5-5": "Sonnet 5.5 (better at obscure art)"}

def _usage_path():
    return os.path.join(config.DATA, "ai_usage.json")

def usage():
    mon = time.strftime("%Y-%m")
    try:
        u = json.load(open(_usage_path()))
    except Exception:
        u = {}
    if u.get("month") != mon:
        u = {"month": mon, "in": 0, "out": 0, "cost": 0.0, "calls": 0}
    return u

def _save_usage(u):
    tmp = _usage_path() + ".tmp"
    json.dump(u, open(tmp, "w")); os.replace(tmp, _usage_path())

def key():
    return (config.options().get("anthropic_key") or "").strip()

def status(settings):
    a = settings.get("ai") or {}
    u = usage()
    return {"key": bool(key()), "enabled": bool(a.get("enabled")), "model": a.get("model"), "limit": float(a.get("monthly_limit_usd") or 0),
            "month": u["month"], "spent": round(u["cost"], 4), "calls": u["calls"]}

def _image_b64(img_id, max_side=1568):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(library.abspath(img_id))).convert("RGB")
    im.thumbnail((max_side, max_side))
    b = io.BytesIO(); im.save(b, "JPEG", quality=85)
    return base64.b64encode(b.getvalue()).decode()

PROMPT = """You are helping label pictures for a digital art frame. Look at the picture and answer with ONE JSON object and nothing else.
Keys: "kind" ("art" for a painting, drawing, print or other artwork; "photo" for a photograph), "artist" (name, or "" if unknown), "title" (or ""), "date" (year or range as text, or ""), "medium" (e.g. "Oil on canvas", or ""), "movement" (art movement or style, or ""), "description" (one or two plain sentences about what it shows), "mood" (exactly one word from this list: {moods}), "confidence" ("high", "medium" or "low" for the artist and title).
Only name an artist or title if you actually recognize the work; otherwise leave them empty. Never guess. Do not invent facts."""

def _cost(model, prices, tin, tout):
    pi, po = (prices.get(model) or DEFAULT_PRICES.get(model) or [3.0, 15.0])
    return (tin * pi + tout * po) / 1e6

def identify(img_id, settings):
    """Returns {"ok": True, "fields": {...}, "cost": x} or {"ok": False, "error": "..."}."""
    a = settings.get("ai") or {}
    k = key()
    if not k:
        return {"ok": False, "error": "No Anthropic key yet. Add it in the add-on's Configuration tab (anthropic_key)."}
    if not a.get("enabled"):
        return {"ok": False, "error": "AI identification is turned off in Settings > AI."}
    model = a.get("model") or "claude-haiku-5-5"
    limit = float(a.get("monthly_limit_usd") or 0)
    prices = dict(DEFAULT_PRICES); prices.update(a.get("prices") or {})
    with _lock:
        u = usage()
        if limit and u["cost"] >= limit:
            return {"ok": False, "error": "Monthly AI limit reached ($%.2f of $%.2f). Raise it in Settings > AI." % (u["cost"], limit)}
    moods = ", ".join(settings.get("moods") or []) or "calm, joyful, dramatic, melancholy"
    body = {"model": model, "max_tokens": 600, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _image_b64(img_id)}},
        {"type": "text", "text": PROMPT.replace("{moods}", moods)}]}]}
    req = urllib.request.Request(API, json.dumps(body).encode(), {"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=60))
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        return {"ok": False, "error": "Claude said HTTP %d %s" % (e.code, msg[:200])}
    except Exception as e:
        return {"ok": False, "error": "Could not reach Claude: %s" % e}
    us = r.get("usage") or {}
    cost = _cost(model, prices, us.get("input_tokens", 0), us.get("output_tokens", 0))
    with _lock:
        u = usage(); u["in"] += us.get("input_tokens", 0); u["out"] += us.get("output_tokens", 0); u["cost"] += cost; u["calls"] += 1
        _save_usage(u)
    text = "".join(c.get("text", "") for c in r.get("content", []) if c.get("type") == "text")
    try:
        f = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except Exception:
        return {"ok": False, "error": "Claude's answer was not understood", "cost": cost}
    mood = str(f.get("mood") or "").strip().lower()
    allowed = [m.lower() for m in (settings.get("moods") or [])]
    f["mood"] = mood if (not allowed or mood in allowed) else ""
    return {"ok": True, "fields": {k2: (str(f.get(k2) or "").strip()) for k2 in ("kind", "artist", "title", "date", "medium", "movement", "description", "mood", "confidence")}, "cost": round(cost, 5), "model": model}

def apply(img_id, fields, model="", overwrite=False):
    """Write identified fields into the sidecar, filling empty fields only (unless overwrite). Returns the names filled."""
    sc = library.load_sidecar(img_id); done = []
    def empty(v): return not (v or "").strip() if isinstance(v, str) else not v
    def put(label, cur, setter, val):
        if val and (overwrite or empty(cur)):
            setter(val); done.append(label)
    art = sc.setdefault("artist", {}) if isinstance(sc.get("artist"), (dict, type(None))) else {}
    if sc.get("kind") != "photo" and fields.get("kind") != "photo":
        put("artist", (sc.get("artist") or {}).get("name") if isinstance(sc.get("artist"), dict) else sc.get("artist"), lambda v: sc.__setitem__("artist", {"name": v}), fields.get("artist"))
        put("title", sc.get("title"), lambda v: sc.__setitem__("title", v), fields.get("title"))
        put("date", (sc.get("date") or {}).get("display") if isinstance(sc.get("date"), dict) else sc.get("date"), lambda v: sc.__setitem__("date", {"display": v}), fields.get("date"))
        ct = sc.setdefault("card_text", {})
        put("medium", ct.get("medium") or sc.get("medium"), lambda v: ct.__setitem__("medium", v), fields.get("medium"))
    put("description", sc.get("description"), lambda v: sc.__setitem__("description", v), fields.get("description"))
    put("mood", sc.get("mood"), lambda v: sc.__setitem__("mood", v), fields.get("mood"))
    if done or True:
        ident = sc.setdefault("identification", {})
        ident.update({"by": "ai", "model": model, "movement": fields.get("movement") or ident.get("movement", ""), "confidence": fields.get("confidence", ""), "when": time.strftime("%Y-%m-%d")})
        sc.setdefault("origin", {})["ai_identified"] = True
    if sc.get("artist") is None or sc.get("artist") == {}:
        sc.pop("artist", None)
    library.save_sidecar(img_id, sc)
    return done
