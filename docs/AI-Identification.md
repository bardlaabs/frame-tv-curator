# Identify pictures with Claude

Claude can look at a picture and fill in **empty** fields: artist, title, date, medium, description and mood (chosen from your [Moods list](Settings-Reference)). It names an artist or title only when it recognizes the work, never overwrites anything you typed, and does not search the web for matches. Where it is unsure it leaves the field empty.

## Set it up

1. Create a key at console.anthropic.com (and set a spend limit there too).
2. In Home Assistant open **Settings > Add-ons > Frame TV Curator > Configuration**, paste the key into **Anthropic key**, Save, and restart the add-on. This is the standard secret store for add-ons: Home Assistant keeps it, masks it, and it never appears in this add-on's web page, its settings file, the daily backups or the repository.
3. In **Settings > AI** turn on **AI identification**, pick a model and check the **Monthly spending limit** (default $10).

## Use it

- **One picture:** open it in the editor and press **Identify with AI** in the Info tab (save any edits first).
- **Many pictures:** select them in the Library and press **Identify with AI**. You are asked to confirm and see how much of the month's limit is used.

Each picture is recorded as AI-identified in its sidecar (`identification` and `origin.ai_identified`), including the model and the art movement Claude reported.

## Cost control

Spending is estimated from the tokens each call uses and totaled per calendar month in `ai_usage.json` in the add-on's data folder. When the estimate reaches the limit, identification stops until the next month or until you raise the limit. The per-million-token prices used for the estimate are in `ai.prices` in the settings file (defaults are rough; check them against Anthropic's price list). The estimate is not a bill; your Anthropic console is the authority.
