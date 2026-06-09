#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Senren Banka Thai PRODUCTION pipeline (CN-slot strategy, keystream packing).

Strategy (proven working on the real game):
  * Translate into the CN language slot (index 2). Player selects "Chinese (Simplified)".
  * Fonts: data.xp3 SourceHanSansSC-{Reg,Bold,Heavy} replaced with Sarabun (done by
    tools/rebuild_data_font.py + keystream). Already applied.
  * Scenarios live (highest priority) in patch.xp3 (87/90) and scn.xp3 (3 only-scn).

WORKFLOW
  0. (GARbro) extract patch.xp3 -> <EXTRACT>\  (real filenames, decrypted plaintext).
       also scn.xp3 -> scnxp3\ (already done) for the 3 scn-only files.
  1. python pipeline_cn.py decompile <EXTRACT>      # *.ks.scn -> json\
  2. python pipeline_cn.py export                   # json -> strings.csv (jp, en | th)
  3. <translate: fill the 'th' column>
  4. python pipeline_cn.py import                   # th -> CN slot(2) in json
  5. python pipeline_cn.py recompile                # json -> psb\
  6. python pipeline_cn.py pack patch.xp3 <EXTRACT> # keystream-rebuild patch.xp3
     python pipeline_cn.py pack scn.xp3   scnxp3    # for the 3 scn-only files

KEYSTREAM packing (no cipher key needed, content-independent):
  keystream = origEnc(in archive) XOR origPlain(from extract dir, matched by size)
  newEnc    = myRecompiledPsb(padded to origEnc size) XOR keystream      ; keep native adlr
  Game regenerates the same keystream from the unchanged adlr -> decrypts to my PSB.
Preserves the Yuzu 'sen:' pre-index blob so the archive stays loadable.
"""
import os, sys, csv, json, glob, struct, zlib, shutil, subprocess
sys.stdout.reconfigure(encoding="utf-8")
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(GAME, "thai_work")
JSOND = os.path.join(WORK, "json_cn")
PSBD  = os.path.join(WORK, "psb_cn")
CSVF  = os.path.join(WORK, "strings_cn.csv")
PSBDEC = os.path.join(GAME, "tools", "FreeMote", "PsbDecompile.exe")
PSBLD  = os.path.join(GAME, "tools", "FreeMote", "PsBuild.exe")
CN = 2   # CN language slot index

def is_block(x):
    # 4 language entries [JP, EN, CN, TW]. Each entry = [name|null, text, ...ruby-variants].
    # JP entry may carry ruby variants (len>2); others usually len 2. CN text = x[2][1].
    return (isinstance(x, list) and len(x) == 4
            and all(isinstance(e, list) and len(e) >= 2
                    and (e[0] is None or isinstance(e[0], str)) and isinstance(e[1], str)
                    for e in x))
def walk(node, cb):
    if isinstance(node, list):
        if is_block(node): cb(node)
        for e in node: walk(e, cb)
    elif isinstance(node, dict):
        for k in node: walk(node[k], cb)

def is_choice(x):
    # choice option: dict with language=[JP|null, EN, CN, TW]; each lang = {searchtext,speechtext,text}
    lang = x.get("language") if isinstance(x, dict) else None
    return (isinstance(lang, list) and len(lang) == 4
            and isinstance(lang[2], dict) and "text" in lang[2])

def walk_choices(node, cb):
    if isinstance(node, dict):
        if is_choice(node): cb(node)
        for k in node: walk_choices(node[k], cb)
    elif isinstance(node, list):
        for e in node: walk_choices(e, cb)

def cmd_decompile():
    srcdir = sys.argv[2]
    os.makedirs(JSOND, exist_ok=True)
    files = sorted(glob.glob(os.path.join(srcdir, "*.ks.scn")))
    print(f"decompiling {len(files)} from {srcdir}")
    for fp in files:
        subprocess.run([PSBDEC, os.path.abspath(fp)], capture_output=True)   # FreeMote writes next to source
        base = os.path.basename(fp)[:-4]
        for ext in (".json", ".resx.json"):
            s = os.path.join(srcdir, base + ext)
            if os.path.exists(s): shutil.move(s, os.path.join(JSOND, base + ext))
    print("done ->", JSOND)

def cmd_export():
    # translation memory: preserve any th already filled in the master CSV
    prev = {}
    if os.path.exists(CSVF):
        with open(CSVF, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("th", "").strip():
                    prev[(r["file"], str(r["idx"]))] = r["th"]
    rows = []
    for jf in sorted(glob.glob(os.path.join(JSOND, "*.ks.json"))):
        if jf.endswith(".resx.json"): continue
        d = json.load(open(jf, encoding="utf-8")); name = os.path.basename(jf); idx = [0]
        def cb(b):
            jp, en = b[0][1], b[1][1]
            if jp.strip() or en.strip():
                th = prev.get((name, str(idx[0])), "")
                rows.append([name, idx[0], b[1][0] or "", jp, en, th])
            idx[0] += 1
        walk(d, cb)
        ch = [0]
        def cbc(x):
            lang = x["language"]
            en = lang[1]["text"] if isinstance(lang[1], dict) else ""
            cn = lang[2]["text"]
            th = prev.get((name, "ch%d" % ch[0]), "")
            rows.append([name, "ch%d" % ch[0], "(choice)", cn, en, th])
            ch[0] += 1
        walk_choices(d, cbc)
    with open(CSVF, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["file","idx","speaker_en","jp","en","th"]); w.writerows(rows)
    print(f"exported {len(rows)} lines -> {CSVF}")

def cmd_import():
    blk = {}; cho = {}                                   # per file: {int idx: row} and {choice n: row}
    with open(CSVF, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["th"] = r["th"].replace("～", "〜")   # FF5E fullwidth tilde -> 301C wave dash (in-font)
            i = r["idx"]
            if i.startswith("ch"): cho.setdefault(r["file"], {})[int(i[2:])] = r
            else: blk.setdefault(r["file"], {})[int(i)] = r
    tot = 0; ctot = 0
    for jf in sorted(glob.glob(os.path.join(JSOND, "*.ks.json"))):
        if jf.endswith(".resx.json"): continue
        name = os.path.basename(jf)
        d = json.load(open(jf, encoding="utf-8")); changed = False
        be = blk.get(name)
        if be:
            idx = [0]; n = [0]
            def cb(b):
                r = be.get(idx[0])
                if r and r["th"].strip():
                    b[CN][1] = r["th"]
                    if r["speaker_en"].strip(): b[CN][0] = r["speaker_en"]
                    n[0] += 1
                idx[0] += 1
            walk(d, cb); tot += n[0]; changed = changed or n[0] > 0
        ce = cho.get(name)
        if ce:
            ci = [0]; cn = [0]
            def cbc(x):
                r = ce.get(ci[0])
                if r and r["th"].strip():
                    for k in ("searchtext", "speechtext", "text"):
                        if k in x["language"][2]: x["language"][2][k] = r["th"]
                    cn[0] += 1
                ci[0] += 1
            walk_choices(d, cbc); ctot += cn[0]; changed = changed or cn[0] > 0
        if changed:
            json.dump(d, open(jf, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"imported {tot} Thai lines + {ctot} choice options into CN slot")

def cmd_recompile():
    os.makedirs(PSBD, exist_ok=True)
    sub = sys.argv[2] if len(sys.argv) > 2 else None   # optional: recompile only files matching substring
    for jf in sorted(glob.glob(os.path.join(JSOND, "*.ks.json"))):
        if jf.endswith(".resx.json"): continue
        if sub and sub not in os.path.basename(jf): continue
        subprocess.run([PSBLD, os.path.abspath(jf)], cwd=PSBD, capture_output=True)   # PsBuild writes to CWD
        base = os.path.basename(jf)[:-5]               # *.ks
        for cand in (base + ".pure.scn", base + ".psb"):
            pc = os.path.join(PSBD, cand)
            if os.path.exists(pc): shutil.move(pc, os.path.join(PSBD, base + ".scn")); break
    print("recompiled ->", PSBD)

def parse_index(d):
    ofs = struct.unpack("<Q", d[11:19])[0]
    real = struct.unpack("<Q", d[ofs+9:ofs+17])[0] if d[ofs] == 0x80 else ofs
    comp = struct.unpack("<Q", d[real+1:real+9])[0]
    return zlib.decompress(d[real+17:real+17+comp])

def cmd_pack():
    archive = os.path.join(GAME, sys.argv[2]); extract = sys.argv[3]
    orig = archive + ".orig"
    if not os.path.exists(orig): shutil.copy(archive, orig)
    d = open(orig, "rb").read()
    idx = parse_index(d)
    sp = idx.find(b"sen:"); sen = idx[sp+12:sp+12+struct.unpack("<Q", idx[sp+4:sp+12])[0]]
    blob = d[struct.unpack("<I", sen[0:4])[0]: struct.unpack("<I", sen[0:4])[0] + struct.unpack("<I", sen[12:16])[0]]
    first = idx.find(b"File"); prefix = bytearray(idx[:first])
    # size -> extracted plaintext path (origPlain), and size -> recompiled psb (myData)
    plain_by_size = {}
    for p in glob.glob(os.path.join(extract, "*.ks.scn")):
        plain_by_size.setdefault(os.path.getsize(p), []).append(p)
    psb_by_name = {os.path.basename(p): p for p in glob.glob(os.path.join(PSBD, "*.ks.scn"))}
    # parse entries
    p = first; ents = []
    while p < len(idx) and idx[p:p+4] == b"File":
        p += 4; cs = struct.unpack("<Q", idx[p:p+8])[0]; p += 8
        chunk = idx[p:p+cs]; p += cs
        q = 0; subs = []; nm = off = size = None
        while q < len(chunk):
            tag = chunk[q:q+4]; q += 4; ss = struct.unpack("<Q", chunk[q:q+8])[0]; q += 8
            sd = bytearray(chunk[q:q+ss]); q += ss; subs.append([tag, sd])
            if tag == b"info":
                nl = struct.unpack("<H", sd[20:22])[0]; nm = sd[22:22+nl*2].decode("utf-16-le", "replace")
            if tag == b"segm":
                off = struct.unpack("<Q", sd[4:12])[0]; size = struct.unpack("<Q", sd[12:20])[0]
        ents.append({"subs": subs, "name": nm, "off": off, "size": size})
    enc_map = {}; nrepl = 0
    for e in ents:
        cands = plain_by_size.get(e["size"], [])
        if len(cands) != 1: continue                   # match scenario entry to its plaintext by unique size
        realname = os.path.basename(cands[0])
        myscn = psb_by_name.get(realname)
        if not myscn: continue                          # not translated/recompiled
        origE = d[e["off"]:e["off"]+e["size"]]
        origP = open(cands[0], "rb").read()
        mydata = open(myscn, "rb").read()
        if len(mydata) > e["size"]:
            print(f"  SKIP {realname}: recompiled {len(mydata)} > orig {e['size']}"); continue
        mydata = mydata + b"\x00" * (e["size"] - len(mydata))
        ks = bytes(origE[i] ^ origP[i] for i in range(e["size"]))
        enc_map[e["name"]] = bytes(mydata[i] ^ ks[i] for i in range(e["size"]))
        nrepl += 1
    print(f"{sys.argv[2]}: matched+encrypted {nrepl} scenarios")
    # write
    buf = bytearray(d[0:40]) if d[struct.unpack('<Q',d[11:19])[0]] == 0x80 else None
    assert buf is not None, "expected v2 header"
    for e in ents:
        payload = enc_map.get(e["name"], d[e["off"]:e["off"]+e["size"]])
        e["newoff"] = len(buf); e["newsize"] = len(payload); buf += payload
    nbo = len(buf); buf += blob; iofs = len(buf)
    struct.pack_into("<I", prefix, prefix.find(b"sen:")+12, nbo)
    nidx = bytearray(prefix)
    for e in ents:
        for tag, sd in e["subs"]:
            if tag == b"segm": sd[4:12] = struct.pack("<Q", e["newoff"])   # only offset moves (sizes unchanged: padded to orig)
        chunk = bytearray()
        for tag, sd in e["subs"]: chunk += tag + struct.pack("<Q", len(sd)) + sd
        nidx += b"File" + struct.pack("<Q", len(chunk)) + chunk
    cidx = zlib.compress(bytes(nidx), 6)
    buf += b"\x01" + struct.pack("<Q", len(cidx)) + struct.pack("<Q", len(nidx)) + cidx
    buf[32:40] = struct.pack("<Q", iofs)
    open(archive, "wb").write(buf)
    print(f"  wrote {archive} ({len(buf)} bytes)")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"decompile": cmd_decompile, "export": cmd_export, "import": cmd_import,
     "recompile": cmd_recompile, "pack": cmd_pack}.get(cmd, lambda: print(__doc__))()
