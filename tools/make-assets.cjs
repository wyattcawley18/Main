// Generates raster brand assets with headless Chromium so they use the real
// web fonts: favicon PNGs, touch/maskable icons and the 1200x630 OG card.
//   NODE_PATH=$(npm root -g) node tools/make-assets.cjs [og-source.jpg]
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const site = path.join(__dirname, "..", "site");
const frame = process.argv[2] || path.join(__dirname, "..", "render", "out", "og-src.jpg");
const font = (f) => "data:font/woff2;base64," + fs.readFileSync(path.join(site, "fonts", f)).toString("base64");
const img = (p) => "data:image/" + (p.endsWith(".png") ? "png" : "jpeg") + ";base64," + fs.readFileSync(p).toString("base64");

const EGG = `<path d="M31.6 9.5c7.7-.4 12.4 4.6 16.4 8.3 4.4 4 8.7 7.4 8.2 14.6-.5 7.5-5.6 10.6-8.6 15.4-3.1 5-7.4 8.4-14.2 8.2-7.3-.2-11.6-4.6-15.6-8.4C13.6 43.6 8.2 40.3 8 32.6c-.2-7.2 4.5-11.4 8.1-15.3 4.1-4.5 7.6-7.4 15.5-7.8z" fill="#fbf5ea"/><circle cx="33.5" cy="31.5" r="11.5" fill="#f4b23a"/><circle cx="33.5" cy="31.5" r="11.5" fill="none" stroke="#e08a1e" stroke-width="2.2"/><ellipse cx="29.6" cy="27.4" rx="3.6" ry="2.4" transform="rotate(-35 29.6 27.4)" fill="#fff7d6" opacity=".85"/>`;

// pad scales the egg inside the tile; rx rounds the tile (0 = full bleed for
// platforms that apply their own mask)
const badge = (size, pad, rx) => `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="${size}" height="${size}">
  <rect width="64" height="64" rx="${rx}" fill="#b23a2e"/>
  <g transform="translate(32 32) scale(${pad}) translate(-32 -32)">${EGG}</g>
</svg>`;

const css = `
@font-face{font-family:C;src:url(${font("caprasimo.woff2")})}
@font-face{font-family:F;src:url(${font("franklin.woff2")});font-weight:400 800}
html,body{margin:0;background:#1c110b}`;

const og = `<!doctype html><html><head><style>${css}
.c{position:relative;width:1200px;height:630px;overflow:hidden;color:#f6ead6;font-family:F}
.bg{position:absolute;inset:0;background:url(${img(frame)}) 0% 55%/118% auto}
.sh{position:absolute;inset:0;background:linear-gradient(90deg,rgba(28,17,11,.93) 0%,rgba(28,17,11,.78) 34%,rgba(28,17,11,.12) 62%,rgba(28,17,11,0) 75%),linear-gradient(0deg,rgba(28,17,11,.6),rgba(28,17,11,0) 35%)}
.in{position:absolute;left:70px;top:62px;bottom:58px;width:620px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:16px;font:800 16px/1 F;letter-spacing:.26em;text-transform:uppercase}
.top::after{content:"";flex:1;height:3px;background:#b23a2e;box-shadow:0 7px 0 #b23a2e;max-width:90px}
h1{margin:auto 0 0;font:400 118px/.9 C;letter-spacing:-.005em}
h1 span{display:block;margin-top:12px;font-size:52px;line-height:1;color:#f4b23a}
p{margin:30px 0 0;font:700 22px/1.35 F;color:rgba(246,234,214,.92)}
p b{color:#f4b23a;font-weight:800}
.band{position:absolute;left:0;right:0;bottom:0;height:12px;background:#b23a2e;box-shadow:inset 0 3px 0 rgba(246,234,214,.6)}
</style></head><body><div class="c"><div class="bg"></div><div class="sh"></div>
<div class="in"><div class="top">${badge(56, 1, 14)}<span>Fort Mill, SC · SC-160</span></div>
<h1>Fort Mill<span>Family Restaurant</span></h1>
<p>Biscuits &amp; gravy, grits, home fries and sweet tea<br>1358 SC-160 <b>·</b> (803) 548-2336</p></div><div class="band"></div></div></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  const icon = async (file, size, pad, rx) => {
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(`<html><body style="margin:0;background:transparent">${badge(size, pad, rx)}</body></html>`);
    await page.screenshot({ path: path.join(site, "img", file), omitBackground: true });
  };
  await icon("favicon-32.png", 32, 1.08, 15);
  await icon("apple-touch-icon.png", 180, 0.9, 0);
  await icon("icon-192.png", 192, 0.9, 15);
  await icon("icon-512.png", 512, 0.9, 15);
  await icon("icon-maskable-512.png", 512, 0.7, 0);

  await page.setViewportSize({ width: 1200, height: 630 });
  await page.setContent(og, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: path.join(site, "img", "og.jpg"), type: "jpeg", quality: 86 });
  await browser.close();
  console.log("assets written");
})();
