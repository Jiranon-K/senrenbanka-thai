#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dump source TSV (idx, speaker_en, jp, en) for a scenario stem prefix.
Control/effect rows (jp has no CJK) are excluded. Usage: _dump_src.py <prefix>"""
import csv, sys, os
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSVF = os.path.join(GAME, "thai_work", "strings_cn.csv")
pref = sys.argv[1]
def is_ctrl(r):
    return not any(ord(c) > 0x3000 for c in r["jp"])
rows = list(csv.DictReader(open(CSVF, encoding="utf-8-sig")))
sub = [r for r in rows if r["file"].startswith(pref)]
ctrl = [r for r in sub if is_ctrl(r)]
tr = [r for r in sub if not is_ctrl(r)]
nums = sorted(int(r["idx"]) for r in tr if r["idx"].isdigit())
ch = [r["idx"] for r in tr if not r["idx"].isdigit()]
out = os.path.join(GAME, "thai_work", "th", pref + ".src.tsv")
with open(out, "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter="\t")
    for r in tr:
        w.writerow([r["idx"], r["speaker_en"], r["jp"], r["en"]])
print(f"rows={len(sub)} control={len(ctrl)} translatable={len(tr)} idx {nums[0]}..{nums[-1]} choices={ch}")
print(f"wrote {out}")
