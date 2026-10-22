# Fort Mill Family Restaurant — website

One-page site for Fort Mill Family Restaurant, a small-town family diner at 1358 SC-160,
Fort Mill, SC 29715. Static, no build step: everything deployable lives in `site/`.

## Design

- **Identity — "morning at the window booth."** Coffee-dark and biscuit-cream, with the red
  band from classic diner china and a yolk yellow. Caprasimo (a Cooper-style soft serif, the
  family-restaurant face) over Libre Franklin, with Caveat as ballpoint handwriting. The mark is
  a sunny-side egg on a china-red tile. The menu is written on a green guest check; slat light
  from the film recurs as warm stripes across the paper sections.
- **Hero film.** A path-traced Blender Cycles scene: a banded diner mug backlit by low sun
  through window blinds, steam glowing where it crosses the light, sweet tea and buttered
  biscuits beside it. Every animated value is periodic, so the 8 s, 24 fps loop is seamless by
  construction; the steam is two noise layers rising half a loop apart and crossfaded so each
  resets while its weight is zero. Delivered as 10-bit AV1 with H.264 fallback at 1080p, 720p
  and a native 9:16 phone cut, with a matching poster frame.
- **Motion.** Transform-only parallax on three hero depths (film 0.42×, copy 0.72×, stamp
  1.25×) plus independent layers further down; layers animate only near the viewport, the film
  pauses off-screen, and `prefers-reduced-motion` turns parallax and autoplay off.

## Content rules

Facts come from the business's Google listing: address, phone, plus code, price band, rating
and review count, menu highlights and the "Popular" tags, service options. Weekly hours
(Tue–Fri 7 AM–3 PM, Sat–Sun 6 AM–3 PM, closed Monday) were supplied with the brief; they live
once in the hours table's data attributes, which drive the "open now" line (computed in US
Eastern time) and are mirrored in the JSON-LD. The menu board (categories and their serving
notes), the three seafood prices and the consumer advisory come from the restaurant's online
ordering menu, also supplied with the brief; the ordering platform's generic dish blurbs are
not used. Reviews are quoted verbatim. No awards or history are stated. Map coordinates in the
JSON-LD are the decoded plus code.

## Layout

- `site/` — the page (`index.html`, `js/main.js`), self-hosted subset fonts, media, icons.
- `render/` — the hero film: `scene.py` (Cycles scene), `post.py` (grade), `encode.sh`,
  `stills.py` (posters, backdrop), `about_shot.py` / `about_images.py` (About photo).
- `tools/make-assets.cjs` — icons and the 1200×630 OG card, drawn with the real web fonts.
- `tools/verify.cjs` — Playwright checks: film autoplay/loop/poster, parallax depths,
  tap-to-call and directions links, SEO tags, phone layout, reduced motion.
- `tools/loopcheck.py` — frame-difference check across the loop seam.

## Deploying

The site's home is **https://wyattcawley18.github.io/fort-mill-family-restaurant/**, from the
`wyattcawley18/fort-mill-family-restaurant` repository (Settings → Pages → Source: GitHub
Actions). `.github/workflows/pages.yml` publishes `site/` there at the Pages root, stamping the
absolute URL into canonical/OG/sitemap, and then runs `tools/verify.cjs` and Lighthouse against
the live URL. A custom domain can be added in the same Pages settings.

The same workflow in `wyattcawley18/Main`, whose Pages root serves another site from the
default branch, republishes that site unchanged and puts a redirect to the home at
`/fort-mill-family-restaurant/` (a full copy only if the home isn't answering).
Re-rendering the film: run the *Render hero film* workflow manually; it renders 192 frames
across runners and commits the encodes to `site/media/`.
