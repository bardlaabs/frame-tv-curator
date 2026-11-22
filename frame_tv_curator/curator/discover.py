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


def _get(url, timeout=30, method="GET", gap=0.25, headers=None, data=None):
    """One polite HTTP request: at most one every `gap` seconds across all threads."""
    with _net:
        w = gap - (time.time() - _last[0])
        if w > 0:
            time.sleep(w)
        _last[0] = time.time()
    h = {"User-Agent": UA, "Accept": "*/*"}
    h.update(headers or {})
    r = urllib.request.Request(url, method=method, headers=h, data=data)
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
    client_fetch = False
    blurb = ("Free classic paintings and photography already extended to 3840×2160, so they fill the screen without cropping. "
             "Title, artist, date, description, source and license are saved with each image.")
    sorts = [["az", "A–Z by artist"], ["recent", "Recently added"], ["random", "Shuffle (changes hourly)"]]
    types = []
    has_artists = True
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

    def search(self, q="", artist="", sort="az", page=0, per=24, **kw):
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


class AIC:
    """Art Institute of Chicago open access (public domain, CC0). Their big images are only served to real browsers
    (Cloudflare), so the page downloads the full-size picture itself and hands it to the add-on."""
    id = "aic"
    name = "Art Institute of Chicago"
    home = "https://www.artic.edu"
    license = "CC0 1.0, public domain (Art Institute of Chicago open access)"
    client_fetch = True
    blurb = ("Public-domain works from the Art Institute of Chicago, shown at up to 3840×2160 with the whole artwork kept "
             "(the mat fills the rest). Large files are downloaded by your browser, so adding takes a little longer.")
    sorts = [["relevance", "Best match"], ["az", "A–Z by artist"], ["random", "Shuffle (changes hourly)"]]
    types = [["Painting", "Paintings"], ["Print", "Prints"], ["Drawing and Watercolor", "Drawings and watercolors"],
             ["Photograph", "Photographs"], ["Poster", "Posters"], ["", "All types"]]
    has_artists = False
    API = "https://api.artic.edu/api/v1"
    IIIF = "https://www.artic.edu/iiif/2"
    HDR = {"AIC-User-Agent": "FrameTVCurator (github.com/bardlaabs/frame-tv-curator; personal use)", "Accept": "application/json"}
    FIELDS = ["id", "title", "artist_title", "date_display", "image_id", "thumbnail", "medium_display", "credit_line",
              "description", "short_description", "artwork_type_title", "style_title"]

    def __init__(self):
        self.det = {}

    def artists(self):
        return []

    def _item(self, r):
        iid = r.get("image_id")
        th = r.get("thumbnail") or {}
        ow, oh = th.get("width") or 0, th.get("height") or 0
        w = h = None
        # The museum only serves a short list of sizes. Its own Download button uses a
        # 3000 px best-fit box ("!3000,3000"); other sizes are refused with 403.
        def u(spec):
            return "%s/%s/full/%s/0/default.jpg" % (self.IIIF, iid, spec)
        if ow and oh:
            sc = min(1.0, 3000.0 / max(ow, oh))
            w, h = max(1, int(ow * sc + 0.5)), max(1, int(oh * sc + 0.5))
        big = u("!3000,3000")
        alts = [u("1686,")] if max(ow, oh) > 1686 else []
        small, mid = u("843,"), u("1686,")
        desc = r.get("description") or r.get("short_description") or ""
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", desc))).strip()
        key = str(r["id"])
        d = {"source": self.id, "key": key, "url": self.home + "/artworks/" + key, "title": r.get("title") or "",
             "artist": r.get("artist_title") or "", "date": r.get("date_display") or "", "description": desc,
             "image": big if w else small,
             "image_alts": alts,
             "image_fallback": mid,
             "thumb": small, "preview": mid,
             "w": w, "h": h, "orig_w": ow or None, "orig_h": oh or None, "ai": False, "client_fetch": True,
             "medium": r.get("medium_display") or "", "credit": r.get("credit_line") or "", "license": self.license}
        self.det[key] = d
        return d

    def search(self, q="", artist="", sort="relevance", page=0, per=24, type="Painting", **kw):
        filt = [{"term": {"is_public_domain": True}}, {"exists": {"field": "image_id"}}]
        if type:
            filt.append({"term": {"artwork_type_title.keyword": type}})
        bq = {"bool": {"filter": filt}}
        if q.strip():
            bq["bool"]["must"] = [{"multi_match": {"query": q.strip(), "fields": ["title^3", "artist_title^3", "style_title", "subject_titles", "place_of_origin", "description"]}}]
        body = {"query": bq, "fields": self.FIELDS, "size": per, "from": min(page * per, 10000 - per)}
        if sort == "az":
            body["sort"] = [{"artist_title.keyword": "asc"}, {"title.keyword": "asc"}]
        elif sort == "random":
            body["query"] = {"function_score": {"query": bq, "random_score": {"seed": int(time.time() // 3600), "field": "id"}}}
        r = _get(self.API + "/artworks/search", 40, "POST", gap=1.0, data=json.dumps(body).encode(),
                 headers=dict(self.HDR, **{"Content-Type": "application/json"}))
        j = json.loads(r.read().decode("utf8", "replace"))
        items = [self._item(x) for x in j.get("data", []) if x.get("image_id")]
        total = min(int((j.get("pagination") or {}).get("total") or 0), 10000)
        return {"total": total, "page": page, "per": per, "items": items}

    def detail(self, key):
        if key in self.det:
            return self.det[key]
        r = _get("%s/artworks/%s?fields=%s" % (self.API, urllib.parse.quote(str(key)), ",".join(self.FIELDS)), 30, gap=1.0, headers=self.HDR)
        return self._item(json.loads(r.read().decode("utf8", "replace"))["data"])


class Met:
    """The Metropolitan Museum of Art open access (CC0). The API needs no key. Search returns only object ids, so each
    result page costs one small request per object; objects that are not public domain or have no image are dropped."""
    id = "met"
    name = "The Metropolitan Museum of Art"
    home = "https://www.metmuseum.org"
    license = "CC0 1.0, public domain (The Met Open Access)"
    client_fetch = False
    blurb = ("Public-domain works from The Met, downloaded at the museum's full original size and kept whole (the mat fills the "
             "rest). Pages can come up a little short because only public-domain objects with a picture are shown.")
    sorts = [["relevance", "Best match"]]
    types = [["highlights", "Highlights"], ["11", "European Paintings"], ["21", "Modern Art"], ["9", "Drawings and Prints"],
             ["6", "Asian Art"], ["1", "American Decorative Arts"], ["19", "Photographs"], ["15", "Robert Lehman Collection"],
             ["14", "Islamic Art"], ["10", "Egyptian Art"], ["13", "Greek and Roman Art"], ["17", "Medieval Art"], ["", "Everything"]]
    has_artists = False
    API = "https://collectionapi.metmuseum.org/public/collection/v1"

    def __init__(self):
        self.det = {}

    def artists(self):
        return []

    def _obj(self, oid):
        key = str(oid)
        if key in self.det:
            return self.det[key]
        try:
            o = json.loads(_get("%s/objects/%s" % (self.API, key), 30, gap=0.05).read().decode("utf8", "replace"))
        except Exception as e:
            log.info("met object %s failed: %s", key, e)
            return None
        if not o.get("isPublicDomain") or not o.get("primaryImage") or (o.get("objectName") or "").lower() == "frame":
            self.det[key] = None
            return None
        desc = ""
        parts = [o.get("culture"), o.get("period"), o.get("dynasty")]
        loc = ", ".join(x for x in parts if x)
        d = {"source": self.id, "key": key, "url": o.get("objectURL") or ("%s/art/collection/search/%s" % (self.home, key)),
             "title": o.get("title") or "", "artist": o.get("artistDisplayName") or "", "date": o.get("objectDate") or "",
             "description": desc, "image": o["primaryImage"], "image_fallback": o.get("primaryImageSmall") or o["primaryImage"],
             "thumb": o.get("primaryImageSmall") or o["primaryImage"], "preview": o.get("primaryImageSmall") or o["primaryImage"],
             "w": None, "h": None, "ai": False, "client_fetch": False,
             "medium": o.get("medium") or "", "credit": ("The Metropolitan Museum of Art, " + o["creditLine"]) if o.get("creditLine") else "The Metropolitan Museum of Art",
             "license": self.license, "origin_note": loc}
        self.det[key] = d
        return d

    def search(self, q="", artist="", sort="relevance", page=0, per=24, type="highlights", **kw):
        prm = {"hasImages": "true", "limit": per, "offset": min(page * per, 10000 - per)}
        if q.strip():
            prm["q"] = q.strip()
        if type == "highlights":
            prm["isHighlight"] = "true"
        elif type:
            prm["departmentId"] = type
        if not q.strip() and not type:
            prm["q"] = "*"
        j = json.loads(_get(self.API.replace("/v1", "/v1.1") + "/search?" + urllib.parse.urlencode(prm), 40, gap=0.05).read().decode("utf8", "replace"))
        ids = j.get("objectIDs") or []
        with ThreadPoolExecutor(6) as ex:
            objs = list(ex.map(self._obj, ids))
        items = [x for x in objs if x]
        return {"total": min(int(j.get("total") or 0), 10000), "page": page, "per": per, "items": items}

    def detail(self, key):
        d = self._obj(key)
        if not d:
            raise ValueError("not a public-domain Met object with an image")
        return d


class Cleveland:
    """Cleveland Museum of Art open access (CC0, no key). The "print" JPEG is up to about 3400 px on the long side."""
    id = "cleveland"
    name = "Cleveland Museum of Art"
    home = "https://www.clevelandart.org"
    license = "CC0 1.0, public domain (Cleveland Museum of Art Open Access)"
    client_fetch = False
    blurb = ("Open-access works from the Cleveland Museum of Art, downloaded at up to about 3400 px and kept whole "
             "(the mat fills the rest).")
    sorts = [["relevance", "Best match"]]
    types = [["Painting", "Paintings"], ["Print", "Prints"], ["Drawing", "Drawings"], ["Photograph", "Photographs"],
             ["Textile", "Textiles"], ["Sculpture", "Sculpture"], ["", "All types"]]
    has_artists = False
    API = "https://openaccess-api.clevelandart.org/api/artworks/"
    FIELDS = "id,accession_number,title,creators,creation_date,images,technique,creditline,url,description,share_license_status"

    def __init__(self):
        self.det = {}

    def artists(self):
        return []

    def _item(self, r):
        im = r.get("images") or {}
        big = im.get("print") or im.get("web") or {}
        web = im.get("web") or big
        if not big.get("url"):
            return None
        def n(v):
            try:
                return int(float(v))
            except Exception:
                return None
        cr = [c for c in (r.get("creators") or []) if c.get("role") in (None, "", "artist")] or (r.get("creators") or [])
        artist = re.sub(r"\s*\(.*$", "", (cr[0].get("description") or "")).strip() if cr else ""
        key = str(r["id"])
        d = {"source": self.id, "key": key, "url": r.get("url") or ("https://clevelandart.org/art/" + str(r.get("accession_number"))),
             "title": r.get("title") or "", "artist": artist, "date": r.get("creation_date") or "",
             "description": re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", r.get("description") or ""))).strip(),
             "image": big["url"], "image_fallback": web["url"], "thumb": web["url"], "preview": web["url"],
             "w": n(big.get("width")), "h": n(big.get("height")), "ai": False, "client_fetch": False,
             "medium": r.get("technique") or "",
             "credit": "Cleveland Museum of Art" + (", " + r["creditline"] if r.get("creditline") else ""),
             "license": self.license}
        self.det[key] = d
        return d

    def search(self, q="", artist="", sort="relevance", page=0, per=24, type="Painting", **kw):
        prm = {"cc0": 1, "has_image": 1, "limit": per, "skip": page * per, "fields": self.FIELDS}
        if q.strip():
            prm["q"] = q.strip()
        if type:
            prm["type"] = type
        j = json.loads(_get(self.API + "?" + urllib.parse.urlencode(prm), 40, gap=0.25).read().decode("utf8", "replace"))
        items = [x for x in (self._item(r) for r in j.get("data", [])) if x]
        return {"total": int((j.get("info") or {}).get("total") or 0), "page": page, "per": per, "items": items}

    def detail(self, key):
        if key in self.det:
            return self.det[key]
        j = json.loads(_get(self.API + urllib.parse.quote(str(key)) + "?fields=" + self.FIELDS, 30).read().decode("utf8", "replace"))
        d = self._item(j["data"])
        if not d:
            raise ValueError("no image for this object")
        return d


class NASA:
    """NASA Image and Video Library (no key). NASA media is generally not copyrighted; images under 1600 px wide are skipped."""
    id = "nasa"
    name = "NASA Image Library"
    home = "https://images.nasa.gov"
    license = "NASA media, generally public domain (see nasa.gov/nasa-brand-center/images-and-media)"
    client_fetch = False
    blurb = ("Space and Earth images from NASA, at least 1600 px wide, kept whole (the mat fills the rest). "
             "Choose a topic or type your own search; pages can come up short because small images are skipped.")
    sorts = [["relevance", "Best match"]]
    types = [["nebula", "Nebulae"], ["galaxy", "Galaxies"], ["James Webb Space Telescope", "James Webb"], ["Hubble", "Hubble"],
             ["Mars", "Mars"], ["Moon", "The Moon"], ["Earth from space", "Earth from space"], ["aurora", "Auroras"],
             ["Saturn", "Saturn and Jupiter"], ["", "Search only"]]
    has_artists = False
    API = "https://images-api.nasa.gov/search"
    MIN_W = 1600

    def __init__(self):
        self.det = {}

    def artists(self):
        return []

    def _item(self, it):
        data = (it.get("data") or [{}])[0]
        orig = next((l for l in (it.get("links") or []) if l.get("rel") == "canonical" and l.get("href")), None)
        thumb = next((l for l in (it.get("links") or []) if l.get("rel") == "preview"), None) or \
            next((l for l in (it.get("links") or []) if "~small" in (l.get("href") or "")), None)
        if not orig or int(orig.get("width") or 0) < self.MIN_W:
            return None
        nid = data.get("nasa_id") or ""
        who = data.get("secondary_creator") or data.get("photographer") or data.get("center") or "NASA"
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", data.get("description") or ""))).strip()
        d = {"source": self.id, "key": nid, "url": "https://images.nasa.gov/details/" + urllib.parse.quote(nid),
             "title": data.get("title") or nid, "artist": who, "date": (data.get("date_created") or "")[:10],
             "description": desc, "image": orig["href"].replace("http://", "https://"),
             "image_fallback": (thumb or orig)["href"], "thumb": (thumb or orig)["href"], "preview": (thumb or orig)["href"],
             "w": int(orig.get("width") or 0) or None, "h": int(orig.get("height") or 0) or None, "ai": False, "client_fetch": False,
             "medium": "Photograph", "credit": "NASA" + ((" / " + who) if who and who != "NASA" else ""), "license": self.license}
        self.det[nid] = d
        return d

    def search(self, q="", artist="", sort="relevance", page=0, per=24, type="nebula", **kw):
        term = q.strip() or type or "space"
        prm = {"q": term, "media_type": "image", "page": page + 1, "page_size": per}
        j = json.loads(_get(self.API + "?" + urllib.parse.urlencode(prm), 40, gap=0.25).read().decode("utf8", "replace"))
        col = j.get("collection") or {}
        items = [x for x in (self._item(i) for i in col.get("items", [])) if x]
        total = int((col.get("metadata") or {}).get("total_hits") or 0)
        return {"total": min(total, 9900), "page": page, "per": per, "items": items}

    def detail(self, key):
        if key in self.det:
            return self.det[key]
        j = json.loads(_get(self.API + "?" + urllib.parse.urlencode({"nasa_id": key, "media_type": "image"}), 30).read().decode("utf8", "replace"))
        its = (j.get("collection") or {}).get("items") or []
        d = self._item(its[0]) if its else None
        if not d:
            raise ValueError("NASA image not found or too small")
        return d


SOURCES = {"reframed": Reframed(), "aic": AIC(), "met": Met(), "cleveland": Cleveland(), "nasa": NASA()}


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
    nb = None if d.get("client_fetch") else remote_bytes(d["image"])
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
         "description_attribution": ("Description from " + src.name + (" (CC BY 4.0)" if src.id == "aic" else "")) if d["description"] else None,
         "collection": {"institution": src.name, "status": "downloaded from " + src.name, "credit_line": d.get("credit") or None},
         "medium": d.get("medium") or None,
         "card_text": {"artist": d["artist"], "title": d["title"], "date": d["date"], "medium": d.get("medium") or "", "credit": d.get("credit") or src.name},
         "source_image": {"width": d.get("w"), "height": d.get("h")},
         "source_url": d["url"], "license": d.get("license") or src.license,
         "links": [{"label": src.name + " page", "url": d["url"], "kind": "record"}],
         "origin": {"discover": src.id, "downloaded": time.strftime("%Y-%m-%d"), "ai_extended": bool(ai)},
         "identification": {"confidence": "high", "status": "from source site", "method": "title, artist and date as published by " + src.name,
                            "verified": False}}
    return p


def finish(source, key, img_id, replace=()):
    """The page downloaded the picture itself and uploaded it; record where it came from."""
    d = SOURCES[source].detail(key)
    library.patch_sidecar(img_id, sidecar_patch(d))
    for old in replace or []:
        try:
            library.delete_image(old)
        except Exception as e:
            log.warning("replace: could not trash %s: %s", old, e)
    library.save_image_cache()
    log.info("discover: added %s (browser download)", img_id)
    return {"ok": True, "id": img_id, "filename": _filename(d, ".jpg")}


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
            data, ctype = _download(d.get("image_fallback") if sp.get("reduced") and d.get("image_fallback") else d["image"], it)
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
