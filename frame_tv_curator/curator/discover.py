"""Discover: find new art online and add it to the library.

Sources are small classes with the same few methods, so more can be added (museum APIs next). Reframed Gallery has no
API: its public sitemap lists every artwork page, and each page carries schema.org data (title, artist, date, size, the
full-size file). Requests are polite (identifying User-Agent, a pause between requests, caching)."""
import os, re, io, json, time, threading, unicodedata, logging, urllib.request, urllib.parse, html, random
from concurrent.futures import ThreadPoolExecutor
from . import config, library
log = logging.getLogger("discover")
UA = "FrameTVCurator/1.0 (+https://github.com/bardlaabs/frame-tv-curator; personal use)"
DIR = os.path.join(config.DATA, "discover")
_net = threading.Lock()
_last = [0.0]


def _get(url, timeout=30, method="GET", gap=0.25):
    """One polite HTTP request: at most one every `gap` seconds across all threads."""
    with _net:
        w = gap - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
    r = urllib.request.Request(url, method=method, headers={"User-Agent": UA, "Accept": "*/*"})
    return urllib.request.urlopen(r, timeout=timeout)


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _jload(name, default):
    try:
        return json.load(open(os.path.join(DIR, name)))
    except Exception:
        return default


def _jsave(name, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = os.path.join(DIR, name + ".tmp")
    json.dump(data, open(tmp, "w"))
    os.replace(tmp, os.path.join(DIR, name))


class Reframed:
    id = "reframed"
    name = "Reframed Gallery"
    home = "https://www.reframed.gallery"
    license = "Free to download and use (per the Reframed Gallery FAQ)"
    RESERVED = {"recent", "artists", "collections", "verticals", "colors", "what-is-reframed", "chrome-extension",
                "faq", "contact", "browse", "search", "privacy", "terms"}

    def __init__(self):
        self.lock = threading.RLock()
        self.items = None
        self.det = _jload("reframed_items.json", {})

    # ---- index (sitemap, cached for a day)
    def index(self, force=False):
        with self.lock:
            if self.items is not None and not force:
                return self.items
            c = _jload("reframed_index.json", {})
            if not force and c.get("items") and time.time() - c.get("ts", 0) < 86400:
                self.items = c["items"]
                return self.items
            try:
                xml = _get(self.home + "/sitemap.xml", 60).read().decode("utf8", "replace")
                seen, items = set(), []
                for u in re.findall(r"<loc>([^<]+)</loc>", xml):
                    parts = [x for x in urllib.parse.urlparse(u).path.split("/") if x]
                    if len(parts) == 2 and parts[0] not in self.RESERVED and parts[0] != "collections":
                        k = "/".join(parts)
                        if k not in seen:
                            seen.add(k); items.append(k)
                if items:
                    _jsave("reframed_index.json", {"ts": time.time(), "items": items})
                    self.items = items
            except Exception as e:
                log.warning("reframed sitemap: %s", e)
                if c.get("items"):
                    self.items = c["items"]
            if self.items is None:
                raise RuntimeError("Could not read the Reframed Gallery sitemap")
            return self.items

    def recent(self):
        try:
            h = _get(self.home + "/recent", 40).read().decode("utf8", "replace")
            known = set(self.index())
            out = []
            for m in re.findall(r'href="/([^"/?#]+/[^"/?#]+)"', h):
                if m in known and m not in out:
                    out.append(m)
            return out
        except Exception as e:
            log.warning("reframed recent: %s", e)
            return []

    @staticmethod
    def _words(slug):
        return slug.replace("-", " ")

    def artists(self):
        n = {}
        for k in self.index():
            a = k.split("/")[0]
            n[a] = n.get(a, 0) + 1
        return [{"slug": a, "name": a.replace("-", " ").title(), "count": c} for a, c in sorted(n.items())]

    def search(self, q="", artist="", sort="az", page=0, per=24):
        items = self.index()
        if sort == "recent":
            rec = self.recent()
            items = rec or items
        ws = [norm(w) for w in re.split(r"\s+", q.strip()) if w.strip()]
        out = []
        for k in items:
            if artist and k.split("/")[0] != artist:
                continue
            h = norm(self._words(k))
            if all(w in h for w in ws):
                out.append(k)
        if sort == "az":
            out.sort()
        elif sort == "random":
            random.Random(int(time.time() // 3600)).shuffle(out)
        total = len(out)
        return {"total": total, "page": page, "per": per, "keys": out[page * per:(page + 1) * per]}

    # ---- one artwork
    def detail(self, key):
        with self.lock:
            d = self.det.get(key)
        if d:
            return d
        url = self.home + "/" + key
        t = _get(url, 40).read().decode("utf8", "replace")
        ld = None
        for m in re.finditer(r'<script type="application/ld\+json"[^>]*>([\s\S]*?)</script>', t):
            try:
                j = json.loads(m.group(1))
            except Exception:
                continue
            if isinstance(j, dict) and j.get("@type") == "VisualArtwork":
                ld = j; break
        if not ld:
            raise RuntimeError("no artwork data on " + url)

        def px(v):
            m = re.search(r"\d+", str((v or {}).get("name") if isinstance(v, dict) else v or ""))
            return int(m.group()) if m else None
        d = {"source": self.id, "key": key, "url": url, "title": html.unescape(ld.get("name") or ""),
             "artist": html.unescape(((ld.get("artist") or {}).get("name")) or ""), "date": str(ld.get("dateCreated") or ""),
             "description": html.unescape(ld.get("description") or ""), "image": ld.get("contentUrl"),
             "thumb": ld.get("thumbnailUrl"), "w": px(ld.get("width")), "h": px(ld.get("height")),
             "ai": bool(re.search(r">\s*AI\s*<|AI[- ]extended|AI[- ]generated", t))}
        if not d["image"]:
            raise RuntimeError("no image link on " + url)
        with self.lock:
            self.det[key] = d
            _jsave("reframed_items.json", self.det)
        return d


SOURCES = {"reframed": Reframed()}


# ---------------- library matching ----------------
def _lib_entries():
    out = []
    for i in library.all_images():
        try:
            sc = library.load_sidecar(i)
            ct = sc.get("card_text") or {}
            a = sc.get("artist") or {}
            title = ct.get("title") or sc.get("placard_title") or sc.get("title") or ""
            artist = ct.get("artist") or a.get("display") or a.get("name") or ""
            f = library.image_facts(i)
            out.append({"id": i, "name": title or os.path.splitext(os.path.basename(i))[0], "folder": i.split("/")[0],
                        "t": norm(title), "a": norm(artist), "file": norm(os.path.splitext(os.path.basename(i))[0]),
                        "w": f["w"], "h": f["h"], "bytes": f["s"], "dh": f["dh"], "source": library.source_of(i, sc)})
        except Exception:
            pass
    library.save_image_cache()
    return out


_thumbcache = {}
_remote_size = {}


def remote_bytes(url):
    if url in _remote_size:
        return _remote_size[url]
    try:
        n = int(_get(url, 30, "HEAD").headers.get("Content-Length") or 0) or None
    except Exception:
        n = None
    _remote_size[url] = n
    return n


_dims = {}


def remote_dims(url):
    """Pixel size of a remote JPEG/PNG from its first 128 KB (a range request), or (None, None)."""
    if url in _dims:
        return _dims[url]
    wh = (None, None)
    try:
        from PIL import ImageFile
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-131071"})
        with _net:
            _last[0] = time.time()
        data = urllib.request.urlopen(r, timeout=30).read(131072)
        p = ImageFile.Parser()
        p.feed(data)
        if p.image:
            wh = p.image.size
    except Exception as e:
        log.info("dimension probe failed for %s: %s", url, e)
    _dims[url] = wh
    return wh


def fill_dims(d):
    if d.get("image") and not (d.get("w") and d.get("h")):
        d["w"], d["h"] = remote_dims(d["image"])
    return d


def check(d, entries=None):
    """Library images that look like this candidate: the same picture (hash of the small preview) or the same title+artist."""
    from PIL import Image
    entries = entries if entries is not None else _lib_entries()
    dh = _thumbcache.get(d["thumb"] or d["image"])
    if dh is None:
        try:
            data = _get(d["thumb"] or d["image"], 40).read()
            dh = library.dhash_image(Image.open(io.BytesIO(data))) if data else ""
        except Exception as e:
            log.info("preview hash failed for %s: %s", d.get("key"), e)
            dh = ""
        _thumbcache[d["thumb"] or d["image"]] = dh
    t, a = norm(d["title"]), norm(d["artist"])
    nb = remote_bytes(d["image"])
    fill_dims(d)
    out = []
    for e in entries:
        how = None
        if dh and library._ham(dh, e["dh"]) <= 6:
            how = "looks like the same picture"
        elif t and a and e["t"] == t and (e["a"] == a or not e["a"]):
            how = "same title and artist"
        elif t and a and t in e["file"] and a in e["file"]:
            how = "same title and artist in the file name"
        if how:
            out.append({"id": e["id"], "name": e["name"], "folder": e["folder"], "w": e["w"], "h": e["h"], "bytes": e["bytes"],
                        "source": e["source"], "how": how})
    return {"new": {"w": d.get("w"), "h": d.get("h"), "bytes": nb, "source": SOURCES[d["source"]].name}, "matches": out}


# ---------------- adding ----------------
JOBS = {}
_jlock = threading.Lock()


def _filename(d, ext):
    base = (d["artist"] + " - " if d["artist"] else "") + (d["title"] or "Untitled")
    base = re.sub(r"[^\w.\-,'() &]", "", base).strip()[:120] or "artwork"
    return base + ext


def sidecar_patch(d):
    fill_dims(d)
    src = SOURCES[d["source"]]
    ai = d.get("ai")
    p = {"schema": "frame-art-sidecar/1", "kind": "art", "title": d["title"] or None,
         "artist": {"name": d["artist"] or None, "display": d["artist"] or None},
         "date": {"display": d["date"] or None, "start": None, "end": None},
         "description": d["description"] or None,
         "description_attribution": "Description from " + src.name if d["description"] else None,
         "collection": {"institution": src.name, "status": "downloaded from " + src.name},
         "card_text": {"artist": d["artist"], "title": d["title"], "date": d["date"], "medium": "", "credit": src.name},
         "source_image": {"width": d.get("w"), "height": d.get("h")},
         "source_url": d["url"], "license": src.license,
         "links": [{"label": src.name + " page", "url": d["url"], "kind": "record"}],
         "origin": {"discover": src.id, "downloaded": time.strftime("%Y-%m-%d"), "ai_extended": bool(ai)},
         "identification": {"confidence": "high", "status": "from source site", "method": "title, artist and date as published by " + src.name,
                            "verified": False}}
    return p


def _download(url, job_item):
    r = _get(url, 120)
    total = int(r.headers.get("Content-Length") or 0)
    job_item["total"] = total
    buf = io.BytesIO()
    while True:
        c = r.read(65536)
        if not c:
            break
        buf.write(c); job_item["got"] = buf.tell()
    return buf.getvalue(), (r.headers.get("Content-Type") or "")


def _run(job, specs, folder):
    from PIL import Image
    for it, sp in zip(job["items"], specs):
        try:
            if it["state"] == "skipped":
                continue
            d = SOURCES[sp["source"]].detail(sp["key"])
            it["state"] = "downloading"
            data, ctype = _download(d["image"], it)
            im = Image.open(io.BytesIO(data)); im.load()
            ext = ".png" if "png" in ctype.lower() or d["image"].lower().endswith(".png") else ".jpg"
            img_id = library.save_upload(folder, _filename(d, ext), data)
            library.patch_sidecar(img_id, sidecar_patch(d))
            it["id"] = img_id
            for old in sp.get("replace") or []:
                try:
                    library.delete_image(old)
                except Exception as e:
                    log.warning("replace: could not trash %s: %s", old, e)
            it["state"] = "done"
            log.info("discover: added %s", img_id)
        except Exception as e:
            log.warning("discover add %s failed: %s", sp.get("key"), e)
            it["state"] = "failed"; it["error"] = str(e)
    job["finished"] = True
    library.save_image_cache()


def add(specs, folder):
    """specs: [{source, key, dup: 'skip'|'keep'|'replace', replace: [library ids]}] -> job id (poll with job())."""
    folder = library.create_folder(folder)
    jid = "%x" % int(time.time() * 1000)
    items = []
    for sp in specs:
        st = "skipped" if sp.get("dup") == "skip" else "queued"
        items.append({"key": sp["key"], "state": st, "got": 0, "total": 0})
        if sp.get("dup") != "replace":
            sp["replace"] = []
    job = {"id": jid, "folder": folder, "items": items, "finished": False}
    with _jlock:
        JOBS[jid] = job
        for k in list(JOBS)[:-8]:
            JOBS.pop(k, None)
    threading.Thread(target=_run, args=(job, specs, folder), daemon=True, name="discover-add").start()
    return job
