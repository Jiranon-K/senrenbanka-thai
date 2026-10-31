# Thai players can read the System Config "Image" page without Chinese

> Produced by `to-spec` from the 2026-10-31 session on image menus (screenshots of the
> System Config pages, `docs/ui-translation.md`, `thai_work/ui/ui_manifest.csv`).
> Status: approved 2026-10-31. AC4 amended during the pilot: "CN box + 2 px" left no room for
> Thai marks above and below, so the limit became the free area around the CN text.

## Problem

Players who install the Thai patch still see Chinese on every menu screen that is drawn
as a picture: the System Config title, its tabs, its section headings and its option
buttons. The text-based menus are already Thai, so the screens look half-translated and
players cannot tell what most options do without guessing.

## Why now

All text-based UI is done (commit `afac769` closed the last gap). The image menus are the
only Chinese left in the all-ages patch. Redrawing by hand was cancelled on 2026-10-26
because nobody had time to draw 384 elements; the user now wants Claude to try producing
them automatically, starting with one page to judge quality.

## Current behaviour

Language = Chinese (Simplified) is the slot the patch overwrites. On System Config →
画面显示 the player sees Chinese in two sheets of `data.xp3`:

- `uipsd/cn/sys_base_cn.pimg` — 34 layers: the "系统设定" title on `bg`, 8 tabs (`defo`,
  `over`, `on`), `back` and `reset` buttons.
- `uipsd/cn/sys_page0_cn.pimg` — 36 layers: `content_bg` (1816×838, 11 headings baked
  into a washi-paper panel) and 11 option buttons × 3 states (184×34 each).

Workaround today: players memorise positions or switch to English.

## Desired behaviour

On that page, every word a player reads is Thai, in the same place, the same box size and
the same colour per state as the Chinese it replaces, and the page still looks like part
of the same game.

## Out of scope

- **The other 24 sheets and 8 full-screen PNGs.** They wait for the pilot verdict; a
  second spec covers the rollout.
- **Latin text** already in the images (ON/OFF, 4:3, 16:9, "IMAGE CONFIG", "SYSTEM
  CONFIG"). It stays as drawn.
- **Matching the gold or embossed title effects exactly.** A flatter look on the
  "系统设定" title is acceptable for the pilot; the user may supply that one image by hand.
- **Shipping a release** (`build_release.py`, new installer). The pilot only changes the
  local `data.xp3`.
- **The R18 build and `adult.xp3`.** These sheets live only in `data.xp3`.
- **Generating images with an AI image model.** No such tool is available here.
- **The opening movie's hard subtitles.**

## In scope

- Thai wording for every Chinese label on the two sheets, consistent with the Thai terms
  already used in `main/syslangtext_cn.ini`.
- Thai versions of every listed layer of the two sheets, in `thai_work/ui/th/` under the
  same names as `thai_work/ui/todo/`.
- Rebuilding those two sheets and packing them into `data.xp3` through the single builder
  `ui_assets.build_data` (rule R15).
- A before/after contact sheet of every changed layer for the user to review.

## Acceptance criteria

| # | Given | When | Then |
| --- | --- | --- | --- |
| AC1 | the rebuilt local `data.xp3`, game set to Chinese (Simplified) | open System Config → 画面显示 | no Han character is visible inside the game window except the game logo "千恋＊万花" |
| AC2 | the same page | hover, then click, each option button and tab | each state shows Thai in that state's colour; none falls back to Chinese |
| AC3 | every file in `thai_work/ui/th/sys_base/` and `th/sys_page0/` | a size check runs against `todo/` | width, height and RGBA mode match the CN original exactly; any mismatch fails with the file name |
| AC4 | every Thai label | its drawn text bounds are measured | the bounds, including tone marks above and vowels below, sit inside the free area around the CN text (button: pill interior; tab: right of the icon; heading: the CN line ±30 % of its height); any overflow is reported as OVERFLOW with the layer name |
| AC5 | the rebuilt `data.xp3` | its entries are diffed against a build without the Thai images | only the two `.pimg` entries differ; the 3 fonts and 10 text files are byte-identical |
| AC6 | the two rebuilt sheets | each layer is decompiled back | layers without a Thai file are byte-identical to the original TLG5 data |
| AC7 | a missing, mis-sized or corrupt Thai PNG, or a sheet that will not rebuild | the build runs | it exits non-zero, names the file, and leaves the installed `data.xp3` untouched |
| AC8 | the contact sheet | the user reviews it and the page in game | the user rates it "good enough to roll out" or lists layers to redo. This is the quality gate. |

## Constraints

- Build from `data.xp3.bak` only (R15). Never commit game images (R12): everything under
  `thai_work/ui/` stays gitignored.
- The cx cipher keystream approach in `tools/xp3.py` can resize entries, so the pimg
  size limit noted in `docs/ui-translation.md` is not a constraint (guess, checked by AC5).
- Fonts must be free to redistribute as rendered pixels (OFL or bundled with Windows for
  rendering only).

## Risks

| Risk | Impact | Mitigation or acceptance |
| --- | --- | --- |
| The engine rejects a FreeMote-rebuilt pimg; no rebuilt pimg has ever run in game | pilot fails | first step is a no-change rebuild of one sheet run in game, before any drawing |
| Thai is wider than Chinese; tabs are only 134–145 px wide | text too small to read | shorter wording, smaller size with a floor; AC4 catches overflow |
| Erasing text on washi paper leaves smudges | headings look patched | user review (AC8); fall back to copying clean paper from the JP or EN panel |
| The chosen font clashes with the game's serif look | looks foreign | Q1 |

## Open questions

| # | Question | Owner | Blocking? |
| --- | --- | --- | --- |
| Q1 | Font: a looped serif (Noto Serif Thai, needs a download) or Sarabun, which is already in the game? The pilot can render both for comparison. | user | no — both are rendered |
| Q2 | Thai wording for the 22 labels. Claude drafts it from the EN reference and `syslangtext_cn.ini`; the user corrects it. | Claude drafts, user approves | no |
| Q3 | Is a flat "ตั้งค่าระบบ" title acceptable, or will the user hand-draw that one? | user | no |

## Rollout and reversal

Local only: `ui_assets.build_data` rewrites `data.xp3` from `data.xp3.bak`. To reverse,
delete `thai_work/ui/th/sys_*` and rebuild, or restore `data.xp3.bak`. Nothing ships to
players until a later spec covers the release.
