# Troubleshooting

- **Nothing changes on the TV**: the TV must be in Art Mode. Check the add-on log (set `log_level` to debug).
- **TV will not wake**: set its MAC address in the TV tab and make sure Wake-on-LAN is enabled on the TV.
- **Pairing prompt keeps appearing**: accept it on the TV once; change the add-on's name in the TV tab only if needed.
- **Images missing**: confirm they are under `frame/` on the media share; allow a minute for scanning.
- **Colors look off**: check the sRGB setting in Display.
- **Placard cut off**: adjust Overscan.
- **Discover add fails**: try again; if a museum refuses the large size the add-on falls back to a smaller copy and tells you.
