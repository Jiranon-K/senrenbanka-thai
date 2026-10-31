# UI translation — menus, buttons, system text

> **Status 2026-10-31 — all image menus:** every CN sheet (24 `uipsd/cn/*_cn.pimg`) and 3 standalone
> PNGs (`attention`, `scramble2`, `extra_watermark`) are drawn in Thai — 917 labels from
> `tools/ui_labels.tsv`. Run `python tools/ui_render.py <sheet ...>` then `python tools/ui_assets.py pack-text`.
> Left as drawn: the game logo (title_bg, aboutdialog, deactivelogo, eyecatch logo) and the Latin
> copyright line. `python tools/ui_render.py survey <sheet>` crops every CN text block next to its EN twin
> for writing new labels.
>
> Label `kind` = `title | heading | tab | button | gold` plus `+flags`: `grad` `outline` `shadow` `flat`
> (paint), `center` `left` (align), `smooth` (diffusion fill, for text on artwork), `interp` (linear fill),
> `whole` (erase the union box), `clearall` (layer is text only), `jponly` (compare with JP only, searching
> ±32 px — for layers whose EN twin is laid out differently), `widen` (layer may grow up to
> `ui_assets.WIDEN_MAX` px to the right; the packer writes the new width into the sheet), `bottom` (only
> text blocks in the lower third — gesture icons). Layer keys are `name`, `name~N` (Nth group with that
> name), `name#N`, `#N-M` or `#N,M` (text blocks in reading order).
>
> Gotcha: FreeMote's `-raw` resource keys are not always layer ids (`gesture_help` stores layer 104 as
> key `"10"`); `build_sheet` maps layer → `#resource#N` from the sheet json → Nth resource.

> **Status 2026-10-31 — image pilot:** System Config → Image page (`sys_base`, `sys_page0`,
> 70 layers) is drawn in Thai by `python tools/ui_render.py sys_base sys_page0` and packed by
> `python tools/ui_assets.py pack-text`, which now also rebuilds every sheet that has a folder in
> `thai_work/ui/th/`. Spec: `docs/agent/specs/ui-image-pilot-system-config.md`.
>
> How `ui_render.py` works: the CN text is located by comparing the CN layer with its JP and EN
> twins (CN must differ from both, and from a 9 px median of itself, so text shared by two
> languages or semi-transparent pills does not fool it). The background is rebuilt by tiling a
> text-free strip from the same rows, using the strip's own repeat period so the checker pattern
> stays aligned; tab text on transparency is simply cleared. Thai is shaped with harfbuzz and
> rasterized with FreeType (Pillow here has no libraqm, so it would stack ั + ้ wrongly).
> Headings and the title use Noto Serif Thai (OFL, `thai_work/fonts/ui/`, downloaded from
> google/fonts); buttons and tabs use Sarabun SemiBold. Wording lives in `tools/ui_labels.tsv`.
>
> Verified in game 2026-10-31: the engine loads FreeMote-rebuilt sheets, including layers rebuilt
> from PNG (stored as TLG0-wrapped TLG5). `build_data` needs `thai_work/fonts/variants/*.ttf` and
> `thai_work/dataxp3/font/*.otf`; both can be re-extracted from the shipped `data.xp3` and from
> `data.xp3.bak` with `garbro_extract.ps1 -Filter "font/SourceHanSansSC-*"`.

> **Status 2026-10-26:** image translation was cancelled. All text-based UI is translated
> and packed into `data.xp3` with `python tools/ui_assets.py pack-text` (10 files,
> read back byte-identical through GARbro). The translated files live in
> `thai_work/ui/text/main/` — gitignored, because they keep the game's Japanese comments.
> 68 flowchart choice labels from sex scenes are left in Chinese on purpose.
>
> `patch.xp3` carries its own copy of `help_sys_cn.txt` (identical to the CN original in
> `data.xp3`) and the game reads it first. `pipeline_cn.py pack patch.xp3` therefore packs the
> Thai `main/help_sys_cn.txt` into `patch.xp3` too (`ui_assets.SHADOWED`, rule R16).
>
> The size limit described below no longer applies to entries packed with
> `xp3.Archive.replace_sized`: the cx cipher is a pure XOR, so `tools/xp3_keystream.ps1`
> gets a keystream of any length from GARbro, and the rebuilt index records the new sizes.

Surveyed 2026-10-26. The patch keeps using the **CN slot** (see `CONTEXT.md`): every asset below is the
`_cn` variant in `data.xp3`, which the game shows when Language = Chinese (Simplified).

## Where the UI lives

| what | where | format | who translates |
|---|---|---|---|
| Menu/button/heading graphics | `data.xp3: uipsd/cn/*_cn.pimg` (26 sheets) | PSB "Pimg", layers stored as TLG5 | **you — redraw images** |
| Full-screen graphics | `data.xp3: image/**/*_cn.png` (8 files) | PNG | **you — redraw images** |
| System strings: dialogs, right-click menu, option labels, TTS settings, error messages | `data.xp3: main/syslangtext_cn.ini` (407 entries) | UTF-16 text, KiriKiri simple-crypt wrapper | Claude |
| Flowchart chapter captions + scene lines | `main/flow_texts_cn.ini` (325 entries) | same | Claude |
| Help pages | `main/help_{sys,file,tui,exch,flow,lang}_cn.txt`, `main/speech_help_cn.txt` | same, zlib-compressed | Claude |
| BGM titles (sound mode) | `main/soundlist_cn.csv` | same | Claude |
| Opening movie with Chinese subtitles | `adult.xp3: cn_OP_1080.mp4` (137 MB) | H.264, hard-subbed | later — needs re-encode |

`SenrenBanka.exe` was checked with REA (`inspect_pe_resources`): it carries only KiriKiri engine
error strings (EN/JP string tables) and boot scripts — no game UI. Nothing to patch there.

## The image hand-off

Generated by `python tools/ui_assets.py inventory` into `thai_work/ui/` (gitignored — game assets):

```
thai_work/ui/todo/<sheet>/<layer_id>_<name>.png      ← the CN original, exact size
thai_work/ui/todo/<sheet>/_en/<same name>.png        ← English version, for meaning
thai_work/ui/todo/_images/image/...                  ← the 8 full-screen PNGs (+ _en/)
thai_work/ui/ui_manifest.csv                         ← every row: sheet, layer, size, screen position
```

**858 layers = 384 distinct elements.** Buttons come in states — `defo` (normal), `over` (hover),
`on` (pressed/selected) — with the same words in different colours, so each word is drawn 2–3 times.

A layer is listed only if the CN layer clearly differs from the JP layer of the same name
(threshold > 64/255 on any channel, alpha-premultiplied), so shared artwork is excluded.
Large `content_bg`/`cont_bg` panels are included on purpose: the section headings are baked into them.

### Rules for the Thai images

1. Put results in `thai_work/ui/th/` with the **same relative path and file name** as in `todo/`.
2. **Keep the exact pixel size** of the CN original. The layer's box and screen position come from the
   sheet, so a different size will be clipped or misplaced.
3. RGBA PNG, keep transparency where the original is transparent.
4. Translate every state of a button (`defo` / `over` / `on`), matching each state's colour.
5. Skip any file you think needs no change — untouched layers stay byte-identical.

## How it goes back into the game (verified feasibility)

Replacing an entry without the archive key requires the new bytes to be **no larger than the original
entry** (keystream packing, `tools/xp3.py`). Measured:

- All 26 CN sheets and 8 PNGs are stored **uncompressed** in `data.xp3`, so the slot size is the file size.
- Rebuilding a sheet from PNGs adds a `TLG0.0` wrapper per layer and overshoots (dialog: 598,141 > 596,976).
- Rebuilding from **raw** resources (`PsbDecompile -raw`) fits: 596,911 ≤ 596,976. So untouched layers keep
  their original TLG5 bytes and only translated layers are re-encoded.
- Remaining risk: a Thai layer that compresses larger than the Chinese one. The packer will report the
  overshoot per sheet; fix by trimming that layer's noise or simplifying its effects.
- Text entries carry KiriKiri's simple-crypt header (`FE FE <mode> FF FE`); mode 2 is zlib. Writing the Thai
  text as mode 2 keeps it far below the original size, even though Thai is longer than Chinese.
