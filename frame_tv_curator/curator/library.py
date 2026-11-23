"""Library: folders, images, sidecars."""
import os, json, re, shutil
from . import config
from PIL import Image as _I
from PIL import Image
_I.MAX_IMAGE_PIXELS = 400_000_000

def _safe(rel):
    p = os.path.normpath(os.path.join(config.ROOT, rel))
    if not p.startswith(os.path.normpath(config.ROOT) + os.sep):
        raise ValueError("bad path")
    return p

def abspath(img_id):
    return _safe(img_id)

def folders():
    out = []
    for n in sorted(os.listdir(config.ROOT), key=lambda x: (x.lower(), x)):
        p = os.path.join(config.ROOT, n)
        if n.startswith("_") or not os.path.isdir(p):
            continue
        out.append({"name": n, "count": len(images(n))})
    return out

def images(folder):
    p = _safe(folder)
    if not os.path.isdir(p):
        return []
    return sorted(f"{folder}/{f}" for f in os.listdir(p)
                  if f.lower().endswith(config.IMG_EXT) and not f.startswith("."))

def sidecar_path(img_id):
    return os.path.splitext(abspath(img_id))[0] + ".json"

def load_sidecar(img_id):
    p = sidecar_path(img_id)
    if os.path.exists(p):
        try:
            return json.load(open(p))
        except Exception:
            return {}
    return {}

def save_sidecar(img_id, sc):
    p = sidecar_path(img_id)
    tmp = p + ".tmp"
    json.dump(sc, open(tmp, "w"), indent=2, ensure_ascii=False)
    os.replace(tmp, p)

def patch_sidecar(img_id, patch):
    from .store import deep_merge
    sc = deep_merge(load_sidecar(img_id), patch)
    save_sidecar(img_id, sc)
    return sc

def create_folder(name):
    name = re.sub(r"[^\w\- ]", "", name).strip()
    if not name or name.startswith("_"):
        raise ValueError("bad folder name")
    os.makedirs(_safe(name), exist_ok=True)
    return name

_PHONE = re.compile(r"\s*[\(\[]?\+?\d[\d\s().\-]{7,}\d[\)\]]?\s*$")

def _dms(v, ref):
    try:
        d, m, s = (float(x) for x in v)
        val = d + m / 60 + s / 3600
        return -val if str(ref).upper() in ("S", "W") else val
    except Exception:
        return None

def geocode(lat, lon):
    """Place name via OpenStreetMap Nominatim (once per photo, result is stored in the sidecar)."""
    import urllib.request, urllib.parse
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "en"})
    r = urllib.request.Request("https://nominatim.openstreetmap.org/reverse?" + q,
                               headers={"User-Agent": "FrameTVCurator/0.3 (home assistant add-on)"})
    a = json.load(urllib.request.urlopen(r, timeout=15)).get("address", {})
    place = a.get("city") or a.get("town") or a.get("village") or a.get("hamlet") or a.get("county") or a.get("state_district")
    region = a.get("state") or a.get("region")
    country = a.get("country")
    if country in ("United States", "United States of America") and region:
        return ", ".join(x for x in (place, region) if x)
    return ", ".join(x for x in (place, region if not place else None, country) if x) or None

def exif_fields(path):
    """EXIF -> {artist, date, lat, lon, camera}. Only what is really present."""
    from PIL import Image, ExifTags
    out = {}
    try:
        ex = Image.open(path).getexif()
        tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
        tags.update({ExifTags.TAGS.get(k, k): v for k, v in ex.get_ifd(0x8769).items()})
        a = tags.get("Artist")
        if a:
            out["artist"] = _PHONE.sub("", str(a)).strip()
        d = tags.get("DateTimeOriginal") or tags.get("DateTime")
        if d:
            import datetime
            try:
                out["date"] = datetime.datetime.strptime(str(d)[:19], "%Y:%m:%d %H:%M:%S").strftime("%B %-d, %Y")
            except Exception:
                out["date"] = str(d)[:4]
        g = ex.get_ifd(0x8825)
        if g.get(2) and g.get(4):
            lat, lon = _dms(g[2], g.get(1)), _dms(g[4], g.get(3))
            if lat is not None and lon is not None and (lat or lon):
                out["lat"], out["lon"] = lat, lon
        cam = " ".join(str(tags[k]) for k in ("Make", "Model") if tags.get(k))
        if cam:
            out["camera"] = cam
    except Exception:
        pass
    return out

def exif_sidecar(path):
    """Prefill a sidecar for a photo from EXIF."""
    f = exif_fields(path)
    sc = {"schema": "frame-art-sidecar/1", "kind": "photo", "exif_v": 2}   # no title: the library shows the filename until you set one
    if f.get("artist"):
        sc["artist"] = {"name": f["artist"], "display": f["artist"]}
    if f.get("date"):
        sc["date"] = {"display": f["date"]}
    if "lat" in f:
        sc["location"] = {"lat": f["lat"], "lon": f["lon"], "name": None}
    if f.get("camera"):
        sc["camera"] = f["camera"]
    return sc

def geocode_image(img_id):
    """Look up the place name for one photo with coordinates; retried later (up to 3 tries) if the lookup fails."""
    import logging
    sc = load_sidecar(img_id)
    loc = sc.get("location")
    if not (isinstance(loc, dict) and loc.get("lat") is not None and not loc.get("name")) or loc.get("tries", 0) >= 3:
        return False
    try:
        loc["name"] = geocode(loc["lat"], loc["lon"])
    except Exception as e:
        logging.getLogger("library").warning("geocode failed for %s: %s", img_id, e)
    loc["tries"] = loc.get("tries", 0) + 1
    sc = load_sidecar(img_id)
    sc["location"] = loc
    save_sidecar(img_id, sc)
    return True

def fill_location_names():
    """Background: reverse-geocode photos that have coordinates but no place name yet (1 request/second)."""
    import time
    for fo in folders():
        for i in images(fo["name"]):
            if geocode_image(i):
                time.sleep(1.2)

def ensure_sidecar(img_id):
    p = sidecar_path(img_id)
    if not os.path.exists(p):
        save_sidecar(img_id, exif_sidecar(abspath(img_id)))
        return load_sidecar(img_id)
    sc = load_sidecar(img_id)
    auto = os.path.splitext(os.path.basename(img_id))[0].replace("_", " ")
    if sc.get("kind") == "photo" and sc.get("title") == auto:      # filename-derived title from earlier versions
        sc.pop("title", None)
        save_sidecar(img_id, sc)
    if sc.get("kind") == "photo" and sc.get("exif_v", 0) < 2:      # upgrade older photo sidecars, never overwriting edits
        new = exif_sidecar(abspath(img_id))
        for k in ("artist", "date", "location", "camera"):
            if k in new and (k not in sc or k in ("artist", "date")):
                sc[k] = new[k]
        auto = os.path.splitext(os.path.basename(img_id))[0].replace("_", " ")
        if sc.get("title") == auto:            # drop the auto-generated filename title written by earlier versions
            sc.pop("title", None)
        sc["exif_v"] = 2
        save_sidecar(img_id, sc)
    return sc

def ensure_all():
    for fo in folders():
        for i in images(fo["name"]):
            try:
                ensure_sidecar(i)
            except Exception:
                pass

def normalize_upload(fn, data):
    """Accept JPEG/PNG as-is; convert HEIC/HEIF (Apple Photos), WebP, TIFF, BMP to JPEG (orientation baked in, EXIF kept)."""
    import io
    from PIL import Image, ImageOps
    stem, ext = os.path.splitext(fn)
    ext = ext.lower()
    if ext in (".jpg", ".jpeg", ".png"):
        return fn, data
    if ext in (".heic", ".heif"):
        import pillow_heif
        pillow_heif.register_heif_opener()
    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im).convert("RGB")
    kw = {}
    try:
        ex = im.getexif(); ex[0x0112] = 1; kw["exif"] = ex.tobytes()
    except Exception:
        pass
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=95, subsampling=0, **kw)
    return stem + ".jpg", buf.getvalue()

def save_upload(folder, filename, data):
    folder = create_folder(folder)
    fn = re.sub(r"[^\w.\- ]", "_", os.path.basename(filename))
    fn, data = normalize_upload(fn, data)
    stem, ext = os.path.splitext(fn)
    n, dest = 1, os.path.join(_safe(folder), fn)
    while os.path.exists(dest):                       # never overwrite an existing image
        fn = f"{stem}-{n}{ext}"; dest = os.path.join(_safe(folder), fn); n += 1
    open(dest, "wb").write(data)
    img_id = f"{folder}/{fn}"
    ensure_sidecar(img_id)
    import threading
    threading.Thread(target=geocode_image, args=(img_id,), daemon=True).start()
    return img_id

def low_res(img_id):
    from PIL import Image
    w, h = Image.open(abspath(img_id)).size
    return w < 1920 or h < 1080


def display_info(img_id, sc=None):
    sc = sc if sc is not None else load_sidecar(img_id)
    ct = sc.get("card_text") or {}
    stem = os.path.splitext(os.path.basename(img_id))[0]
    a = sc.get("artist") or {}
    artist = ct.get("artist") or a.get("display") or a.get("name") or ""
    if artist.lower() in ("unknown artist", "unknown"):
        artist = ""
    title = ct.get("title") or sc.get("placard_title") or sc.get("title") or ""
    return {"id": img_id, "folder": img_id.split("/")[0], "file": os.path.basename(img_id), "title": title,
            "name": title or stem, "artist": artist}


# ---- delete (to a recoverable trash folder) ----
def delete_image(img_id):
    import time
    src = abspath(img_id)
    if not os.path.isfile(src):
        raise ValueError("image not found")
    folder, fn = img_id.split("/", 1)
    tdir = _safe("_trash/" + folder)
    os.makedirs(tdir, exist_ok=True)
    stem, ext = os.path.splitext(fn)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    dst = os.path.join(tdir, f"{stem}__{stamp}{ext}")
    os.replace(src, dst)
    sp = sidecar_path(img_id)
    if os.path.exists(sp):
        os.replace(sp, os.path.splitext(dst)[0] + ".json")
    try:
        from . import albums
        albums.forget(img_id)
    except Exception:
        pass
    return dst

# ---- files dropped into the folders from outside the add-on (SMB, scripts, sync tools) ----
CONVERT_EXT = (".heic", ".heif", ".webp", ".tif", ".tiff", ".bmp")
SETTLE_S = 15          # ignore files modified in the last N seconds (still being copied)

def _settled(path):
    import time
    try:
        return time.time() - os.path.getmtime(path) >= SETTLE_S
    except OSError:
        return False

def scan():
    """Pick up images added behind the add-on's back: convert HEIC/WebP/TIFF/BMP to JPEG, create missing sidecars
    (EXIF prefill), and look up place names. Returns the list of image ids that were newly processed."""
    import logging
    log = logging.getLogger("library")
    new = []
    for fo in folders():
        d = _safe(fo["name"])
        for f in sorted(os.listdir(d)):
            if f.startswith(".") or not f.lower().endswith(CONVERT_EXT):
                continue
            p = os.path.join(d, f)
            if not (os.path.isfile(p) and _settled(p)):
                continue
            try:
                fn, data = normalize_upload(f, open(p, "rb").read())
                stem, ext = os.path.splitext(fn)
                n, dest = 1, os.path.join(d, fn)
                while os.path.exists(dest):
                    fn = f"{stem}-{n}{ext}"; dest = os.path.join(d, fn); n += 1
                open(dest, "wb").write(data)
                od = _safe("_originals/" + fo["name"]); os.makedirs(od, exist_ok=True)
                os.replace(p, os.path.join(od, f))
                log.info("converted %s/%s -> %s (original kept in _originals)", fo["name"], f, fn)
            except Exception as e:
                log.warning("could not convert %s/%s: %s", fo["name"], f, e)
        for i in images(fo["name"]):
            p = abspath(i)
            if os.path.exists(sidecar_path(i)):
                geocode_image(i)
                continue
            if not _settled(p):
                continue
            try:
                Image.open(p).verify()
                ensure_sidecar(i)
                new.append(i)
                log.info("new image found: %s", i)
                geocode_image(i)
            except Exception as e:
                log.warning("skipping %s (unreadable so far): %s", i, e)
    return new


# ---- automatic backups of sidecars + settings ----
def backup_dir():
    d = _safe("_backups"); os.makedirs(d, exist_ok=True); return d

def list_backups():
    d = backup_dir()
    out = [{"file": f, "bytes": os.path.getsize(os.path.join(d, f)), "mtime": os.path.getmtime(os.path.join(d, f))}
           for f in os.listdir(d) if f.endswith(".tar.gz")]
    return sorted(out, key=lambda x: -x["mtime"])

def backup_all(keep=14):
    """tar.gz of every sidecar JSON plus the add-on's settings/state; the newest `keep` are kept."""
    import tarfile, time
    dest = os.path.join(backup_dir(), "curator-" + time.strftime("%Y%m%d-%H%M%S") + ".tar.gz")
    n = 0
    with tarfile.open(dest, "w:gz") as t:
        for fo in folders():
            d = _safe(fo["name"])
            for f in os.listdir(d):
                if f.endswith(".json") and not f.startswith("."):
                    t.add(os.path.join(d, f), arcname=f"sidecars/{fo['name']}/{f}"); n += 1
        for f in ("settings.json", "state.json"):
            p = os.path.join(config.DATA, f)
            if os.path.exists(p):
                t.add(p, arcname=f"data/{f}")
    for old in list_backups()[keep:]:
        os.remove(os.path.join(backup_dir(), old["file"]))
    return {"file": os.path.basename(dest), "sidecars": n}


# ---- image facts (size, perceptual hash) cached in DATA/imgcache.json: low-res warning + duplicate detection ----
import threading as _th
_ic_lock = _th.Lock()
_ic = {}

def _ic_load():
    global _ic
    if not _ic:
        try:
            _ic = json.load(open(os.path.join(config.DATA, "imgcache.json")))
        except Exception:
            _ic = {}

def image_facts(img_id):
    """{w, h, dh (64-bit difference hash as hex)} for an image, cached until the file changes."""
    from PIL import ImageOps
    p = abspath(img_id)
    st = os.stat(p)
    with _ic_lock:
        _ic_load()
        e = _ic.get(img_id)
        if e and e.get("m") == st.st_mtime and e.get("s") == st.st_size:
            return e
    im = Image.open(p)
    w, h = im.size
    im.draft("L", (256, 256))
    sm = ImageOps.exif_transpose(im).convert("L").resize((9, 8), Image.LANCZOS)
    px = list(sm.getdata())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    e = {"m": st.st_mtime, "s": st.st_size, "w": w, "h": h, "dh": "%016x" % bits}
    with _ic_lock:
        _ic[img_id] = e
    return e

def save_image_cache():
    with _ic_lock:
        tmp = os.path.join(config.DATA, "imgcache.json.tmp")
        json.dump(_ic, open(tmp, "w"))
        os.replace(tmp, os.path.join(config.DATA, "imgcache.json"))

def warm_facts(budget=40):
    """Compute size/hash facts for up to `budget` not-yet-cached images per call (keeps duplicate check and low-res badges fast)."""
    n = 0
    for i in all_images():
        try:
            p = abspath(i); st = os.stat(p)
            with _ic_lock:
                _ic_load(); e = _ic.get(i)
            if e and e.get("m") == st.st_mtime and e.get("s") == st.st_size:
                continue
            image_facts(i); n += 1
        except Exception:
            pass
        if n >= budget:
            break
    if n:
        save_image_cache()

def is_low_res(img_id):
    try:
        e = image_facts(img_id)
        return e["w"] < 1920 or e["h"] < 1080
    except Exception:
        return False

def dhash_image(im):
    """64-bit difference hash (hex) of a PIL image; same algorithm as image_facts."""
    from PIL import ImageOps
    sm = ImageOps.exif_transpose(im).convert("L").resize((9, 8), Image.LANCZOS)
    px = list(sm.getdata())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    return "%016x" % bits

def source_of(img_id, sc=None):
    """Where the image came from, if known (museum / site / camera), for duplicate comparisons."""
    sc = sc if sc is not None else load_sidecar(img_id)
    col = sc.get("collection") or {}
    src = col.get("institution") or sc.get("source")
    if not isinstance(src, str):
        src = None
    if not src and sc.get("kind") == "photo":
        src = "own photo" + (" (%s)" % sc["camera"] if sc.get("camera") else "")
    return src or (sc.get("card_text") or {}).get("credit") or None

def _ham(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")

def all_images():
    return [i for fo in folders() for i in images(fo["name"])]

def find_duplicates(threshold=4):
    """Groups of images that look the same (difference-hash distance <= threshold). Each group lists the files with size info."""
    ids = all_images()
    facts = {}
    for i in ids:
        try:
            facts[i] = image_facts(i)
        except Exception:
            pass
    save_image_cache()
    parent = {i: i for i in facts}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    keys = list(facts)
    for a in range(len(keys)):
        for b in range(a + 1, len(keys)):
            if _ham(facts[keys[a]]["dh"], facts[keys[b]]["dh"]) <= threshold:
                parent[find(keys[a])] = find(keys[b])
    groups = {}
    for i in keys:
        groups.setdefault(find(i), []).append(i)
    out = []
    for g in groups.values():
        if len(g) > 1:
            out.append([{"id": i, "name": display_info(i)["name"], "folder": i.split("/")[0], "w": facts[i]["w"], "h": facts[i]["h"],
                         "bytes": facts[i]["s"], "source": source_of(i)} for i in sorted(g)])
    return out

def duplicate_of(img_id, threshold=5):
    try:
        me = image_facts(img_id)
    except Exception:
        return None
    for i in all_images():
        if i != img_id:
            try:
                if _ham(me["dh"], image_facts(i)["dh"]) <= threshold:
                    return i
            except Exception:
                pass
    return None


DEFAULT_FOLDERS = ("Art", "Photos")


def ensure_default_folders():
    """Create the Art and Photos folders on first run (matched case-insensitively, so existing folders are kept)."""
    os.makedirs(config.ROOT, exist_ok=True)
    have = {n.lower() for n in os.listdir(config.ROOT) if os.path.isdir(os.path.join(config.ROOT, n))}
    for n in DEFAULT_FOLDERS:
        if n.lower() not in have:
            os.makedirs(os.path.join(config.ROOT, n), exist_ok=True)


def _retarget(o, old, new):
    if isinstance(o, str):
        if o == old:
            return new
        if o.startswith(old + "/"):
            return new + o[len(old):]
        return o
    if isinstance(o, list):
        return [_retarget(x, old, new) for x in o]
    if isinstance(o, dict):
        return {_retarget(k, old, new): _retarget(v, old, new) for k, v in o.items()}
    return o


def migrate_folder_case():
    """One-time opt-in rename of art/photos to Art/Photos. Runs only when the marker file
    <media>/frame/_meta/rename_folders_to_title_case exists, then renames the marker to .done."""
    import logging
    log = logging.getLogger("library")
    marker = os.path.join(config.ROOT, "_meta", "rename_folders_to_title_case")
    if not os.path.exists(marker):
        return
    pairs = []
    for new in DEFAULT_FOLDERS:
        old = new.lower()
        names = os.listdir(config.ROOT)
        if old in names and new not in names:
            tmp = os.path.join(config.ROOT, "." + old + ".renaming")
            os.rename(os.path.join(config.ROOT, old), tmp)
            os.rename(tmp, os.path.join(config.ROOT, new))
            pairs.append((old, new))
            for sub in ("_originals", "_trash"):
                sp = os.path.join(config.ROOT, sub, old)
                if os.path.isdir(sp) and not os.path.exists(os.path.join(config.ROOT, sub, new)):
                    os.rename(sp, os.path.join(config.ROOT, sub, new))
            log.info("renamed folder %s -> %s", old, new)
    if pairs and os.path.isdir(config.DATA):
        for fn in os.listdir(config.DATA):
            if not fn.endswith(".json"):
                continue
            p = os.path.join(config.DATA, fn)
            try:
                data = json.load(open(p))
            except Exception:
                continue
            new_data = data
            for old, new in pairs:
                new_data = _retarget(new_data, old, new)
            if new_data != data:
                json.dump(new_data, open(p + ".tmp", "w"), indent=1)
                os.replace(p + ".tmp", p)
                log.info("updated folder names in %s", fn)
    os.replace(marker, marker + ".done")
