# Troubleshooting

- **Nothing changes on the TV**: the TV must be in Art Mode. Check the add-on log (set `log_level` to debug).
- **TV will not wake**: set its MAC address in the TV tab and make sure Wake-on-LAN is enabled on the TV.
- **Pairing prompt keeps appearing**: accept it on the TV once; change the add-on's name in the TV tab only if needed.
- **Images missing**: confirm they are under `frame/` on the media share; allow a minute for scanning.
- **Colors look off**: check the sRGB setting in Display.
- **Placard cut off**: adjust Overscan ([steps](Display-and-Look#overscan-the-calibration-grid-and-the-color-bars)).
- **TV does not turn on when I come home**: check the Presence card's "What it is doing now" status and that the add-on turned the TV off itself ([Presence](Optional-Presence)).
- **A Smithsonian search says a key is needed**: follow the Smithsonian steps in [Discover](Discover#smithsonian).
- **Discover add fails**: try again; if a museum refuses the large size the add-on falls back to a smaller copy and tells you.

## The TV shows art but pictures stop changing ("Art Mode status unknown")
The add-on only changes the picture while the TV is in Art Mode. Home Assistant's Samsung integration normally reports that. If its own connection to the TV's art channel gets stuck (Home Assistant's log shows "Art API ... art channel looks wedged"), the report goes missing even though the TV is showing art, and turning the TV off and on does not help.

- The add-on then asks the TV directly, one connection at a time, and retries when the TV answers with a "client connected / disconnected" notice (the TV sends one to every connected client whenever another client joins or leaves). The status line says **Art Mode status unknown** when the TV could not be asked, which is different from **not in Art Mode**.
- If the TV stays on with an unreadable Art Mode for 5 minutes, the add-on reloads the Samsung integration in Home Assistant to clear the stuck connection (at most once every 30 minutes) and sends a notification if you set one up under Notifications. Turn this off with **If the TV is on but its Art Mode cannot be read, reload the Samsung integration** on the TV tab.
- If it keeps happening, reload the Samsung integration by hand (Settings > Devices & services) and check Home Assistant's log for the Art API messages.

## Health check

Open `/api/health` (through the add-on's panel address) to see a quick self-check: whether the add-on can write its data folder and the picture share, whether its settings, state and album files can be read, how long it has been running, and the last rotation error. It answers with an error status (503) when something is wrong, so a Home Assistant REST sensor can watch it.
