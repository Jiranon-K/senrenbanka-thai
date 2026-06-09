#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QC for translated scenarios. Run after `import`, before `pack`.
  qc.py <substr|all>
Checks (on post-import json_cn + strings_cn.csv):
  1 untranslated  : CN slot still has Han/kana  (=> □ or original Chinese on screen)
  2 missing glyph : char in CN slot not in Sarabun-merged.ttf cmap  (=> □)
  3 tag preserve  : control codes (%NN; [..] \\n ${..} 【】) count en vs th mismatch
  4 overflow      : len(th)/len(en) > 1.7  (may overflow textbox)
  5 glossary      : en has glossary key but th missing its value
Exit 1 if any untranslated or missing-glyph (hard errors).
"""
import os, sys, csv, json, glob, re
sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(GAME, "thai_work")
JSOND = os.path.join(WORK, "json_cn")
CSVF  = os.path.join(WORK, "strings_cn.csv")
FONT  = os.path.join(WORK, "fonts", "Sarabun-merged.ttf")
GLOSS = os.path.join(WORK, "glossary.csv")

def han_kana(s): return [c for c in s if 0x4E00<=ord(c)<=0x9FFF or 0x3040<=ord(c)<=0x30FF]
def codes(s):
    return (len(re.findall(r"%\d+;", s)), len(re.findall(r"\[[^\]]*\]", s)),
            s.count("\\n"), len(re.findall(r"\$\{[^}]*\}", s)))

def main():
    sub = sys.argv[1] if len(sys.argv) > 1 else "all"
    cmap = set(TTFont(FONT).getBestCmap().keys())
    gloss = [(r["en"].strip(), r["th"].strip()) for r in csv.DictReader(open(GLOSS, encoding="utf-8-sig")) if r["en"].strip()]
    jfiles = [f for f in glob.glob(os.path.join(JSOND, "*.ks.json"))
              if not f.endswith(".resx.json") and (sub == "all" or sub in os.path.basename(f))]
    hard = 0
    for jf in jfiles:
        name = os.path.basename(jf); d = json.load(open(jf, encoding="utf-8"))
        untr=[]; miss={}
        def isb(x): return isinstance(x,list) and len(x)==4 and all(isinstance(e,list) and len(e)>=2 and isinstance(e[1],str) for e in x)
        def chk(txt):
            hk = han_kana(txt)
            if hk: untr.append(txt[:40])
            for c in txt:
                if ord(c)>0x7e and ord(c) not in cmap and not (0x0e00<=ord(c)<=0x0e7f):
                    miss[c]=miss.get(c,0)+1
        def w(x):
            if isinstance(x,list):
                if isb(x): chk(x[2][1])
                for e in x: w(e)
            elif isinstance(x,dict):
                lang=x.get("language")
                if isinstance(lang,list) and len(lang)==4 and isinstance(lang[2],dict) and "text" in lang[2]: chk(lang[2]["text"])
                for v in x.values(): w(v)
        w(d)
        print(f"\n=== {name} ===")
        if untr: print(f"  [1] UNTRANSLATED: {len(untr)}  e.g. {untr[:3]}"); hard+=1
        else: print("  [1] untranslated: 0 ✓")
        if miss: print(f"  [2] MISSING GLYPH: {[(c,hex(ord(c)),n) for c,n in miss.items()]}"); hard+=1
        else: print("  [2] missing glyph: 0 ✓")
    # CSV-based checks (tag/overflow/glossary)
    if os.path.exists(CSVF):
        rows=[r for r in csv.DictReader(open(CSVF,encoding="utf-8-sig"))
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
