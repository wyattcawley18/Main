# Bedford Falls CHS — website

One-page site for Bedford Falls, a late-night bar & grill at 430 Meeting St, Charleston, SC.

- `site/` — the deployable static site (no build step).
- `render/` — the hero film: a Blender Cycles scene (`scene.py`), grade (`post.py`),
  encodes (`encode.sh`) and poster stills (`stills.py`).
- `.github/workflows/render-hero.yml` — renders the 240-frame loop across 20 runners
  and commits the encoded media to `site/media/`.
