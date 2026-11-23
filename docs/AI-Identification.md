# Identify pictures with Claude

Claude can look at a picture and fill in empty fields, and lets you replace wrong ones: artist, title, date, medium, description, mood, season and occasion, and it adds tags (to yours, never replacing them) (chosen from your [Moods list](Settings-Reference)). It names an artist or title only when it recognizes the work, never changes anything you typed unless you say so (see below), and does not search the web for matches. Where it is unsure it leaves the field empty.

## Set it up

1. Create a key at console.anthropic.com (and set a spend limit there too).
2. In Home Assistant open **Settings > Add-ons > Frame TV Curator > Configuration**, paste the key into **Anthropic key**, Save, and restart the add-on. This is the standard secret store for add-ons: Home Assistant keeps it, masks it, and it never appears in this add-on's web page, its settings file, the daily backups or the repository.
3. In **Settings > AI** turn on **AI identification**, pick a model and check the **Monthly spending limit** (default $10).

## Use it

- **One picture:** open it in the editor and press **Identify with AI** in the Info tab (save any edits first).
- **Many pictures:** select them in the Library and press **Identify with AI**. You are asked to confirm and see how much of the month's limit is used.

Each picture is recorded as AI-identified in its sidecar (`identification` and `origin.ai_identified`), including the model and the art movement Claude reported.

## Checking against museums

Claude's answer is checked, not trusted. It uses what is already filled in (artist, title, date, file name) as a lead, and may confirm it or correct it. Then the add-on searches the Art Institute of Chicago, The Met, Cleveland, Getty and Smithsonian (museums first) and, last, Wikimedia Commons for a matching record.

- **One clear museum match:** its details are used (the museum's wording wins over Claude's), and a link to the museum record is added to the picture's links and source.
- **Several possible matches:** you are asked. Each option shows the source, title, artist, date and a link to open the record. You can also choose "None of these" to keep Claude's answer without a source link. In a bulk run, pictures needing a choice are shown one after another at the end.
- **No match:** Claude's answer fills the empty fields, marked as not checked against a museum.

Anything you already typed is kept. The picture's `identification` records whether a museum record was matched.

## Refresh from EXIF (no AI)

In the editor's Info tab (or on a Library selection) **Refresh from EXIF** re-reads the photo's EXIF: date, camera, GPS location (and the place name) and photographer. It replaces those fields only.

## Cost control

Spending is estimated from the tokens each call uses and totaled per calendar month in `ai_usage.json` in the add-on's data folder. When the estimate reaches the limit, identification stops until the next month or until you raise the limit. The per-million-token prices used for the estimate are in `ai.prices` in the settings file (defaults are rough; check them against Anthropic's price list). The estimate is not a bill; your Anthropic console is the authority.


## Replacing existing details

Empty fields are filled automatically. If the result differs from something already filled in (for example the old title was wrong), a review window shows each field with what is there now and the new value. Tick **Overwrite** for the fields you want replaced, or use **Keep all current** / **Overwrite all**, then Apply. Tags are added to yours. In a batch, these pictures are put aside and shown one by one at the end.
