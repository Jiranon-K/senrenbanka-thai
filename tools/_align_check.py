#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flag idx where source bracket-structure (dialogue 「/『 vs narration) disagrees with th."""
import csv, sys, os
sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10**9)
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSVF = os.path.join(GAME, "thai_work", "strings_cn.csv")
rows = [r for r in csv.DictReader(open(CSVF, encoding="utf-8-sig")) if r["file"].startswith("010")]
by = {r["idx"]: r for r in rows}
th = {}
for line in open(os.path.join(GAME, "thai_work", "th", "010.tsv"), encoding="utf-8"):
    line = line.rstrip("\n")
    if not line: continue
    i, t = line.split("\t", 1); th[i] = t
def kind(s):
    s = s.lstrip()
    if s.startswith("「") or s.startswith("『"): return "D"   # dialogue
    return "N"  # narration
mis = []
for r in rows:
    i = r["idx"]
    if i in ("0","1") or not i.isdigit(): continue
    if i not in th: continue
    sj, st = kind(r["jp"]), kind(th[i])
    if sj != st:
        mis.append((i, sj, st, r["jp"][:30], th[i][:30]))
print(f"structural mismatches: {len(mis)}")
for i, sj, st, jp, t in mis:
    print(f"[{i}] src={sj} th={st} | JP={jp} | TH={t}")
