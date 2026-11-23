#!/usr/bin/env python3
"""Take the wiki's UI screenshots (docs/images/ui-*.png) from a demo copy of the add-on.

It builds sample data (make_demo_data.py), starts the add-on in dry-run mode on a
local port, and drives it with Playwright + Chrome. Close-ups are element
screenshots of single cards, so the part being described fills the picture.

Run from the repository root:  python3 tools/make_screenshots.py
Needs: pip install playwright (and Google Chrome; set CHROME=/path if it is elsewhere).
"""
import os, sys, subprocess, time, urllib.request, shutil
from playwright.sync_api import sync_playwright

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "docs", "images")
DEMO = "/tmp/frame_demo"
PORT = int(os.environ.get("PORT", "8199"))
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")
BASE = "http://localhost:%d/" % PORT
VERSION_LABEL = os.environ.get("VERSION_LABEL")   # text for the footer, e.g. "v0.20.5"

shutil.rmtree(DEMO, ignore_errors=True)
subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "make_demo_data.py"), DEMO])
env = dict(os.environ, FC_MEDIA=DEMO + "/media", FC_DATA=DEMO + "/data", FC_PORT=str(PORT), FC_DRY_RUN="1", FC_NO_MQTT="1")
srv = subprocess.Popen([sys.executable, "-m", "curator"], cwd=os.path.join(REPO, "frame_tv_curator"), env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(40):
        try:
            urllib.request.urlopen(BASE + "api/health", timeout=2); break
        except Exception:
            time.sleep(0.5)

    # sample Discover results use the demo pictures (no museum images are used)
    names = [("Evening Over the Lake", "Sample Artist", "Art"), ("Morning Ridge", "Sample Artist", "Art"), ("Red Mesa", "Another Painter", "Art"),
             ("Winter Pines", "Sample Artist", "Art"), ("Harbor Dusk", "Another Painter", "Art"), ("Green Valley", "Third Example", "Art"),
             ("Night Hills", "Third Example", "Art"), ("Golden Field", "Another Painter", "Art")]
    items = []
    for i, (t, a, f) in enumerate(names * 3):
        u = BASE + "api/thumb?id=%s/%s.jpg" % (f, t.replace(" ", "_"))
        items.append({"key": "k%d" % i, "source": "reframed", "title": t, "artist": a, "date": "2021", "thumb": u, "preview": u,
                      "image": u, "w": 3840, "h": 2160, "license": "Public domain", "client_fetch": False})

    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)   # 2x so close-ups stay sharp
        pg.route("**/api/discover/search*", lambda r: r.fulfill(json={"total": 2879, "page": 0, "per": 24, "items": items}))
        pg.route("**/api/discover/artists*", lambda r: r.fulfill(json={"artists": [{"key": "a", "name": "Another Painter"}, {"key": "s", "name": "Sample Artist"}]}))
        pg.goto(BASE); pg.wait_for_timeout(2500)

        def label():
            if VERSION_LABEL:
                pg.evaluate("t=>{const f=document.querySelector('#foot');if(f)f.textContent='Frame TV Curator '+t+' · github.com/bardlaabs/frame-tv-curator'}", VERSION_LABEL)

        def tab(t, wait=1200):
            pg.click('nav button[data-t="%s"]' % t); pg.wait_for_timeout(wait)

        def page(name, full=False):
            label(); pg.screenshot(path=os.path.join(OUT, name + ".png"), full_page=full); print(name)

        def card(name, scope, text, kind=".card"):
            """Screenshot one card/fieldset that contains `text` (a close-up)."""
            label()
            pg.locator("%s %s" % (scope, kind)).filter(has_text=text).first.screenshot(path=os.path.join(OUT, name + ".png")); print(name)

        # --- whole tabs
        tab("lib"); page("ui-library")
        tab("disc", 2500)
        pg.locator("#t-disc .tile").nth(1).click(); pg.locator("#t-disc .tile").nth(3).click(); pg.wait_for_timeout(400)
        page("ui-discover")
        tab("disp"); page("ui-display", True)
        tab("tv"); page("ui-tv", True)
        tab("set"); page("ui-settings", True)
        # top of the Settings tab down to the end of the Image source card (the part the Rotation page needs)
        bb = pg.locator("#t-set .card").filter(has_text="Image source").first.bounding_box()
        label(); pg.screenshot(path=os.path.join(OUT, "ui-settings-top.png"), full_page=True,
                               clip={"x": 0, "y": 0, "width": 1440, "height": bb["y"] + bb["height"] + 14}); print("ui-settings-top")

        # --- Display tab close-ups
        tab("disp")
        for nm, txt in [("placard", "Show placard"), ("mat", "Use a mat"), ("liner", "Inner liner"), ("bevel", "Bevel")]:
            card("ui-display-" + nm, "#t-disp", txt, "fieldset")

        # --- TV tab close-ups
        tab("tv")
        card("ui-tv-connection", "#t-tv", "Connection & remote control")
        card("ui-tv-cache", "#t-tv", "TV picture cache")
        card("ui-tv-presence", "#t-tv", "Turn the Frame on and off with presence")
        pg.get_by_text("Lux sensor", exact=True).first.click(); pg.wait_for_timeout(400)
        card("ui-tv-brightness", "#t-tv", "Art brightness")
        pg.get_by_text("Follow Adaptive Lighting (or another entity)", exact=True).last.click(); pg.wait_for_timeout(400)
        card("ui-tv-color", "#t-tv", "Art color temperature")
        card("ui-tv-light", "#t-tv", "Light that follows the TV")
        card("ui-tv-overscan", "#t-tv", "Overscan / TV edge")
        card("ui-tv-status", "#t-tv", "What it is doing now")

        # --- Settings tab close-ups
        tab("set")
        pg.get_by_text("Weighted mix of folders", exact=True).first.click(); pg.wait_for_timeout(300)
        card("ui-set-source", "#t-set", "Image source")
        card("ui-set-bird", "#t-set", "Bird Frame interleave")
        card("ui-set-epaper", "#t-set", "E-paper card")

        # --- Schedules
        tab("sched")
        pg.get_by_role("button", name="+ Add schedule").click(); pg.wait_for_timeout(900)
        label(); pg.locator("#mbox").screenshot(path=os.path.join(OUT, "ui-schedule-editor.png")); print("ui-schedule-editor")
        pg.reload(); pg.wait_for_timeout(2000)

        # --- Library: tile with flags, selection bar, editor, lightbox
        tab("lib")
        tile = pg.locator(".tile").nth(2)
        tile.hover(); pg.wait_for_timeout(300)
        tile.screenshot(path=os.path.join(OUT, "ui-library-tile.png")); print("ui-library-tile")
        pg.get_by_role("button", name="Select").first.click(); pg.wait_for_timeout(300)
        pg.locator(".tile").nth(0).click(); pg.locator(".tile").nth(2).click(); pg.wait_for_timeout(400)
        label(); pg.screenshot(path=os.path.join(OUT, "ui-library-select.png"), clip={"x": 340, "y": 700, "width": 760, "height": 200}); print("ui-library-select")
        pg.reload(); pg.wait_for_timeout(2000); tab("lib")
        pg.locator(".tile").nth(0).hover(); pg.locator(".tile").nth(0).locator("button[title^='Open large']").click(); pg.wait_for_timeout(1200)
        page("ui-lightbox"); pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        pg.locator(".tile").nth(0).click(); pg.wait_for_timeout(1800)
        label(); pg.screenshot(path=os.path.join(OUT, "ui-editor-info.png")); print("ui-editor-info")
        for t, nm in [("Display", "ui-editor-display"), ("Crop", "ui-editor-crop")]:
            pg.get_by_text(t, exact=True).last.click(); pg.wait_for_timeout(1500)
            label(); pg.screenshot(path=os.path.join(OUT, nm + ".png")); print(nm)

        # --- Now Playing with a framed picture on the "TV" (done last: it changes the demo settings, which are put back afterwards)
        import json as _json
        def post(path, body):
            rq = urllib.request.Request(BASE + "api/" + path, _json.dumps(body).encode(), {"Content-Type": "application/json"})
            return _json.load(urllib.request.urlopen(rq, timeout=60))
        orig = _json.load(urllib.request.urlopen(BASE + "api/settings"))["display"]
        post("settings", {"display": {"mat": {"enabled": True, "color": "#e9e4d8", "width_pct": 8, "auto_tint": "warm_white",
                                              "liner": {"enabled": True, "color": "#8a2f2f", "width_pct": 0.7}},
                                      "placard": {"enabled": True, "placement": "mat", "template": "classical_editorial"}}})
        post("show", {"id": "Art/Evening_Over_the_Lake.jpg"})
        pg.goto(BASE); pg.wait_for_timeout(2500)
        tab("now", 2500); page("ui-now-playing", True)
        post("settings", {"display": orig})
        b.close()
finally:
    srv.terminate()
