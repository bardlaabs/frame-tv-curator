#!/usr/bin/env python3
"""Create a demo media share with generated sample art, for screenshots.

Usage: python3 tools/make_demo_data.py [DEMO_DIR]     (default /tmp/frame_demo)
Writes DEMO_DIR/media/frame/{Art,Photos}/*.jpg + sidecars. Nothing here is real artwork.
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

DEMO = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frame_demo"


def scene(seed, sky_t, sky_b, hills, sun, w=2400, h=1350, water=None):
    r = np.random.default_rng(seed)
    y = np.linspace(0, 1, h)[:, None, None]
    a, b = np.array(sky_t), np.array(sky_b)
    im = Image.fromarray(((a + (b - a) * y) * np.ones((h, w, 1))).astype(np.uint8))
    d = ImageDraw.Draw(im)
    if sun:
        x = int(w * r.uniform(.2, .8))
        d.ellipse((x, int(h * .2), x + 170, int(h * .2) + 170), fill=sun)
    im = im.filter(ImageFilter.GaussianBlur(2))
    d = ImageDraw.Draw(im)
    for i, c in enumerate(hills):
        base = h * (.5 + i * .1)
        xs = np.arange(0, w + 30, 30)
        ys = base + np.sin(xs / (250 + r.integers(0, 200)) + i * 1.3) * 70 + np.sin(xs / 90 + i) * 22
        d.polygon([(0, h)] + list(zip(xs, ys)) + [(w, h)], fill=c)
    if water:
        d.rectangle((0, int(h * .86), w, h), fill=water)
    return im.filter(ImageFilter.GaussianBlur(1))


S = [("Evening Over the Lake", "Sample Artist", "2026", "Oil on canvas", (38, 70, 120), (245, 190, 120), [(98, 92, 140), (70, 80, 120), (46, 62, 92)], (255, 236, 190), (22, 38, 64), "Art"),
     ("Morning Ridge", "Sample Artist", "2025", "Watercolor", (120, 160, 200), (250, 225, 190), [(120, 150, 130), (80, 120, 100), (50, 90, 80)], (255, 250, 220), None, "Art"),
     ("Red Mesa", "Another Painter", "2024", "Acrylic", (210, 120, 70), (250, 200, 120), [(170, 70, 50), (130, 50, 40), (90, 35, 35)], (255, 230, 170), None, "Art"),
     ("Winter Pines", "Sample Artist", "2023", "Oil on panel", (70, 90, 120), (200, 215, 230), [(60, 80, 90), (35, 55, 65), (20, 35, 45)], None, None, "Art"),
     ("Harbor Dusk", "Another Painter", "2022", "Oil on canvas", (60, 50, 100), (240, 150, 110), [(70, 60, 100), (45, 45, 80)], (250, 200, 160), (30, 35, 70), "Art"),
     ("Green Valley", "Third Example", "2021", "Gouache", (130, 190, 220), (240, 240, 200), [(150, 190, 120), (100, 160, 100), (60, 120, 80)], (255, 245, 200), None, "Art"),
     ("Night Hills", "Third Example", "2020", "Ink and wash", (10, 15, 40), (50, 50, 100), [(25, 30, 60), (15, 20, 45)], (235, 235, 255), (10, 15, 35), "Art"),
     ("Golden Field", "Another Painter", "2019", "Oil on canvas", (150, 190, 230), (255, 225, 140), [(220, 180, 80), (190, 150, 60), (150, 115, 45)], (255, 255, 220), None, "Art"),
     ("Backyard Sunrise", None, "2025-06-14", "", (90, 120, 190), (255, 190, 150), [(60, 80, 70), (35, 55, 50)], (255, 240, 200), None, "Photos"),
     ("Beach Walk", None, "2025-08-02", "", (100, 170, 220), (230, 240, 240), [(200, 190, 160)], None, (70, 130, 170), "Photos"),
     ("Mountain Trail", None, "2024-09-21", "", (110, 150, 200), (220, 230, 240), [(110, 120, 120), (70, 85, 90), (40, 55, 60)], (255, 255, 240), None, "Photos"),
     ("Desert Road", None, "2024-04-10", "", (120, 170, 220), (250, 220, 170), [(200, 150, 100), (170, 115, 80)], None, None, "Photos")]

for i, (t, a, dt, m, st, sb, hl, sun, wa, folder) in enumerate(S):
    d = os.path.join(DEMO, "media", "frame", folder)
    os.makedirs(d, exist_ok=True)
    fn = os.path.join(d, t.replace(" ", "_") + ".jpg")
    scene(i + 3, st, sb, hl, sun, water=wa).save(fn, quality=90)
    sc = {"title": t, "date": {"display": dt}, "kind": "photo" if folder == "Photos" else "art", "tags": [], "flags": {}}
    if a:
        sc["artist"] = {"name": a}
    if m:
        sc["card_text"] = {"medium": m}
    if folder == "Photos":
        sc["location"] = {"name": "San Diego, California"}
    if i in (0, 2):
        sc["flags"] = {"favorite": True}
    json.dump(sc, open(fn[:-4] + ".json", "w"))
os.makedirs(os.path.join(DEMO, "data"), exist_ok=True)
print("demo data in", DEMO)
