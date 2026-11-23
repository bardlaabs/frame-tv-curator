# Optional: Discover

Find public-domain art from museum collections and add it to your library, with metadata and license filled into the sidecar.

## Sources
- **Reframed**: a curated gallery of public-domain art.
- **Art Institute of Chicago**: public-domain works from the museum's open-access API (CC0 data). Images come at the museum's own 3000 px download size (the largest it publishes), downloaded by your browser and uploaded to the add-on.
- **The Metropolitan Museum of Art**: public-domain works (CC0). Choose Highlights or a department, or search by keyword. The add-on downloads the original file (often several thousand pixels wide). A page can show fewer than 24 items because only public-domain objects with a picture are listed.
- **Cleveland Museum of Art**: open-access works (CC0) at up to about 3400 px, with the museum's description and credit line.
- **Wikimedia Commons**: free-licensed pictures (public domain, CC0, CC BY, CC BY-SA only) by category: ukiyo-e, holiday postcards, vintage posters, Google Art Project, pop art, or any search. Pictures come at up to 3840 px wide; the artist and license are saved with each one (CC BY and CC BY-SA need credit, which the placard and Info tab show). Requests to Commons are throttled to one per second.
- **NASA Image Library**: space and Earth images (generally public domain). Pick a topic or search; images under 1600 px wide are skipped, so a page can show fewer than 24 items.

## Using it
1. Open **Library > Discover**, choose a source, type and order, or search by keyword or artist.
2. Tick items (a duplicate check warns about images you already have) and choose the destination folder.
3. Use the preview button for a full-screen look with details before adding.
4. A toast summarizes how many were added or skipped.

Please keep the polite request rate; the add-on throttles requests to museum servers.

## Adding to an album

Next to **Add to folder** is **and album**. Pick an album there and everything you add is also put in that album (the pictures still live in the folder you chose). The list shows the albums that existed when you opened Discover; reload the page after creating a new album.

## Smithsonian

Open-access art and design from the Smithsonian museums (CC0, at least 1600 px wide). It needs a free API key: request one at https://api.data.gov/signup/, paste it into the add-on Configuration (Smithsonian API key), save and restart the add-on. Pick a museum from the Type menu or search all of them.

## Getty Museum

Open Content from the J. Paul Getty Museum (CC0, no key): choose Paintings, Drawings, Prints, Photographs or All types, or search by title or artist. Images are fetched at up to 3840 px on the long side through the Getty's IIIF image server. The accession number goes into the credit line.

Discover remembers where you were (source, type, search, artist, order, page, folder and album) in this browser.
