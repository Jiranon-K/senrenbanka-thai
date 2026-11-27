# Notes kept from removed comments

The code carries no comments ([RULES.md](../RULES.md)); `python -m tools.code_rules.comments`
fails the baseline when one appears. These are the reasons that used to live in comments and
that the code still depends on. Background that was already written down is linked, not repeated:
module background in [internals.md](../internals.md), invariants in [RULES.md](../RULES.md),
vocabulary in [CONTEXT.md](../../CONTEXT.md).

## `.gitignore`

- The file is a deny-all whitelist: `/*` ignores every top-level entry, and each `!` line
  re-allows one thing we wrote. The repository sits inside the game directory or anywhere below
  it, so anything not listed could be a copyrighted game asset or a multi-gigabyte archive (R12).
- Do not assume the repository root is the game folder. `tools/paths.py` walks up until it finds
  `SenrenBanka.exe`.
- `docs/` is allowed for README illustrations: screenshots of the installer we wrote, and
  in-game screenshots under `docs/screenshots/`. That is the R12 exception and covers screenshots
  only, never a file extracted from the game.
- `tools/` is allowed for our own scripts and guides. Third-party binaries stay out
  (`FreeMote/`, `xdelta/`, `GARbro/`, `_dl/`).
- The one third-party binary that is committed is `tools/gui/ui/fonts/Sarabun-*.ttf`. The Open
  Font License permits redistribution, `OFL.txt` ships beside the fonts, and the installer has to
  render Thai offline. Without them it falls back to whatever font the machine has.
- `tools/gui/ui/bg.png`, `icon.ico` and `logo@*.png` are crops of the game's own artwork, cut by
  `tools/gui/build/make_logo.py` and `make_bg.py` from an image you point them at. They belong to
  Yuzusoft, so they are ignored and built locally. `assets.py` returns `None` for each missing
  file and the installer falls back to the plain design.
- Under `thai_work/` only the translation data and the dashboards are allowed.
- `thai_work/th/*.src.tsv` is ignored because the source dumps hold the original Japanese and the
  official English text.
- These paths must never be committed. The whitelist already excludes them; the list is the
  reason the whitelist exists:
  - `*.xp3`, `*.xp3.orig`: game archives.
  - `thai_work/strings_cn.csv`: master table with Japanese and official English text.
  - `thai_work/fonts/`: base, merged and variant font binaries, built locally.
  - `thai_work/json_cn/`, `psb_cn/`, `json_r18/`, `psb_r18/`: decompiled scenarios.
  - `thai_work/dataxp3/`, `scnxp3/`: extracted archives (locations in `tools/paths.py`).
  - `thai_work/dist/`: built installer packages.

## `.gitattributes`

- `core.autocrlf=true` is set globally on the author's machine. Without `*.sh text eol=lf` a
  fresh clone checks shell scripts out with CRLF and bash fails on the carriage return.
- Images, icons and fonts are marked `binary` for the same reason: line-ending conversion must
  never touch them.
- The rules for generated `.bat` files (UTF-8 without a byte-order mark, CRLF, `chcp 65001`) are
  in [internals.md](../internals.md) under `tools/build_release.py`.

## `.github/workflows/ci.yml`

- The job runs on Windows because `tools/` targets Windows (the game engine and the PowerShell
  helpers).
- `tools/test_pipeline.py` needs no game files; the cases that do need them skip themselves.
- The site build step fails on a missing site asset or on a `var(--token)` that nothing defines.

## `site/build.py`

- A typo such as `var(--shuu)` fails silently in CSS: the property just vanishes. The build
  therefore rejects any custom property read with `var()` that nothing declares, sets inline, or
  sets from JavaScript.

## `site/app.js`

- The latest-release lookup is cached for the browser session. The GitHub API allows 60 anonymous
  calls an hour per address, and a shared address would otherwise spend one on every page view.
- Reveal-on-scroll and the progress count-up are skipped entirely under reduced motion. The CSS
  only hides an element after this script has marked it, so nothing can stay hidden.
- The segmented control is generic; callers listen for the `seg:change` event.
- The style-guide page prints each token's computed value so the documentation cannot drift from
  the CSS.
- The FAQ opens a single answer when the URL hash names it (for example `#faq-smartscreen`).

## `site/styles.css` and `site/design-system.css`

Design rationale is in [site-design-system.md](../design/site-design-system.md).

- Components read the semantic tokens, never the primitive colour tokens above them.
- Reveal-on-scroll hides content only under `html.js`, so readers without JavaScript see
  everything. It animates the individual `translate` property so it never fights a card's own
  hover `transform`.
- The border beam is a masked conic gradient whose start angle (`--beam`, registered with
  `@property`) is animated.
- The spotlight applies to hover-capable fine pointers only.
- The install-steps beam is driven by `--flow-p` (0 to 1), which the script sets.
- `design-system.css` holds only the scaffolding of the style-guide page. Every component shown
  there comes from `styles.css`.

## `tools/check_shadowing.ps1`

- Reports which archive the game reads each scenario from, to detect another archive shadowing
  the Thai scripts in `patch.xp3`. Load order, lowest first:
  `scn.xp3 < patch_extra.xp3 < patch.xp3 < adult.xp3`. See
  [R18_COMPAT.md](../../tools/R18_COMPAT.md).
- Real file names come from the `sen:` blob's `hnfn` table (adler32 to file name).
- Exit 0 means the Thai scripts win everywhere; exit 1 means they are shadowed.
- `-ExtraDir <folder>` simulates an installed R18 patch without copying 2.5 GB of archives.
  `-Ignore adult.xp3` simulates a machine without `adult.xp3`.

```powershell
powershell -File tools\check_shadowing.ps1 -GameDir "E:\SteamLibrary\steamapps\common\SenrenBanka"
powershell -File tools\check_shadowing.ps1 -GameDir "...\SenrenBanka" -ExtraDir "...\senrenbanka_r18patch"
powershell -File tools\check_shadowing.ps1 -GameDir "...\SenrenBanka" -Ignore adult.xp3
```

## `tools/check_thai.ps1`

- One command answers "will the game really show Thai": find the archive that wins the load
  order (`check_shadowing.ps1`), extract it with GARbro, count Thai strings in the real scripts
  (`verify_thai.py`), and check that the fonts in `data.xp3` have Thai glyphs.
- The last archive in the load order that holds a file is the one the game uses.
- Exit 0 is pass, 1 is fail, 2 is partial (Thai shows, some scenarios are untranslated).

```powershell
powershell -File tools\check_thai.ps1 -GameDir "E:\SteamLibrary\steamapps\common\SenrenBanka"
```

## `tools/garbro_extract.ps1`

- GARbro ships only `GARbro.GUI.exe`, but `GameRes.dll` and `ArcFormats.dll` are plain .NET
  assemblies, so the script drives them directly and extraction can be automated.
- Never hook `AppDomain.AssemblyResolve` with a PowerShell script block. Running PowerShell code
  inside the resolver re-enters assembly resolution and ends in an uncatchable
  `StackOverflowException`. The script preloads every DLL in the GARbro folder instead.
- `GameData\Formats.dat` is the per-game encryption scheme database; the GUI loads it at start-up
  and the script has to do the same.
- `-ListAll` (with `-ListOnly`) prints every match instead of the first five. `-KeepPaths` keeps
  the archive's sub-folders, which UI images need because they share file names across folders.

```powershell
powershell -File tools\garbro_extract.ps1 -Archive "...\adult.xp3" -OutDir "...\adult_extract" -Filter "*.ks.scn"
powershell -File tools\garbro_extract.ps1 -Archive "...\patch.xp3" -OutDir "..." -Filter "*.ks.scn" -ListOnly
```

## `tools/xp3_keystream.ps1`

- The game's cipher (`SenrenCxCrypt` in GARbro) is a pure XOR: `Decrypt(x) = x ^ Decrypt(0)`,
  checked on 4,096 random bytes with no violations. Decrypting a buffer of zeros therefore gives
  the keystream of an entry at any length, so the new file may be any size. The
  `origEnc XOR origPlain` method (R4) only covers the original length. See
  [ui-translation.md](../ui-translation.md).
- Input: a TSV with `<entry name> TAB <length>` per line.
- Output: `<OutDir>\<index>.ks` (raw keystream bytes; the index is the zero-based line number) and
  `<OutDir>\manifest.tsv` with `index TAB name TAB archive offset`. The archive index stores
  hashed names, so the offset is how `xp3.py` finds the entry.

```powershell
powershell -File tools\xp3_keystream.ps1 -Archive "...\data.xp3.orig" -List req.tsv -OutDir ks
```

## `tools/test_installer.sh`

- Tests the installer package that `build_release.py` produces by simulating fresh installs:
  `bash tools/test_installer.sh thai_work/dist/senrenbanka-thai-patch-v1.1`. `install.bat`
  touches gigabytes of game files, and a mistake costs a player those files, so this runs before
  every release without touching the real game.
- The source files in each test folder are hard links to the real pristine archives. Nothing is
  copied, and `move` in `install.bat` only renames the link. Test 6 confirms the originals are
  unchanged.
- Expected SHA256 values are read from the built `install.bat`. The installer is the source of
  truth; nothing is synchronised by hand.
- A Steam-only machine also has `patch_extra.xp3`, but it is Steam's file, not the R18 patch's.
  The all-ages cases link it from `patch_extra.xp3.steam.bak`.
- The `.bat` files are always called by full path. A machine with
  `NoDefaultCurrentDirectoryInExePath` set does not find a `.bat` in the current directory; this
  happened while the test was written.
- Helper arguments: `chk <label> <file> <expected sha256>`, `setup <dir> <r18|allages>`.

## Python files

- `# -*- coding: utf-8 -*-` lines were removed: Python 3 source is UTF-8 by default.
- `# noqa: E402` markers were removed: no linter runs in CI. The imports they marked come after
  a `sys.path.insert(...)` on purpose, because `tools/` is not a package. `import PIL` in
  `tools/test_pipeline.py` is an availability probe, not an unused import.
- `tools/hfilter.py`, `pipeline_cn.py`, `port_r18.py`, `track.py`, `tsv.py` and `ui_assets.py`
  print their usage text from a `USAGE` constant. The text is unchanged and stays in the code.
- `tools/ui_render.py`: how the CN text is located and redrawn is described in
  [ui-translation.md](../ui-translation.md). Inputs are
  `thai_work/ui/pimg/<sheet>_{cn,jp,en}.json` with their layer images (from
  `ui_assets.py inventory`), `thai_work/fonts/ui/NotoSerifThai.ttf` and
  `tools/gui/ui/fonts/Sarabun-*.ttf`. Outputs are `thai_work/ui/th/<sheet>/` and
  `thai_work/ui/review/<sheet>.png`.
