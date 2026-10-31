#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
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
import os, sys, csv, json, glob
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
import scenario
import corpus

# ระบบเลข idx ของฝั่ง all-ages — ตัวเดียวกับที่ strings_cn.csv กับ thai_work/th/
# ถูกนับไว้ **ห้ามสลับเป็น scenario.R18** ไม่งั้นคำแปล 45,182 บรรทัดเลื่อนทั้งเกม
# โดยไม่มี error อะไรเลย (อ่านหัวไฟล์ tools/scenario.py)
CORPUS = corpus.ALL_AGES_CORPUS
LAYOUT = CORPUS.layout
CN = scenario.CN

def cmd_decompile():
    srcdir = sys.argv[2]
    print(f"decompiled {corpus.decompile(CORPUS, srcdir)} from {srcdir} ->", P.JSON_CN)

def cmd_export():
    # translation memory: preserve any th already filled in the master CSV
    prev = {}
    if os.path.exists(P.CSV_CN):
        with open(P.CSV_CN, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r.get("th", "").strip():
                    prev[(r["file"], str(r["idx"]))] = r["th"]
    rows = []
    for jf in scenario.json_files(P.JSON_CN):
        d = json.load(open(jf, encoding="utf-8")); name = os.path.basename(jf)
        for idx, b in enumerate(LAYOUT.blocks(d)):
            jp, en = b[0][1], b[1][1]
            if jp.strip() or en.strip():
                rows.append([name, idx, b[1][0] or "", jp, en,
                             prev.get((name, str(idx)), "")])
        for n, x in enumerate(LAYOUT.choices(d)):
            lang = x["language"]
            en = lang[1]["text"] if isinstance(lang[1], dict) else ""
            rows.append([name, "ch%d" % n, "(choice)", lang[CN]["text"], en,
                         prev.get((name, "ch%d" % n), "")])
    with open(P.CSV_CN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f); w.writerow(["file","idx","speaker_en","jp","en","th"]); w.writerows(rows)
    print(f"exported {len(rows)} lines -> {P.CSV_CN}")

def cmd_import():
    sub = sys.argv[2] if len(sys.argv) > 2 else None   # optional: import only files matching substring
    tot, ctot = corpus.apply(CORPUS, sub)
    print(f"imported {tot} Thai lines + {ctot} choice options into CN slot")

def cmd_recompile():
    corpus.recompile(CORPUS, sys.argv[2] if len(sys.argv) > 2 else None)
    print("recompiled ->", P.PSB_CN)

def cmd_pack():
    corpus.pack(CORPUS, sys.argv[2], sys.argv[3])

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"decompile": cmd_decompile, "export": cmd_export, "import": cmd_import,
     "recompile": cmd_recompile, "pack": cmd_pack}.get(cmd, lambda: print(__doc__))()
