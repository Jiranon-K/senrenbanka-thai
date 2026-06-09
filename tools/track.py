#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Progress tracker for the Senren Banka Thai translation.
  track.py scan            -> build/update manifest.json + progress.json (auto-detect)
  track.py report          -> render PROGRESS.md dashboard
  track.py set <stem> packed|verified [0|1]
Auto-detect: decompiled (json_cn), translated% (strings_cn.csv). packed/verified = persisted flags.
"""
import os, sys, csv, json, glob, struct, zlib
sys.stdout.reconfigure(encoding="utf-8")
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(GAME, "thai_work")
SCN  = os.path.join(GAME, "scnxp3")
JSOND = os.path.join(WORK, "json_cn")
CSVF  = os.path.join(WORK, "strings_cn.csv")
MAN   = os.path.join(WORK, "manifest.json")
PROG  = os.path.join(WORK, "progress.json")
MD    = os.path.join(WORK, "PROGRESS.md")
H_KEYWORDS = ["初体験", "オナニー", "２回目", "いちゃラヴ", "その後"]

def route_of(name):
    for kw, r in [("芳乃","Yoshino"),("茉子","Mako"),("ムラサメ","Murasame"),("レナ","Lena"),("サブ","Sub")]:
        if kw in name: return r
    return "Common"

def is_h(name):
    return any(k in name for k in H_KEYWORDS)

def counts(stem):
    """blocks + choices from decompiled json (None if not decompiled)."""
    jf = os.path.join(JSOND, stem + ".json")
    if not os.path.exists(jf): return None, None
    d = json.load(open(jf, encoding="utf-8"))
    def isb(x): return isinstance(x,list) and len(x)==4 and all(isinstance(e,list) and len(e)>=2 and isinstance(e[1],str) for e in x)
    nb=[0]; nc=[0]
    def w(x):
        if isinstance(x,list):
            if isb(x): nb[0]+=1
            for e in x: w(e)
        elif isinstance(x,dict):
            lang=x.get("language")
            if isinstance(lang,list) and len(lang)==4 and isinstance(lang[2],dict) and "text" in lang[2]: nc[0]+=1
            for v in x.values(): w(v)
    w(d); return nb[0], nc[0]

def translated_counts():
    """per json-file: (filled, total) th from strings_cn.csv"""
    res={}
    if not os.path.exists(CSVF): return res
    for r in csv.DictReader(open(CSVF, encoding="utf-8-sig")):
        f=r["file"]; t=res.setdefault(f,[0,0]); t[1]+=1
        if r["th"].strip(): t[0]+=1
    return res

def cmd_scan():
    prog = json.load(open(PROG, encoding="utf-8")) if os.path.exists(PROG) else {}
    tc = translated_counts()
    manifest=[]
    for fp in sorted(glob.glob(os.path.join(SCN, "*.ks.scn"))):
        scn = os.path.basename(fp); stem = scn[:-4]              # *.ks
        jname = stem + ".json"
        nb, nc = counts(stem)
        filled, total = tc.get(jname, [0, 0])
        man = {"file": scn, "route": route_of(scn), "is_h": is_h(scn),
               "blocks": nb, "choices": nc}
        manifest.append(man)
        p = prog.setdefault(scn, {"packed": False, "verified": False})
        p["decompiled"] = nb is not None
        p["tr_filled"] = filled; p["tr_total"] = total or (nb or 0)
    json.dump(manifest, open(MAN, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(prog, open(PROG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"scanned {len(manifest)} files -> manifest.json + progress.json")

def stage(p):
    if p.get("verified"): return "✅ verified"
    if p.get("packed"):   return "📦 packed"
    tt, tf = p.get("tr_total", 0), p.get("tr_filled", 0)
    if tt and tf >= tt:   return "📝 translated"
    if tf:                return f"✏️ {tf}/{tt}"
    if p.get("decompiled"): return "🔧 decompiled"
    return "⬜ pending"

def cmd_report():
    manifest = json.load(open(MAN, encoding="utf-8"))
    prog = json.load(open(PROG, encoding="utf-8"))
    order = ["Common","Yoshino","Murasame","Mako","Lena","Sub"]
    by={}
    for m in manifest: by.setdefault(m["route"],[]).append(m)
    done = sum(1 for m in manifest if prog.get(m["file"],{}).get("verified"))
    packed = sum(1 for m in manifest if prog.get(m["file"],{}).get("packed"))
    lines=[f"# Senren Banka — Thai Translation Progress\n",
           f"**{packed}/{len(manifest)} packed · {done} verified**\n"]
    for r in order:
        ms = by.get(r,[])
        if not ms: continue
        pk = sum(1 for m in ms if prog.get(m["file"],{}).get("packed"))
        lines.append(f"\n## {r}  ({pk}/{len(ms)} packed)\n")
        lines.append("| file | lines | choices | H | status |")
        lines.append("|---|--:|--:|:-:|---|")
        for m in ms:
            p = prog.get(m["file"],{})
            lines.append(f"| {m['file'][:34]} | {m['blocks'] if m['blocks'] is not None else '-'} | "
                         f"{m['choices'] if m['choices'] is not None else '-'} | {'🔞' if m['is_h'] else ''} | {stage(p)} |")
    open(MD,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    print(f"report -> {MD}  ({packed}/{len(manifest)} packed, {done} verified)")

def cmd_set():
    scn, field = sys.argv[2], sys.argv[3]
    val = (sys.argv[4] != "0") if len(sys.argv) > 4 else True
    prog = json.load(open(PROG, encoding="utf-8"))
    prog.setdefault(scn, {})[field] = val
    json.dump(prog, open(PROG,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"set {scn}.{field} = {val}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv)>1 else ""
    {"scan":cmd_scan, "report":cmd_report, "set":cmd_set}.get(cmd, lambda: print(__doc__))()
