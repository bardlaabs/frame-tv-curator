# Sidecar files and data layout (technical)

This page describes where the add-on keeps its data and what is inside each file. You do not need it to use the add-on. It is for backups, scripts, and anyone who wants to read or edit the files directly.

## The principle: your images are never changed

Every image can have a small JSON **sidecar** next to it with the same name and a `.json` extension. Everything the add-on knows about a picture lives there: its title and artist, your flags and tags, your crop and rotation, and any per-image look. The image file itself is never rewritten.

- Crop, rotate, straighten, mat, inner liner, bevel, placard and overscan are all applied only when the add-on **renders** the picture for the TV. The result is a separate cached JPEG.
- Delete a sidecar and the picture simply goes back to defaults. Delete the rendered cache and it is rebuilt.
- The one exception is **format conversion**: a HEIC, WebP, TIFF or BMP file that you add is converted to JPEG (orientation baked in, EXIF kept), and the original is kept under `_originals/`.

## Where things live

On the media share (`/media`, usually your NAS):

```
frame/
  Art/                      your folders (any names; Art and Photos are created on first run)
    Evening_Over_the_Lake.jpg
    Evening_Over_the_Lake.json    <- the sidecar
  Photos/
  _originals/<Folder>/      the files you added before conversion to JPEG
  _trash/<Folder>/          deleted pictures and their sidecars (recoverable)
  _rendered/                cached 3840x2160 renders sent to the TV (safe to delete)
  _thumbs/                  cached thumbnails (safe to delete)
  _epaper/                  rendered e-paper cards
  _backups/                 daily curator-YYYYMMDD-HHMMSS.tar.gz (newest 14 kept)
```

In the add-on's own data folder (`/data`, inside Home Assistant, included in HA backups):

| File | What it holds |
|---|---|
| `settings.json` | All settings: source, rotation, default look, TV, presence, ambient, schedules, e-paper, Bird Frame |
| `state.json` | Rotation state: shuffle bags, history, current picture, the TV picture cache list |
| `albums.json` | Albums: id, name, created date and the list of image ids |
| `imgcache.json` | Cached image facts (pixel size, content hash) used by the low-resolution warning and the duplicate finder; rebuilt automatically |
| `discover/` | Cached Discover indexes (for example the Reframed sitemap) |

An **image id** is the path under `frame/`, such as `Art/Evening_Over_the_Lake.jpg`. Albums and rotation state refer to images by id; moving or deleting an image in the add-on updates them.

## The sidecar format

Schema name: `frame-art-sidecar/1` (the `schema` key is written for pictures added from Discover; older and photo sidecars may omit it). Every key is optional. Unknown keys are kept, so you can add your own.

### A sidecar from Discover (art)

```json
{
  "schema": "frame-art-sidecar/1",
  "kind": "art",
  "title": "Evening Over the Lake",
  "artist": { "name": "Sample Artist", "display": "Sample Artist" },
  "date": { "display": "2026", "start": null, "end": null },
  "medium": "Oil on canvas",
  "description": "Text from the source site.",
  "description_attribution": "Description from Art Institute of Chicago (CC BY 4.0)",
  "collection": { "institution": "Art Institute of Chicago", "status": "downloaded from Art Institute of Chicago", "credit_line": "Gift of ..." },
  "card_text": { "artist": "Sample Artist", "title": "Evening Over the Lake", "date": "2026", "medium": "Oil on canvas", "credit": "Art Institute of Chicago" },
  "source_image": { "width": 3000, "height": 1688 },
  "source_url": "https://www.artic.edu/artworks/12345",
  "license": "CC0",
  "links": [ { "label": "Art Institute of Chicago page", "url": "https://www.artic.edu/artworks/12345", "kind": "record" } ],
  "origin": { "discover": "aic", "downloaded": "2026-11-22", "ai_extended": false },
  "identification": { "confidence": "high", "status": "from source site", "method": "title, artist and date as published by Art Institute of Chicago", "verified": false },
  "tags": ["landscape", "blue"],
  "flags": { "favorite": true },
  "edit": { "rotate": 0, "straighten": 0, "crop": { "x": 0.05, "y": 0.1, "w": 0.9, "h": 0.8 } },
  "display": { "mat": { "enabled": true, "color": "#efece4", "width_pct": 8 } },
  "notes": "My private note"
}
```

### A sidecar for a photo

Photos get a sidecar the first time the add-on sees them, prefilled from EXIF. There is no title until you set one (the file name is shown instead).

```json
{
  "schema": "frame-art-sidecar/1",
  "kind": "photo",
  "exif_v": 2,
  "artist": { "name": "Photographer", "display": "Photographer" },
  "date": { "display": "2025-06-14" },
  "location": { "lat": 32.7157, "lon": -117.1611, "name": "San Diego, California", "tries": 1 },
  "camera": "iPhone 15 Pro",
  "tags": [],
  "flags": {}
}
```

### Field reference

| Key | Type | Meaning |
|---|---|---|
| `schema` | string | `frame-art-sidecar/1` |
| `kind` | `art` or `photo` | Decides which detail line the placard prints (art: date and medium; photo: date and place) |
| `title` | string | The picture's title. Empty for photos until you set one |
| `placard_title` | string | Optional different title just for the placard |
| `artist.name`, `artist.display` | string | Artist. `display` is used for the card when present; "Unknown artist" is never printed |
| `date.display` | string | Date as text (`1889`, `c. 1500`, `2025-06-14`). `start` / `end` are optional numeric years |
| `medium` | string | Medium (art) |
| `description`, `description_attribution` | string | Description text and where it came from |
| `collection` | object | Institution, status and credit line |
| `card_text` | object | **Overrides for what the placard prints**: `artist`, `title`, `date`, `medium`, `credit`. Edit these to change the placard without changing the record |
| `source_image` | object | Pixel size of the source image as downloaded |
| `source_url`, `license`, `links` | | Where the picture came from, its license, and related links |
| `origin` | object | `discover` (source id), `downloaded` (date), `ai_extended` (guess that the image was AI-extended; not verified) |
| `identification` | object | How the metadata was determined and whether it was verified |
| `location` | object | `lat`, `lon`, `name` (place name looked up once from OpenStreetMap), `tries` |
| `camera` | string | Camera from EXIF |
| `exif_v` | number | Version of the EXIF prefill (used for one-time upgrades) |
| `tags` | list of strings | Your tags. Replaced as a whole when edited |
| `mood` | string | How the picture feels, in a word or two (for example `calm`). Shown in Now Playing, matched by the Library search; meant for future weather and mood matching |
| `flags` | object | `favorite` (weight 3 in the shuffle bag), `show_more` (+1), `exclude` (never picked) |
| `notes` | string | Private notes, never shown on the TV |
| `edit` | object | Non-destructive edits, see below |
| `display` | object | Per-image look, see below |

### `edit`: crop, rotate, straighten

```json
"edit": { "rotate": 90, "straighten": -1.5, "crop": { "x": 0.1, "y": 0.0, "w": 0.8, "h": 0.8 } }
```

- `rotate`: 0, 90, 180 or 270 degrees clockwise.
- `straighten`: a small angle in degrees. The picture is turned and the corners are trimmed away so no empty corners show.
- `crop`: a rectangle as **fractions** of the rotated and straightened image: `x`, `y` (top-left) and `w`, `h` (size), each between 0 and 1. Fractions mean the crop keeps working if you replace the file with a higher-resolution copy.
- Order of operations: color conversion to sRGB, EXIF orientation, rotate, straighten, crop.
- If all three are neutral the `edit` key is removed.

### `display`: per-image look

`display` holds only the settings that differ from your defaults. It is merged over the defaults (see [Display defaults](Display-Defaults)), key by key, so you only store what you changed. It appears when you tick **Customize** in the image editor; unticking it removes the key and the picture follows the defaults again.

```json
"display": {
  "mat":     { "enabled": true, "color": "#efece4", "width_pct": 8, "shape": "even", "texture": "paper", "auto_tint": "",
               "liner": { "enabled": true, "color": "#8a2f2f", "width_pct": 0.8 },
               "bevel": { "enabled": true, "width_pct": 0.4, "intensity": 60, "light_angle": 0, "elevation": 50, "shadow": 35 } },
  "placard": { "enabled": true, "template": "classical_editorial", "placement": "mat", "mat_layout": "two_line", "position": "bottom-right", "scale": 1.0 },
  "overscan": { "top": 2, "right": 2, "bottom": 2, "left": 2, "mode": "placard" },
  "srgb": true
}
```

Every key is explained in the [Settings reference](Settings-Reference).

## How a picture becomes the TV image

1. Load the original file (never modified).
2. Apply `edit` (sRGB, rotate, straighten, crop).
3. Merge the defaults from `settings.json` with the sidecar's `display`.
4. Compose the mat, inner liner and bevel on a 3840 x 2160 canvas.
5. Draw the placard from `card_text`, `title`, `artist`, `date` and `medium`.
6. Apply overscan correction.
7. Save a JPEG to `_rendered/`. The file name is a hash of the picture's file size and modified time, the settings that apply to it, its edit and its text, so any change produces a new render and unchanged pictures are reused.
8. Upload the render to the TV (or select it, if the TV picture cache already holds the same render).

## Backups and moving pictures

- A **daily backup** archives every sidecar plus `settings.json` and `state.json` into `_backups/`, keeping the newest 14. (The backup holds sidecars, not images.)
- **Copy or move a picture together with its sidecar** (same name, `.json`) to keep its information. The add-on's own Move command does this for you and updates albums.
- A picture with no sidecar gets a fresh one automatically (photos are prefilled from EXIF).
- Sidecars are plain UTF-8 JSON and are written atomically (a temporary file is renamed over the old one), so a crash never leaves half a file. If a sidecar is damaged it is treated as empty, and the daily backup has the last good copy.
- It is safe to edit sidecars by hand while the add-on is stopped. Keep the JSON valid.
