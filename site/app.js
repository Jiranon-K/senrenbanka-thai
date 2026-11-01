(() => {
  const REPO = 'Jiranon-K/senrenbanka-thai';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  const nav = document.querySelector('[data-nav]');
  const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 8);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

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

  const typer = document.querySelector('[data-type]');
  if (typer && !reduced && 'Segmenter' in Intl) {
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
    setTimeout(step, 350);
    typer.closest('.dialog').addEventListener('click', () => { chars.forEach((c) => c.classList.add('on')); i = chars.length; });
  }

  document.querySelectorAll('[data-compare]').forEach((box) => {
    const range = box.querySelector('input[type=range]');
    const script = box.parentElement.querySelector('[data-compare-script]');
    const set = (v, anim = false) => {
      v = Math.max(0, Math.min(100, v));
      box.classList.toggle('is-anim', anim);
      box.style.setProperty('--pos', `${v}%`);
      box.style.setProperty('--p', v);
      range.value = v;
      if (script) script.dataset.side = v > 50 ? 'en' : 'th';
    };
    range.addEventListener('input', () => set(Number(range.value)));
    box.addEventListener('pointerdown', () => box.classList.add('is-drag'));
    window.addEventListener('pointerup', () => box.classList.remove('is-drag'));
    if (matchMedia('(hover: hover) and (pointer: fine)').matches) {
      let frame = 0;
      let x = 0;
      box.addEventListener('pointermove', (e) => {
        if (e.buttons) return;
        x = e.clientX;
        frame ||= requestAnimationFrame(() => {
          frame = 0;
          const r = box.getBoundingClientRect();
          set((x - r.left) / r.width * 100);
        });
      });
    }
    set(Number(range.value));

    if (reduced || !('IntersectionObserver' in window)) return;
    let touched = false;
    ['pointerdown', 'pointermove', 'keydown'].forEach((ev) => box.addEventListener(ev, () => { touched = true; }, { once: true }));
    const io = new IntersectionObserver(([en]) => {
      if (!en.isIntersecting) return;
      io.disconnect();
      [38, 62, 50].forEach((v, k) => setTimeout(() => { if (!touched) set(v, true); }, 300 + k * 560));
      setTimeout(() => box.classList.remove('is-anim'), 300 + 3 * 560 + 200);
    }, { threshold: 0.5 });
    io.observe(box);
  });

  const lightbox = document.querySelector('[data-lightbox]');
  if (lightbox && typeof lightbox.showModal === 'function') {
    const big = lightbox.querySelector('img');
    document.querySelectorAll('[data-gallery] .save__btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const img = btn.querySelector('img');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt;
        lightbox.showModal();
      });
    });
    lightbox.addEventListener('click', (e) => { if (e.target === lightbox) lightbox.close(); });
  }
})();
