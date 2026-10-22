(() => {
  "use strict";
  const doc = document.documentElement;
  // reveal styles only apply once this script is running; if setup throws,
  // the class comes off again so no content is left hidden
  doc.classList.add("js");
  try {
    init();
  } catch (err) {
    doc.classList.remove("js");
    console.error(err);
  }

  function init() {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)");
    const hasIO = "IntersectionObserver" in window;
    const bar = document.getElementById("bar");
    const hero = document.querySelector(".hero");
    const video = document.getElementById("hero-video");
    const toggle = document.querySelector(".video-toggle");
    const marquee = document.querySelector("[data-marquee]");
    const layers = [...document.querySelectorAll("[data-speed]")].map((el) => ({
      el,
      speed: parseFloat(el.dataset.speed),
      fade: el.hasAttribute("data-fade"),
      top: 0,
      h: 0,
      rest: 0,
      on: !hasIO,
    }));
    const onChange = (mq, fn) => (mq.addEventListener ? mq.addEventListener("change", fn) : mq.addListener(fn));

    /* ---------- parallax: transform-only, measured once per resize ---------- */
    let vh = innerHeight;
    let ticking = false;
    let halfMarquee = 0;

    function measure() {
      vh = innerHeight;
      const y = scrollY;
      for (const l of layers) l.el.style.transform = "";
      for (const l of layers) {
        const r = l.el.getBoundingClientRect();
        l.top = r.top + y;
        l.h = r.height;
        // layers visible on load sit at rest at scroll 0; others when centred
        l.rest = l.top < vh ? 0 : l.top + l.h / 2 - vh / 2;
      }
      if (marquee) halfMarquee = marquee.scrollWidth / 2;
      frame();
    }

    function frame() {
      ticking = false;
      const y = scrollY;
      bar.classList.toggle("is-solid", y > 40);
      if (reduce.matches) return;
      for (const l of layers) {
        if (!l.on) continue;
        const t = (y - l.rest) * (1 - l.speed);
        l.el.style.transform = `translate3d(0,${t.toFixed(1)}px,0)`;
        if (l.fade) l.el.style.opacity = Math.max(0, 1 - y / (vh * 0.75)).toFixed(3);
      }
      if (marquee && halfMarquee) {
        const x = -((y * 0.45) % halfMarquee);
        marquee.style.transform = `translate3d(${x.toFixed(1)}px,0,0)`;
      }
    }

    function onScroll() {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(frame);
      }
    }

    // only animate layers whose section is near the viewport
    if (hasIO) {
      const near = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            const l = layers.find((x) => x.el === e.target);
            if (l) l.on = e.isIntersecting;
          }
          onScroll();
        },
        { rootMargin: "25% 0px 25% 0px" }
      );
      layers.forEach((l) => near.observe(l.el));
    }

    function resetMotion() {
      if (reduce.matches) {
        for (const l of layers) {
          l.el.style.transform = "";
          l.el.style.opacity = "";
        }
        if (marquee) marquee.style.transform = "";
      }
      measure();
    }

    addEventListener("scroll", onScroll, { passive: true });
    let rz;
    addEventListener("resize", () => {
      clearTimeout(rz);
      rz = setTimeout(measure, 120);
    });
    addEventListener("load", measure);
    if (document.fonts) document.fonts.ready.then(measure);
    onChange(reduce, () => {
      resetMotion();
      syncVideo();
    });
    measure();

    /* ---------- reveal on scroll ---------- */
    const reveals = document.querySelectorAll(".reveal");
    if (hasIO) {
      const io = new IntersectionObserver(
        (entries) => {
          for (const e of entries) {
            if (e.isIntersecting) {
              e.target.classList.add("is-in");
              io.unobserve(e.target);
            }
          }
        },
        { rootMargin: "0px 0px -8% 0px", threshold: 0.12 }
      );
      reveals.forEach((el) => io.observe(el));
    } else {
      reveals.forEach((el) => el.classList.add("is-in"));
    }

    /* ---------- hero film ---------- */
    let userPaused = false;
    let heroVisible = true;
    const saveData = navigator.connection && navigator.connection.saveData;

    function setToggle(paused) {
      toggle.dataset.paused = String(paused);
      toggle.querySelector("span").textContent = paused ? "Play film" : "Pause film";
    }

    function syncVideo() {
      const allowed = !reduce.matches && !saveData && !userPaused && heroVisible;
      if (allowed) {
        if (video.preload === "none") video.preload = "auto";
        const p = video.play();
        if (p && p.catch) p.catch(() => setToggle(true));
      } else {
        video.pause();
      }
      setToggle(reduce.matches || saveData || userPaused);
    }

    function markPlaying() {
      if (video.paused) return;
      hero.classList.add("is-playing");
      setToggle(false);
    }

    // the film may already be playing by the time this deferred script runs,
    // in which case its one "playing" event has fired; timeupdate catches up
    video.addEventListener("playing", markPlaying);
    video.addEventListener("timeupdate", markPlaying, { once: true });
    toggle.addEventListener("click", () => {
      userPaused = !video.paused;
      if (!userPaused && (reduce.matches || saveData)) {
        // explicit request to play overrides the motion/data preference
        video.preload = "auto";
        video.play();
        setToggle(false);
        return;
      }
      syncVideo();
    });
    if (hasIO) {
      new IntersectionObserver(
        ([e]) => {
          heroVisible = e.isIntersecting;
          if (!reduce.matches && !saveData && !userPaused) syncVideo();
        },
        { threshold: 0.05 }
      ).observe(hero);
    }
    syncVideo();
    if (!video.paused && video.readyState > 2) markPlaying();
  }
})();
