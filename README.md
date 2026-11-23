# Frame TV Curator

[![Open your Home Assistant instance and show the add app repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fbardlaabs%2Fframe-tv-curator)

A Home Assistant add-on that curates, renders and rotates art and photos on a Samsung **The Frame** TV.

- Shuffle-bag rotation with favorites, "show more", exclude, folders, and schedules (weekday, time window, yearly date ranges)
- Renders 3840x2160 images with mats, bevel, liner, placards, overscan correction and optional sRGB conversion
- Non-destructive crop / rotate / straighten kept in sidecar files; originals never change
- Albums (named collections) usable as a rotation source or schedule
- Library tools: EXIF and place-name prefill, bulk actions, duplicate finder, low-resolution warnings, quick flag buttons
- TV tab: Art Mode and power control (with Wake-on-LAN), ambient art brightness and color temperature (lux sensor, entity, sun, or manual), companion light
- Discover: add public-domain art from museum collections (Reframed, Art Institute of Chicago, The Met, Cleveland, NASA, Wikimedia Commons, Smithsonian (free key), Getty)
- Optional e-paper card and Bird Frame interleave

## Install

Click the button above, or add the repository by hand: **Settings > Add-ons > Add-on Store**, menu (top right) > **Repositories**, then add `https://github.com/bardlaabs/frame-tv-curator`. Install **Frame TV Curator**, start it, and open **Frame Curator** from the sidebar.

## Minimal setup

Only these are required:

1. **A Samsung Frame TV** on the same network/VLAN as Home Assistant, with a Home Assistant `media_player` entity for it (the author uses the `TheFab21/ha-samsungtv-smart` integration in local-only mode).
2. **The TV address**: set `tv_ip` in the add-on Configuration tab (or leave blank to take it from the media player entity), and confirm the media player entity in the **TV** tab (default `media_player.frametv`).
3. **A media share** mapped as `/media`. The add-on creates `frame/Art` and `frame/Photos` on first run; put images there (new files are picked up within a minute).
4. **Pair**: accept the pairing prompt on the TV the first time the add-on connects.
5. **Rotation**: choose an interval and folder in **Settings**. The TV must be in Art Mode for pictures to change.

Defaults: no mat, `modern_minimal` placard, lower-right overlay.

## Optional settings

Everything below is off by default and falls back to a manual value if an entity goes missing, so it can never break rotation.

| Feature | Where | What it does |
|---|---|---|
| Wake-on-LAN | TV tab, MAC address | Wake a fully powered-off TV |
| Presence | TV tab | Turn the TV off after nobody is detected for N minutes; restore on return |
| Art brightness | TV tab | Follow a lux sensor, an entity, the sun, or a manual value |
| Color temperature | TV tab | Follow the sun, an entity (for example Adaptive Lighting) or a manual Kelvin value |
| Companion light | TV tab | A light that follows the TV's brightness and color |
| Mats, placards, auto-fit | Display tab, per-image Customize | Frame the picture and show title/artist |
| Overscan | Display tab | Keep placards visible on TVs that crop the edge |
| Schedules | Schedules tab | Holiday and time-of-day source rules |
| Discover | Library > Discover | Add public-domain museum art with metadata |
| Bird Frame interleave | Settings | Mix bird photos into the rotation |
| E-paper card | Settings | Show the current piece on an e-paper display |

## Full manual

See the [manual in `docs/`](docs/Home.md) for every setting.

## Status

Personal project, shared as-is. Tested on one Frame TV (2022 model). See [CHANGELOG](frame_tv_curator/CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).

The add-on installs these libraries when its container is built (they are not part of this repository and keep their own licenses): Pillow (MIT-CMU), numpy (BSD-3-Clause), pillow-heif (BSD-3-Clause, bundles libheif under LGPL), samsungtvws (LGPL-3.0), paho-mqtt (EPL-2.0 / EDL-1.0), websocket-client (Apache-2.0) and requests (Apache-2.0).
