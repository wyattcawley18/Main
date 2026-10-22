// Generates raster brand assets with headless Chromium so they use the real
// web fonts: favicon PNGs, touch/maskable icons and the 1200x630 OG card.
//   NODE_PATH=$(npm root -g) node tools/make-assets.cjs <graded-frame.png>
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const site = path.join(__dirname, "..", "site");
const frame = process.argv[2] || path.join(site, "media", "frame-150.png");
const font = (f) => "data:font/woff2;base64," + fs.readFileSync(path.join(site, "fonts", f)).toString("base64");
const img = (p) => "data:image/" + (p.endsWith(".png") ? "png" : "jpeg") + ";base64," + fs.readFileSync(p).toString("base64");

const moon = (size, pad) => `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}">
  <defs><radialGradient id="g" cx="38%" cy="62%" r="70%"><stop offset="0" stop-color="#ffd58a"/><stop offset="1" stop-color="#f09a2e"/></radialGradient>
  <mask id="m"><rect width="64" height="64" fill="#fff"/><circle cx="41.5" cy="24" r="17.5" fill="#000"/></mask></defs>
  <rect width="64" height="64" fill="#140f0b"/>
  <g transform="translate(32 32) scale(${pad}) translate(-32 -32)">
    <circle cx="29" cy="35" r="20" fill="url(#g)" mask="url(#m)"/>
    <path d="M46 19.5l1.8 4.1 4.1 1.8-4.1 1.8-1.8 4.1-1.8-4.1-4.1-1.8 4.1-1.8z" fill="#ffd58a"/>
  </g>
</svg>`;

const css = `
@font-face{font-family:F;src:url(${font("fraunces.woff2")});font-weight:300 700}
@font-face{font-family:F;src:url(${font("fraunces-italic.woff2")});font-style:italic;font-weight:300 700}
@font-face{font-family:S;src:url(${font("big-shoulders.woff2")});font-weight:600 800}
html,body{margin:0;background:#0f0c0a}`;

const og = `<!doctype html><html><head><style>${css}
.c{position:relative;width:1200px;height:630px;overflow:hidden;color:#f4e7d3;font-family:F}
.bg{position:absolute;inset:0;background:url(${img(frame)}) 72% 46%/cover}
.sh{position:absolute;inset:0;background:linear-gradient(90deg,rgba(15,12,10,.92) 0%,rgba(15,12,10,.7) 38%,rgba(15,12,10,.05) 66%),linear-gradient(0deg,rgba(15,12,10,.75),rgba(15,12,10,0) 40%)}
.in{position:absolute;left:72px;top:64px;bottom:60px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:14px}
.tag{font:800 17px/1 S;letter-spacing:.3em;color:#f4a63c;border:1.5px solid rgba(244,166,60,.6);padding:7px 6px 6px 11px;border-radius:4px}
h1{margin:auto 0 0;font-weight:520;font-size:150px;line-height:.82;letter-spacing:-.035em}
h1 span{display:block}
h1 em{display:block;font-style:italic;font-weight:400;color:#ffd28a;padding-left:62px;text-shadow:0 0 40px rgba(244,166,60,.35)}
p{margin:34px 0 0;font:700 22px/1.3 S;letter-spacing:.22em;text-transform:uppercase;color:#f4e7d3}
p b{color:#f4a63c;font-weight:800}
</style></head><body><div class="c"><div class="bg"></div><div class="sh"></div>
<div class="in"><div class="top">${moon(52, 1).replace('<rect width="64" height="64" fill="#140f0b"/>', "")}<span class="tag">CHS</span></div>
<h1><span>Bedford</span><em>Falls</em></h1>
<p>Bar &amp; Grill <b>✦</b> 430 Meeting St <b>✦</b> Kitchen open late</p></div></div></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const icon = async (file, size, pad, round) => {
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(`<html><body style="margin:0;background:transparent">${moon(size, pad).replace(
      '<rect width="64" height="64" fill="#140f0b"/>',
      round ? '<rect width="64" height="64" rx="15" fill="#140f0b"/>' : '<rect width="64" height="64" fill="#140f0b"/>'
    )}</body></html>`);
    await page.screenshot({ path: path.join(site, "img", file), omitBackground: true });
  };
  await icon("favicon-32.png", 32, 1, true);
  await icon("apple-touch-icon.png", 180, 0.86, false);
  await icon("icon-192.png", 192, 0.86, true);
  await icon("icon-512.png", 512, 0.86, true);
  await icon("icon-maskable-512.png", 512, 0.68, false);

  await page.setViewportSize({ width: 1200, height: 630 });
  await page.setContent(og, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(site, "img", "og.jpg"), type: "jpeg", quality: 86 });
  await browser.close();
  console.log("assets written");
})();
