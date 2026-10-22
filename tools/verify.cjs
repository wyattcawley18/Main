// End-to-end checks for the site: hero film, parallax, links, SEO, mobile.
//   NODE_PATH=$(npm root -g) node tools/verify.cjs <url> [screenshot-dir] [--engines=chromium,webkit]
// Exits non-zero if any check fails.
const { chromium, webkit, devices } = require("playwright");
const fs = require("fs");
const path = require("path");

const url = process.argv[2];
const shots = process.argv[3] && !process.argv[3].startsWith("--") ? process.argv[3] : null;
const engines = (process.argv.find((a) => a.startsWith("--engines=")) || "--engines=chromium").split("=")[1].split(",");
if (shots) fs.mkdirSync(shots, { recursive: true });

let failed = 0;
const ok = (cond, msg, extra = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${msg}${extra ? "  — " + extra : ""}`);
  if (!cond) failed++;
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ty = (t) => {
  if (!t || t === "none") return 0;
  const v = t.slice(t.indexOf("(") + 1, -1).split(",").map(Number);
  return t.startsWith("matrix3d") ? v[13] : v[5];
};

// wait in animation frames (not wall-clock) until an element's transform stops changing
async function settle(page, sel) {
  let last = null, stable = 0;
  for (let i = 0; i < 90; i++) {
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const v = await page.evaluate((s) => getComputedStyle(document.querySelector(s)).transform, sel);
    if (v === last) { if (++stable >= 3) return v; } else { stable = 0; last = v; }
  }
  return last;
}

async function videoState(page) {
  return page.evaluate(() => {
    const v = document.getElementById("hero-video");
    return {
      src: v.currentSrc, w: v.videoWidth, h: v.videoHeight, t: v.currentTime, paused: v.paused,
      loop: v.loop, muted: v.muted, autoplay: v.hasAttribute("autoplay"), playsinline: v.hasAttribute("playsinline"),
      poster: v.poster, ready: v.readyState, duration: v.duration,
      playingClass: document.querySelector(".hero").classList.contains("is-playing"),
    };
  });
}

async function desktop(browser, name) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && !/maps|google|gstatic/i.test(m.text()) && errors.push(m.text()));
  const bad = [];
  page.on("response", (r) => r.status() >= 400 && !/google|gstatic/.test(r.url()) && bad.push(`${r.status()} ${r.url()}`));
  const res = await page.goto(url, { waitUntil: "load" });
  ok(res.status() === 200, `[${name}] page responds 200`, String(res.status()));

  // hero film
  await page.waitForFunction(() => { const v = document.getElementById("hero-video"); return v && !v.paused && v.currentTime > 0.6; }, null, { timeout: 20000 }).catch(() => {});
  const v1 = await videoState(page);
  ok(!v1.paused && v1.t > 0.5, `[${name}] hero film autoplays`, `t=${v1.t.toFixed(2)}s src=${v1.src.split("/").pop()}`);
  ok(v1.muted && v1.loop && v1.autoplay && v1.playsinline, `[${name}] muted + loop + autoplay + playsinline`);
  ok(v1.h >= 1080, `[${name}] desktop stream is ≥1080p`, `${v1.w}x${v1.h}`);
  ok(!!v1.poster, `[${name}] poster frame set`, v1.poster.split("/").pop());
  ok(v1.playingClass, `[${name}] film faded in over poster`);
  // loop: wait past the loop point and confirm time wrapped while still playing
  const dur = v1.duration || 10;
  const startT = v1.t;
  let wrapped = false;
  for (let i = 0; i < Math.ceil(dur * 2) + 6; i++) {
    await sleep(500);
    const t = await page.evaluate(() => document.getElementById("hero-video").currentTime);
    if (t + 0.5 < startT || (i > 4 && t < 0.6)) { wrapped = true; break; }
  }
  const v2 = await videoState(page);
  ok(wrapped && !v2.paused, `[${name}] loops (time wrapped, still playing)`, `duration=${dur.toFixed(2)}s`);
  if (shots) await page.screenshot({ path: path.join(shots, `${name}-hero.png`) });

  // parallax
  const before = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-media")).transform);
  await page.evaluate(() => window.scrollTo({ top: 400, behavior: "instant" }));
  await sleep(300);
  const after = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-media")).transform);
  const moved = ty(after) - ty(before);
  ok(Math.abs(moved - 400 * (1 - 0.42)) < 12, `[${name}] hero video layer at 0.42× scroll`, `Δ=${moved.toFixed(1)}px for 400px`);
  const fg = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-stamp")).transform);
  ok(Math.abs(ty(fg) - 400 * (1 - 1.25)) < 12, `[${name}] foreground stamp at 1.25× scroll (in front of the page)`, `ty=${ty(fg).toFixed(1)}`);
  const copy = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-content")).transform);
  ok(Math.abs(ty(copy) - 400 * (1 - 0.72)) < 12, `[${name}] hero copy at 0.72× scroll (middle depth)`, `ty=${ty(copy).toFixed(1)}`);
  for (const [sel, label] of [[".art-photo .parallax-inner", "about photo"], [".art-note", "about note"], [".check-wrap", "guest check"], [".quotes .quote:nth-child(3)", "review card"], [".visit-bg", "visit backdrop"]]) {
    const speed = await page.evaluate((s) => parseFloat(document.querySelector(s).dataset.speed), sel);
    await page.evaluate((s) => document.querySelector(s).scrollIntoView({ block: "start", behavior: "instant" }), sel);
    const t1 = await settle(page, sel);
    await page.evaluate(() => window.scrollBy({ top: 240, behavior: "instant" }));
    const t2 = await settle(page, sel);
    const d = ty(t2) - ty(t1), want = 240 * (1 - speed);
    ok(Math.abs(d - want) < 3, `[${name}] ${label} layer moves at ${speed}× scroll`, `Δ=${d.toFixed(1)}px, expected ${want.toFixed(1)}px for 240px`);
  }
  const offscreenPaused = await page.evaluate(() => document.getElementById("hero-video").paused);
  ok(offscreenPaused, `[${name}] film pauses when scrolled out of view`);
  if (shots) {
    for (const id of ["about", "menu", "reviews", "visit"]) {
      await page.evaluate((i) => document.getElementById(i).scrollIntoView({ behavior: "instant" }), id);
      await sleep(1200);
      await page.screenshot({ path: path.join(shots, `${name}-${id}.png`) });
    }
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "instant" }));
    await sleep(900);
    await page.screenshot({ path: path.join(shots, `${name}-footer.png`) });
  }

  // links
  const links = await page.evaluate(() => [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href")));
  const tel = links.filter((h) => h.startsWith("tel:"));
  ok(tel.length >= 6 && tel.every((h) => h === "tel:+18035482336"), `[${name}] phone links are tap-to-call`, `${tel.length} × tel:+18035482336`);
  const dir = links.filter((h) => h.includes("google.com/maps/dir/?api=1&destination="));
  ok(dir.length >= 4 && dir.every((h) => h.includes("1358%20SC-160") && h.includes("29715")), `[${name}] addresses open Google Maps directions`, `${dir.length} links`);
  const addrLinks = await page.evaluate(() => { const a = [...document.querySelectorAll("a")].filter((x) => /1358 SC-160/.test(x.textContent)); return a.length >= 2 && a.every((x) => x.href.includes("/maps/dir/")); });
  const phoneText = await page.evaluate(() => [...document.querySelectorAll("a")].filter((x) => /548-2336/.test(x.textContent)).every((x) => x.getAttribute("href") === "tel:+18035482336"));
  ok(phoneText, `[${name}] every printed phone number is a tel: link`);
  ok(addrLinks, `[${name}] every printed address is a directions link`);
  const dd = await page.evaluate(() => [...document.querySelectorAll('a[href*="doordash.com"]')].map((a) => ({ href: a.getAttribute("href"), target: a.target, rel: a.rel })));
  ok(dd.length >= 5 && dd.every((a) => a.href === "https://www.doordash.com/store/fort-mill-family-restaurant-fort-mill-36321367/" && a.target === "_blank" && /noopener/.test(a.rel)),
    `[${name}] order-online links go to the DoorDash store`, `${dd.length} links`);
  const anchors = links.filter((h) => h.startsWith("#") && h.length > 1);
  const missing = await page.evaluate((a) => a.filter((h) => !document.querySelector(h)), anchors);
  ok(missing.length === 0, `[${name}] in-page anchors resolve`, missing.join(",") || `${anchors.length} anchors`);

  // SEO
  const seo = await page.evaluate(() => {
    const m = (s) => document.querySelector(s)?.getAttribute("content") || document.querySelector(s)?.getAttribute("href") || "";
    let ld = null;
    try { ld = JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent); } catch (e) {}
    return { title: document.title, desc: m('meta[name="description"]'), canonical: m('link[rel="canonical"]'), ogImage: m('meta[property="og:image"]'), ogTitle: m('meta[property="og:title"]'), tw: m('meta[name="twitter:card"]'), ld, h1: document.querySelectorAll("h1").length, lang: document.documentElement.lang };
  });
  ok(seo.title.length > 20 && seo.desc.length > 80, `[${name}] title + meta description`, `${seo.title.length}/${seo.desc.length} chars`);
  ok(/^https?:\/\//.test(seo.canonical) || url.startsWith("http://localhost") || url.startsWith("http://127."), `[${name}] canonical is absolute`, seo.canonical);
  ok(!!seo.ld && seo.ld["@type"] === "Restaurant" && seo.ld.telephone === "+1-803-548-2336" && seo.ld.address.streetAddress === "1358 SC-160", `[${name}] JSON-LD restaurant data parses`);
  const menu = await page.evaluate(() => ({
    prices: [...document.querySelectorAll(".prices div")].map((d) => `${d.querySelector("dt").textContent}=${d.querySelector("dd").textContent}`),
    board: document.querySelectorAll(".board dt").length,
    advisory: /undercooked meat can be hazardous/.test(document.querySelector(".board-note").textContent),
  }));
  ok(menu.prices.join("|") === "Calabash Shrimp=$14.49|Fried Shrimp & Flounder Combo=$16.49|Fried Filet of Flounder=$14.49" && menu.board >= 15 && menu.advisory,
    `[${name}] menu: listed prices, full board, consumer advisory`, `${menu.prices.length} prices, ${menu.board} board lines`);
  const seafood = ((seo.ld && seo.ld.hasMenu && seo.ld.hasMenu.hasMenuSection) || []).find((x) => x.name === "Seafood");
  ok(!!seafood && seafood.hasMenuItem.every((i) => i.offers && i.offers.priceCurrency === "USD"), `[${name}] JSON-LD menu carries the listed prices`);
  const oh = (seo.ld && seo.ld.openingHoursSpecification) || [];
  const openDays = oh.flatMap((o) => o.dayOfWeek);
  ok(openDays.length === 6 && !openDays.includes("Monday") && oh.every((o) => o.closes === "15:00"), `[${name}] JSON-LD opening hours (Tue–Sun, closes 15:00)`, oh.map((o) => `${o.dayOfWeek.join("/")} ${o.opens}-${o.closes}`).join("; "));
  ok(seo.h1 === 1 && seo.lang === "en-US" && seo.tw === "summary_large_image", `[${name}] one h1, lang, twitter card`);
  if (/^https?:\/\//.test(seo.ogImage) && !seo.ogImage.includes("__SITE_URL__")) {
    const r = await page.request.get(seo.ogImage);
    ok(r.status() === 200 && /image\/jpeg/.test(r.headers()["content-type"]), `[${name}] OG image is reachable`, `${r.status()} ${seo.ogImage}`);
  } else {
    ok(url.includes("localhost") || url.includes("127.0.0.1"), `[${name}] OG image URL absolute`, seo.ogImage);
  }
  // map: nothing from Google loads until asked; the button swaps in the embed
  const mapReqs = bad.length;
  await page.evaluate(() => document.querySelector(".map-load").click());
  const iframe = await page.waitForSelector("#map iframe", { timeout: 5000 }).then((h) => h.getAttribute("src")).catch(() => "");
  ok(/google\.com\/maps\?q=.*output=embed/.test(iframe), `[${name}] map embed loads on demand`, iframe.slice(0, 60));
  ok(errors.length === 0, `[${name}] no console errors`, errors.slice(0, 3).join(" | "));
  ok(bad.length === 0, `[${name}] no failed same-site requests`, bad.slice(0, 3).join(" | "));
  await ctx.close();
}

async function mobile(browser, name, device) {
  const ctx = await browser.newContext({ ...device });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "load" });
  await page.waitForFunction(() => { const v = document.getElementById("hero-video"); return v && !v.paused && v.currentTime > 0.4; }, null, { timeout: 20000 }).catch(() => {});
  const v = await videoState(page);
  ok(!v.paused && v.t > 0.3, `[${name}] film autoplays inline on phone`, `t=${v.t.toFixed(2)} src=${v.src.split("/").pop()}`);
  ok(/portrait/.test(v.src), `[${name}] phone gets the 9:16 cut`, `${v.w}x${v.h}`);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
  ok(overflow <= 0, `[${name}] no horizontal scroll`, `${overflow}px`);
  const dock = await page.evaluate(() => ({ display: getComputedStyle(document.querySelector(".dock")).display, links: [...document.querySelectorAll(".dock a")].map((a) => a.textContent.trim()) }));
  ok(dock.display !== "none" && dock.links.join("|") === "Call|Order|Directions", `[${name}] call/order/directions dock visible`, dock.links.join(" · "));
  const before = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-media")).transform);
  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "instant" }));
  await sleep(300);
  const after = await page.evaluate(() => getComputedStyle(document.querySelector(".hero-media")).transform);
  ok(Math.abs(ty(after) - ty(before) - 300 * 0.58) < 12, `[${name}] parallax runs on mobile`, `Δ=${(ty(after) - ty(before)).toFixed(1)}px`);
  const small = await page.evaluate(() => [...document.querySelectorAll(".btn, .dock a, .video-toggle")].filter((b) => b.offsetParent && b.getBoundingClientRect().height < 44).map((b) => b.className));
  ok(small.length === 0, `[${name}] tap targets ≥ 44px`, small.join(","));
  if (shots) {
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await sleep(600);
    await page.screenshot({ path: path.join(shots, `${name}-hero.png`) });
    for (const id of ["about", "menu", "reviews", "visit"]) {
      await page.evaluate((i) => document.getElementById(i).scrollIntoView({ behavior: "instant" }), id);
      await sleep(1100);
      await page.screenshot({ path: path.join(shots, `${name}-${id}.png`) });
    }
    await page.evaluate(() => window.scrollTo({ top: document.body.scrollHeight, behavior: "instant" }));
    await sleep(900);
    await page.screenshot({ path: path.join(shots, `${name}-footer.png`) });
  }
  await ctx.close();
}

async function reduced(browser, name) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, reducedMotion: "reduce" });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "load" });
  await sleep(1500);
  const v = await videoState(page);
  ok(v.paused && !v.autoplay, `[${name}] reduced motion: film stays on poster`);
  await page.evaluate(() => window.scrollTo({ top: 500, behavior: "instant" }));
  await sleep(300);
  const t = await page.evaluate(() => [...document.querySelectorAll("[data-speed]")].map((e) => getComputedStyle(e).transform));
  ok(t.every((x) => x === "none"), `[${name}] reduced motion: parallax disabled`);
  const label = await page.evaluate(() => document.querySelector(".video-toggle").textContent.trim());
  ok(/Play/.test(label), `[${name}] reduced motion: play control offered`, label);
  await ctx.close();
}

async function robustness(browser, name) {
  // 1. film already playing before the deferred script attaches its listeners
  let ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  let page = await ctx.newPage();
  await page.route(/js\/main\.js/, async (r) => { await sleep(4000); r.continue(); });
  await page.goto(url, { waitUntil: "load", timeout: 30000 });
  await sleep(1500);
  const late = await page.evaluate(() => ({
    playing: !document.getElementById("hero-video").paused,
    cls: document.querySelector(".hero").classList.contains("is-playing"),
    op: getComputedStyle(document.getElementById("hero-video")).opacity,
    label: document.querySelector(".video-toggle").textContent.trim(),
  }));
  ok(late.playing && late.cls && late.op === "1" && /Pause/.test(late.label), `[${name}] film shows when script loads late`, JSON.stringify(late));
  await ctx.close();
  // 2. script fails entirely: nothing may stay hidden
  ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  page = await ctx.newPage();
  await page.route(/js\/main\.js/, (r) => r.abort());
  await page.goto(url, { waitUntil: "load" });
  const hidden = await page.evaluate(() => [...document.querySelectorAll(".reveal")].filter((e) => getComputedStyle(e).opacity === "0").length);
  ok(hidden === 0, `[${name}] content visible without JavaScript`, `${hidden} hidden`);
  await ctx.close();
  // 3. review cards track scroll exactly (no transform transition lag)
  ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  page = await ctx.newPage();
  await page.goto(url, { waitUntil: "load" });
  await page.evaluate(() => document.querySelector(".quotes").scrollIntoView({ behavior: "instant" }));
  await sleep(1500);
  await page.evaluate(() => window.scrollBy({ top: 300, behavior: "instant" }));
  await sleep(120);
  const lag = await page.evaluate(() => [...document.querySelectorAll(".quote")].map((q) => {
    const m = getComputedStyle(q).transform;
    const v = m === "none" ? 0 : Number(m.slice(m.indexOf("(") + 1, -1).split(",")[m.startsWith("matrix3d") ? 13 : 5]);
    const inline = Number((q.style.transform.match(/,\s*(-?[\d.]+)px/) || [0, 0])[1]);
    return Math.abs(v - inline);
  }));
  ok(lag.every((d) => d < 1), `[${name}] review cards track scroll without lag`, lag.map((d) => d.toFixed(1)).join(","));
  await ctx.close();
}

// The open/closed line is computed in US Eastern time from the hours table.
// Freeze the clock at known moments (EDT, UTC-4) and check the wording.
async function hours(browser, name) {
  const cases = [
    ["2026-10-22T06:30:00-04:00", "Thursday", false, "Closed now · opens today at 7 AM"],
    ["2026-10-22T14:59:00-04:00", "Thursday", true, "Open now · until 3 PM"],
    ["2026-10-24T06:30:00-04:00", "Saturday", true, "Open now · until 3 PM"],
    ["2026-10-25T15:30:00-04:00", "Sunday", false, "Closed now · opens Tuesday at 7 AM"],
    ["2026-10-26T10:00:00-04:00", "Monday", false, "Closed now · opens tomorrow at 7 AM"],
  ];
  for (const [iso, day, open, want] of cases) {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, timezoneId: "America/Los_Angeles" });
    const page = await ctx.newPage();
    await page.route(/\.mp4$/, (r) => r.abort());
    await page.clock.setFixedTime(new Date(iso));
    await page.goto(url, { waitUntil: "load" });
    const r = await page.evaluate(() => {
      const st = document.querySelector("[data-hours-status]");
      const today = [...document.querySelectorAll("[data-week] tr.is-today th")].map((th) => th.firstChild.textContent);
      return { text: st.textContent, open: st.dataset.open, hidden: st.hidden, today };
    });
    ok(!r.hidden && r.text === want && r.open === String(open) && r.today.length === 1 && r.today[0] === day,
      `[${name}] hours status at ${iso.slice(0, 16)} ET`, `"${r.text}", today=${r.today.join(",")}`);
    await ctx.close();
  }
}

async function narrow(browser, name) {
  for (const width of [320, 360]) {
    const ctx = await browser.newContext({ viewport: { width, height: 640 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
    const page = await ctx.newPage();
    await page.goto(url, { waitUntil: "load" });
    const r = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, iw: innerWidth }));
    ok(r.sw <= r.cw && r.iw === width, `[${name}] no horizontal overflow at ${width}px`, JSON.stringify(r));
    await ctx.close();
  }
}

async function dockClearance(browser, name, device) {
  const ctx = await browser.newContext({ ...device });
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "load" });
  const r = await page.evaluate(() => {
    const t = document.querySelector(".video-toggle").getBoundingClientRect();
    const d = document.querySelector(".dock").getBoundingClientRect();
    const x = t.left + t.width / 2, y = t.top + t.height / 2;
    return { toggleBottom: t.bottom, dockTop: d.top, hit: document.elementFromPoint(x, y)?.closest(".video-toggle") !== null };
  });
  ok(r.toggleBottom <= r.dockTop && r.hit, `[${name}] film control clear of the phone dock`, JSON.stringify(r));
  await ctx.close();
}

(async () => {
  for (const e of engines) {
    const browser = await ({ chromium, webkit })[e].launch();
    await desktop(browser, `${e}-desktop`);
    await mobile(browser, `${e}-phone`, e === "webkit" ? devices["iPhone 13"] : devices["Pixel 7"]);
    await reduced(browser, `${e}-reduced`);
    await robustness(browser, `${e}-robust`);
    await dockClearance(browser, `${e}-phone`, e === "webkit" ? devices["iPhone 13"] : devices["Pixel 7"]);
    await hours(browser, `${e}-hours`);
    await narrow(browser, `${e}-narrow`);
    await browser.close();
  }
  console.log(failed ? `\n${failed} check(s) failed` : "\nall checks passed");
  process.exit(failed ? 1 : 0);
})();
