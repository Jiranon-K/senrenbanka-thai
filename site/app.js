// Senren Banka แปลไทย — small progressive enhancements. The page works without this file.
(() => {
  const REPO = 'Jiranon-K/senrenbanka-thai';

  // Nav turns solid once the page leaves the very top.
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
