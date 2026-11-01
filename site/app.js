// Senren Banka แปลไทย — progressive enhancements. Everything is visible and usable without this file.
(() => {
  const REPO = 'Jiranon-K/senrenbanka-thai';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Nav gets a rule once the page leaves the very top.
  const nav = document.querySelector('[data-nav]');
  const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 8);
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

  // Dialogue text appears one grapheme at a time, like the game's text box.
  // Graphemes keep Thai vowels and tone marks attached to their consonant.
  // Every character is laid out from the start (opacity only), so the box never changes size.
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
      // two graphemes per frame tick keeps a ~1.5 s line, close to the game's default text speed
      for (let k = 0; k < 2 && i < chars.length; k++) chars[i++].classList.add('on');
      if (i < chars.length) setTimeout(step, 28);
    };
    setTimeout(step, 350);
    // A click on the box finishes the line at once, as in the game.
    typer.closest('.dialog').addEventListener('click', () => { chars.forEach((c) => c.classList.add('on')); i = chars.length; });
  }

  // Before/after slider: a native range input drives the split, so keyboard and touch work for free.
  document.querySelectorAll('[data-compare]').forEach((box) => {
    const range = box.querySelector('input[type=range]');
    const update = () => box.style.setProperty('--pos', `${range.value}%`);
    range.addEventListener('input', update);
    update();
  });

  // Gallery lightbox (real screenshots only; mock slots have no button).
  const box = document.querySelector('[data-lightbox]');
  if (box && typeof box.showModal === 'function') {
    const big = box.querySelector('img');
    document.querySelectorAll('[data-gallery] .save__btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const img = btn.querySelector('img');
        big.src = img.currentSrc || img.src;
        big.alt = img.alt;
        box.showModal();
      });
    });
    box.addEventListener('click', (e) => { if (e.target === box) box.close(); });
  }
})();
