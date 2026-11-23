#!/usr/bin/env python3
"""Generate the sample renders used by the wiki (docs/images/*.jpg).

Uses the add-on's own renderer on a generated sample painting (so no third-party
artwork is involved). Close-ups are cropped from the full 3840x2160 render so
the detail being described is large and clear.

Run from the repository root:  python3 tools/make_sample_renders.py
Needs: Pillow, numpy.
"""
import os, sys, copy
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "frame_tv_curator"))
from curator import render as R          # noqa: E402

OUT = os.path.join(REPO, "docs", "images")
TMP = "/tmp/wiki_samples"
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)


def sample(path, w, h):
    """A generated landscape: sky gradient, sun, layered hills, lake."""
    y = np.linspace(0, 1, h)[:, None, None]
    top, bot = np.array([38, 70, 120]), np.array([245, 190, 120])
    im = Image.fromarray(((top + (bot - top) * (y ** 0.9)) * np.ones((h, w, 1))).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse((int(w * .66), int(h * .24), int(w * .66) + int(h * .17), int(h * .24) + int(h * .17)), fill=(255, 236, 190))
    im = im.filter(ImageFilter.GaussianBlur(3))
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(4)
    for i, c in enumerate([(98, 92, 140), (70, 80, 120), (46, 62, 92), (28, 44, 70)]):
        base = h * (.48 + i * .083)
        xs = np.arange(0, w + 40, 40)
        ys = base + np.sin(xs / 380 + i * 1.7) * h * .05 + np.sin(xs / 130 + i) * h * .02 + rng.normal(0, 5, len(xs))
        d.polygon([(0, h)] + list(zip(xs, ys)) + [(w, h)], fill=c)
    d.rectangle((0, int(h * .8), w, h), fill=(22, 38, 64))
    for _ in range(260):
        x = rng.integers(0, w); yy = rng.integers(int(h * .81), h); l = rng.integers(40, 260)
        d.line((x, yy, x + l, yy), fill=(60 + rng.integers(0, 90), 70 + rng.integers(0, 70), 90 + rng.integers(0, 60)), width=3)
    im.filter(ImageFilter.GaussianBlur(1.2)).save(path, quality=93)


SAMPLE_WIDE = os.path.join(TMP, "wide.jpg")      # 16:9
SAMPLE_PHOTO = os.path.join(TMP, "threetwo.jpg")  # 3:2 (not 16:9)
sample(SAMPLE_WIDE, 3200, 1800)
sample(SAMPLE_PHOTO, 3000, 2000)

SC = {"title": "Evening Over the Lake", "artist": {"name": "Sample Artist"},
      "date": {"display": "2026"}, "card_text": {"medium": "Oil on canvas"}}


def go(name, disp, src=SAMPLE_WIDE, crop=None):
    """Render with display overrides `disp`; `crop` = (x0, y0, x1, y1) of the 3840x2160 render
    for a close-up, else the whole picture. Saved as a 1280x720 JPEG."""
    sc = copy.deepcopy(SC)
    sc["display"] = disp
    full = R.render(src, sc, settings=None, out_path=os.path.join(TMP, "full_%s.jpg" % name), force=True)
    im = Image.open(full)
    if crop:
        im = im.crop(crop)
    im.resize((1280, round(1280 * im.height / im.width)), Image.LANCZOS).save(os.path.join(OUT, name + ".jpg"), quality=86, optimize=True)
    print(name)


P = lambda **k: {"placard": dict(enabled=True, **k)}
M = lambda **k: {"mat": dict(enabled=True, color="#efece4", width_pct=8, **k)}

# crop boxes on the 3840x2160 render
BR = (2240, 1260, 3840, 2160)    # bottom-right, 1600x900 (2.4x zoom vs the full picture)
BL = (0, 1260, 1600, 2160)
TR = (2240, 0, 3840, 900)
TL = (0, 0, 1600, 900)           # top-left corner: mat, liner, bevel and the picture edge
TLZ = (0, 0, 800, 450)           # tighter corner (4.8x) for textures, liner and bevel

# --- whole-picture views
go("default-look", {})
go("no-placard", {"placard": {"enabled": False}})
for tint in ("warm_white", "deep_neutral", "accent", "complement", "dominant"):
    go("tint-" + tint, {"mat": {"enabled": True, "width_pct": 8, "auto_tint": tint}})
go("overscan-inset", {"overscan": {"top": 3, "right": 3, "bottom": 3, "left": 3, "mode": "inset"}})
go("mat-even", M(shape="even"), SAMPLE_PHOTO)
go("mat-proportional", M(shape="proportional"), SAMPLE_PHOTO)

# --- placards: close-ups
for t in ("modern_minimal", "classical_editorial", "gallery_zine"):
    go("placard-" + t, P(template=t), crop=BR)
go("placard-pos-bottom-left", P(position="bottom-left"), crop=BL)
go("placard-pos-top-right", P(position="top-right"), crop=TR)
go("placard-large", P(scale=1.6), crop=(2000, 1160, 3840, 2160))
go("placard-on-mat", {"mat": {"enabled": True, "color": "#efece4", "width_pct": 10},
                      "placard": {"enabled": True, "placement": "mat", "template": "classical_editorial"}},
   crop=(2240, 1560, 3840, 2160))
go("placard-on-mat-autofit", {"mat": {"enabled": True, "color": "#efece4", "width_pct": 10},
                              "placard": {"enabled": True, "placement": "mat", "template": "modern_minimal", "mat_fit": True}},
   crop=(2240, 1560, 3840, 2160))


# --- test patterns and overscan examples
def save_img(name, im, size=(1280, 720)):
    im.resize(size, Image.LANCZOS).save(os.path.join(OUT, name + ".jpg"), quality=88, optimize=True)
    print(name)

grid = R.render_calibration()
save_img("calibration-grid", grid)
save_img("colorbars", R.render_colorbars())
# what a TV that hides 3 % on every side would show: the 0, 1 and 2 outlines are gone, 3 is the outermost visible
Wd, Hd = grid.size
save_img("calibration-hidden-3pct", grid.crop((int(Wd * .03), int(Hd * .03), Wd - int(Wd * .03), Hd - int(Hd * .03))))
OV4 = {"top": 4, "right": 4, "bottom": 4, "left": 4}
# a portrait picture (a tall crop of the 3:2 sample) on a blurred background
_ph = Image.open(SAMPLE_PHOTO); _pw = int(_ph.height * 2 / 3)
_ph.crop(((_ph.width - _pw) // 2, 0, (_ph.width + _pw) // 2, _ph.height)).save(os.path.join(TMP, "portrait.jpg"))
go("framing-blur", {"framing": "blur", "placard": {"enabled": False}}, src=os.path.join(TMP, "portrait.jpg"))
# framing mode: a 3:2 photo kept whole (mat fills the sides) vs filled to 16:9
go("framing-whole", {"framing": "whole", "mat": dict(enabled=True, color="#efece4", width_pct=6), "placard": {"enabled": False}}, src=SAMPLE_PHOTO)
go("framing-fill", {"framing": "fill", "mat": dict(enabled=True, color="#efece4", width_pct=6), "placard": {"enabled": False}}, src=SAMPLE_PHOTO)
go("overscan-none-placard", {"placard": {"enabled": True, "position": "bottom-right"}}, crop=BR)
go("overscan-placard-mode", {"overscan": dict(OV4, mode="placard"), "placard": {"enabled": True, "position": "bottom-right"}}, crop=BR)
go("overscan-inset-4pct", {"overscan": dict(OV4, mode="inset")})

# --- hero images for the README and the Features page
go("hero-classical", {"mat": {"enabled": True, "color": "#e9e4d8", "width_pct": 9, "auto_tint": "warm_white",
                              "liner": {"enabled": True, "color": "#8a2f2f", "width_pct": 0.7}},
                      "placard": {"enabled": True, "placement": "mat", "template": "classical_editorial"}})
go("hero-modern", {"mat": {"enabled": True, "width_pct": 7, "auto_tint": "deep_neutral"},
                   "placard": {"enabled": True, "template": "modern_minimal"}})

# before / after, and a grid of looks, for the README
def label(im, text):
    d = ImageDraw.Draw(im); f = R.font("kumbh", 30, 700)
    w = int(d.textlength(text, font=f)) + 28
    d.rounded_rectangle((16, 16, 16 + w, 66), radius=10, fill=(0, 0, 0, 170) if im.mode == "RGBA" else (20, 20, 24))
    d.text((30, 41), text, font=f, fill=(255, 255, 255), anchor="lm")
    return im

orig = Image.open(SAMPLE_WIDE).convert("RGB").resize((1280, 720), Image.LANCZOS)
framed = Image.open(os.path.join(OUT, "hero-classical.jpg")).convert("RGB")
ba = Image.new("RGB", (2570, 720), (255, 255, 255))
ba.paste(label(orig, "Original file (never changed)"), (0, 0)); ba.paste(label(framed, "What the TV shows"), (1290, 0))
ba.resize((1600, 448), Image.LANCZOS).save(os.path.join(OUT, "before-after.jpg"), quality=88, optimize=True); print("before-after")
tiles = [Image.open(os.path.join(OUT, n + ".jpg")).convert("RGB").resize((640, 360), Image.LANCZOS)
         for n in ("hero-classical", "hero-modern", "tint-dominant", "default-look")]
grid = Image.new("RGB", (1290, 730), (255, 255, 255))
for i, t in enumerate(tiles):
    grid.paste(t, ((i % 2) * 650, (i // 2) * 370))
grid.save(os.path.join(OUT, "looks-grid.jpg"), quality=88, optimize=True); print("looks-grid")


# --- e-paper card layouts (522x152, black / white / red only), enlarged 2x without smoothing so the pixels stay crisp
SC_LONG = {"title": "View of the Harbor at Dusk with Fishing Boats Returning", "artist": {"name": "Another Example Painter"},
           "date": {"display": "c. 1880"}, "card_text": {"medium": "Oil on panel"}}
SC_PHOTO = {"kind": "photo", "title": "Sunset at the Pier", "date": {"display": "2025-06-14"}, "location": {"name": "San Diego, California"}}
for style in ("gallery", "inverted", "grid"):
    for tag, sc in (("art", SC), ("long", SC_LONG), ("photo", SC_PHOTO)):
        im = R.render_epaper(sc, style=style)
        im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(os.path.join(OUT, "epaper-%s-%s.png" % (style, tag)))
        print("epaper", style, tag)

# --- mat placards: one, two and three line layouts (bottom strip of the mat, 1600x900 crop)
for lay in ("one_line", "two_line", "three_line"):
    go("placard-mat-" + lay.replace("_", "-"),
       {"mat": {"enabled": True, "color": "#efece4", "width_pct": 10},
        "placard": {"enabled": True, "placement": "mat", "template": "modern_minimal", "mat_layout": lay}},
       crop=(2240, 1560, 3840, 2160))

# --- mats: close-ups of a corner
go("mat-dark", {"mat": {"enabled": True, "color": "#1e2230", "width_pct": 8}}, crop=TL)
go("mat-paper", M(texture="paper"), crop=TLZ)
go("mat-linen", {"mat": {"enabled": True, "color": "#e6dfd0", "width_pct": 8, "texture": "linen"}}, crop=TLZ)
go("mat-liner", M(liner={"enabled": True, "color": "#8a2f2f", "width_pct": 0.8}), crop=TLZ)
go("mat-liner-dark", M(liner={"enabled": True, "color": "#2b2b2b", "width_pct": 1.0}), crop=TLZ)
go("mat-nobevel", M(bevel={"enabled": False}), crop=TLZ)
go("mat-bevel-strong", M(bevel={"enabled": True, "width_pct": 0.9, "intensity": 90, "shadow": 60}), crop=TLZ)
print("done ->", OUT)
