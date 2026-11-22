"""Frame TV Curator - renderer (v1.1).

Turns an art/photo + its sidecar into a finished 3840x2160 JPEG for the Frame:
mat (never applied to the original file), optional placard (overlay box or
printed on the mat), directional bevel lighting, and a hash-keyed cache.
Also suggests mat colors from the image's own colors (numpy only, no AI) and
renders the tri-color (black / white / red) e-paper card.
"""
import os, re, json, math, copy, hashlib, colorsys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps, ImageChops

VERSION = "1.12"
W, H = 3840, 2160
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

# ------------------------------------------------------------------ defaults
DEFAULTS = {
    "fit": "contain",
    "mat": {
        "auto_tint": "",             # "" = use the color below; else pick the mat color from the picture (see TINTS)
        "enabled": False, "color": "#efece4", "width_pct": 6.0, "texture": "flat",
        "shape": "even",             # even = same mat width on all four sides (crops the picture a little); proportional = sides wider, no crop
        "letterbox": "mat",          # mat | bars_inside | bars_outside
        "layers": None,              # optional [{color,width_pct,texture}, ...] outer -> inner
        "liner": {"enabled": False, "color": "#2b2b2b", "width_pct": 0.8, "texture": "flat"},   # thin inner mat around the picture
        "bevel": {"enabled": True, "width_pct": 0.40, "intensity": 60, "light_angle": 0,
                  "elevation": 50, "color": "auto", "shadow": 35},
    },
    "placard": {"enabled": True, "template": "modern_minimal", "placement": "overlay",
                "position": "bottom-right", "scale": 1.0, "margin_pct": 2.2, "mat_layout": "two_line", "mat_fit": False, "overrides": {}},
    "overscan": {"top": 0, "right": 0, "bottom": 0, "left": 0, "mode": "placard"},   # % of the TV edge that is not visible
}

def merge(*dicts):
    out = {}
    for d in dicts:
        for k, v in (d or {}).items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = merge(out[k], v)
            else:
                out[k] = copy.deepcopy(v)
    return out

# ------------------------------------------------------------------ fonts
_FILES = {
    "kumbh": "KumbhSans[YOPQ,wght].ttf", "inter": "Inter[opsz,wght].ttf",
    "inter-italic": "Inter-Italic[opsz,wght].ttf", "literata": "Literata[opsz,wght].ttf",
    "literata-italic": "Literata-Italic[opsz,wght].ttf", "source-sans": "SourceSans3[wght].ttf",
    "space-grotesk": "SpaceGrotesk[wght].ttf", "plex-mono": "IBMPlexMono-Regular.ttf",
    "space-mono": "SpaceMono-Regular.ttf", "space-mono-bold": "SpaceMono-Bold.ttf",
}
_fc = {}

def font(name, size, wght=None):
    key = (name, int(round(size)), wght)
    if key in _fc:
        return _fc[key]
    f = ImageFont.truetype(os.path.join(FONTS, _FILES[name]), max(6, int(round(size))))
    try:
        vals = []
        for a in f.get_variation_axes():
            nm = a["name"].decode() if isinstance(a["name"], bytes) else a["name"]
            if nm == "Weight" and wght is not None:
                vals.append(min(max(wght, a["minimum"]), a["maximum"]))
            elif nm == "Optical size":
                vals.append(min(max(size / 2, a["minimum"]), a["maximum"]))
            else:
                vals.append(a["default"])
        f.set_variation_by_axes(vals)
    except (OSError, AttributeError):
        pass
    _fc[key] = f
    return f

# ------------------------------------------------------------------ colors
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def rgb2hex(c):
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in c)

def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))

def lum(c):
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = [f(v / 255) for v in c]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)

def _kmeans(px, k=5, it=12):
    rng = np.random.default_rng(1)
    cen = px[rng.choice(len(px), k, replace=False)].astype(float)
    for _ in range(it):
        lab = ((px[:, None, :] - cen[None]) ** 2).sum(2).argmin(1)
        for i in range(k):
            m = lab == i
            if m.any():
                cen[i] = px[m].mean(0)
    return cen, np.bincount(lab, minlength=k)

TINTS = {"warm_white": "Warm gallery white", "deep_neutral": "Deep neutral", "accent": "Accent tint",
         "complement": "Complement", "dominant": "Dominant muted"}

def tint_color(img, tint):
    """Mat color for a tint style ('best' = the suggestion with the most contrast against the picture edge)."""
    sug = suggest_mats(img)
    if tint == "best":
        return sug[0]["color"]
    name = TINTS.get(tint)
    return next((x["color"] for x in sug if x["name"] == name), None)

def image_palette(img, n=14):
    """The picture's main colors (k-means), biggest first: [{color, pct}]."""
    im = img.convert("RGB")
    im.thumbnail((128, 128))
    arr = np.asarray(im).reshape(-1, 3)
    n = min(n, max(2, len(arr) // 50))
    cen, cnt = _kmeans(arr, k=n, it=14)
    order = np.argsort(-cnt)
    out, kept = [], []
    for i in order:
        if cnt[i] / cnt.sum() < 0.006 or any(np.linalg.norm(cen[i] - k) < 28 for k in kept):
            continue
        kept.append(cen[i])
        out.append({"color": rgb2hex(cen[i]), "pct": round(float(cnt[i] / cnt.sum() * 100), 1)})
    return out

def suggest_mats(img):
    """Mat colors computed from the image's own palette (k-means + HLS math)."""
    im = img.convert("RGB")
    im.thumbnail((160, 160))
    arr = np.asarray(im)
    cen, cnt = _kmeans(arr.reshape(-1, 3))
    order = np.argsort(-cnt)
    cen, cnt = cen[order], cnt[order]
    hls_of = lambda c: colorsys.rgb_to_hls(*[v / 255 for v in c])
    sat = lambda c: hls_of(c)[2] * (1 - abs(2 * hls_of(c)[1] - 1))
    big = [i for i in range(len(cen)) if cnt[i] >= 0.06 * cnt.sum()] or [0]
    acc = max(big, key=lambda i: sat(cen[i]))
    dh, dl, ds = hls_of(cen[0])
    ah, al, as_ = hls_of(cen[acc])
    avg_l = float(np.dot(cnt, [hls_of(c)[1] for c in cen]) / cnt.sum())
    hls = lambda h, l, s: tuple(v * 255 for v in colorsys.hls_to_rgb(h % 1, l, s))
    edge = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]]).mean(0)
    out = [
        ("Warm gallery white", hls(dh, 0.93, min(0.35, ds * 0.6 + 0.08))),
        ("Deep neutral", hls(dh, 0.11, min(0.25, ds * 0.5))),
        ("Accent tint", hls(ah, 0.80 if avg_l < 0.5 else 0.30, min(0.35, as_ * 0.55 + 0.06))),
        ("Complement", hls(ah + 0.5, 0.84 if avg_l < 0.5 else 0.22, 0.22)),
        ("Dominant muted", hls(dh, 0.72 if avg_l < 0.5 else 0.38, min(0.3, ds * 0.5))),
    ]
    res = [{"name": n, "color": rgb2hex(c), "edge_contrast": round(float(contrast(c, edge)), 2)} for n, c in out]
    res.sort(key=lambda r: -min(r["edge_contrast"], 4))
    return res

# ------------------------------------------------------------------ text fitting (whole words only)
def wrap(draw, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def fit(draw, text, fname, wght, size, maxw, maxlines, minsize=0.55):
    """Wrap on word boundaries only. Shrinks the font until the text fits; never cuts a word,
    and only if even the smallest size does not fit does it drop whole trailing words with an ellipsis."""
    if not text:
        return font(fname, size, wght), []
    s = size
    while True:
        f = font(fname, s, wght)
        lines = wrap(draw, text, f, maxw)
        widest = max(draw.textlength(l, font=f) for l in lines)
        if len(lines) <= maxlines and widest <= maxw + 1:
            return f, lines
        if s <= size * minsize:
            break
        s *= 0.94
    f = font(fname, s, wght)
    lines = wrap(draw, text, f, maxw)
    if len(lines) > maxlines:
        keep = lines[:maxlines]
        last = keep[-1]
        while last and draw.textlength(last + " …", font=f) > maxw and " " in last:
            last = last.rsplit(" ", 1)[0]
        keep[-1] = last + " …"
        lines = keep
    return f, lines

def spaced_len(draw, text, f, tracking):
    return sum(draw.textlength(c, font=f) + f.size * tracking for c in text) - f.size * tracking

def draw_spaced(draw, xy, text, f, fill, tracking, anchor="l"):
    x, y = xy
    total = spaced_len(draw, text, f, tracking)
    if anchor == "r":
        x -= total
    for c in text:
        draw.text((x, y), c, font=f, fill=fill)
        x += draw.textlength(c, font=f) + f.size * tracking
    return total

def card_fields(sc):
    ct = sc.get("card_text") or {}
    artist = ct.get("artist") or ((sc.get("artist") or {}).get("name")) or ""
    if artist.lower() in ("unknown artist", "unknown"):
        artist = ""
    title = sc.get("placard_title") or ct.get("title") or sc.get("title") or ""
    if not sc.get("placard_title"):
        title = re.split(r", from the series|, also known as|, from \d", title)[0]
    date = ct.get("date") or (sc.get("date") or {}).get("display") or ""
    medium = ct.get("medium") or ""
    return artist, title, date, medium, ct.get("credit") or ""

def card_location(sc):
    ct = sc.get("card_text") or {}
    loc = sc.get("location")
    if isinstance(loc, dict):
        loc = loc.get("name")
    return ct.get("location") or loc or ""

UNTITLED = ("", "untitled", "untitled image", "unknown", "unknown title", "no title")

def has_content(sc):
    """False for images with nothing worth printing (e.g. 'Untitled', unknown artist, no date/medium): no placard at all."""
    artist, title, date, medium, credit = card_fields(sc)
    return bool(artist or (title and title.strip().lower() not in UNTITLED) or meta_parts(sc))

def meta_parts(sc):
    """Detail line: art -> date, medium.  Photographs -> date, location (a photo's medium is always 'photograph')."""
    artist, title, date, medium, credit = card_fields(sc)
    if sc.get("kind") == "photo":
        return [p for p in (date, card_location(sc)) if p]
    return [p for p in (date, medium) if p]

# ------------------------------------------------------------------ mat, bevel, lighting
def _texture(size, kind, base, seed=7):
    w, h = size
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), np.float32) + np.array(base, np.float32)
    if kind == "paper":
        arr += rng.normal(0, 2.2, (h, w, 1)).astype(np.float32)
    elif kind == "linen":
        n = rng.normal(0, 1.6, (h, w, 1)).astype(np.float32)
        x = (np.arange(w) % 6 < 3).astype(np.float32)[None, :, None] * 2.5
        y = (np.arange(h) % 6 < 3).astype(np.float32)[:, None, None] * 2.5
        arr += n + x - y * 0.8
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

def _bevel(canvas, box, mat_color, b, opt):
    """Draw a 45-degree bevel just outside `box` (the window opening), lit from opt['light_angle']
    (degrees clockwise from the top of the screen). Light from above lights the bottom bevel."""
    if not opt.get("enabled", True) or b < 2:
        return
    a = math.radians(opt.get("light_angle", 0))
    e = math.radians(opt.get("elevation", 50))
    L = (math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))
    s45 = c45 = math.sqrt(0.5)
    flat = c45 * L[2]
    base = hex2rgb(opt["color"]) if opt.get("color", "auto") != "auto" else mix(mat_color, (255, 255, 255), 0.82)
    k = opt.get("intensity", 60) / 100.0
    x0, y0, x1, y1 = box
    faces = {  # face polygon, in-plane normal toward the window centre
        "top": ([(x0 - b, y0 - b), (x1 + b, y0 - b), (x1, y0), (x0, y0)], (0, 1)),
        "bottom": ([(x0, y1), (x1, y1), (x1 + b, y1 + b), (x0 - b, y1 + b)], (0, -1)),
        "left": ([(x0 - b, y0 - b), (x0, y0), (x0, y1), (x0 - b, y1 + b)], (1, 0)),
        "right": ([(x1, y0), (x1 + b, y0 - b), (x1 + b, y1 + b), (x1, y1)], (-1, 0)),
    }
    d = ImageDraw.Draw(canvas)
    for poly, n in faces.values():
        dot = n[0] * s45 * L[0] + n[1] * s45 * L[1] + c45 * L[2]
        tone = (dot - flat) / 0.9           # <0 shadow side, >0 lit side
        col = mix(base, (255, 255, 255), min(1, tone * k)) if tone >= 0 else mix(base, (0, 0, 0), min(1, -tone * k * 1.15))
        d.polygon(poly, fill=tuple(int(v) for v in col))

def _cast_shadow(canvas, pic_box, opt):
    """Soft shadow the raised mat casts onto the picture, away from the light."""
    k = opt.get("shadow", 35) / 100.0
    if not opt.get("enabled", True) or k <= 0:
        return
    a = math.radians(opt.get("light_angle", 0))
    depth = H * 0.006
    dx, dy = -math.sin(a) * depth, math.cos(a) * depth
    x0, y0, x1, y1 = pic_box
    pw, ph = x1 - x0, y1 - y0
    pad = int(depth * 3)
    m = Image.new("L", (pw + pad * 2, ph + pad * 2), 255)
    ImageDraw.Draw(m).rectangle((pad + dx, pad + dy, pad + pw + dx - 1, pad + ph + dy - 1), fill=0)
    m = m.filter(ImageFilter.GaussianBlur(depth * 0.9)).crop((pad, pad, pad + pw, pad + ph)).point(lambda v: int(v * k * 0.75))
    region = canvas.crop(pic_box)
    region = Image.composite(Image.new("RGB", region.size, (0, 0, 0)), region, m)
    canvas.paste(region, (x0, y0))

_SRGB = None

def to_srgb(im):
    """Convert from the embedded ICC profile (Display P3, Adobe RGB, ProPhoto, CMYK...) to sRGB; the TV assumes sRGB, so
    untagged wide-gamut photos otherwise look over- or under-saturated. Returns an RGB image (EXIF kept for rotation)."""
    global _SRGB
    exif = im.info.get("exif")
    icc = im.info.get("icc_profile")
    out = None
    try:
        from PIL import ImageCms
        import io
        if icc:
            src = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            desc = (ImageCms.getProfileDescription(src) or "").lower()
            if "srgb" not in desc:
                if _SRGB is None:
                    _SRGB = ImageCms.createProfile("sRGB")
                base = im if im.mode in ("RGB", "CMYK", "L") else im.convert("RGB")
                out = ImageCms.profileToProfile(base, src, _SRGB, renderingIntent=ImageCms.Intent.PERCEPTUAL,
                                                outputMode="RGB", flags=ImageCms.Flags.BLACKPOINTCOMPENSATION)
    except Exception:
        out = None
    if out is None:
        out = im.convert("RGB")
    if exif:
        out.info["exif"] = exif
    return out

def apply_edit(img, edit, srgb=True):
    """Non-destructive edit from the sidecar: rotate (90 degree steps), straighten (small angle, corners trimmed away), crop (fractions)."""
    if srgb:
        img = to_srgb(img)
    img = ImageOps.exif_transpose(img).convert("RGB")
    if not edit:
        return img
    r = int(edit.get("rotate") or 0) % 360
    if r:
        img = img.transpose({90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}[r])   # clockwise degrees
    ang = float(edit.get("straighten") or 0)
    if abs(ang) > 0.01:
        import math
        w, h = img.size
        t = math.radians(abs(ang)); c, sn = math.cos(t), math.sin(t); a = w / h
        k = min(1 / (c + sn / a), 1 / (a * sn + c))          # largest same-aspect rectangle that stays inside the rotated picture
        img = img.rotate(ang, resample=Image.BICUBIC, expand=False)
        cw, ch = w * k, h * k
        img = img.crop((round((w - cw) / 2), round((h - ch) / 2), round((w + cw) / 2), round((h + ch) / 2)))
    cr = edit.get("crop")
    if cr:
        w, h = img.size
        x0, y0 = max(0, int(round(cr["x"] * w))), max(0, int(round(cr["y"] * h)))
        x1, y1 = min(w, int(round((cr["x"] + cr["w"]) * w))), min(h, int(round((cr["y"] + cr["h"]) * h)))
        if x1 - x0 > 16 and y1 - y0 > 16:
            img = img.crop((x0, y0, x1, y1))
    return img

def compose(img, disp):
    """Mat + picture on a 3840x2160 canvas. Returns (canvas, geometry)."""
    mat = disp["mat"]
    img = ImageOps.exif_transpose(img).convert("RGB")
    if not mat["enabled"]:
        if disp.get("fit") == "fill":
            return ImageOps.fit(img, (W, H), Image.LANCZOS), None
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        im = ImageOps.contain(img, (W, H), Image.LANCZOS)
        pos = ((W - im.width) // 2, (H - im.height) // 2)
        canvas.paste(im, pos)
        return canvas, {"img_box": (*pos, pos[0] + im.width, pos[1] + im.height), "mat": False}
    bev = mat["bevel"]
    bpx = int(H * bev["width_pct"] / 100)
    layers = mat["layers"] or [{"color": mat["color"], "width_pct": mat["width_pct"], "texture": mat["texture"]}]
    ln = mat.get("liner") or {}
    if ln.get("enabled") and not mat["layers"]:
        layers = layers + [{"color": ln.get("color", "#2b2b2b"), "width_pct": float(ln.get("width_pct", 0.8)), "texture": ln.get("texture", "flat")}]
    widths = [int(H * L["width_pct"] / 100) for L in layers]
    total = sum(widths)
    mode = mat["letterbox"]
    ar = img.width / img.height
    if mode == "bars_outside" and abs(ar - W / H) < 0.012:
        mode = "mat"                         # already 16:9: nothing to put outside
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    if mode == "bars_outside":
        pw_max, ph_max = W - 2 * total, H - 2 * total
        im = ImageOps.contain(img, (pw_max, ph_max), Image.LANCZOS)
        pic = ((W - im.width) // 2, (H - im.height) // 2)
        block = [pic[0] - total, pic[1] - total, pic[0] + im.width + total, pic[1] + im.height + total]
        insets = [(w, w) for w in widths]
    else:
        block = [0, 0, W, H]
        even = mat.get("shape", "even") == "even"
        insets = [(w, w) if even else (int(w * W / H), w) for w in widths]   # proportional: a 16:9 picture exactly fills the window
    bx0, by0, bx1, by1 = block
    canvas.paste(_texture((bx1 - bx0, by1 - by0), layers[0].get("texture", "flat"), hex2rgb(layers[0]["color"])), (bx0, by0))
    box = list(block)
    for i, (hp, vp) in enumerate(insets):
        box = [box[0] + hp, box[1] + vp, box[2] - hp, box[3] - vp]
        if i + 1 < len(layers):
            col = hex2rgb(layers[i + 1]["color"])
            canvas.paste(_texture((box[2] - box[0], box[3] - box[1]), layers[i + 1].get("texture", "flat"), col, 9 + i), (box[0], box[1]))
            _bevel(canvas, tuple(box), hex2rgb(layers[i]["color"]), bpx, bev)
    inner = hex2rgb(layers[-1]["color"])
    x0, y0, x1, y1 = box
    ww, wh = x1 - x0, y1 - y0
    if mode == "bars_outside":
        pic_box = (pic[0], pic[1], pic[0] + im.width, pic[1] + im.height)
        _bevel(canvas, pic_box, inner, bpx, bev)
        canvas.paste(im, pic)
    elif mode == "bars_inside":
        _bevel(canvas, tuple(box), inner, bpx, bev)
        im = ImageOps.contain(img, (ww, wh), Image.LANCZOS)
        win = Image.new("RGB", (ww, wh), (0, 0, 0))
        win.paste(im, ((ww - im.width) // 2, (wh - im.height) // 2))
        canvas.paste(win, (x0, y0))
        pic_box = (x0, y0, x1, y1)
    else:
        if even and abs((img.width / img.height) / (ww / wh) - 1) < 0.2:
            im = ImageOps.fit(img, (ww, wh), Image.LANCZOS)          # even mat: trim the picture slightly to fill the window
        else:
            im = ImageOps.contain(img, (ww, wh), Image.LANCZOS)
        px, py = x0 + (ww - im.width) // 2, y0 + (wh - im.height) // 2
        pic_box = (px, py, px + im.width, py + im.height)
        if im.width < ww - 2 or im.height < wh - 2:   # mat fills the sides; bevel hugs the picture
            canvas.paste(_texture((ww, wh), layers[-1].get("texture", "flat"), inner, 21), (x0, y0))
        _bevel(canvas, pic_box, inner, bpx, bev)
        canvas.paste(im, (px, py))
    _cast_shadow(canvas, pic_box, bev)
    strip = (block[0], pic_box[3], block[2], block[3])  # mat area below the picture
    return canvas, {"img_box": pic_box, "mat": True, "mat_color": hex2rgb(layers[0]["color"]),
                    "inner_color": inner, "strip": strip, "block": tuple(block)}

# ------------------------------------------------------------------ placard templates
# fonts: (family, weight, size@2160, UPPER, tracking)
TEMPLATES = {
    "modern_minimal": {"label": "Modern Minimal", "order": ("artist", "title", "meta"),
        "artist": ("kumbh", 700, 58, False, 0), "title": ("kumbh", 400, 52, False, 0), "meta": ("plex-mono", None, 40, True, 0),
        "box": "dark", "card": (20, 20, 20, 184), "text": "#F5F4F0", "muted": "#EDEBE5", "maxw": 1150, "pad": 44},
    "classical_editorial": {"label": "Classical Editorial", "order": ("title", "artist", "meta"),
        "artist": ("source-sans", 600, 32, True, 0.12), "title": ("literata-italic", 400, 54, False, 0), "meta": ("source-sans", 400, 30, False, 0),
        "box": "cream", "card": (244, 238, 224, 238), "text": "#1F1B16", "muted": "#5A5247", "maxw": 1100, "pad": 44},
    "gallery_zine": {"label": "Gallery Zine", "order": ("artist", "title", "meta"),
        "artist": ("space-grotesk", 700, 56, True, 0), "title": ("space-grotesk", 400, 46, False, 0), "meta": ("space-mono", None, 30, True, 0),
        "box": "zine", "card": (244, 241, 234, 255), "text": "#111111", "muted": "#333333", "maxw": 1100, "pad": 36},
}

def _fields(sc, tpl):
    artist, title, date, medium, credit = card_fields(sc)
    meta = "  ·  ".join(meta_parts(sc))
    out = {"artist": artist, "title": title, "meta": meta}
    for k in ("artist", "title", "meta"):
        if tpl[k][3]:
            out[k] = out[k].upper()
    return out

def _anchor(pos, bw, bh, m, region=(0, 0, W, H)):
    x0, y0, x1, y1 = region
    x = x0 + m if pos.endswith("left") else (x1 - m - bw if pos.endswith("right") else (x0 + x1 - bw) // 2)
    y = y0 + m if pos.startswith("top") else y1 - m - bh
    return int(x), int(y)

def draw_overlay(base, sc, pl):
    tpl = TEMPLATES[pl["template"]]
    s = pl.get("scale", 1.0) * H / 2160
    fl = _fields(sc, tpl)
    if not has_content(sc):
        return base
    lay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    pad, maxw = int(tpl["pad"] * s), int(tpl["maxw"] * s)
    col, mut = hex2rgb(tpl["text"]), hex2rgb(tpl["muted"])
    rows = []
    for key in tpl["order"]:
        if not fl[key]:
            continue
        fam, wg, sz, up, tr = tpl[key]
        f, lines = fit(d, fl[key], fam, wg, sz * s, maxw, 3 if key != "artist" else 2)
        rows.append((key, f, lines, tr, mut if key == "meta" else col))
    lh = lambda f: int(f.size * 1.2)
    gap = int(12 * s)
    h = sum(len(r[2]) * lh(r[1]) for r in rows) + gap * (len(rows) - 1)
    wmax = max(max(d.textlength(l, font=r[1]) + (len(l) - 1) * r[1].size * r[3] for l in r[2]) for r in rows)
    bw, bh = int(wmax + pad * 2), int(h + pad * 2)
    x, y = _anchor(pl["position"], bw, bh, int(H * float(pl.get("margin_pct", 2.2)) / 100), pl.get("_region") or (0, 0, W, H))
    box = tpl["box"]
    if box == "dark":
        d.rounded_rectangle((x, y, x + bw, y + bh), radius=int(14 * s), fill=tpl["card"])
    elif box == "cream":
        d.rectangle((x, y, x + bw, y + bh), fill=tpl["card"])
    else:
        d.rectangle((x, y, x + bw, y + bh), fill=tpl["card"], outline=(0, 0, 0, 255), width=max(4, int(5 * s)))
    cy = y + pad
    for i, (key, f, lines, tr, c) in enumerate(rows):
        if box == "dark" and key == "meta" and i > 0:
            if pl.get("divider", False):
                d.line((x + pad, cy - gap // 2, x + bw - pad, cy - gap // 2), fill=(*mut, 150), width=max(2, int(2 * s)))
            cy += gap // 2
        if box == "zine" and i > 0:
            d.line((x, cy - gap // 2 - pad // 4, x + bw, cy - gap // 2 - pad // 4), fill=(0, 0, 0, 255), width=max(2, int(3 * s)))
        for ln in lines:
            if tr:
                draw_spaced(d, (x + pad, cy), ln, f, c, tr)
            else:
                d.text((x + pad, cy), ln, font=f, fill=c)
            cy += lh(f)
        cy += gap
    out = base.convert("RGBA")
    out.alpha_composite(lay)
    return out.convert("RGB")

def draw_on_mat(base, sc, pl, geom, region=None):
    """Caption printed straight on the mat (no box). Layouts: one_line | two_line | three_line."""
    tpl = TEMPLATES[pl["template"]]
    s = pl.get("scale", 1.0) * H / 2160
    x0, y0, x1, y1 = geom["strip"]
    rx0, ry0, rx1, ry1 = region or (0, 0, W, H)
    y1 = min(y1, ry1)
    hs = max(40, y1 - y0)
    pic = geom["img_box"]
    d = ImageDraw.Draw(base)
    artist, title, date, medium, credit = card_fields(sc)
    parts = meta_parts(sc)
    if not has_content(sc):
        return base
    mc = geom["mat_color"] if geom["mat"] else (0, 0, 0)
    tc = (26, 23, 20) if lum(mc) > 0.35 else (240, 236, 226)
    mt = tuple(int(v) for v in mix(tc, mc, 0.42))
    layout = pl.get("mat_layout", "two_line")
    margin = int(8 * s)
    left_lim, right_lim = max(pic[0], rx0) + margin, min(pic[2], rx1) - margin
    avail = right_lim - left_lim
    atxt = artist.upper() if tpl["artist"][3] else artist
    tr = tpl["artist"][4]
    ttxt = title or atxt
    show_artist = bool(title and atxt)
    fit = bool(pl.get("mat_fit"))
    if fit:      # largest text that fits the mat strip, equal space above and below (about 14% of the strip each, plus line spacing)
        base_ts = hs * 0.5
        steps, hmax = [1 - 0.02 * i for i in range(0, 46)], hs * 0.72
    else:
        base_ts = min(tpl["title"][2] * 0.85 * s, hs * 0.31 * pl.get("scale", 1.0)) * {"one_line": 0.85, "two_line": 1.0, "three_line": 0.8}.get(layout, 1.0)
        steps, hmax = [1 - 0.05 * i for i in range(0, 12)], hs * 0.86

    def seg_w(txt, f, t):
        return spaced_len(d, txt, f, t) if t else d.textlength(txt, font=f)

    def build(k, parts_):
        ts = base_ts * k
        ss = ts * (0.74 if layout == "one_line" else 0.62)
        tF = font(tpl["title"][0], ts, tpl["title"][1])
        aF = font(tpl["artist"][0], ss, tpl["artist"][1])
        mF = font(tpl["meta"][0], ss, tpl["meta"][1])
        mtxt = "  ·  ".join(parts_)
        if tpl["meta"][3]:
            mtxt = mtxt.upper()
        T = (ttxt, tF, tc, 0)
        A = (atxt, aF, tc, tr) if show_artist else None
        M = (mtxt, mF, mt, 0) if mtxt else None
        gap = int(ss * 1.3)
        if layout == "one_line":
            lines = [[x for x in (T, A, M) if x]]
        elif layout == "three_line":
            lines = [[T]] + [[x] for x in (A, M) if x]
        else:
            lines = [[T]] + ([[x for x in (A, M) if x]] if (A or M) else [])
        wmax = max(sum(seg_w(t_[0], t_[1], t_[3]) for t_ in ln) + gap * (len(ln) - 1) for ln in lines)
        hts = [int(max(t_[1].size for t_ in ln) * 1.3) for ln in lines]
        return lines, gap, wmax, hts

    chosen = None
    pp = list(parts)
    while True:
        for k in steps:
            lines, gap, wmax, hts = build(k, pp)
            if wmax <= avail and sum(hts) <= hmax:
                chosen = (lines, gap, hts); break
        if chosen or not pp:
            break
        pp = pp[:-1]                                            # drop whole trailing parts, never cut a word
    if not chosen:
        lines, gap, wmax, hts = build(0.45, [])
        chosen = (lines, gap, hts)
    lines, gap, hts = chosen
    cy = y0 + (hs - sum(hts)) // 2
    pos = pl["position"]
    for ln, lh_ in zip(lines, hts):
        wd = int(sum(seg_w(t_[0], t_[1], t_[3]) for t_ in ln) + gap * (len(ln) - 1))
        x = right_lim - wd if pos.endswith("right") else ((left_lim + right_lim - wd) // 2 if pos.endswith("center") else left_lim)
        asc = max(t_[1].getmetrics()[0] for t_ in ln)
        for t_ in ln:
            yy = cy + (asc - t_[1].getmetrics()[0])
            if t_[3]:
                x += draw_spaced(d, (x, yy), t_[0], t_[1], t_[2], t_[3])
            else:
                d.text((x, yy), t_[0], font=t_[1], fill=t_[2]); x += d.textlength(t_[0], font=t_[1])
            x += gap
        cy += lh_
    return base

# ------------------------------------------------------------------ public API
def resolve(sidecar, settings=None):
    return merge(DEFAULTS, settings, sidecar.get("display"))

def cache_key(image_path, sidecar, disp):
    src = json.dumps({"v": VERSION, "mtime": os.path.getmtime(image_path), "size": os.path.getsize(image_path),
                      "disp": disp, "card": sidecar.get("card_text"), "t": sidecar.get("title"),
                      "pt": sidecar.get("placard_title"), "edit": sidecar.get("edit"), "a": (sidecar.get("artist") or {}).get("name")}, sort_keys=True, default=str)
    return hashlib.sha1(src.encode()).hexdigest()[:16]

def render(image_path, sidecar, settings=None, out_path=None, cache_dir=None, force=False):
    """Render to JPEG. With cache_dir, a finished render is reused until image/sidecar/settings change."""
    disp = resolve(sidecar, settings)
    key = cache_key(image_path, sidecar, disp)
    cached = None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        cached = os.path.join(cache_dir, key + ".jpg")
        if os.path.exists(cached) and not force:
            return cached
    src = apply_edit(Image.open(image_path), sidecar.get("edit"), srgb=disp.get("srgb", True))
    tint = disp["mat"].get("auto_tint")
    if disp["mat"].get("enabled") and tint:
        c = tint_color(src, tint)
        if c:
            disp["mat"]["color"] = c
    base, geom = compose(src, disp)
    ov = disp.get("overscan") or {}
    sides = [float(ov.get(k) or 0) for k in ("left", "top", "right", "bottom")]
    ol, ot, orr, ob = int(W * sides[0] / 100), int(H * sides[1] / 100), int(W * sides[2] / 100), int(H * sides[3] / 100)
    inset = ov.get("mode") == "inset" and any(sides)
    region = None if (inset or not any(sides)) else (ol, ot, W - orr, H - ob)
    pl = dict(disp["placard"])
    pl["_region"] = region
    if pl["enabled"]:
        if pl["placement"] == "mat" and geom and geom.get("mat"):
            base = draw_on_mat(base, sidecar, pl, geom, region)
        else:
            base = draw_overlay(base, sidecar, pl)
    if inset:                                   # shrink the whole picture into the area the TV really shows
        inner = (max(100, W - ol - orr), max(100, H - ot - ob))
        canvas = Image.new("RGB", (W, H), (0, 0, 0))
        canvas.paste(base.resize(inner, Image.LANCZOS), (ol, ot))
        base = canvas
    dest = out_path or cached
    base.save(dest, "JPEG", quality=95, subsampling=0)
    return dest

def render_colorbars():
    """SMPTE color bars (EG 1-1990 layout: 75% bars, reverse-blue strip, -I / white / +Q / PLUGE row) at 3840x2160."""
    im = Image.new("RGB", (W, H), (16, 16, 16))
    d = ImageDraw.Draw(im)
    g = 192
    top = [(g, g, g), (g, g, 0), (0, g, g), (0, g, 0), (g, 0, g), (g, 0, 0), (0, 0, g)]
    mid = [(0, 0, g), (16, 16, 16), (g, 0, g), (16, 16, 16), (0, g, g), (16, 16, 16), (g, g, g)]
    y1, y2 = int(H * 0.67), int(H * 0.75)
    for i in range(7):
        x0, x1 = round(W * i / 7), round(W * (i + 1) / 7)
        d.rectangle((x0, 0, x1, y1), fill=top[i])
        d.rectangle((x0, y1, x1, y2), fill=mid[i])
    bottom = [((0, 33, 76), 5), ((255, 255, 255), 5), ((50, 0, 106), 5), ((16, 16, 16), 2),
              ((9, 9, 9), 1), ((16, 16, 16), 1), ((23, 23, 23), 1), ((16, 16, 16), 1)]
    x = 0.0
    for col, u in bottom:
        nx = x + W * u / 21
        d.rectangle((round(x), y2, round(nx), H), fill=col)
        x = nx
    try:
        f = font("kumbh", 110, 700)
        txt = "FRAME TV CURATOR"
        bb = d.textbbox((W // 2, H // 2), txt, font=f, anchor="mm")
        d.rectangle((bb[0] - 60, bb[1] - 40, bb[2] + 60, bb[3] + 40), fill=(0, 0, 0))
        d.text((W // 2, H // 2), txt, font=f, fill=(255, 255, 255), anchor="mm")
    except Exception:
        pass
    return im

def render_calibration():
    """Overscan test pattern: nested outlines at 0..10 % from each edge. Read the outermost number you can fully see on each side."""
    im = Image.new("RGB", (W, H), (20, 20, 24))
    d = ImageDraw.Draw(im)
    f, fb = font("kumbh", 46, 700), font("kumbh", 90, 700)
    for i in range(0, 11):
        x0, y0 = int(W * i / 100), int(H * i / 100)
        x1, y1 = W - 1 - x0, H - 1 - y0
        col = (255, 70, 70) if i == 0 else ((255, 255, 255) if i % 2 == 0 else (255, 205, 70))
        d.rectangle((x0, y0, x1, y1), outline=col, width=5)
        t = str(i)
        xl = int(W * (0.18 + 0.06 * i))
        yl = int(H * (0.22 + 0.055 * i))
        d.text((xl, y0 + 8), t, font=f, fill=col, anchor="ma")             # top
        d.text((xl, y1 - 8), t, font=f, fill=col, anchor="md")             # bottom
        d.text((x0 + 12, yl), t, font=f, fill=col, anchor="lm")            # left
        d.text((x1 - 12, yl), t, font=f, fill=col, anchor="rm")            # right
    d.text((W // 2, H // 2 - 60), "OVERSCAN CALIBRATION", font=fb, fill=(255, 255, 255), anchor="mm")
    d.text((W // 2, H // 2 + 40), "For each side (top, right, bottom, left) note the outermost number whose line you can fully see.",
           font=font("kumbh", 40, 400), fill=(220, 220, 220), anchor="mm")
    d.text((W // 2, H // 2 + 100), "Enter those four numbers in Settings > Overscan. If you can see the red 0 line on every side, set all to 0.",
           font=font("kumbh", 40, 400), fill=(220, 220, 220), anchor="mm")
    return im

# ------------------------------------------------------------------ e-paper (black / white / red)
EPAPER = {"size": (522, 152), "red": (200, 0, 0)}  # "4 Inch ePaper Display" (OpenEPaperLink): 522 x 152

def render_epaper(sc, style="gallery", size=None):
    """Tri-color card: only black, white and red, no anti-aliasing, whole words only."""
    w, h = size or EPAPER["size"]
    BL, WH, RD = (0, 0, 0), (255, 255, 255), EPAPER["red"]
    artist, title, date, medium, credit = card_fields(sc)
    inv = style == "inverted"
    bg, fg = (BL, WH) if inv else (WH, BL)
    im = Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    mar = 12
    wide = w >= h * 2
    split = int(w * 0.63) if wide else w
    left_w = split - mar * 2 if wide else w - mar * 2
    y = mar - 2
    if artist:
        f, ls = fit(d, artist.upper(), "kumbh", 800, 20 if wide else 25, left_w, 2, 0.7)
        for ln in ls:
            d.text((mar, y), ln, font=f, fill=WH if inv else RD); y += int(f.size * 1.15)
        d.rectangle((mar, y + 2, mar + 40, y + 4), fill=RD)
        y += 13
    avail = h - y - mar - (0 if wide else 92)
    size_t = 22
    while True:
        fam, wg = ("kumbh", 500) if style == "grid" else ("literata-italic", 500)
        ft, tl = fit(d, title, fam, wg, size_t, left_w, 6, 1.0)
        if len(tl) * int(ft.size * 1.2) <= avail or size_t <= 13:
            break
        size_t -= 1
    for ln in tl:
        d.text((mar, y), ln, font=ft, fill=fg); y += int(ft.size * 1.2)
    if wide:
        d.line((split, mar, split, h - mar), fill=fg, width=1)
        x0, rw = split + 12, w - split - 12 - mar
        yy = mar - 1
        if date:
            fm = font("source-sans", 17, 600)
            d.text((x0, yy), date, font=fm, fill=RD if style == "grid" else fg); yy += 22
        creds_h = 0
        cf = cl = None
        if credit:
            cf, cl = fit(d, credit, "source-sans", 500, 12, rw, 3, 0.85)
            creds_h = len(cl) * int(cf.size * 1.18) + 4
        if medium:
            f2, ml = fit(d, medium, "source-sans", 500, 14, rw, 6, 0.8)
            for ln in ml:
                if yy + f2.size > h - mar - creds_h:
                    break
                d.text((x0, yy), ln, font=f2, fill=fg); yy += int(f2.size * 1.2)
        if cl:
            cy = h - mar - creds_h + 4
            for ln in cl:
                d.text((x0, cy), ln, font=cf, fill=fg); cy += int(cf.size * 1.18)
        if style == "grid":
            d.rectangle((1, 1, w - 2, h - 2), outline=fg, width=2)
    else:
        d.line((mar, h - 96, w - mar, h - 96), fill=fg, width=1)
        yy = h - 88
        f2 = font("source-sans", 17, 500)
        if date:
            d.text((mar, yy), date, font=f2, fill=fg)
        yy += 22
        if medium:
            f3, ml = fit(d, medium, "source-sans", 500, 17, w - mar * 2, 1, 0.7)
            d.text((mar, yy), ml[0], font=f3, fill=fg)
        if credit:
            f4, cl2 = fit(d, credit, "source-sans", 500, 14, w - mar * 2, 1, 0.7)
            d.text((mar, h - 12), cl2[0], font=f4, fill=fg, anchor="ls")
    return im
