#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge thai_work/th/<prefix>.tsv (idx<TAB>th) into strings_cn.csv th column.
Usage: _merge.py <prefix>   e.g. _merge.py 010
"""
import csv, sys, os
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSVF = os.path.join(GAME, "thai_work", "strings_cn.csv")
pref = sys.argv[1]
th = {}
for line in open(os.path.join(GAME, "thai_work", "th", pref + ".tsv"), encoding="utf-8"):
    line = line.rstrip("\n")
    if not line: continue
    i, t = line.split("\t", 1); th[i] = t
rows = list(csv.DictReader(open(CSVF, encoding="utf-8-sig")))
fields = rows[0].keys()
applied = 0
for r in rows:
    if r["file"].startswith(pref) and r["idx"] in th:
        r["th"] = th[r["idx"]]; applied += 1
w = csv.DictWriter(open(CSVF, "w", encoding="utf-8-sig", newline=""), fieldnames=list(fields))
w.writeheader(); w.writerows(rows)
print(f"merged prefix={pref}: applied {applied} / th_entries {len(th)} -> {CSVF}")
