"""Albums: named collections of library images (an image can be in several). Stored in /data/albums.json as image ids."""
import os, re, json, threading, time
from . import config

_lock = threading.RLock()
_PATH = lambda: os.path.join(config.DATA, "albums.json")


def _load():
    try:
        return json.load(open(_PATH()))
    except Exception:
        return {"albums": []}


def _save(d):
    os.makedirs(config.DATA, exist_ok=True)
    tmp = _PATH() + ".tmp"
    json.dump(d, open(tmp, "w"), indent=1)
    os.replace(tmp, _PATH())


def _exists(i):
    from . import library
    try:
        return os.path.isfile(library.abspath(i))
    except Exception:
        return False


def listing():
    with _lock:
        return [{"id": a["id"], "name": a["name"], "count": len([i for i in a["images"] if _exists(i)])}
                for a in sorted(_load()["albums"], key=lambda a: a["name"].lower())]


def images(album_id):
    with _lock:
        for a in _load()["albums"]:
            if a["id"] == album_id:
                return [i for i in a["images"] if _exists(i)]
    return []


def create(name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if not name:
        raise ValueError("name needed")
    with _lock:
        d = _load()
        for a in d["albums"]:
            if a["name"].lower() == name.lower():
                return a["id"]
        aid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "album"
        ids = {a["id"] for a in d["albums"]}
        base, n = aid, 2
        while aid in ids:
            aid = "%s-%d" % (base, n); n += 1
        d["albums"].append({"id": aid, "name": name, "images": [], "created": time.strftime("%Y-%m-%d")})
        _save(d)
        return aid


def _edit(album_id, fn):
    with _lock:
        d = _load()
        for a in d["albums"]:
            if a["id"] == album_id:
                fn(a, d)
                _save(d)
                return True
    raise ValueError("album not found")


def rename(album_id, name):
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:60]
    if not name:
        raise ValueError("name needed")
    _edit(album_id, lambda a, d: a.update(name=name))


def delete(album_id):
    with _lock:
        d = _load()
        d["albums"] = [a for a in d["albums"] if a["id"] != album_id]
        _save(d)


def add(album_id, ids):
    def f(a, d):
        have = set(a["images"])
        a["images"] += [i for i in ids if i not in have and _exists(i)]
    _edit(album_id, f)


def remove(album_id, ids):
    s = set(ids)
    _edit(album_id, lambda a, d: a.update(images=[i for i in a["images"] if i not in s]))


def forget(img_id):
    """An image was deleted."""
    with _lock:
        d = _load()
        ch = False
        for a in d["albums"]:
            if img_id in a["images"]:
                a["images"] = [i for i in a["images"] if i != img_id]; ch = True
        if ch:
            _save(d)


def remap(old, new):
    """An image moved to another folder."""
    with _lock:
        d = _load()
        ch = False
        for a in d["albums"]:
            if old in a["images"]:
                a["images"] = [new if i == old else i for i in a["images"]]; ch = True
        if ch:
            _save(d)
