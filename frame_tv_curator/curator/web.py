"""JSON API + single-page UI. Served on port 8099 (HA ingress)."""
import os, io, json, logging, mimetypes, hashlib, tempfile, urllib.parse, urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from PIL import Image
from . import ha, library, render, store, config, discover
log = logging.getLogger("web")
STATIC = os.path.join(os.path.dirname(__file__), "static")
THUMBS = os.path.join(config.ROOT, "_thumbs")

def thumb(img_id, w=480):
    p = library.abspath(img_id)
    key = hashlib.sha1(f"{p}{os.path.getmtime(p)}{w}".encode()).hexdigest()[:16]
    os.makedirs(THUMBS, exist_ok=True)
    dest = os.path.join(THUMBS, key + ".jpg")
    if not os.path.exists(dest):
        im = Image.open(p); im.draft("RGB", (w * 2, w * 2)); im = im.convert("RGB")
        im.thumbnail((w, w * 9 // 16 * 2)); im.save(dest, "JPEG", quality=80)
    return dest

def preview(engine, img_id, display, w=1280, edit=False):
    sc = dict(library.load_sidecar(img_id))
    if edit is not False:
        sc["edit"] = edit
    if display is not None:
        sc["display"] = display
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False); tmp.close()
    try:
        render.render(library.abspath(img_id), sc, settings=engine.settings.get()["display"], out_path=tmp.name)
        im = Image.open(tmp.name); im.thumbnail((w, w * 9 // 16)) if w < 3840 else None; buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85); return buf.getvalue()
    finally:
        os.unlink(tmp.name)

def _year(sc):
    import re
    d = sc.get("date") or {}
    for v in (d.get("start"), d.get("display"), (sc.get("card_text") or {}).get("date")):
        m = re.search(r"\d{4}", str(v or ""))
        if m:
            return int(m.group())
    return None

def library_list(folder, ids=None):
    out = []
    for i in (ids if ids is not None else library.images(folder)):
        sc = library.load_sidecar(i)
        a = sc.get("artist") or {}
        stem = os.path.splitext(os.path.basename(i))[0]
        title = (sc.get("card_text") or {}).get("title") or sc.get("placard_title") or sc.get("title") or ""
        try:
            added = os.path.getmtime(library.abspath(i))
        except OSError:
            added = 0
        out.append({"id": i, "file": stem, "title": title, "name": title or stem,
                    "artist": a.get("display") or a.get("name") or "", "medium": (sc.get("medium") or (sc.get("card_text") or {}).get("medium") or "").strip() if isinstance(sc.get("medium") or "", str) else "", "year": _year(sc), "added": added,
                    "flags": sc.get("flags") or {}, "has_display": bool(sc.get("display")), "low_res": library.is_low_res(i)})
    library.save_image_cache()
    return out

def chunk_upload(q, data):
    """Large files arrive in pieces (HA's ingress rejects request bodies over ~16 MB). Pieces are sent in order."""
    import re, shutil
    uid = re.sub(r"[^\w\-]", "", q["uid"])[:40]
    idx, total = int(q["index"]), int(q["total"])
    d = os.path.join(config.DATA, "uploads", uid)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{idx:06d}"), "wb").write(data)
    have = len([f for f in os.listdir(d) if f.isdigit()])
    if have < total:
        return {"partial": True, "have": have}
    blob = b"".join(open(os.path.join(d, f"{i:06d}"), "rb").read() for i in range(total))
    shutil.rmtree(d, ignore_errors=True)
    log.info("upload %s -> %s (%d bytes, %d chunks)", q.get("name"), q.get("folder"), len(blob), total)
    img_id = library.save_upload(q["folder"], q["name"], blob)
    return {"id": img_id, "low_res": library.low_res(img_id), "duplicate_of": library.duplicate_of(img_id)}

def make(engine):
    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        def log_message(self, *a): pass
        def _send(self, code, body, ctype="application/json", cache=False):
            if not isinstance(body, (bytes, bytearray)):
                body = json.dumps(body).encode()
            self.send_response(code); self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if cache: self.send_header("Cache-Control", "max-age=3600")
            self.end_headers(); self.wfile.write(body)
        def _raw(self):
            n = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(n) if n else b""
        def _body(self):
            r = self._raw()
            return json.loads(r) if r else {}
        def do_GET(self):
            u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            p = u.path.rstrip("/") or "/"
            try:
                if p == "/api/status": return self._send(200, engine.status())
                if p == "/api/ambient": return self._send(200, dict(engine.ambient.status(), presence=engine.presence.status()))
                if p == "/api/tv_cache": return self._send(200, engine.tv_cache_status())
                if p == "/api/tv_probe": return self._send(200, engine.ambient.probe(force=True))
                if p == "/api/ha_state":
                    ent = q.get("entity", "")
                    return self._send(200, ha.get_state(ent, quiet=True) or {})
                if p == "/api/ha_entities":
                    doms = [d for d in q.get("domains", "").split(",") if d]
                    out = []
                    for st in ha.states():
                        eid = st.get("entity_id", "")
                        if doms and eid.split(".")[0] not in doms:
                            continue
                        at = st.get("attributes") or {}
                        out.append({"id": eid, "name": at.get("friendly_name") or eid, "state": st.get("state"),
                                    "unit": at.get("unit_of_measurement"), "dc": at.get("device_class")})
                    out.sort(key=lambda x: x["id"])
                    return self._send(200, out)
                if p == "/api/settings": return self._send(200, engine.settings.get())
                if p == "/api/folders": return self._send(200, library.folders())
                if p == "/api/library":
                    if q.get("album"):
                        from . import albums
                        return self._send(200, library_list(None, albums.images(q["album"])))
                    return self._send(200, library_list(q["folder"]))
                if p == "/api/albums":
                    from . import albums
                    return self._send(200, albums.listing())
                if p == "/api/sidecar":
                    w, h = Image.open(library.abspath(q["id"])).size
                    return self._send(200, {"sidecar": library.load_sidecar(q["id"]), "low_res": w < 1920 or h < 1080,
                                            "size": [w, h], "info": library.display_info(q["id"])})
                if p == "/api/geocode":
                    try:
                        return self._send(200, {"name": library.geocode(float(q["lat"]), float(q["lon"]))})
                    except Exception as e:
                        return self._send(502, {"error": "place lookup failed: %s" % e})
                if p == "/api/edit_base":         # the picture after rotate + straighten (no crop), for the crop editor
                    ed = {"rotate": int(q.get("rotate") or 0), "straighten": float(q.get("straighten") or 0)}
                    im = render.apply_edit(Image.open(library.abspath(q["id"])), ed)
                    im.thumbnail((int(q.get("w") or 1400),) * 2); buf = io.BytesIO(); im.save(buf, "JPEG", quality=88)
                    return self._send(200, buf.getvalue(), "image/jpeg")
                if p == "/api/pattern":           # what is on the TV when it is not a library image
                    kind = q.get("kind")
                    if kind == "colorbars": im = render.render_colorbars()
                    elif kind == "calibration": im = render.render_calibration()
                    elif kind == "birdframe":
                        bf = engine.settings.get()["birdframe"]
                        raw = urllib.request.urlopen("http://%s:%s/preview.jpg" % (bf.get("host") or "local-birdframe-local", bf.get("port") or 8099), timeout=10).read()
                        return self._send(200, raw, "image/jpeg")
                    else: return self._send(404, {"error": "unknown pattern"})
                    im.thumbnail((1280, 720)); buf = io.BytesIO(); im.save(buf, "JPEG", quality=85)
                    return self._send(200, buf.getvalue(), "image/jpeg")
                if p == "/api/discover/artists":
                    return self._send(200, discover.SOURCES[q.get("source", "reframed")].artists())
                if p == "/api/discover/search":
                    from concurrent.futures import ThreadPoolExecutor
                    src = discover.SOURCES[q.get("source", "reframed")]
                    r = src.search(q.get("q", ""), q.get("artist", ""), q.get("sort", "az"), int(q.get("page") or 0), int(q.get("per") or 24), type=urllib.parse.parse_qs(u.query, keep_blank_values=True).get("type", ["Painting"])[0])
                    if "items" in r:
                        return self._send(200, r)
                    def one(k):
                        try:
                            return src.detail(k)
                        except Exception as e:
                            return {"key": k, "source": src.id, "error": str(e)}
                    with ThreadPoolExecutor(4) as ex:
                        items = list(ex.map(one, r["keys"]))
                    return self._send(200, {"total": r["total"], "page": r["page"], "per": r["per"], "items": items})
                if p == "/api/discover/sources":
                    return self._send(200, [{"id": s.id, "name": s.name, "blurb": s.blurb, "sorts": s.sorts, "types": s.types,
                                             "has_artists": s.has_artists, "client_fetch": s.client_fetch, "license": s.license}
                                            for s in discover.SOURCES.values()])
                if p == "/api/discover/job":
                    return self._send(200, discover.JOBS.get(q.get("id")) or {"error": "unknown job"})
                if p == "/api/duplicates": return self._send(200, library.find_duplicates())
                if p == "/api/backups": return self._send(200, library.list_backups())
                if p == "/api/templates":
                    return self._send(200, {k: v["label"] for k, v in render.TEMPLATES.items()})
                if p == "/api/palette":
                    return self._send(200, render.image_palette(render.apply_edit(Image.open(library.abspath(q["id"])), library.load_sidecar(q["id"]).get("edit"))))
                if p == "/api/suggest_mats":
                    return self._send(200, render.suggest_mats(render.apply_edit(Image.open(library.abspath(q["id"])), library.load_sidecar(q["id"]).get("edit"))))
                if p == "/api/thumb":
                    return self._send(200, open(thumb(q["id"]), "rb").read(), "image/jpeg", cache=True)
                if p == "/api/render":
                    return self._send(200, open(engine.render_image(q["id"]), "rb").read(), "image/jpeg")
                if p == "/api/original":
                    return self._send(200, open(library.abspath(q["id"]), "rb").read(),
                                      mimetypes.guess_type(q["id"])[0] or "image/jpeg")
                if p == "/":
                    return self._send(200, open(os.path.join(STATIC, "index.html"), "rb").read(), "text/html")
                self._send(404, {"error": "not found"})
            except Exception as e:
                log.exception("GET %s", p); self._send(500, {"error": str(e)})
        def do_POST(self):
            u = urllib.parse.urlparse(self.path); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
            p = u.path.rstrip("/")
            try:
                if p == "/api/clientlog":
                    b = self._body(); log.warning("client: %s | %s", b.get("msg"), (b.get("ua") or "")[:120])
                    return self._send(200, {"ok": True})
                if p == "/api/upload_chunk":
                    raw = self._raw()
                    ct = self.headers.get("Content-Type") or ""
                    log.info("chunk %s/%s of %s (%d bytes, %s)", q.get("index"), q.get("total"), q.get("name"), len(raw), ct)
                    if "json" in ct:
                        import base64
                        raw = base64.b64decode(json.loads(raw)["data"])
                    return self._send(200, chunk_upload(q, raw))
                if p == "/api/upload":
                    data = self._raw()
                    log.info("upload %s -> %s (%d bytes)", q.get("name"), q.get("folder"), len(data))
                    img_id = library.save_upload(q["folder"], q["name"], data)
                    return self._send(200, {"id": img_id, "low_res": library.low_res(img_id)})
                b = self._body()
                if p == "/api/next": return self._send(200, engine.next())
                if p == "/api/previous": return self._send(200, engine.previous())
                if p == "/api/show": return self._send(200, engine.show(b["id"], force_push=b.get("force", False)))
                if p == "/api/settings":
                    r = engine.settings.update(b); engine.tv.cfg = r.get("tv", engine.tv.cfg); config.apply_log_level(r.get("log_level")); engine.invalidate_next(); engine._notify(); return self._send(200, r)
                if p == "/api/discover/check":
                    src = discover.SOURCES[b.get("source", "reframed")]
                    return self._send(200, discover.check(src.detail(b["key"])))
                if p == "/api/discover/finish":
                    return self._send(200, discover.finish(b["source"], b["key"], b["id"], b.get("replace") or []))
                if p == "/api/discover/add":
                    return self._send(200, discover.add(b["items"], b["folder"]))
                if p == "/api/folder": return self._send(200, {"folder": library.create_folder(b["name"])})
                if p == "/api/sidecar": return self._send(200, library.patch_sidecar(b["id"], b["patch"]))
                if p == "/api/display":           # replace the per-image display block entirely ({} = use globals)
                    sc = library.load_sidecar(b["id"])
                    if b.get("display"): sc["display"] = b["display"]
                    else: sc.pop("display", None)
                    library.save_sidecar(b["id"], sc); return self._send(200, sc)
                if p == "/api/flags":
                    sc = library.load_sidecar(b["id"]); sc["flags"] = b["flags"]
                    library.save_sidecar(b["id"], sc); return self._send(200, sc)
                if p == "/api/preview":
                    return self._send(200, preview(engine, b["id"], b.get("display"), int(b.get("w") or 1280), b["edit"] if "edit" in b else False), "image/jpeg")
                if p == "/api/edit":              # non-destructive crop/rotate/straighten; null or empty clears it
                    sc = library.load_sidecar(b["id"]); e = b.get("edit")
                    if e and (e.get("crop") or e.get("rotate") or abs(float(e.get("straighten") or 0)) > 0.01): sc["edit"] = e
                    else: sc.pop("edit", None)
                    library.save_sidecar(b["id"], sc); return self._send(200, sc.get("edit") or {})
                if p == "/api/album":       # {action: create|rename|delete|add|remove, id, name, ids}
                    from . import albums
                    a = b.get("action")
                    if a == "create": aid = albums.create(b.get("name"))
                    else: aid = b.get("id")
                    if a == "rename": albums.rename(aid, b.get("name"))
                    elif a == "delete": albums.delete(aid)
                    elif a == "add": albums.add(aid, b.get("ids") or [])
                    elif a == "remove": albums.remove(aid, b.get("ids") or [])
                    engine.invalidate_next()
                    return self._send(200, {"id": aid, "albums": albums.listing()})
                if p == "/api/bulk":              # {ids, flags:{favorite..}, card_text:{artist..}, move_to, delete}
                    done = 0; ids = list(b.get("ids") or [])
                    for i in ids:
                        try:
                            if b.get("delete"):
                                library.delete_image(i); engine.forget(i)
                            else:
                                sc = library.load_sidecar(i)
                                if b.get("flags"):
                                    sc["flags"] = dict(sc.get("flags") or {}, **b["flags"])
                                if b.get("card_text"):
                                    ct = dict(sc.get("card_text") or {})
                                    ct.update({k: v for k, v in b["card_text"].items() if v not in (None, "")})
                                    sc["card_text"] = ct
                                    if ct.get("artist"):
                                        sc["artist"] = dict(sc.get("artist") or {}, name=ct["artist"], display=ct["artist"])
                                library.save_sidecar(i, sc)
                                if b.get("move_to"):
                                    dst_folder = library.create_folder(b["move_to"]); src = library.abspath(i)
                                    fn = os.path.basename(src); dst = os.path.join(library.abspath(dst_folder), fn)
                                    os.replace(src, dst)
                                    try:
                                        from . import albums
                                        albums.remap(i, dst_folder + "/" + fn)
                                    except Exception: pass
                                    sp = os.path.splitext(src)[0] + ".json"
                                    if os.path.exists(sp): os.replace(sp, os.path.splitext(dst)[0] + ".json")
                            done += 1
                        except Exception as e:
                            log.warning("bulk %s: %s", i, e)
                    engine.invalidate_next()
                    return self._send(200, {"done": done, "of": len(ids)})
                if p == "/api/tv":
                    ok, msg = engine.tv.control(b.get("action"))
                    return self._send(200, {"ok": ok, "message": msg})
                if p == "/api/tv_cache_clear":
                    return self._send(200, engine.tv_cache_clear())
                if p == "/api/tv_apply":
                    ok, msg = engine.tv.apply_art(brightness=b.get("brightness"), color_temp=b.get("color_temp"), sensor_off=b.get("sensor_off"))
                    engine.ambient.poke() if b.get("repoke") else None
                    return self._send(200, {"ok": ok, "message": msg})
                if p == "/api/ha_select":
                    ent, opt = b.get("entity"), b.get("option")
                    if not ent or not ent.startswith("select.") or opt is None: return self._send(400, {"ok": False, "message": "entity and option required"})
                    ha.call("select", "select_option", {"entity_id": ent, "option": str(opt)})
                    return self._send(200, {"ok": True, "message": "set to %s" % opt})
                if p == "/api/ambient_now": engine.ambient.poke(); return self._send(200, {"ok": True})
                if p == "/api/light_test":
                    ent = (engine.settings.get().get("ambient", {}).get("light") or {}).get("entity")
                    if not ent: return self._send(200, {"ok": False, "message": "No light chosen"})
                    ha.call(ent.split(".")[0], "turn_on" if b.get("on") else "turn_off", {"entity_id": ent})
                    return self._send(200, {"ok": True, "message": "sent"})
                if p == "/api/bird_now": return self._send(200, engine.show_bird())
                if p == "/api/backup_now": return self._send(200, library.backup_all())
                if p == "/api/colorbars": return self._send(200, engine.colorbars())
                if p == "/api/calibrate": return self._send(200, engine.calibrate())
                if p == "/api/resend": return self._send(200, engine.resend())
                if p == "/api/location":          # replace the GPS block; blank lat/lon removes it
                    sc = library.load_sidecar(b["id"])
                    try:
                        lat, lon = float(b["lat"]), float(b["lon"])
                        assert -90 <= lat <= 90 and -180 <= lon <= 180
                        sc["location"] = {"lat": lat, "lon": lon, "name": b.get("name") or None, "tries": 1 if b.get("name") else 0}
                    except (TypeError, ValueError, KeyError, AssertionError):
                        if b.get("lat") not in (None, "") or b.get("lon") not in (None, ""):
                            return self._send(400, {"error": "latitude/longitude not valid"})
                        sc.pop("location", None)
                    library.save_sidecar(b["id"], sc); return self._send(200, sc.get("location") or {})
                if p == "/api/delete":
                    library.delete_image(b["id"]); engine.forget(b["id"])
                    return self._send(200, {"deleted": b["id"]})
                if p == "/api/move":
                    src = library.abspath(b["id"]); dst_folder = library.create_folder(b["folder"])
                    fn = os.path.basename(src); dst = os.path.join(library.abspath(dst_folder), fn)
                    os.replace(src, dst)
                    sp = os.path.splitext(src)[0] + ".json"
                    if os.path.exists(sp): os.replace(sp, os.path.splitext(dst)[0] + ".json")
                    return self._send(200, {"id": f"{dst_folder}/{fn}"})
                self._send(404, {"error": "not found"})
            except Exception as e:
                log.exception("POST %s", p); self._send(500, {"error": str(e)})
    return H

def serve(engine, port=8099):
    srv = ThreadingHTTPServer(("0.0.0.0", port), make(engine))
    import threading
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
