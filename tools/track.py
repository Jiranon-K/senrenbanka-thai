#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Progress tracker for the Senren Banka Thai translation.
  track.py scan            -> build/update scenarios.json + progress.json (auto-detect)
  track.py report          -> render PROGRESS.md dashboard
  track.py set <stem> packed|verified [0|1]
Auto-detect: decompiled (json_cn), translated% (strings_cn.csv). packed/verified = persisted flags.
"""
import os, sys, csv, json, glob
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
H_KEYWORDS = ["初体験", "オナニー", "２回目", "いちゃラヴ", "その後"]

def route_of(name):
    for kw, r in [("芳乃","Yoshino"),("茉子","Mako"),("ムラサメ","Murasame"),("レナ","Lena"),("サブ","Sub")]:
        if kw in name: return r
    return "Common"

def is_h(name):
    return any(k in name for k in H_KEYWORDS)

def counts(stem):
    """blocks + choices from decompiled json (None if not decompiled)."""
    jf = os.path.join(P.JSON_CN, stem + ".json")
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
    if not os.path.exists(P.CSV_CN): return res
    for r in csv.DictReader(open(P.CSV_CN, encoding="utf-8-sig")):
        f=r["file"]; t=res.setdefault(f,[0,0]); t[1]+=1
        if r["th"].strip(): t[0]+=1
    return res

def cmd_scan():
    prog = json.load(open(P.PROGRESS, encoding="utf-8")) if os.path.exists(P.PROGRESS) else {}
    tc = translated_counts()
    scenarios=[]
    for fp in sorted(glob.glob(os.path.join(P.EXTRACT_SCN, "*.ks.scn"))):
        scn = os.path.basename(fp); stem = scn[:-4]              # *.ks
        jname = stem + ".json"
        nb, nc = counts(stem)
        filled, total = tc.get(jname, [0, 0])
        entry = {"file": scn, "route": route_of(scn), "is_h": is_h(scn),
               "blocks": nb, "choices": nc}
        scenarios.append(entry)
        p = prog.setdefault(scn, {"packed": False, "verified": False})
        p["decompiled"] = nb is not None
        p["tr_filled"] = filled; p["tr_total"] = total or (nb or 0)
    json.dump(scenarios, open(P.SCENARIOS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(prog, open(P.PROGRESS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"scanned {len(scenarios)} files -> scenarios.json + progress.json")

def stage(p):
    if p.get("verified"): return "✅ verified"
    if p.get("packed"):   return "📦 packed"
    tt, tf = p.get("tr_total", 0), p.get("tr_filled", 0)
    if tt and tf >= tt:   return "📝 translated"
    if tf:                return f"✏️ {tf}/{tt}"
    if p.get("decompiled"): return "🔧 decompiled"
    return "⬜ pending"

def cmd_report():
    scenarios = json.load(open(P.SCENARIOS, encoding="utf-8"))
    prog = json.load(open(P.PROGRESS, encoding="utf-8"))
    order = ["Common","Yoshino","Murasame","Mako","Lena","Sub"]
    by={}
    for m in scenarios: by.setdefault(m["route"],[]).append(m)
    done = sum(1 for m in scenarios if prog.get(m["file"],{}).get("verified"))
    packed = sum(1 for m in scenarios if prog.get(m["file"],{}).get("packed"))
    lines=[f"# Senren Banka — Thai Translation Progress\n",
           f"**{packed}/{len(scenarios)} packed · {done} verified**\n"]
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
    open(P.PROGRESS_MD,"w",encoding="utf-8").write("\n".join(lines)+"\n")
    print(f"report -> {P.PROGRESS_MD}  ({packed}/{len(scenarios)} packed, {done} verified)")

def cmd_set():
    scn, field = sys.argv[2], sys.argv[3]
    val = (sys.argv[4] != "0") if len(sys.argv) > 4 else True
    prog = json.load(open(P.PROGRESS, encoding="utf-8"))
    hits = [k for k in prog if scn in k]
    if len(hits) == 1:
        scn = hits[0]                      # substring match (e.g. "005" -> full stem)
    elif len(hits) > 1:
        sys.exit(f"ambiguous '{scn}': {hits}")
    prog.setdefault(scn, {})[field] = val
    json.dump(prog, open(P.PROGRESS,"w",encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"set {scn}.{field} = {val}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv)>1 else ""
    {"scan":cmd_scan, "report":cmd_report, "set":cmd_set}.get(cmd, lambda: print(__doc__))()
