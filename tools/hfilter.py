#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hfilter.py — mark which R18 script lines belong to sexual scenes, so mt.py never
sends them for translation.

The patch's policy: story lines in the R18 chapters are machine-translated; lines
inside sex scenes are left for a human translator. R18 scripts interleave both,
so each line is labelled by Claude Haiku from the JP/EN text in context, then the
labels are smoothed — a scene is contiguous, so short unlabelled gaps between
sexual lines (<= GAP) are treated as part of the scene. When unsure, the model is
told to label the line sexual: a missed story line costs a line of Chinese, a
missed scene line would be translated against policy.

    python tools/hfilter.py run 115 211 317 429 513 523
    python tools/hfilter.py show 115            # print the scene ranges

Output: thai_work/mt/hflags_r18.json  {prefix: [idx, ...]}   (R18 idx numbering)
"""
import os, sys, json
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
import mt

MODEL = "claude-haiku-5-5"
CHUNK = 60
GAP = 3
MARGIN = 6
FLAGS = mt.HFLAGS
RAW = FLAGS.replace(".json", ".raw.json")


def _idx_key(i: str) -> int:
    return int(i) if i.isdigit() else 10 ** 9

PROMPT = """You label lines of a Japanese visual-novel script (with the official English).
Return the idx of every line that is part of a sexual scene: sexual acts or foreplay,
undressing for sex, explicit descriptions of bodies in a sexual context, moaning or
dialogue during sex, and the immediate afterglow of the act.
Lines that are NOT sexual: everyday conversation, story events, romance without sex
(confessions, holding hands, an ordinary kiss outside a sex scene), jokes and teasing
that don't describe sexual acts.
If a line sits inside a sexual scene, or you are unsure, include it."""

SCHEMA = {"type": "object",
          "properties": {"sexual_idx": {"type": "array", "items": {"type": "string"}}},
          "required": ["sexual_idx"], "additionalProperties": False}


def rows_of(pf: str) -> list:
    return [r for r in mt.load_rows("r18") if mt.prefix(r["file"]) == pf and not mt.is_marker(r)]


def label(key: str, rows: list) -> set:
    body = {"model": MODEL, "max_tokens": 8000,
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            "system": PROMPT,
            "messages": [{"role": "user", "content": json.dumps(
                [{"idx": r["idx"], "speaker": r["speaker_en"], "jp": r["jp"], "en": r["en"]} for r in rows],
                ensure_ascii=False)}]}
    msg = mt.call("POST", "/messages", body, key)
    mt.log_usage("hfilter", msg.get("usage", {}), False)
    if msg.get("stop_reason") != "end_turn":
        return {r["idx"] for r in rows}
    want = {r["idx"] for r in rows}
    return {i for i in json.loads(mt.text_of(msg))["sexual_idx"] if i in want}


def smooth(rows: list, flagged: set) -> set:
    pos = [k for k, r in enumerate(rows) if r["idx"] in flagged]
    keep = set(pos)
    for a, b in zip(pos, pos[1:]):
        if 1 < b - a <= GAP + 1:
            keep.update(range(a + 1, b))
    wide = set()
    for k in keep:
        wide.update(range(max(0, k - MARGIN), min(len(rows), k + MARGIN + 1)))
    return {rows[k]["idx"] for k in wide}


def cmd_resmooth(prefixes: list):
    raw = json.load(open(RAW, encoding="utf-8"))
    flags = json.load(open(FLAGS, encoding="utf-8"))
    for pf in prefixes:
        rows = rows_of(pf)
        flags[pf] = sorted(smooth(rows, set(raw[pf])), key=_idx_key)
        print("%s: %d raw -> %d flagged of %d" % (pf, len(raw[pf]), len(flags[pf]), len(rows)))
    json.dump(flags, open(FLAGS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)


def cmd_run(prefixes: list):
    key = mt.load_key()
    flags = json.load(open(FLAGS, encoding="utf-8")) if os.path.exists(FLAGS) else {}
    raw = json.load(open(RAW, encoding="utf-8")) if os.path.exists(RAW) else {}
    for pf in prefixes:
        rows = rows_of(pf)
        parts = [rows[i:i + CHUNK] for i in range(0, len(rows), CHUNK)]
        with ThreadPoolExecutor(4) as ex:
            got = set().union(*ex.map(lambda p: label(key, p), parts))
        raw[pf] = sorted(got)
        final = smooth(rows, got)
        flags[pf] = sorted(final, key=_idx_key)
        print("%s: %d lines, %d labelled sexual, %d after smoothing" % (pf, len(rows), len(got), len(final)))
    os.makedirs(mt.MT, exist_ok=True)
    json.dump(flags, open(FLAGS, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(raw, open(RAW, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    mt.cmd_cost()


def cmd_show(pf: str):
    flags = set(json.load(open(FLAGS, encoding="utf-8")).get(pf, []))
    rows = rows_of(pf)
    start = None
    for k, r in enumerate(rows + [None]):
        on = r is not None and r["idx"] in flags
        if on and start is None:
            start = k
        if not on and start is not None:
            print("  scene idx %s..%s (%d lines)" % (rows[start]["idx"], rows[k - 1]["idx"], k - start))
            start = None
    print("%s: %d of %d lines flagged" % (pf, len(flags), len(rows)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 2 and sys.argv[1] == "run":
        cmd_run(sys.argv[2:])
    elif len(sys.argv) > 2 and sys.argv[1] == "resmooth":
        cmd_resmooth(sys.argv[2:])
    elif len(sys.argv) > 2 and sys.argv[1] == "show":
        cmd_show(sys.argv[2])
    else:
        print(__doc__)
