(() => {
  const REPO = 'Jiranon-K/senrenbanka-thai';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const finePointer = matchMedia('(hover: hover) and (pointer: fine)').matches;

  /* Latest release: tag, size, date, and a direct link to the zip. Cached for the session so a
     shared IP (60 anonymous API calls an hour) does not turn every page view into a request. */
  const CACHE_KEY = 'sbtp.release';
  const readCache = () => {
    try {
      const hit = JSON.parse(sessionStorage.getItem(CACHE_KEY));
      return hit && Date.now() - hit.at < 30 * 60e3 ? hit.rel : null;
    } catch { return null; }
  };
  const writeCache = (rel) => { try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), rel })); } catch {} };
  const applyRelease = (rel) => {
    const set = (sel, text) => $$(sel).forEach((el) => { el.textContent = text; });
    set('[data-latest-tag]', rel.tag);
    if (rel.zip) {
      set('[data-latest-size]', `${Math.round(rel.zip.size / 1048576)} MB`);
      set('[data-latest-name]', rel.zip.name);
      $$('[data-latest-url]').forEach((a) => { a.href = rel.zip.url; });
    }
    if (rel.date) {
      const d = new Date(rel.date);
      set('[data-latest-date]', d.toLocaleDateString('th-TH-u-ca-gregory', { day: 'numeric', month: 'short', year: 'numeric' }));
    }
  };
  const cachedRelease = readCache();
  if (cachedRelease) applyRelease(cachedRelease);
  else {
    fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((raw) => {
        const zip = (raw.assets || []).find((a) => a.name.endsWith('.zip'));
        const rel = {
          tag: raw.tag_name,
          date: raw.published_at,
          zip: zip && { name: zip.name, size: zip.size, url: zip.browser_download_url },
        };
        writeCache(rel);
        applyRelease(rel);
      })
      .catch(() => {});
  }

  /* Segmented control: one thumb slides between options. Generic; callers listen for `seg:change`. */
  $$('[data-seg]').forEach((el) => {
    const btns = $$('.seg__btn', el);
    const select = (i) => {
      el.style.setProperty('--i', i);
      btns.forEach((b, k) => b.setAttribute('aria-pressed', String(k === i)));
    };
    el.style.setProperty('--n', btns.length);
    el._seg = { select };
    btns.forEach((b, i) => b.addEventListener('click', () => {
      select(i);
      el.dispatchEvent(new CustomEvent('seg:change', { detail: { index: i, value: b.dataset.value } }));
    }));
    select(Math.max(0, btns.findIndex((b) => b.getAttribute('aria-pressed') === 'true')));
  });

  /* Style-guide page: print each token's computed value so the docs cannot drift from the CSS. */
  const rootStyle = getComputedStyle(document.documentElement);
  $$('[data-token]').forEach((el) => { el.textContent = rootStyle.getPropertyValue(el.dataset.token).trim(); });

  /* Navigation: mobile sheet, reading progress, and a scrollspy with one sliding underline. */
  const nav = $('[data-nav]');
  const menu = $('[data-nav-menu]');
  const toggle = $('[data-nav-toggle]');
  const ind = $('[data-nav-ind]');
  const links = menu ? $$('a[href^="#"]:not(.btn)', menu) : [];
  const spyItems = links.map((a) => ({ a, el: document.getElementById(a.hash.slice(1)) })).filter((x) => x.el);
  let current = null;

  const setOpen = (open) => {
    if (!nav || !toggle) return;
    nav.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'ปิดเมนู' : 'เปิดเมนู');
  };
  if (nav && toggle) {
    toggle.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
    $('[data-nav-scrim]')?.addEventListener('click', () => setOpen(false));
    menu.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape' || !nav.classList.contains('is-open')) return;
      setOpen(false);
      toggle.focus();
    });
    matchMedia('(min-width: 901px)').addEventListener('change', (e) => { if (e.matches) setOpen(false); });
  }

  const placeIndicator = () => {
    if (!ind) return;
    const a = current && current.a;
    if (!a || getComputedStyle(ind).display === 'none') { ind.classList.remove('is-on'); return; }
    const first = !ind.classList.contains('is-on');
    if (first) ind.style.transition = 'none';
    ind.style.setProperty('--ind-x', `${a.offsetLeft}px`);
    ind.style.setProperty('--ind-w', `${a.offsetWidth}px`);
    if (first) { void ind.offsetWidth; ind.style.transition = ''; }
    ind.classList.add('is-on');
  };
  const spy = () => {
    const line = innerHeight * 0.35;
    const hit = spyItems.find(({ el }) => {
      const r = el.getBoundingClientRect();
      return r.top <= line && r.bottom > line;
    }) || null;
    if (hit === current) return;
    current = hit;
    links.forEach((a) => a.removeAttribute('aria-current'));
    if (hit) hit.a.setAttribute('aria-current', 'location');
    placeIndicator();
  };

  /* Install steps: a beam fills the line as the reader scrolls, and each step lights up once reached. */
  const flowEl = $('.flow');
  const steps = flowEl ? $$('.node', flowEl) : [];
  const flow = () => {
    if (!flowEl) return;
    const line = innerHeight * 0.6;
    const r = flowEl.getBoundingClientRect();
    const span = r.height - 60;
    flowEl.style.setProperty('--flow-p', span > 0 ? clamp((line - r.top - 30) / span, 0, 1).toFixed(4) : 0);
    steps.forEach((n) => n.classList.toggle('is-reached', n.getBoundingClientRect().top + 28 <= line));
  };

  /* Mobile dock: shows once the hero CTA has scrolled away, hides while the closing CTA is on screen. */
  const dock = $('[data-dock]');
  const heroCta = $('[data-hero-cta]');
  const finalCta = $('[data-final-cta]');
  const updateDock = () => {
    if (!dock || !heroCta) return;
    const pastHero = heroCta.getBoundingClientRect().bottom < (nav ? nav.offsetHeight : 0);
    const atEnd = finalCta ? finalCta.getBoundingClientRect().top < innerHeight : false;
    dock.classList.toggle('is-on', pastHero && !atEnd);
  };

  const hero = $('[data-hero]');
  const heroFrame = (y) => {
    if (!hero || reduced()) return;
    const h = hero.offsetHeight;
    if (y > h * 1.2) return;
    hero.style.setProperty('--hero-p', h > 0 ? clamp(y / h, 0, 1).toFixed(4) : 0);
  };
  if (hero && finePointer) {
    let raf = 0;
    let px = 0;
    let py = 0;
    const lean = () => {
      raf = 0;
      hero.style.setProperty('--hx', px.toFixed(3));
      hero.style.setProperty('--hy', py.toFixed(3));
    };
    hero.addEventListener('pointermove', (e) => {
      if (reduced()) return;
      const r = hero.getBoundingClientRect();
      px = clamp((e.clientX - r.left) / r.width * 2 - 1, -1, 1);
      py = clamp((e.clientY - r.top) / r.height * 2 - 1, -1, 1);
      raf ||= requestAnimationFrame(lean);
    }, { passive: true });
    hero.addEventListener('pointerleave', () => { px = 0; py = 0; raf ||= requestAnimationFrame(lean); });
  }

  let queued = false;
  const frame = () => {
    queued = false;
    const y = window.scrollY;
    if (nav) {
      const max = document.documentElement.scrollHeight - innerHeight;
      nav.classList.toggle('is-solid', y > 8);
      nav.style.setProperty('--read', max > 0 ? clamp(y / max, 0, 1).toFixed(4) : 0);
    }
    heroFrame(y);
    spy();
    flow();
    updateDock();
  };
  const schedule = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };
  window.addEventListener('scroll', schedule, { passive: true });
  window.addEventListener('resize', () => { placeIndicator(); schedule(); });
  document.fonts?.ready.then(placeIndicator);
  frame();

  /* Reveal on scroll, plus a count-up on the progress meters. Skipped entirely under reduced motion,
     and the CSS only hides content once an element has been marked here, so nothing can stay hidden. */
  const countUp = (el, delay = 0) => {
    const to = parseFloat(el.textContent);
    if (!Number.isFinite(to)) return;
    const unit = el.textContent.replace(/[\d.]+/, '');
    const start = performance.now() + delay + 150;
    const step = (now) => {
      const t = clamp((now - start) / 1100, 0, 1);
      el.textContent = `${Math.round(to * (1 - (1 - t) ** 4))}${unit}`;
      if (t < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };
  const REVEAL = ['.chap', '.config .slider', '.config .slot', '.config .side .dialog', '.flow .node', '.seg', '.compare', '.compare-script', '.saves .save', '.choices .choice', '.choices__more', '.warn', '.final .lbox'];
  if ('IntersectionObserver' in window && !reduced()) {
    const seen = new Map();
    const els = [...new Set(REVEAL.flatMap((sel) => $$(sel)))];
    const show = (el) => {
      el.classList.add('is-in');
      if (el.matches('.slider')) countUp($('.slider__val', el), (Number(el.style.getPropertyValue('--i')) || 0) * 120);
    };
    const io = new IntersectionObserver((entries) => {
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        io.unobserve(en.target);
        show(en.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.1 });
    els.forEach((el) => {
      const i = seen.get(el.parentElement) || 0;
      seen.set(el.parentElement, i + 1);
      el.style.setProperty('--i', Math.min(i, 5));
      el.setAttribute('data-reveal', '');
      if (el.getBoundingClientRect().top < innerHeight) show(el);
      else io.observe(el);
    });
  }

  /* Hero dialog: types itself out, tap to skip. */
  const typer = $('[data-type]');
  if (typer && !reduced() && 'Segmenter' in Intl) {
    const seg = new Intl.Segmenter('th', { granularity: 'grapheme' });
    const chars = [];
    const walker = document.createTreeWalker(typer, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const frag = document.createDocumentFragment();
      for (const { segment } of seg.segment(node.data)) {
        const s = document.createElement('span');
        s.className = 'type-ch';
        s.textContent = segment;
        frag.appendChild(s);
        chars.push(s);
      }
      node.replaceWith(frag);
    });
    let i = 0;
    const step = () => {
      for (let k = 0; k < 2 && i < chars.length; k++) chars[i++].classList.add('on');
      if (i < chars.length) setTimeout(step, 28);
    };
    setTimeout(step, 1100);
    typer.closest('.dialog').addEventListener('click', () => { chars.forEach((c) => c.classList.add('on')); i = chars.length; });
  }

  /* Before/after slider: drag, hover, keyboard, or the segmented buttons. */
  $$('[data-compare]').forEach((box) => {
    const range = $('input[type=range]', box);
    const script = $('[data-compare-script]', box.parentElement);
    const seg = $('[data-compare-seg]', box.parentElement);
    let touched = false;
    const set = (v, anim = false) => {
      v = clamp(v, 0, 100);
      box.classList.toggle('is-anim', anim);
      box.style.setProperty('--pos', `${v}%`);
      box.style.setProperty('--p', v);
      range.value = v;
      if (script) script.dataset.side = v > 50 ? 'en' : 'th';
      if (seg) seg._seg.select(v >= 98 ? 0 : v <= 2 ? 2 : 1);
    };
    range.addEventListener('input', () => set(Number(range.value)));
    seg?.addEventListener('seg:change', (e) => { touched = true; set(Number(e.detail.value), true); });
    box.addEventListener('pointerdown', () => box.classList.add('is-drag'));
    window.addEventListener('pointerup', () => box.classList.remove('is-drag'));
    if (finePointer) {
      let raf = 0;
      let x = 0;
      box.addEventListener('pointermove', (e) => {
        if (e.buttons) return;
        x = e.clientX;
        raf ||= requestAnimationFrame(() => {
          raf = 0;
          const r = box.getBoundingClientRect();
          set((x - r.left) / r.width * 100);
        });
      });
    }
    set(Number(range.value));

    if (reduced() || !('IntersectionObserver' in window)) return;
    ['pointerdown', 'pointermove', 'keydown'].forEach((ev) => box.addEventListener(ev, () => { touched = true; }, { once: true }));
    const io = new IntersectionObserver(([en]) => {
      if (!en.isIntersecting) return;
      io.disconnect();
      [38, 62, 50].forEach((v, k) => setTimeout(() => { if (!touched) set(v, true); }, 300 + k * 560));
      setTimeout(() => box.classList.remove('is-anim'), 300 + 3 * 560 + 200);
    }, { threshold: 0.5 });
    io.observe(box);
  });

  /* Spotlight: hand the pointer position to the card so CSS can paint the glow there. */
  if (finePointer) {
    document.addEventListener('pointermove', (e) => {
      const el = e.target.closest?.('[data-spot]');
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty('--mx', `${e.clientX - r.left}px`);
      el.style.setProperty('--my', `${e.clientY - r.top}px`);
    }, { passive: true });
  }

  /* Gallery lightbox: previous/next, arrow keys, swipe, caption and counter. */
  const lb = $('[data-lightbox]');
  if (lb && typeof lb.showModal === 'function') {
    const big = $('[data-lb-img]', lb);
    const nameEl = $('[data-lb-name]', lb);
    const countEl = $('[data-lb-count]', lb);
    const items = $$('[data-gallery] .save').map((fig) => ({
      btn: $('.save__btn', fig),
      img: $('img', fig),
      name: $('.save__name', fig).textContent,
      cap: $('figcaption', fig)?.textContent ?? '',
    }));
    let cur = 0;
    const srcOf = (it) => it.img.currentSrc || it.img.src;
    const show = (i, swap) => {
      cur = (i + items.length) % items.length;
      const it = items[cur];
      const paint = () => {
        big.src = srcOf(it);
        big.alt = it.img.alt;
        nameEl.textContent = !it.cap || it.cap.startsWith(it.name) ? (it.cap || it.name) : `${it.name} · ${it.cap}`;
        countEl.textContent = `${cur + 1} / ${items.length}`;
      };
      if (swap && !reduced()) {
        big.classList.add('is-swap');
        setTimeout(paint, 120);
        big.addEventListener('load', () => big.classList.remove('is-swap'), { once: true });
        setTimeout(() => big.classList.remove('is-swap'), 500);
      } else paint();
      const next = items[(cur + 1) % items.length];
      new Image().src = srcOf(next);
    };
    items.forEach((it, i) => it.btn.addEventListener('click', () => { show(i, false); lb.showModal(); }));
    $('[data-lb-prev]', lb).addEventListener('click', () => show(cur - 1, true));
    $('[data-lb-next]', lb).addEventListener('click', () => show(cur + 1, true));
    lb.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft') show(cur - 1, true);
      else if (e.key === 'ArrowRight') show(cur + 1, true);
    });
    lb.addEventListener('click', (e) => { if (e.target === lb) lb.close(); });
    let x0 = null;
    const stage = $('.lightbox__stage', lb);
    stage.addEventListener('pointerdown', (e) => { x0 = e.clientX; });
    stage.addEventListener('pointerup', (e) => {
      if (x0 === null) return;
      const dx = e.clientX - x0;
      x0 = null;
      if (Math.abs(dx) > 50) show(cur + (dx < 0 ? 1 : -1), true);
    });
  }

  /* FAQ: animate open/close, and let a URL hash (#faq-smartscreen) open one answer directly. */
  const faqToggle = (d, open) => {
    const body = $('.dialog', d);
    d._want = open;
    if (reduced() || !body || !body.animate) { d.open = open; return; }
    d._anim?.cancel();
    if (open) d.open = true;
    const cs = getComputedStyle(body);
    const full = { height: `${body.offsetHeight}px`, marginTop: cs.marginTop, marginBottom: cs.marginBottom, paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, opacity: 1 };
    const none = { height: '0px', marginTop: '0px', marginBottom: '0px', paddingTop: '0px', paddingBottom: '0px', opacity: 0 };
    body.style.overflow = 'hidden';
    const anim = body.animate(open ? [none, full] : [full, none], { duration: 260, easing: 'cubic-bezier(.22, 1, .36, 1)' });
    d._anim = anim;
    anim.onfinish = () => { body.style.overflow = ''; if (!open) d.open = false; d._anim = null; };
    anim.oncancel = () => { body.style.overflow = ''; };
  };
  $$('.choice').forEach((d) => {
    $('summary', d).addEventListener('click', (e) => {
      e.preventDefault();
      faqToggle(d, !(d._want ?? d.open));
    });
  });
  const openFromHash = () => {
    const d = location.hash.length > 1 && document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (!d || !d.matches('.choice')) return;
    if (!d.open) faqToggle(d, true);
    d.classList.add('is-flash');
    setTimeout(() => d.classList.remove('is-flash'), 1600);
  };
  window.addEventListener('hashchange', openFromHash);
  openFromHash();
})();
