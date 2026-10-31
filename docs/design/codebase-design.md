# Codebase design — deepening proposal (2026-10-31)

Status: **proposal**, nothing implemented. Vocabulary follows the deep-module
glossary (module, interface, depth, seam, adapter, leverage, locality).
Project terms follow [CONTEXT.md](../../CONTEXT.md) — `cn`, `repo`, `game dir`,
`target`, `layout` keep their meaning.

## Where the codebase already stands

Three modules are already deep and should be the template for the rest:

| Module | Interface | What it hides |
|---|---|---|
| `xp3.Archive` | `read` / `match_by_size` / `replace` / `save` | index format, `segm` sizes, shared payloads, `sen:` blob, keystream XOR |
| `scenario.Layout` | `blocks(d)` / `choices(d)` + two values `ALL_AGES`, `R18` | block-shape rules, walk order that idx depends on |
| `targets` | one table + `bat_*` renderers | install.bat ↔ GUI parity |

`paths.py` gives locality for every location. `test_pipeline.py` already
tests through `xp3.Archive`'s interface with synthetic archives.

## Findings (ranked by leverage)

### 1. The two scenario pipelines are one module written twice

`pipeline_cn.py` and `port_r18.py` differ only in three values:
layout (`ALL_AGES` / `R18`), CSV path, json/psb directories.
`cmd_import`, `cmd_recompile`, `cmd_pack` are copy-paste
(`port_r18.cmd_pack`'s docstring says so). This is exactly how `xp3` drifted
before it was extracted.

**Deletion test:** delete either copy's `import/recompile/pack` and nothing
is lost except the three values — a pass-through duplicated.

**Proposal:** one module `tools/line_store.py` (name open) behind a tiny interface:

```python
@dataclass(frozen=True)
class Track:            # "all-ages" or "r18"; never merged (CONTEXT.md trap #1)
    layout: scenario.Layout
    csv: str
    json_dir: str
    psb_dir: str

ALL_AGES_TRACK = Track(scenario.ALL_AGES, P.CSV_CN, P.JSON_CN, P.PSB_CN)
R18_TRACK      = Track(scenario.R18,      P.CSV_R18, P.JSON_R18, P.PSB_R18)

def apply(track, rows, only=None) -> ImportReport         # th -> CN slot, pure over dicts
def recompile(track, compiler, only=None) -> list[str]
def pack(track, archive: xp3.Archive, extract_dir) -> PackReport
```

The `Track` *value* keeps the two idx systems apart while the code is shared;
the type makes "use the wrong layout" a visible argument, not a silent copy edit.
`port_r18.py` keeps only what is really R18: `align` and `report`.

### 2. Translation-row CSV access is spread over 7 modules

`csv.DictReader(... encoding="utf-8-sig")` is open-coded in `pipeline_cn`,
`port_r18` (×3), `mt`, `tsv`, `track`, `qc`; the `"ch%d"` choice-key convention
and the `～ → 〜` normalisation live in two copies each.

**Proposal:** a `rows` module owning the row format:

```python
def load(track) -> Rows                 # keyed by (file, idx|ChoiceIdx)
def save(track, rows) -> None           # keeps BOM, column order, translation memory
Rows.blocks(file) / Rows.choices(file) / Rows.translated()
```

Normalisation (`～ → 〜`) happens once, on load. `mt`, `tsv`, `track`, `qc`,
`hfilter` become callers. Locality: a column rename touches one file.

### 3. FreeMote is a hidden dependency, not a seam

`subprocess.run([P.PSB_BUILD, ...], capture_output=True)` with the output
**discarded**, then a guess at which filename it wrote (`.pure.scn` or `.psb`).
A failed compile is silent and the scenario is just missing from the pack.

**Proposal:** a `freemote` adapter with `decompile(scn) -> json_path` and
`build(json) -> psb_path` that raises on non-zero exit or missing output.
Pass it into `recompile` (finding 1) — *accept dependencies, don't create them*.
This is a real seam (two adapters): FreeMote in production, a fake that writes
`json.dumps` bytes in `test_pipeline.py`, so import→recompile→pack can be tested
end-to-end without Windows binaries.

### 4. `cmd_*` functions read `sys.argv` and print

Every CLI entry reads `sys.argv[n]` inside the command, so no command is
callable from another module or a test (`test_pipeline.py:13` already notes
this). Pattern for every tool, matching what `tsv.py` half-does:

```python
def pack(track, archive_name, extract) -> PackReport: ...   # returns, no print
def main(argv=None) -> int:                                 # argparse, printing only here
```

Use `argparse` subparsers (stdlib; already used in `mt.py`, `build_release.py`).

### 5. Tests and CI

* CI runs `test_pipeline.py` only; `tools/gui/test_core.py`, `test_app.py`
  and `test_installer.sh` are not in the workflow although CONTEXT.md calls
  them the guard for GUI ↔ `.bat` parity. Add them.
* The hand-rolled `chk`/`skip` runner works; moving to `pytest` is optional.
  Only worth it once the suite grows (fixtures for the synthetic archive,
  `pytest.skip` for game-file cases). Do not switch just for style.
* Add a **golden idx test**: run both layouts over a small committed json
  fixture and assert block counts/order. This turns CONTEXT.md trap #1
  (layouts differ → 45,182 lines shift silently) into a mechanical check.

### 6. Packaging hygiene (low effort)

* No `pyproject.toml` / requirements — `fontTools` is an undeclared
  dependency. Add a minimal `pyproject.toml` with `fonttools` and a
  `[project.optional-dependencies] gui` group. Keep the flat `tools/` layout:
  this is a tool repo, not a library, so the `src/` layout's benefit
  (preventing accidental import of the uninstalled package) does not apply.
* Drop the `sys.path.insert(0, ...)` + `# noqa: E402` preamble once tools run
  as `python -m tools.<name>` from the repo root.
* Add `ruff` (lint + format) in CI with a narrow rule set; no reformat-all commit
  mixed with logic changes.

## Proposed layout (after 1–4)

```
tools/
  paths.py        locations (unchanged)
  xp3.py          archive module (unchanged)
  scenario.py     Layout (unchanged)
  rows.py         NEW  translation-row CSV format          (finding 2)
  line_store.py   NEW  Track + apply/recompile/pack        (finding 1)
  freemote.py     NEW  FreeMote adapter, raises on failure (finding 3)
  pipeline_cn.py  thin CLI over line_store(ALL_AGES_TRACK)
  port_r18.py     align + report, CLI over line_store(R18_TRACK)
  mt.py hfilter.py tsv.py qc.py track.py   callers of rows.py
  targets.py build_release.py gui/          (unchanged)
  tests/          test_pipeline.py split by module + fixtures/
```

## Order of work (one PR each, per the PR-only workflow)

1. ~~`freemote.py` + fake adapter + test~~ — done 2026-10-31 (branch `refactor/freemote-adapter`).
2. `line_store.py`; make both pipelines thin; golden idx test first.
3. `rows.py`; migrate callers one at a time.
4. CLI `main(argv)` refactor per tool.
5. CI: add GUI tests and `test_installer.sh`; `pyproject.toml`; ruff.

Verification for each step: `python tools/test_pipeline.py` green, plus a
byte-identical comparison of the produced `patch.xp3` / `adult.xp3` against
the v1.2 build (`build_release.py` already does reverse-diff checks).

## Sources

* J. Ousterhout, *A Philosophy of Software Design* — deep vs shallow modules.
* M. Feathers, *Working Effectively with Legacy Code* — seams; characterization
  tests before refactoring (the golden idx test).
* PyPA, "src layout vs flat layout" — packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/
* PyPA, "Writing your pyproject.toml" — packaging.python.org/en/latest/guides/writing-pyproject-toml/
* Python docs, `argparse` sub-commands.
