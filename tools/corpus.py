#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import glob
import json
import os
from dataclasses import dataclass

import freemote
import paths as P
import scenario
import xp3

CN = scenario.CN


@dataclass(frozen=True)
class Corpus:
    name: str
    json_dir: str
    psb_dir: str
    csv: str
    layout: scenario.Layout


ALL_AGES_CORPUS = Corpus("all-ages", P.JSON_CN, P.PSB_CN, P.CSV_CN, scenario.ALL_AGES)
R18_CORPUS = Corpus("r18", P.JSON_R18, P.PSB_R18, P.CSV_R18, scenario.R18)


def split_rows(rows) -> tuple[dict, dict]:
    blk, cho = {}, {}
    for r in rows:
        i = r["idx"]
        if i.startswith("ch"):
            cho.setdefault(r["file"], {})[int(i[2:])] = r
        else:
            blk.setdefault(r["file"], {})[int(i)] = r
    return blk, cho


def decompile(c: Corpus, srcdir: str, fm: freemote.FreeMote | None = None) -> int:
    fm = fm or freemote.default()
    files = sorted(glob.glob(os.path.join(srcdir, "*.ks.scn")))
    for fp in files:
        fm.decompile(fp, c.json_dir)
    return len(files)


def apply(c: Corpus, sub: str | None = None) -> tuple[int, int]:
    with open(c.csv, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["th"] = r["th"].replace("～", "〜")
    blk, cho = split_rows(rows)

    tot = ctot = 0
    for jf in scenario.json_files(c.json_dir):
        name = os.path.basename(jf)
        if sub and sub not in name:
            continue
        be, ce = blk.get(name), cho.get(name)
        if not be and not ce:
            continue
        with open(jf, encoding="utf-8") as f:
            d = json.load(f)
        n = cn = 0
        for i, b in enumerate(c.layout.blocks(d)):
            r = be and be.get(i)
            if r and r["th"].strip():
                b[CN][1] = r["th"]
                if r["speaker_en"].strip():
                    b[CN][0] = r["speaker_en"]
                n += 1
        for i, x in enumerate(c.layout.choices(d)):
            r = ce and ce.get(i)
            if r and r["th"].strip():
                for k in ("searchtext", "speechtext", "text"):
                    if k in x["language"][CN]:
                        x["language"][CN][k] = r["th"]
                cn += 1
        tot += n
        ctot += cn
        if n or cn:
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
    return tot, ctot


def recompile(c: Corpus, sub: str | None = None, fm: freemote.FreeMote | None = None):
    fm = fm or freemote.default()
    for jf in scenario.json_files(c.json_dir):
        if sub and sub not in os.path.basename(jf):
            continue
        fm.build(jf, c.psb_dir)


def pack(c: Corpus, name: str, extract: str):
    archive = P.game_file(name)
    ar = xp3.Archive.read(xp3.backup_once(archive))

    mine = {os.path.basename(p): p for p in glob.glob(os.path.join(c.psb_dir, "*.ks.scn"))}
    skipped = []
    for entry, plain in ar.match_by_size(extract).items():
        myscn = mine.get(os.path.basename(plain))
        if not myscn:
            continue
        with open(plain, "rb") as f:
            orig = f.read()
        with open(myscn, "rb") as f:
            new = f.read()
        if not ar.replace(entry, new, orig):
            skipped.append((os.path.basename(plain), len(new), entry.size))

    print(f"{name}: matched+encrypted {ar.replaced} scenarios")
    for n, got, cap in skipped:
        print(f"  SKIP {n}: recompiled {got} > orig {cap}")
    ar.save(archive)
    print(f"  wrote {archive} ({os.path.getsize(archive)} bytes)")
