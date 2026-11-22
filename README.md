# Frame TV Curator

A Home Assistant add-on that curates, renders and rotates art and photos on a Samsung **The Frame** TV.

- Shuffle-bag rotation with favorites, "show more", exclude, folders, and schedules (weekday, time window, yearly date ranges)
- Renders 3840x2160 images with mats, bevel, liner, placards, overscan correction and optional sRGB conversion
- Non-destructive crop / rotate / straighten kept in sidecar files; originals never change
- Library tools: EXIF and place-name prefill, bulk actions, duplicate finder, low-resolution warnings, quick flag buttons
- TV tab: Art Mode and power control (with Wake-on-LAN), ambient art brightness and color temperature (lux sensor, entity, sun, or manual), companion light
- Optional e-paper card and Bird Frame interleave

## Install

1. In Home Assistant open **Settings > Add-ons > Add-on Store**, menu (top right) > **Repositories**.
2. Add `https://github.com/bardlaabs/frame-tv-curator` and click **Add**.
3. Install **Frame TV Curator**, start it, and open **Frame Curator** from the sidebar.

Requirements: a Samsung Frame TV on the same network/VLAN as Home Assistant, a media share mapped as `/media`, and a Home Assistant `media_player` entity for the TV. The author runs it with the `TheFab21/ha-samsungtv-smart` integration in local-only mode. On first use, accept the pairing prompt on the TV. See [frame_tv_curator/DOCS.md](frame_tv_curator/DOCS.md) for setup and settings.

## Status

Personal project, shared as-is. Tested on one Frame TV (2022 model). See [CHANGELOG](frame_tv_curator/CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).

The add-on installs these libraries when its container is built (they are not part of this repository and keep their own licenses): Pillow (MIT-CMU), numpy (BSD-3-Clause), pillow-heif (BSD-3-Clause, bundles libheif under LGPL), samsungtvws (LGPL-3.0), paho-mqtt (EPL-2.0 / EDL-1.0), websocket-client (Apache-2.0) and requests (Apache-2.0).
