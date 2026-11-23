"""Check an identification against museum collections (and Wikimedia Commons last) and gather record links.
Museum records are authoritative; nothing here downloads an image."""
import re, unicodedata, threading, time
from . import discover

MUSEUMS = ["aic", "met", "cleveland", "getty", "smithsonian"]      # priority order
OTHERS = ["commons"]
STOP = {"the", "a", "an", "of", "and", "in", "on", "at", "with", "de", "la", "le", "du", "von", "van", "der"}

def toks(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z0-9]+", s) if t not in STOP and len(t) > 1}

def title_score(a, b):
    x, y = toks(a), toks(b)
    if not x or not y:
        return 0.0
    return len(x & y) / len(x | y)

def artist_score(a, b):
    x, y = toks(a), toks(b)
    if not x or not y:
        return 0.0
    return len(x & y) / min(len(x), len(y))

def _search(sid, q, out, errs):
    try:
        r = discover.SOURCES[sid].search(q=q, per=6, type="", sort="relevance")
        out[sid] = r.get("items") or []
    except Exception as e:
        errs[sid] = str(e)[:100]

def candidates(title, artist, date="", budget=14):
    """Search the sources in parallel. Returns (list of candidates, notes). If nothing matches the title (museums often
    use another title for the same work, e.g. 'Under the Wave off Kanagawa'), the same artist's works are offered as loose matches."""
    if not (title or artist):
        return [], ["nothing to search for"]
    def run(q, loose):
        out, errs, th = {}, {}, []
        for sid in MUSEUMS + OTHERS:
            if sid not in discover.SOURCES:
                continue
            t = threading.Thread(target=_search, args=(sid, q, out, errs), daemon=True); t.start(); th.append(t)
        end = time.time() + budget
        for t in th:
            t.join(max(0.1, end - time.time()))
        cands = []
        for sid, items in out.items():
            src = discover.SOURCES[sid]
            for d in items:
                ts = title_score(title, d.get("title")) if title else 0.0
                as_ = artist_score(artist, d.get("artist")) if (artist and d.get("artist")) else None
                score = ts if as_ is None else 0.65 * ts + 0.35 * as_
                if not title:
                    score = as_ or 0.0
                if loose:
                    ok = bool(artist) and as_ is not None and as_ > 0
                    score = min(score, 0.6)           # a loose match is never taken automatically
                else:
                    ok = (ts >= 0.5 or not title) and (as_ is None or as_ > 0 or not artist)
                if not ok:
                    continue
                cands.append({"source": sid, "source_name": src.name, "museum": sid in MUSEUMS, "key": d.get("key"), "title": d.get("title") or "",
                              "artist": d.get("artist") or "", "date": d.get("date") or "", "medium": d.get("medium") or "", "credit": d.get("credit") or "",
                              "url": d.get("url") or "", "description": d.get("description") or "", "license": d.get("license") or src.license,
                              "score": round(score, 3), "loose": loose, "thumb": d.get("thumb") or d.get("preview") or ""})
        cands.sort(key=lambda c: (not c["museum"], -c["score"], MUSEUMS.index(c["source"]) if c["source"] in MUSEUMS else 99))
        notes = ["%s unreachable" % discover.SOURCES[s].name for s in errs]
        notes += ["%s did not answer in time" % discover.SOURCES[s].name for s in MUSEUMS + OTHERS if s in discover.SOURCES and s not in out and s not in errs]
        return cands, notes
    q = ((title or "") + " " + (artist or "").split(",")[0]).strip()
    cands, notes = run(q, False)
    if not cands and artist:
        cands, notes2 = run((artist or "").split(",")[0].strip(), True)
        notes = notes2 or notes
        if cands: notes.append("no record has that exact title; showing other works by the same artist")
    return cands, notes

def decide(cands):
    """('auto', cand) | ('choose', list) | ('none', None). Museum records win over everything else."""
    if not cands:
        return "none", None
    mus = [c for c in cands if c["museum"]]
    pool = mus or cands
    best = pool[0]
    second = pool[1] if len(pool) > 1 else None
    if any(c.get("loose") for c in pool):
        return "choose", pool[:6]
    if len(pool) == 1 or (best["score"] >= 0.85 and best["score"] - second["score"] >= 0.2):
        return "auto", best
    return "choose", pool[:6]
