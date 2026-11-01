// Senren Banka แปลไทย — progressive enhancements. The page reads fine without this file.
(() => {
  const REPO = 'Jiranon-K/senrenbanka-thai';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Floating navbar gets a stronger shadow once the page leaves the very top.
  const nav = document.querySelector('[data-nav]');
  const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 24);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  // Keep version, size and date current without rebuilding the page.
  fetch(`https://api.github.com/repos/${REPO}/releases/latest`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((rel) => {
      const zip = (rel.assets || []).find((a) => a.name.endsWith('.zip'));
      const set = (sel, text) => document.querySelectorAll(sel).forEach((el) => { el.textContent = text; });
      set('[data-latest-tag]', rel.tag_name);
      if (zip) set('[data-latest-size]', `${Math.round(zip.size / 1048576)} MB`);
      if (rel.published_at) {
        const d = new Date(rel.published_at);
        set('[data-latest-date]', d.toLocaleDateString('th-TH-u-ca-gregory', { day: 'numeric', month: 'short', year: 'numeric' }));
      }
    })
    .catch(() => {});

  // Reveal on scroll: elements fade up the first time they enter the viewport.
  const revealed = document.querySelectorAll('.reveal');
  if (reduced || !('IntersectionObserver' in window)) {
    revealed.forEach((el) => el.classList.add('in'));
  } else {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        e.target.classList.add('in');
        io.unobserve(e.target);
      });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.1 });
    revealed.forEach((el) => io.observe(el));
  }

  // Container scroll animation: the title screen lies flat as it reaches mid-viewport.
  const tilt = document.querySelector('[data-tilt]');
  if (tilt && !reduced) {
    const MAX = 22;
    let ticking = false;
    const update = () => {
      ticking = false;
      const r = tilt.getBoundingClientRect();
      const vh = window.innerHeight;
      // 0 when the card's top is at the bottom edge, 1 when its centre reaches ~45% of the viewport.
      const start = vh, end = vh * 0.45 - r.height / 2;
      const p = Math.min(1, Math.max(0, (start - r.top) / (start - end)));
      const ease = 1 - Math.pow(1 - p, 3);
      tilt.style.setProperty('--rx', `${MAX * (1 - ease)}deg`);
      tilt.style.setProperty('--s', `${0.92 + 0.08 * ease}`);
    };
    const req = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', req, { passive: true });
    window.addEventListener('resize', req);
    update();
  } else if (tilt) {
    tilt.style.setProperty('--rx', '0deg');
    tilt.style.setProperty('--s', '1');
  }

  // Number ticker: counts up when the number scrolls into view.
  document.querySelectorAll('[data-count]').forEach((el) => {
    const target = Number(el.dataset.count);
    if (reduced || !('IntersectionObserver' in window)) { el.textContent = target; return; }
    const io = new IntersectionObserver((entries) => {
      if (!entries[0].isIntersecting) return;
      io.disconnect();
      const t0 = performance.now(), dur = 1400;
      const tick = (t) => {
        const p = Math.min(1, (t - t0) / dur);
        el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.4 });
    io.observe(el);
  });

  // Magic-card spotlight: each bento card tracks the cursor.
  document.querySelectorAll('[data-bento] .card').forEach((card) => {
    card.addEventListener('pointermove', (e) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty('--mx', `${e.clientX - r.left}px`);
      card.style.setProperty('--my', `${e.clientY - r.top}px`);
    });
  });

  // Sticky scroll reveal: the step nearest the middle of the viewport owns the sticky panel.
  const sticky = document.querySelector('[data-sticky]');
  if (sticky) {
    const steps = [...sticky.querySelectorAll('[data-step]')];
    const panels = [...sticky.querySelectorAll('[data-panel]')];
    const activate = (n) => {
      steps.forEach((s) => s.classList.toggle('is-active', s.dataset.step === n));
      panels.forEach((p) => p.classList.toggle('is-active', p.dataset.panel === n));
    };
    activate('1');
    if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((entries) => {
        entries.forEach((e) => { if (e.isIntersecting) activate(e.target.dataset.step); });
      }, { rootMargin: '-45% 0px -45% 0px', threshold: 0 });
      steps.forEach((s) => io.observe(s));
    } else {
      steps.forEach((s) => s.classList.add('is-active'));
    }
  }

  // Before/after slider: a native range input drives the split, so keyboard and touch work for free.
  document.querySelectorAll('[data-compare]').forEach((box) => {
    const range = box.querySelector('input[type=range]');
    const update = () => box.style.setProperty('--pos', `${range.value}%`);
    range.addEventListener('input', update);
    update();
  });

  // Gallery lightbox.
  const box = document.querySelector('[data-lightbox]');
  if (box && typeof box.showModal === 'function') {
    const big = box.querySelector('img');
    document.querySelectorAll('[data-gallery] .tile__btn').forEach((tile) => {
      tile.addEventListener('click', () => {
        const img = tile.querySelector('img');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt;
        box.showModal();
      });
    });
    box.addEventListener('click', (e) => { if (e.target === box) box.close(); });
  }
})();
