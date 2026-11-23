# TV tab

- **Media player entity**: default `media_player.frametv`.
- **IP address**: also available as the `tv_ip` add-on option.
- **MAC address**: needed for Wake-on-LAN when the TV is fully off.
- **Name**: how the add-on appears in the TV's pairing list.
- **Keep uploads**: how many previously uploaded images to keep on the TV.
- Remote-style buttons: Art Mode, power, previous / next / resend.
- **Overscan** correction (see Display and look).

If the TV is off, power-on actions use Wake-on-LAN when a MAC address is set.

## TV picture cache (optional)
Off by default. When on, the add-on keeps the last N pictures (default 5, including the current one) and optionally your favorites (default up to 10) on the TV instead of deleting each picture when the next one arrives.
- Showing a kept picture again only selects it on the TV (a couple of seconds, no upload).
- Kept pictures stay on the TV in Art Store > My Photos, so they remain available when Home Assistant is down.
- If you change a picture's look or edits, a fresh copy is uploaded and the old one is removed.
- **Clear cached pictures** removes them all from the TV. Turning the cache off removes them at the next picture change.

## Brightness steadiness

If the brightness keeps flipping between two neighboring TV steps (a lux reading hovering near the halfway point), raise **Steadiness** in the Art brightness card. At 0.3 (the default) the brightness moves to another step only when the target is clearly past the halfway point; 0 gives the old behavior and 1 is very steady.
