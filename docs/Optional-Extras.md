# Optional: Bird Frame and e-paper

Both are off by default and are set on the **Settings** tab.

## Bird Frame interleave

![Bird Frame settings](images/ui-set-bird.png)
Mixes bird pictures into the rotation.

### Set it up, step by step
1. Install and start the Bird Frame add-on if you want the live collage (set its own interval long so it does not change the TV by itself).
2. In Frame TV Curator open **Settings > Bird Frame interleave** and tick **Interleave birds**.
3. Choose how often: **Every N art changes** (default 10) or **...or every N minutes**.
4. Set **Show it for (minutes)** (default 10; 0 = one change slot).
5. Choose **Bird source**: **Live Bird Frame collage** or **Image from a folder** (then pick the **Bird folder**).
6. Click **Save settings**. Use **Show bird picture now** to test.

## E-paper card

![E-paper settings](images/ui-set-epaper.png)
Sends a small card (current title, artist and more) to an e-paper display through Home Assistant.

1. Open **Settings > E-paper card** and tick **Send info to e-paper**.
2. Enter your display's **Device ID**.
3. Choose a **Style**: Gallery, Inverted or Grid.
4. Click **Save settings**.

### The three styles

The card is 522 x 152 pixels and uses only black, white and red, so it works on a tri-color e-paper display. Long titles are wrapped on whole words and shrunk to fit. The samples below are enlarged 2x.

**Gallery** (black text on white, the artist in red, the date and medium in a column on the right):

![Gallery style](images/epaper-gallery-art.png)

**Inverted** (white text on black, same layout):

![Inverted style](images/epaper-inverted-art.png)

**Grid** (a thin frame, with the date in red):

![Grid style](images/epaper-grid-art.png)

**A long title** wraps onto up to three lines and the text steps down in size to fit (Gallery shown):

![Long title](images/epaper-gallery-long.png)

**A photograph** shows its title and date (the e-paper card has a line for the medium, which photographs do not have, and it does not print the place name):

| Gallery | Inverted | Grid |
|---|---|---|
| ![Gallery photo](images/epaper-gallery-photo.png) | ![Inverted photo](images/epaper-inverted-photo.png) | ![Grid photo](images/epaper-grid-photo.png) |
