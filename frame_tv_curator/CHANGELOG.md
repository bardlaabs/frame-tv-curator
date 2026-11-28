# Changelog

## 0.34.10

- Text printed on the mat now sits a little higher in the strip (it looked too low on the TV, e.g. on "The Eruption of Vesuvius"). Cached renders are redrawn.

## 0.34.9

- Watchdog for a hung upload: right after a TV reboot a picture upload could sit forever (the TV's art service was not ready), holding the TV connection and the engine. If a push to the TV runs longer than 4 minutes, the add-on now restarts itself to abort it (at most once every 30 minutes; same TV-tab setting as the Art Mode reload, on by default) and sends a notification if you set one up. Settings, state and the presence flag are on disk, so nothing is lost.

## 0.34.8

- When the TV's art service hangs and stops answering, brightness/probe calls no longer hold the TV connection for minutes (shorter timeout, fewer retries), and the status says **Art Mode status unknown: the TV is not answering** instead of "connection is busy". A hung TV needs a full power cycle (unplug it for about 30 seconds); the add-on cannot restart the TV's own art service.

## 0.34.7

- Fix: the TV showed art but pictures stopped changing for hours because the add-on decided it was not in Art Mode. When Home Assistant's own Art connection to the TV is stuck its Art Mode report disappears, and the add-on's fallback (asking the TV directly) failed on almost every try: the TV sends "client connected / disconnected" notices to every open connection, the Samsung library treats such a notice during its handshake as a failed connection, and the add-on opened several connections at once (the Art Mode check every few seconds, brightness, probing), which set those notices off in each other.
- All art-channel conversations now go through one connection at a time that is always closed afterwards, and a handshake spoiled by such a notice is retried. The direct Art Mode answer is remembered for 15 seconds (up to a minute while the TV cannot be asked) instead of opening a connection every 5 seconds.
- "Could not ask the TV" is now reported as **Art Mode status unknown**, no longer as "not in Art Mode".
- Protection against getting stuck again: if the TV is on and its Art Mode stays unreadable for 5 minutes, the add-on reloads the Samsung integration in Home Assistant (at most once every 30 minutes; new TV-tab setting, on by default) and sends a notification when notifications are set up. An unreadable status also counts toward the "TV is not responding" notification.

## 0.34.6

- Fix: presence did not wake the TV when you came back if something other than the add-on had turned it off (a manual power-off, the TV's own timer, the end of the active hours). The wake required that presence itself had turned the TV off. Now a TV that is off is also woken into Art Mode when you return after the sensors read "nobody" for at least a set time (new setting "Also wake a TV that is off after being away at least", default 2 minutes, 0 = any absence). Shorter absences still leave the TV alone, so switching it off by hand while you sit there stays off. Active hours still apply, and the log now says why a return did not wake the TV.

## 0.34.5

- Text fields in the editor: the page behind a window (Now Playing redraws when the TV rotates or its status changes, every few seconds) no longer redraws while a window is open or you are typing in a field, and catches up right afterward. This is meant to stop selections from being cleared mid-edit. Text in fields and windows is also explicitly selectable, and keyboard shortcuts of the full-screen preview ignore keys typed in a text field.

## 0.34.4

- The "Back to the matches" button now also appears when one museum record was matched automatically (the other candidates are kept so you can go back and pick a different one), including in batches.
- The choose-what-to-keep list is cleaner: no labels or check marks, the highlight alone shows which side is kept.
- "Skip" is now "Cancel (no changes)"; it closes the window without changing anything.

## 0.34.3

- Fix: choosing to overwrite did not change the title, artist, date, medium or credit you see in the editor and on the placard. Those are kept in a separate text block that took priority; the AI result is now saved there too (and a shortened placard title is cleared when the title is replaced). Credit from the museum record is now offered as well.
- The review window is now a left/right list: for each field click the current value (left) or the new value (right); the highlighted side is what gets saved. "Select all current" and "Select all new" are at the top of the columns. Only the fields you chose are changed.
- Back button: after picking a match, "Back to the matches" returns to the list so you can choose another before anything is saved. The review now always shows after you pick a match.

## 0.34.2

- The "Which one is it?" window now shows thumbnails: your picture at the top and each museum or source match beside its details. The overwrite review shows them too.
- Fix: with an inner mat (liner), a placard printed on the mat was centered across the liner and the main mat together, so it sat too high and overlapped the liner. It is now centered in the main mat band.

## 0.34.1

- Fix: museum matching missed works the museums title differently (for example Hokusai's "The Great Wave off Kanagawa" is "Under the Wave off Kanagawa" at the Art Institute). When no record has the exact title, other works by the same artist are now offered in the chooser (never applied automatically).
- Fix: "Claude's answer was not understood". The reply is now read more tolerantly, there is more room for the answer, it retries once, and the error says why. The last answer is kept in the add-on's data folder (`ai_last.json`) for troubleshooting.
- The "no match" message now says what was searched.

## 0.34.0

- **AI and museum results can now replace what is already there, field by field.** When the result differs from something already filled in, a review window lists each field with what is there now and the new value, an Overwrite box per field, and Keep all current / Overwrite all buttons. Empty fields are still filled automatically, and tags are still added (never replaced) unless you choose otherwise. In a batch, pictures that need a decision are put aside and shown at the end.

## 0.33.1

- Fix: the Library was slow to open right after 0.33.0 because colors were worked out while it loaded. Colors now fill in only in the background.

## 0.33.0

- **Color:** every picture's dominant colors (up to three: red, orange, yellow, green, teal, blue, purple, pink, brown, black, gray, white) are worked out by the add-on (no AI, computed in the background after the update). The Library has a Color filter with swatches and two new sorts: Color (rainbow order) and Brightness.
- **Season and Occasion** fields (Info tab, Library filters). Season is spring to winter; Occasions is an editable list (Settings > Moods and appearance), default Christmas, Halloween, Easter, Thanksgiving, Valentine's Day, New Year, Fourth of July.
- **AI** now also adds **tags** (added to yours, never replacing them), season and occasion.

## 0.32.0

- **Identify / verify with AI** now uses the existing artist, title, date and file name as a lead, then checks the result against museum collections (Art Institute of Chicago, The Met, Cleveland, Getty, Smithsonian, Wikimedia Commons last). A clear museum match fills in the museum's details and adds a link to its record; several possible matches are shown for you to choose from.
- **Refresh from EXIF** button (editor and Library selection, no AI) re-reads date, camera, location and photographer from a photo.

## 0.31.0

- **Identify with Claude:** new add-on option `anthropic_key` (password field, kept by Home Assistant) and a Settings > AI page (on/off, model Haiku or Sonnet, monthly limit default $10). Press Identify with AI in a picture's Info tab, or on a Library selection, to fill empty artist, title, date, medium, description and mood. Existing values are never overwritten.

## 0.30.0

- **Weather nudge** (Settings > Moods and appearance > Weather): pick a Home Assistant weather entity (automatic finds `weather.weather_home` or the first one), and pictures whose mood fits the current weather are picked more often. Strength and the weather-to-mood mapping are adjustable. Nothing is excluded; with no entity or no moods it does nothing.
- **Named crops on schedules:** a schedule can name a saved crop; pictures that have it are shown with that crop while the schedule is active.

## 0.29.0

- **Settings sub-menu:** Settings now has General, Display, TV, Notifications and Moods and appearance pages. The Display and TV tabs moved inside Settings, so the top bar has five tabs. It reopens on the page you were last on.

## 0.28.0

- **Fix:** notifications (0.23.0) failed with "name 'ha' is not defined"; they now send.
- **Fix:** the Library's tag chips crashed when no album was open; tags now show.
- Framing choice renamed **Fill the screen (crop as needed)**; it is a non-destructive crop you can adjust in the Crop tab.
- Discover: choose a **framing** for the pictures you add (set after the download, per picture).
- Settings: **Appearance** (auto, light or dark, remembered per browser) and an editable **Moods** list (add, rename everywhere, remove). The editor's Mood is now a dropdown from that list, and the Library has a Mood filter.
- Now Playing shows a status picture ("TV is off" or "TV is on, regular TV") instead of stale art when the TV is not in Art Mode.

## 0.27.0

- Discover: **Search all sources** (first item in the Source list) searches every source for your words and shows the first six results from each, labelled by source.

## 0.26.0

- **Blurred background** framing choice: the whole picture on top of a soft, darkened, blurred copy of itself that fills the screen (good for portrait pictures). Display tab > Framing, also per image.

## 0.25.1

- E-paper card: photographs now print the place they were taken (where art prints its medium).

## 0.25.0

- **Matte style** presets (Classic gallery, Modern, Shadow box, Panoramic) at the top of the Mat settings, on the Display tab and in each picture's editor. They fill in width, shape, texture, liner, bevel and shadow; you can adjust everything afterwards.

## 0.24.0

- **Phone and tablet layout:** the tab bar scrolls sideways, buttons and fields are larger, forms stack, editors and dialogs fill the screen, and the Library grid uses two columns on small phones.
- **Automatic light mode:** the add-on follows your device's light or dark setting (dark remains the default look in the screenshots).

## 0.23.1

- **Mood** field for each picture (editor Info > Details > Mood). Shown in Now Playing and matched by the Library search. Stored in the sidecar.

## 0.23.0

- **Several named crops per picture:** in the editor's Crop tab, save the current crop under a name, switch between saved crops, delete them. Each remembers its rotation and straighten. Stored in the sidecar; the original is never changed.
- **TV unreachable notification** (Settings > Notifications, off by default): sends a message through a Home Assistant notify service when pictures keep failing to reach a TV that is on, after the number of minutes you choose, and again when it recovers. Includes a test button.

## 0.22.1

- Art brightness: new **Smoothing** setting (default 120 seconds, 0 = off). A light sensor that jumps between readings every second (for example 0 to 24 lux) made the TV change brightness step every 20 seconds; the reading is now averaged over time first.

## 0.22.0

- **Framing mode** (Display tab, and per image with Customize): **Whole artwork** keeps the whole picture with a mat or bars (as before); **Fill the screen** crops a non-16:9 picture to 16:9 with no mat. Originals are never changed.

## 0.21.0

- Discover: new **Shape** filter next to Order: Any shape, Fits the screen (16:9, no mat needed), Landscape (mat at the sides), Wide / panoramic (mat top and bottom), Square-ish, Portrait. It hides pictures of other shapes on the current page and says how many were hidden; pictures whose size the source does not publish (The Met, Getty) are always shown. The choice is remembered with the rest of Discover's state.
- Discover: Wikimedia Commons now opens on the postcard set for the season when you switch to it (Halloween in October, Christmas from 20 November to 6 January, Easter from three weeks before Easter to a week after); any other time it opens on the first type as before. You can still pick any type.

## 0.20.5

- Library: fixed the folder buttons, add block and picture tiles sometimes showing twice. Two refreshes of the Library could overlap (for example right after switching tabs); the newer one now wins and the older one stops.

## 0.20.4

- Smithsonian: some records (many in the Portrait Gallery) list a picture the Smithsonian's image server no longer has; their cards are now hidden when the thumbnail fails to load instead of showing a broken image (page counts can still include them).

## 0.20.3

- Footer: every page now shows the installed add-on version at the bottom.
- Getty: downloads no longer fail (HTTP 400) for images smaller than 3840 px; it tries 3840, then 2730, then the full size. Any source can now list fallback sizes.
- Smithsonian: thumbnails and previews now use the ids.si.edu small "thumb" and "screen" versions (before, the full file was requested for every card, which made pages crawl), and records whose media is hosted elsewhere use the link the API gives for it.
- Dropdown lists are now alphabetical (case-insensitive): the Discover source list, each source's Type list (for example the Smithsonian museums), the artist list and the album lists.

## 0.20.2

- Smithsonian: the search now asks only for CC0 images, so the counts, pages and cards match what you can actually add (before, most results were silently dropped and a page could show one record out of 24).

## 0.20.1

- Library: the **Move…** dialogs (selected images, and the single-image editor) now offer a dropdown of your existing folders (with counts) plus a box for a new folder, instead of typing a name.
- Library: switching back to the Library tab now reloads the folders and pictures, so art you just added in Discover appears (in the folder you added it to).
- Discover: remembers the last source, type, search text, artist, order, page, destination folder and album, and comes back to them when you return to the tab or reload the page (kept in this browser).

## 0.20.0

- Discover: new **Getty Museum** source (Open Content, CC0; no key). Paintings, drawings, prints, photographs or all types, searchable by title or artist, fetched through Getty's IIIF image server at up to 3840 px.

## 0.19.2

- Presence: the add-on now remembers across restarts that it turned the TV off for an absence, so an add-on update or restart while you are away no longer leaves the TV off when you return.

## 0.19.1

- Developer aid for the upcoming Getty source: `/api/discover/getty_raw?url=...` fetches a Getty data or media URL through the add-on (those two hosts only).

## 0.19.0

- Discover: new **Smithsonian** source (American Art, Portrait Gallery, Cooper Hewitt, Freer | Sackler, Hirshhorn and more). Only CC0 images at least 1600 px wide are shown. It needs a free key from api.data.gov: paste it into the add-on Configuration (Smithsonian API key) and restart. Without a key the source shows a short explanation.

## 0.18.2

- New health check: `/api/health` reports whether the add-on can write its data and the picture share, whether its data files are readable, uptime and the last rotation error (HTTP 503 if something is wrong). Handy for a Home Assistant REST sensor or a dashboard.

## 0.18.1

- TV brightness: new "Steadiness" setting (default 0.3; 0 turns it off). The brightness only moves to a new TV step when the target is clearly past the halfway point, which stops it flickering between two neighboring steps around a threshold.

## 0.18.0

- Library: tags. Add them in the editor (Info tab > Details > Tags, separated by commas) or to many images at once with + Tag… / − Tag… in the selection bar. A row of tag chips filters the grid, search also matches tags, and Now Playing shows them. Stored in the sidecar.

## 0.17.1

- Discover: "and album" next to the destination folder also puts everything you add into a chosen album (works for server and browser downloads).

## 0.17.0

- Library: large preview (lightbox). Click the small expand button on a tile to see the picture large with its details. Arrow keys browse in the order shown (including groups); F favorite, M show more, X exclude, T show on TV, E edit, Esc close.

## 0.16.5

- Wikimedia Commons: category presets replaced by keyword searches that return many more pictures (ukiyo-e, vintage travel and Art Nouveau posters, Google Art Project, pop art, digital art; Christmas, Easter and Halloween postcards stay category based); small files are filtered out by Commons itself.

## 0.16.4

- Discover: fixed "All types" / "Search only" choices (an empty type was replaced by the default, so Cleveland "All types", Art Institute "All" and Commons "Search all" were still filtering to paintings).

## 0.16.3

- Wikimedia Commons: search results include the API status and the search text used, for troubleshooting.

## 0.16.2

- Wikimedia Commons: search results report how many files were skipped and why (license, size), to tune the category presets.

## 0.16.1

- Wikimedia Commons: category presets match files directly in the category (deepcategory pulled in unrelated pictures); a preset may also be a full search clause such as `deepcategory:"Name"`.

## 0.16.0

- Discover: new source Wikimedia Commons. Category presets (ukiyo-e, Christmas, Easter and Halloween postcards, vintage and Art Nouveau posters, Google Art Project, pop art, digital art) or free search; only public domain, CC0, CC BY and CC BY-SA files at least 1600 px wide; saves artist, license and file page; one request per second.

## 0.15.1

- Library: grouping by artist now merges name variants (e.g. "Winslow Homer" with and without nationality and dates) into one group.

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
