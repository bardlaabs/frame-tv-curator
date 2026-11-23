"""Identify artwork with Claude (Anthropic Messages API, stdlib only). The key comes from the add-on option
`anthropic_key` (kept by Home Assistant's Supervisor), never from the settings file."""
import base64, io, json, os, re, time, threading, urllib.request, urllib.error
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
Keys: "kind" ("art" for a painting, drawing, print or other artwork; "photo" for a photograph), "artist" (name, or "" if unknown), "title" (or ""), "date" (year or range as text, or ""), "medium" (e.g. "Oil on canvas", or ""), "movement" (art movement or style, or ""), "description" (one or two plain sentences about what it shows), "mood" (exactly one word from this list: {moods}), "tags" (3 to 6 short lowercase words about subject and style, e.g. "landscape", "river", "impressionism"), "season" (exactly one of spring, summer, autumn, winter, or "" if it is not clearly seasonal), "occasion" (exactly one word or phrase from this list if the picture is clearly about it, else ""): {occasions}), "confidence" ("high", "medium" or "low" for the artist and title).
Only name an artist or title if you actually recognize the work; otherwise leave them empty. Never guess. Do not invent facts.
{hints}"""

def _cost(model, prices, tin, tout):
    pi, po = (prices.get(model) or DEFAULT_PRICES.get(model) or [3.0, 15.0])
    return (tin * pi + tout * po) / 1e6

def _parse_obj(text):
    """First JSON object in the text (tolerates code fences, chatter before or after, braces inside strings)."""
    dec = json.JSONDecoder(); i = text.find("{")
    while i != -1:
        try:
            o, _ = dec.raw_decode(text[i:])
            if isinstance(o, dict): return o
        except ValueError:
            pass
        i = text.find("{", i + 1)
    return None

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
    sc0 = library.load_sidecar(img_id)
    hv = []
    an = (sc0.get("artist") or {}).get("name") if isinstance(sc0.get("artist"), dict) else sc0.get("artist")
    base = os.path.splitext(os.path.basename(img_id))[0].replace("_", " ")
    for lab, v in (("artist", an), ("title", sc0.get("title")), ("date", (sc0.get("date") or {}).get("display") if isinstance(sc0.get("date"), dict) else None), ("file name", base)):
        if v:
            hv.append("%s: %s" % (lab, v))
    hints = ("Existing information about this picture (it may be partial or wrong): " + "; ".join(hv) + ". Use it as a lead and check it against what you see: if the picture matches, confirm and complete it; if it clearly shows a different work, give your own answer.") if hv else ""
    moods = ", ".join(settings.get("moods") or []) or "calm, joyful, dramatic, melancholy"
    body = {"model": model, "max_tokens": 1500, "messages": [{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": _image_b64(img_id)}},
        {"type": "text", "text": PROMPT.replace("{moods}", moods).replace("{occasions}", ", ".join(settings.get("occasions") or [])).replace("{hints}", hints)}]}]}
    req = urllib.request.Request(API, json.dumps(body).encode(), {"x-api-key": k, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    f = None; cost = 0.0
    for attempt in (1, 2):                      # one retry if the answer cannot be read
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
        c = _cost(model, prices, us.get("input_tokens", 0), us.get("output_tokens", 0)); cost += c
        with _lock:
            u = usage(); u["in"] += us.get("input_tokens", 0); u["out"] += us.get("output_tokens", 0); u["cost"] += c; u["calls"] += 1
            _save_usage(u)
        text = "".join(c2.get("text", "") for c2 in r.get("content", []) if c2.get("type") == "text")
        f = _parse_obj(text)
        try:                                    # keep the last raw answer so a failure can be diagnosed
            json.dump({"id": img_id, "stop": r.get("stop_reason"), "text": text[:4000], "when": time.strftime("%Y-%m-%d %H:%M:%S")}, open(os.path.join(config.DATA, "ai_last.json"), "w"))
        except Exception:
            pass
        if f is not None:
            break
    if f is None:
        why = "it was cut off" if r.get("stop_reason") == "max_tokens" else ("it did not contain the details: " + text.strip()[:120].replace("\n", " ") if text.strip() else "it was empty")
        return {"ok": False, "error": "Claude's answer could not be read (%s). Nothing was changed; try again." % why, "cost": cost}
    mood = str(f.get("mood") or "").strip().lower()
    allowed = [m.lower() for m in (settings.get("moods") or [])]
    f["mood"] = mood if (not allowed or mood in allowed) else ""
    season = str(f.get("season") or "").strip().lower()
    occ = str(f.get("occasion") or "").strip()
    occ_ok = {o.lower(): o for o in (settings.get("occasions") or [])}
    tags = f.get("tags") if isinstance(f.get("tags"), list) else []
    tags = [re.sub(r"\s+", " ", str(t).strip().lower())[:30] for t in tags if str(t).strip()][:8]
    out = {k2: (str(f.get(k2) or "").strip()) for k2 in ("kind", "artist", "title", "date", "medium", "movement", "description", "mood", "confidence")}
    out.update(season=season if season in ("spring", "summer", "autumn", "winter") else "", occasion=occ_ok.get(occ.lower(), ""), tags=tags)
    return {"ok": True, "fields": out, "cost": round(cost, 5), "model": model}

def merged(fields, cand):
    """A museum record wins over Claude's wording for the fields it has."""
    f = dict(fields)
    if cand:
        for k in ("artist", "title", "date", "medium", "description"):
            if (cand.get(k) or "").strip():
                f[k] = cand[k].strip()
        f["kind"] = "art"
    return f

def identify_verify(img_id, settings):
    """identify + museum check. decision: 'auto' (one clear match), 'choose' (several, ask the person) or 'none'."""
    from . import verify
    r = identify(img_id, settings)
    if not r.get("ok"):
        return r
    f = r["fields"]
    sc = library.load_sidecar(img_id)
    an = (sc.get("artist") or {}).get("name") if isinstance(sc.get("artist"), dict) else sc.get("artist")
    title = f.get("title") or sc.get("title") or ""
    artist = f.get("artist") or an or ""
    if f.get("kind") == "photo" or not (title or artist):
        r.update(decision="none", candidates=[], notes=["no title or artist to check"]); return r
    cands, notes = verify.candidates(title, artist, f.get("date"))
    dec, pick = verify.decide(cands)
    r.update(decision=dec, notes=notes, search={"title": title, "artist": artist})
    if dec == "auto": r["candidate"] = pick
    elif dec == "choose": r["candidates"] = pick
    return r

def _spec(sc, fields, cand):
    """The fields a result can fill: (key, label, current value, new value, setter)."""
    def txt(v): return v.strip() if isinstance(v, str) else ""
    def nm(k): 
        v = sc.get(k); return (v.get("name") if k == "artist" and isinstance(v, dict) else v.get("display") if k == "date" and isinstance(v, dict) else v) or ""
    ct = sc.setdefault("card_text", {}) if isinstance(sc.get("card_text"), (dict, type(None))) else {}
    rows = []
    if sc.get("kind") != "photo" and fields.get("kind") != "photo":
        rows += [("artist", "Artist", nm("artist"), fields.get("artist"), lambda v: sc.__setitem__("artist", {"name": v})),
                 ("title", "Title", nm("title"), fields.get("title"), lambda v: sc.__setitem__("title", v)),
                 ("date", "Date", nm("date"), fields.get("date"), lambda v: sc.__setitem__("date", {"display": v})),
                 ("medium", "Medium", ct.get("medium") or sc.get("medium") or "", fields.get("medium"), lambda v: ct.__setitem__("medium", v))]
    rows += [("description", "Description", sc.get("description") or "", fields.get("description"), lambda v: sc.__setitem__("description", v)),
             ("mood", "Mood", sc.get("mood") or "", fields.get("mood"), lambda v: sc.__setitem__("mood", v)),
             ("season", "Season", sc.get("season") or "", fields.get("season"), lambda v: sc.__setitem__("season", v)),
             ("occasion", "Occasion", sc.get("occasion") or "", fields.get("occasion"), lambda v: sc.__setitem__("occasion", v))]
    if cand:
        inst = (sc.get("collection") or {}).get("institution") if isinstance(sc.get("collection"), dict) else ""
        rows += [("source", "Source", inst or "", cand.get("source_name"), lambda v: sc.__setitem__("collection", {"institution": v, "status": "identified from " + v, "credit_line": cand.get("credit") or None})),
                 ("license", "License", sc.get("license") or "", cand.get("license"), lambda v: sc.__setitem__("license", v))]
    return [r for r in rows if txt(r[3])]

def preview(img_id, fields, cand=None):
    """Row-by-row comparison of what is stored and what the result would write. 'conflict' = both have a different value."""
    fields = merged(fields, cand)
    sc = library.load_sidecar(img_id)
    out = []
    for key, label, cur, new, _ in _spec(sc, fields, cand):
        cur = str(cur or "").strip(); new = str(new).strip()
        if cur == new: continue
        out.append({"key": key, "label": label, "current": cur, "new": new, "conflict": bool(cur)})
    have = [x.lower() for x in (sc.get("tags") or []) if isinstance(x, str)]
    nt = [t for t in dict.fromkeys(fields.get("tags") or []) if t and t.lower() not in have]
    if nt:
        out.append({"key": "tags", "label": "Tags", "current": ", ".join(sc.get("tags") or []), "new": ", ".join(nt), "conflict": False, "add": True})
    return out

def apply(img_id, fields, model="", overwrite=False, cand=None):
    """Write identified fields into the sidecar. Empty fields are always filled; a filled field is replaced only when
    overwrite is True (all) or its key is in the overwrite list. Tags are added to yours (replaced only if 'tags' is in the list)."""
    fields = merged(fields, cand)
    sc = library.load_sidecar(img_id); done = []
    allow = (lambda k: True) if overwrite is True else (lambda k: bool(overwrite) and k in overwrite)
    for key, label, cur, new, setter in _spec(sc, fields, cand):
        if str(cur or "").strip() and not allow(key): continue
        if str(cur or "").strip() == str(new).strip(): continue
        setter(str(new).strip()); done.append(key)
    new_tags = list(dict.fromkeys(t for t in (fields.get("tags") or []) if t and t.lower() not in [x.lower() for x in (sc.get("tags") or []) if isinstance(x, str)]))
    old_tags = [x for x in (sc.get("tags") or []) if isinstance(x, str)]
    if fields.get("tags") and allow("tags"):
        sc["tags"] = list(dict.fromkeys(fields["tags"])); done.append("tags")
    elif new_tags:                                  # tags are added to yours
        sc["tags"] = old_tags + new_tags; done.append("tags")
    if cand:
        lk = sc.setdefault("links", [])
        if cand.get("url") and not any(l.get("url") == cand["url"] for l in lk if isinstance(l, dict)):
            lk.append({"label": cand["source_name"] + " page", "url": cand["url"], "kind": "record"}); done.append("link")
        if cand.get("url") and (not sc.get("source_url") or allow("source")):
            sc["source_url"] = cand["url"]
    if True:
        ident = sc.setdefault("identification", {})
        ident.update({"by": "ai", "model": model, "movement": fields.get("movement") or ident.get("movement", ""), "confidence": ("high" if cand else fields.get("confidence", "")), "status": ("matched to " + cand["source_name"] if cand else "identified by AI, not checked against a museum"), "verified": bool(cand), "when": time.strftime("%Y-%m-%d")})
        sc.setdefault("origin", {})["ai_identified"] = True
    if sc.get("artist") is None or sc.get("artist") == {}:
        sc.pop("artist", None)
    library.save_sidecar(img_id, sc)
    return done
