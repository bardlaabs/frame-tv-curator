# Changelog

## 0.15.0
- Library: group the grid under sticky headings by year, decade, artist or medium, with a row of jump chips to scroll to a group (Group by next to Sort by; remembered). New Sort by Medium. Undated and unknown groups go last.

## 0.14.0
- Albums: named collections of images from any folder (an image can be in several). Create them in the Library (+ Album), add selected images with "+ Album...", and use an album as the rotation source (Settings > Pick from > An album) or in a schedule (Show > An album). Albums follow images that are moved to another folder and drop images that are deleted.

## 0.13.0
- TV picture cache (TV tab, off by default): keep the last N pictures and your favorites on the TV. A kept picture that is shown again is selected in a couple of seconds instead of being uploaded again, and stays on the TV (My Photos) even if Home Assistant is down. A changed look or edit uploads a fresh copy. Includes a Clear cached pictures button.
- NASA credit line no longer repeats "NASA".

## 0.12.2
- Discover: NASA Image Library (no key). Topics (nebulae, galaxies, James Webb, Hubble, Mars, the Moon, Earth, auroras, Saturn and Jupiter) or your own search; images under 1600 px wide are skipped, so pages can come up short.

## 0.12.1
- Discover: Cleveland Museum of Art (CC0, no key). Paintings, prints, drawings, photographs, textiles and sculpture at up to about 3400 px, with the museum's description and credit line.

## 0.12.0
- Discover: The Metropolitan Museum of Art (public domain, CC0, no key needed). Browse by highlights or department, or search by keyword; originals are downloaded by the add-on at full size. Frames and non-public-domain objects are skipped, so a page can come up short.

## 0.11.2
- Folder lists (chips, dropdowns) are sorted alphabetically, ignoring case.
- The add-on creates the Art and Photos folders on first run if they do not exist (existing folders of any case are kept). Defaults now use Art and Photos.
- Optional one-time rename of lowercase art/photos folders to Art/Photos, including folder names in settings, schedules and state (enabled by a marker file).
- Added the "Add to my Home Assistant" button, a minimal-setup section, an optional-settings table and a full manual in `docs/`.

## 0.11.1
- Art Institute of Chicago downloads now use the same 3000 px best-fit size as the museum's own Download button (the largest it publishes; other sizes are refused). If that is refused, the browser tries 1686 px, then the add-on falls back to a reduced copy, and the dialog says which size you got.

## 0.11.0
- Discover: second source, the **Art Institute of Chicago** (public domain, CC0). Pick the source at the top of the tab; filter by type (paintings, prints, drawings and watercolors, photographs, posters), search by title or artist, order by best match, A-Z by artist or shuffle.
- Pictures are fitted inside 3840x2160 without cropping (the mat fills the rest). The museum's CDN only serves large sizes to real browsers, so your browser downloads the picture and hands it to the add-on; if the site refuses, the add-on falls back to a reduced 1686 px copy and says so.
- Medium, credit line and the museum's description (CC BY 4.0) are saved in the sidecar.
- The duplicate comparison shows pixel size for these; the file size is unknown until it is downloaded.

## 0.10.9
- The open-license fonts used by the placard are now included in the repository. They were missing from GitHub, so a fresh install from the repo could not draw placards.

## 0.10.8
- New placard option "Auto-fit text to the mat height" (Display tab, for text printed on the mat, also per image with Customize). It picks the largest text that fits the mat strip while keeping the text centered with even space above and below, and still shrinks to fit the picture width. When on, the Size slider is ignored.

## 0.10.7
- Placard Size (scale) now changes the caption size when it is printed on the mat. It was capped by the height of the mat strip, so values above 1 had no effect. The text still shrinks if needed to fit the strip and the picture width.

## 0.10.6
- Now Playing: Controls and Rotation sit in a column under the preview, so the details on the right can grow downward without pushing them.

## 0.10.5
- Now Playing details always list every field, including Title, Camera, Description, Notes, Links, Source, License and Edits. Fields with no value read "Not set" (dimmed); click one to open the editor and fill it in.

## 0.10.4
- Now Playing details are stacked in labelled blocks that wrap instead of running off to the right, and show everything known about the image: title, artist, date, medium or location, GPS, credit, source, license, folder, file, size, original size, description, notes, links, origin and identification notes.
- Fixed a style clash from 0.10.0 (the preview's row style overrode the details grid), which was the cause of the overflow.

## 0.10.3
- Editor Info tab: new Details section with Description, Source, Source link (with an open link), License and private Notes, plus a read-only line with the original size, where it came from and whether the edges were AI-extended. Everything is saved in the sidecar.

## 0.10.2
- Fixed a stray "null" showing below lists on several screens (empty slots are now ignored everywhere).
- Discover: the Add button now follows the destination folder as you change it.
- Discover: the add dialog is colorful (overall bar, thumbnails, per-image status chips), closes itself when everything finishes, and shows a summary toast (added / skipped / failed). If something failed, it stays open so you can read the reason.
- Discover: full-screen preview with all details (size, MB, source, license, AI-extended, description, page link, duplicate warning), arrow keys to browse, Select or Add this one now. Click a card to select as before; the preview is the small expand button on a card.

## 0.10.1
- Discover: image width and height now come from the image itself (Reframed pages do not publish them), so duplicate comparisons and sidecars show the real pixel size.

## 0.10.0
- New **Discover** tab. First source: Reframed Gallery (free, already 3840x2160). Search by title or artist, filter by artist, order A-Z / recently added / shuffle, preview, select several, pick a destination folder (or type a new one), add with download progress.
- Everything the source publishes is saved in the sidecar: title, artist, date, description, source and page URL, license, size, and whether the image was AI-extended. The placard and Info tab show them.
- Duplicate warning: selecting something that is already in your library (same picture by preview hash, or same title and artist) is flagged. A side-by-side comparison shows each file's size in pixels and MB and its source; choose skip, keep both, or replace (the old one goes to _trash).
- Library > Find duplicates now also shows each image's source.
- Reads the public sitemap (cached for a day) with a polite request rate; no API keys.

## 0.9.7
- TV tab: Save & apply now moved to its own card above the status card.

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
