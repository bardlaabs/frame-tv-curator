# Docs tooling

Scripts that regenerate the wiki images in `docs/images/`. They use sample art generated on the fly, never real library or museum images.

Requirements: Python 3, Pillow, numpy, Playwright (Python) and Google Chrome.

- `python3 tools/make_sample_renders.py` renders the sample paintings through `curator.render` and saves close-up crops (placards, mats, liner, bevel, tints, overscan, one/two/three-line mat placards).
- `python3 tools/make_screenshots.py` builds demo data with `tools/make_demo_data.py`, starts a local dry-run add-on and captures the UI screenshots and card close-ups at 2x. Environment options: `PORT`, `CHROME` (path to Chrome), `VERSION_LABEL` (footer text).
- `python3 tools/make_demo_data.py [DIR]` creates 12 sample pictures with sidecars.

After regenerating, commit `docs/images`. Pushing to `main` publishes the wiki through `.github/workflows/wiki-sync.yml`.
