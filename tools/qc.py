#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, json, re
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fontTools.ttLib import TTFont
import paths as P
import scenario

CORPUS = {
    "all-ages": (P.JSON_CN, P.CSV_CN, scenario.ALL_AGES),
    "r18":      (P.JSON_R18, P.CSV_R18, scenario.R18),
}

def han_kana(s): return [c for c in s if 0x4E00<=ord(c)<=0x9FFF or 0x3040<=ord(c)<=0x30FF]
def codes(s):
    return (len(re.findall(r"%\d+;", s)), len(re.findall(r"\[[^\]]*\]", s)),
            s.count("\\n"), len(re.findall(r"\$\{[^}]*\}", s)))

def main():
    sub = sys.argv[1] if len(sys.argv) > 1 else "all"
    which = sys.argv[2] if len(sys.argv) > 2 else "all-ages"
    if which not in CORPUS:
        sys.exit("corpus ต้องเป็น all-ages หรือ r18 (ได้ %r)" % which)
    json_dir, csv_path, layout = CORPUS[which]
    print("corpus: %s  (%s)" % (which, json_dir))

    cmap = set(TTFont(P.FONT_MERGED).getBestCmap().keys())
    gloss = [(r["en"].strip(), r["th"].strip()) for r in csv.DictReader(open(P.GLOSSARY, encoding="utf-8-sig")) if r["en"].strip()]
    jfiles = [f for f in scenario.json_files(json_dir)
              if sub == "all" or sub in os.path.basename(f)]
    hard = 0
    for jf in jfiles:
        name = os.path.basename(jf); d = json.load(open(jf, encoding="utf-8"))
        untr=[]; miss={}
        def chk(txt):
            hk = han_kana(txt)
            if hk: untr.append(txt[:40])
            for c in txt:
                if ord(c)>0x7e and ord(c) not in cmap and not (0x0e00<=ord(c)<=0x0e7f):
                    miss[c]=miss.get(c,0)+1
        for b in layout.blocks(d):
            chk(b[scenario.CN][1])
        for x in layout.choices(d):
            chk(x["language"][scenario.CN]["text"])
        print(f"\n=== {name} ===")
        if untr: print(f"  [1] UNTRANSLATED: {len(untr)}  e.g. {untr[:3]}"); hard+=1
        else: print("  [1] untranslated: 0 ✓")
        if miss: print(f"  [2] MISSING GLYPH: {[(c,hex(ord(c)),n) for c,n in miss.items()]}"); hard+=1
        else: print("  [2] missing glyph: 0 ✓")
    if os.path.exists(csv_path):
        rows=[r for r in csv.DictReader(open(csv_path,encoding="utf-8-sig"))
              if (sub=="all" or sub in r["file"]) and r["th"].strip()]
        tagbad=[]; over=[]; glo=[]
        for r in rows:
            en,th=r["en"],r["th"]
            if codes(en)!=codes(th): tagbad.append((r["idx"],codes(en),codes(th)))
            if len(en)>=20 and len(th)/max(1,len(en))>1.7: over.append((r["idx"],len(en),len(th)))
            for ge,gt in gloss:
                if ge and re.search(r"\b"+re.escape(ge)+r"\b",en) and gt and gt not in th:
                    glo.append((r["idx"],ge,gt)); break
        print(f"\n=== CSV checks ({sub}) ===")
        print(f"  [3] tag/code mismatch: {len(tagbad)}" + (f"  e.g.{tagbad[:3]}" if tagbad else " ✓"))
        print(f"  [4] overflow(>1.7x): {len(over)}" + (f"  e.g.{over[:3]}" if over else " ✓"))
        print(f"  [5] glossary miss: {len(glo)}" + (f"  e.g.{glo[:5]}" if glo else " ✓"))
    print(f"\n{'❌ HARD ERRORS — fix before pack' if hard else '✅ QC PASS (hard checks)'}")
    sys.exit(1 if hard else 0)

main()
