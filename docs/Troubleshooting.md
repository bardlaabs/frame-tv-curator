# Troubleshooting

- **Nothing changes on the TV**: the TV must be in Art Mode. Check the add-on log (set `log_level` to debug).
- **TV will not wake**: set its MAC address in the TV tab and make sure Wake-on-LAN is enabled on the TV.
- **Pairing prompt keeps appearing**: accept it on the TV once; change the add-on's name in the TV tab only if needed.
- **Images missing**: confirm they are under `frame/` on the media share; allow a minute for scanning.
- **Colors look off**: check the sRGB setting in Display.
- **Placard cut off**: adjust Overscan ([steps](Display-and-Look#overscan)).
- **TV does not turn on when I come home**: check the Presence card's "What it is doing now" status and that the add-on turned the TV off itself ([Presence](Optional-Presence)).
- **A Smithsonian search says a key is needed**: follow the Smithsonian steps in [Discover](Discover#smithsonian).
- **Discover add fails**: try again; if a museum refuses the large size the add-on falls back to a smaller copy and tells you.

## Health check

Open `/api/health` (through the add-on's panel address) to see a quick self-check: whether the add-on can write its data folder and the picture share, whether its settings, state and album files can be read, how long it has been running, and the last rotation error. It answers with an error status (503) when something is wrong, so a Home Assistant REST sensor can watch it.
