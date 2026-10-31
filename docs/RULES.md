# Rules

Invariants the code depends on. Breaking most of them corrupts data **without
an error**. Each one names the check that enforces it; if a rule has no
check, add one before relying on it. Run every check with:

```bash
python tools/test_pipeline.py
```

The code itself carries no comments. The rule lives here, the check lives
in tests, and the vocabulary lives in [CONTEXT.md](../CONTEXT.md).
The longer background notes that used to sit at the top of each module are in
[internals.md](internals.md).

| # | Rule | Why | Enforced by |
|---|---|---|---|
| R1 | The all-ages track uses `scenario.ALL_AGES`, the R18 track uses `scenario.R18`. Never swap them or merge them into one layout. | The two layouts count blocks differently in 70 of 86 scenarios (46,303 vs 45,208 blocks). `strings_cn.csv` and `thai_work/th/*.tsv` are numbered by `ALL_AGES`. Swapping them shifts 45,182 translated lines onto the wrong speakers, with no error. | `test_layouts_differ`, `test_corpus_layouts` |
| R2 | `Layout.blocks` / `Layout.choices` yield parent before children, left to right. Do not change the walk order. | The yield order *is* the `idx` stored in every CSV and TSV. | `test_walk_order` |
| R3 | Thai goes into slot 2 (`CN`). Names containing `cn` (`pipeline_cn.py`, `strings_cn.csv`, `json_cn`) describe that mechanism and must not be renamed to `th`. | The player selects "Chinese (Simplified)" to see Thai. The engine is not modified. | `test_layouts_differ` (`CN == 2`) |
| R4 | Archive writes use the keystream: `newEnc = newPlain (padded to the original size) XOR (origEnc XOR origPlain)`. Never touch `adlr`. A replacement must not be larger than the original entry. | The game regenerates the keystream from the untouched `adlr`. A larger file has no keystream to cover it. | `test_xp3_roundtrip`, `test_xp3_guards` |
| R5 | Copy `entry.stored` bytes, not `entry.size`. | Compressed entries store fewer bytes than their size (318 of 1,278 in `data.xp3`). Copying `size` drags in the neighbouring entry. | `test_xp3_compressed` |
| R6 | Entries that point at the same byte range share one payload when the archive is rebuilt. | `data.xp3` has 13 shared ranges (26 MB). Copying each one separately grows the file for no reason. | `test_xp3_shared_payload` |
| R7 | Keep the Yuzusoft `sen:` blob that sits before the index. | Without it the game will not load the archive. | `test_xp3_roundtrip` |
| R8 | FreeMote failures raise `FreeMoteError`. Never discard its exit code or output. | A failed build used to drop a scenario from the pack silently. | `test_freemote` |
| R9 | `install.bat` and the GUI installer act on the same target table (`tools/targets.py`). | The `.bat` runs on machines without Python; the two must stay byte-for-byte equivalent in effect. | `test_targets_table`, `test_generated_bat_matches_shipped`, `gui/test_core.py`, `test_installer.sh` |
| R10 | Never patch halfway: if `adult.xp3` exists but cannot be patched, fail the whole install. | Half-patched installs show Chinese silently, which is the hardest failure to diagnose. | `gui/test_core.py` |
| R11 | Back up by rename, not copy; check SHA256 before touching any file. | `adult.xp3` is 855 MB. The hash tells "already patched", "Steam updated" and "different R18 build" apart. | `gui/test_core.py` |
| R12 | Never commit game files or Yuzusoft artwork (`tools/gui/ui/bg.png`, `logo@*.png`, `icon.ico`). | Not ours to distribute. | `.gitignore` (deny-all, then allow) |
| R13 | `tools/gui/` must not import `paths.py` or anything under `tools/gui/build/`. | The installer ships as an `.exe` to machines with no repo. | `build_gui.py` asserts |
| R15 | Build every patched archive from the pristine file named in `targets.Target.orig`. `data.xp3` has one builder (`ui_assets.build_data`): `data.xp3.bak` → 3 fonts → UI text → one save. Every other entry must stay identical to `data.xp3.bak`. | `data.xp3.orig` was copied after the font swap. Building from it carried a blanked `main/imagedressmap.txt` into v1.2 that no tool produced. | `test_corpus_layouts` (pristine names); entry diff against v1.2 recorded in commit `8cdeaf5` |
| R14 | The R18 scripts must be packed into both `adult.xp3` and `patch_extra.xp3`. | The game has been observed reading `patch_extra.xp3`. | none yet — manual check in `tools/R18_COMPAT.md` |
