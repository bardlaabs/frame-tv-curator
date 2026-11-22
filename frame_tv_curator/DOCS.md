# Frame TV Curator

## Setup
1. Put images in the `frame` folder of your media share (for example `art/` and `photos/` subfolders). Files dropped there are picked up within a minute.
2. Open the add-on panel. In **Settings** choose the rotation interval and folders; in the **TV** tab set the media player entity (default `media_player.frametv`) and, optionally, the TV's IP address and MAC address (used for Wake-on-LAN when the TV is fully off).
3. Accept the pairing prompt on the TV the first time the add-on connects.

## Tabs
- **Now Playing**: current image, previous / next / resend, Art Mode and power buttons.
- **Library**: browse, search, flag (star = favorite, plus = show more, eye-slash = exclude), bulk actions, find duplicates, edit an image (crop, display look, placard).
- **Display**: global look (mat, bevel, liner, placard, sRGB conversion). Each image can override a section with its Customize checkbox.
- **Schedules**: special occasions and time-of-day rules.
- **TV**: connection, remote buttons, ambient brightness and color temperature, companion light, overscan.
- **Settings**: rotation, Bird Frame interleave, logging level.

## Add-on options
- `log_level`: debug, info, warning or error.
- `tv_ip`: TV address (blank = taken from the media player entity).
- `dry_run`: render but never touch the TV.

## Notes
- A TV change takes about 10-14 seconds. The add-on only pushes while the TV is in Art Mode.
- Ambient control, companion light and other entity-linked features are off by default and always fall back to a manual value if an entity is missing.
- Your data (settings, sidecars, caches) lives in the add-on's `/data` folder; images and sidecars live on the media share.
