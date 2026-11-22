# Changelog

## 0.9.2
- Fix: the TV tab status panel showed Presence as "off" even when it was enabled and working.

## 0.9.1
- Entity pickers are now searchable: type any part of an entity id, name or state (several words allowed) to filter the list; arrow keys and Enter select.

## 0.9.0
- Presence: turn the Frame on when someone returns and off after everyone has been gone (debounced). Choose any number of presence/motion sensors; falls back to a clock window or does nothing if sensors are unavailable. Optional active hours, "only while Art Mode is showing", and power-off vs. leave Art Mode.
- TV tab: set the Frame's own motion sensitivity and motion timer.

## 0.8.10
- Added MIT license and third-party notes. No functional changes.

## 0.8.9
- Art Mode on from a fully off TV runs in the background (Wake-on-LAN), so the button returns immediately.

## 0.8.8
- Wake-on-LAN fallback when Home Assistant's own power-on fails; power-off falls back to a direct key press; new TV MAC setting.

## 0.8.7
- Eye-slash icon for Exclude everywhere; editor uses the same flag buttons as Now Playing.

## 0.8.6
- Quick Favorite / Show more / Exclude buttons on library tiles.

## 0.8.5
- Editor: Customize checkbox for placard, mat, liner and bevel; flags under the preview; top bar with Close / Save / Save & show on TV and an unsaved-changes prompt.

## 0.8.1 - 0.8.4
- Logging level setting and client error logging; per-image Customize for placard and mat; Bird Frame error message; TV remote connection-notice fix.

## 0.8.0
- TV tab, ambient brightness and color temperature, companion light, sRGB conversion, new tabs.

## 0.7.x
- Schedules, bulk actions, duplicate finder, in-page color picker, picture palette and eyedropper, crop save.
