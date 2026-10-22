# Bedford Falls CHS — website

One-page site for Bedford Falls, a late-night bar & grill at 430 Meeting St, Charleston, SC.
Static, no build step: everything deployable lives in `site/`.

## Design

- **Identity — "late night on Meeting Street."** Warm ink black, string-light amber and a
  Charleston haint-blue accent; Fraunces (soft, vintage-menu serif) with Big Shoulders signage
  caps; a crescent-and-star mark that nods to the crescent on the South Carolina flag. Arched
  photo frames echo Charleston doorways; menu art is drawn as neon tubing that flickers on.
- **Hero film.** A path-traced Blender Cycles scene — a backlit pint on a patio table, votive
  bokeh in front, oval anamorphic bokeh from string lights and gas lanterns behind, palmetto
  silhouettes. Every animated value is periodic, so the 10 s, 24 fps loop is seamless by
  construction. Delivered as 10-bit AV1 with H.264 fallback at 1080p, 720p and a native 9:16
  phone cut, with a matching poster frame.
- **Motion.** Transform-only parallax on three depths (film at 0.42×, copy at 0.72×, badge at
  1.28×) plus independent layers further down; layers animate only near the viewport, the film
  pauses off-screen, and `prefers-reduced-motion` turns parallax and autoplay off.

## Content rules

Facts come from the business's Google listing: address, phone, closing time, price band,
rating and review count, popular dishes, services. Reviews are quoted verbatim. No prices,
awards, history or opening hours beyond what is listed are stated.

## Layout

- `site/` — the page (`index.html`, `js/main.js`), self-hosted subset fonts, media, icons.
- `render/` — the hero film: `scene.py` (Cycles scene), `post.py` (grade), `encode.sh`,
  `stills.py` (posters), `about_shot.py` / `about_images.py` (About photo).
- `tools/make-assets.cjs` — icons and the 1200×630 OG card, drawn with the real web fonts.
- `tools/verify.cjs` — Playwright checks: film autoplay/loop/poster, parallax depths,
  tap-to-call and directions links, SEO tags, phone layout, reduced motion.

## Deploying

GitHub Pages, source **GitHub Actions** (Settings → Pages). `deploy` stamps the absolute URL
into canonical/OG/sitemap, publishes `site/`, then runs `tools/verify.cjs` and Lighthouse
against the live URL. Re-rendering the film: run the *Render hero film* workflow; it renders
240 frames across runners and commits the encodes to `site/media/`.
