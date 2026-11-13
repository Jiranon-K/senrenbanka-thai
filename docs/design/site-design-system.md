# Site design system

The landing page (`site/`) is plain HTML, CSS and JS with no build step beyond
`site/build.py`. This file records how its design system is organised and where each
interaction pattern came from. The live reference is `site/design-system.html`
(published at `/design-system.html`, `noindex`); it reads token values straight from the
CSS, so this file lists names and rules, not values.

## Direction

Keep the skin: washi paper, shu red, gold titles, sakura, the game's own dialog box and
chapter ribbon. That identity was a deliberate rebuild of the page in earlier commits. The
work here changes the interaction layer on top of it and makes the rules explicit.

## Layers

| Layer | Where | Rule |
|---|---|---|
| Primitives | `:root` in `styles.css` (`--washi`, `--shu`, `--gold-*`, ...) | Named after things in the game. Never read directly by new components. |
| Semantic | `--c-*` | What a colour is for (`--c-accent`, `--c-surface`, ...). Components use these. `--c-bg-rgb` is the page colour as an RGB triplet for fades (`rgba(var(--c-bg-rgb), .5)`). |
| Scale | `--sp-1..9`, `--fs-*` | 4px space scale; type scale. `--fs-display` and `--fs-display-en` are the hero headline sizes. |
| Motion | `--dur-1..3`, `--ease`, `--ease-io`, `--beam-dur` | State changes 150-420ms. Only the CTA beam loops. |
| Elevation / layers | `--sh-*`, `--z-*` | |
| Components | `.btn`, `.lbox`, `.dialog`, `.seg`, `.choice`, `.slider`, `[data-spot]`, `.beam`, `.dock`, ... | Defined once in `styles.css`. |

`site/design-system.css` holds only the scaffolding of the style-guide page.

## Rules

- Motion never hides content and never exceeds 420ms, except the CTA beam and the hero intro
  (one pass on load, 0.7 to 1.4s per element; see Hero below).
- `html.js` (set in `<head>`) is the only thing that allows an initial hidden state. Without
  JS everything is visible. Reveal state is added per element (`[data-reveal]`), so a failed
  script cannot leave anything hidden.
- `prefers-reduced-motion: reduce` turns off transitions, animations, the beam, petals,
  reveal and count-up. FAQ open/close and the lightbox cross-fade check the preference in JS.
- Hover-only effects (`[data-spot]`, hover-follow on the compare slider) are gated on
  `(hover: hover) and (pointer: fine)`.
- Body text pairs meet WCAG AA 4.5:1. Gold gradient headings are large bold text (3:1).
  Contrast was computed, not eyeballed; two failing pairs in the earlier palette were fixed
  (`--muted` on `--washi-2`, white on coral in open FAQ rows).
- New colours go in as primitives plus a semantic alias. Do not write hex values in components.

## Interaction patterns and where they came from

Patterns only. All code was written from scratch for this stack; no source or asset was
copied. The pages read give no clear per-component licence (Animata calls itself open source,
Aceternity has its own licence page, Magic UI and React Bits pages state none), so only the
behaviour was taken.

| Ours | Pattern | Read at |
|---|---|---|
| `.beam` on the download buttons | Light circling a CTA frame | [Magic UI Border Beam](https://magicui.design/docs/components/border-beam), [Shimmer Button](https://magicui.design/docs/components/shimmer-button) |
| Meter count-up | Count from zero once in view, ease out | [Magic UI Number Ticker](https://magicui.design/docs/components/number-ticker), [Animata Counter](https://animata.design/docs/text/counter) |
| Install-step beam and reached state | Line fills with scroll, step lights when reached | [Animata Animated Timeline](https://animata.design/docs/progress/animatedtimeline), [Aceternity Timeline](https://ui.aceternity.com/components/timeline) |
| `.seg`, nav underline | One thumb slides to the active option (200-260ms) | [coss ui Segmented Control](https://coss.com/ui/docs/components/segmented-control) (originui.com redirects here) |
| `[data-spot]` | Glow and edge follow the pointer | [React Bits Spotlight Card](https://reactbits.dev/components/spotlight-card), [Animata Glowing Card](https://animata.design/docs/card/glowing-card) |
| Reveal on scroll | Short upward fade, staggered | [Animata Scroll Reveal](https://animata.design/docs/text/scroll-reveal) (ordering idea only) |

Read but not adopted: Aceternity Sticky Scroll Reveal (pins content to scroll position,
which makes skimming harder). Motion Primitives returned HTTP 403 when fetched, so nothing
here is derived from it; the reading-progress bar and FAQ height animation are standard
patterns written from first principles.

## UX changes this introduced

- Navigation: the link row used to disappear below 720px with nothing in its place. It is now
  a menu button and sheet up to 900px, with a scrollspy underline and a reading-progress bar.
- Download: buttons link straight to the release zip (from the GitHub API, cached for the
  session), falling back to the Releases page. A mobile dock keeps the button in reach.
- Hero: the title screenshot runs full-bleed on the right and fades into washi on the left; the
  headline sits top-left, the primary action and an install ring-link under it, the dialog box
  bottom-left, a before/after preview card (`.reel`, a `.lbox` with a `compare-th` thumbnail)
  bottom-right, and a hairline bar with a scroll cue and the patch facts along the bottom. The
  composition follows fitosauna.com; colours, type, frames and the dialog box stay ours. The
  six-item title-screen menu left the hero (the nav already links every section), and the two
  pins on the screenshot went with it because the menu is cropped out of view.
- Hero motion: the art zooms in from 1.1x and then breathes (1 to 1.045x over 24s), headline lines
  wipe up one after the other, the action row, dialog and card slide in, the bar's hairline
  draws left to right, and the dialog types itself after it lands. On scroll the art lags the page
  (`--hero-p`); with a mouse it leans a few pixels against the pointer (`--hx`, `--hy`). Petals and
  orbs keep drifting. Only `transform`, `translate`, `scale`, `opacity` and `clip-path` move.
  Reduced motion removes all of it; JS never sets the scroll and pointer variables then.
- Hero on phones: the art becomes a band at the top, the headline overlaps its faded lower edge,
  and the facts list is two columns, so the action row stays inside the first screen.
- Before/after: segmented buttons (English / slider / Thai) for touch, alongside dragging.
- Gallery: previous/next, arrow keys, swipe, caption and counter.
- FAQ: animated open/close and a stable id per answer, so a link such as
  `/#faq-smartscreen` opens that answer. The issue forms and README can use it.
- Fixed two existing layout bugs. At 1080px and below the primary button was meant to span
  both menu columns, but the rule targeted the `<a>` instead of its `<li>` grid item. And the
  first two gallery cards were meant to be large (`span 3`) but `.save { span 2 }` came later
  in the file and overrode them, leaving a gap in the second row.

## Checking changes

```bash
python site/build.py        # asset references exist; every var(--x) is defined
python -m http.server 8765 --directory _site
```

`build.py` runs in CI. Check by eye at 360px and 1280px, with the keyboard only (menu,
lightbox, FAQ), and with the OS reduced-motion setting on.
