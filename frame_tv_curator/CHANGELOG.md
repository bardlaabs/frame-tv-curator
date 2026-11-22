# Changelog

## 0.9.6
- Status panel: states such as "on", "off", "unavailable" are bold white too.

## 0.9.5
- Entity pickers: every empty box now reads "Select…" (no more example ids that look like a chosen value); boxes widen to fit the full entity name.
- Status panel: entity names are bold in the accent color and numbers/values are bold. When a mode needs an entity and none is chosen (or it is unavailable) the panel says so, e.g. "No entity chosen — using sun +31°".

## 0.9.4
- TV tab: "What it is doing now" moved to a sticky right-hand column (on top on narrow screens) and reorganized into a labelled grid: TV, Brightness, Color temp., Presence, Light, each with a short detail line.
- Entities are shown by friendly name everywhere (status panel, chips, pickers); the entity id appears as a second line in the dropdown and under the field. Search still matches name, id and state.

## 0.9.3
- TV tab: Refresh status button on the "What it is doing now" panel.

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
