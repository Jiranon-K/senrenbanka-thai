#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
port_r18.py — ย้ายคำแปลไทยจากสคริปต์ all-ages (patch.xp3) ไปใส่สคริปต์ R18
              (adult.xp3 / patch_extra.xp3) เพื่อให้ไทยยังแสดงผลหลังลงแพตช์ R18

ทำไมต้องมีไฟล์นี้
-----------------
แพตช์ R18 ติดตั้งไฟล์ที่ทับสคริปต์บทพูด:

  * adult.xp3            861 entries — มี *.ks.scn **92 บท** + append_setup_0.tjs
                         + !scnlist_98/99.txt + cglist_0.csv + scenelist_0.csv
                         (= "append pack 0" ของระบบ sysscn/append_init.tjs)
                         **ตัวการหลัก** — append pack อยู่บนสุดของลำดับโหลด
  * patch_extra.xp3      173 MB (ของเดิม Steam = 53 MB) — มี *.ks.scn 92 บท
                         อยู่ "ใต้" patch.xp3 → ไม่ใช่ตัวการ (แต่แพ็กด้วยก็ไม่เสียหาย)

ลำดับโหลดจริง (ต่ำ -> สูง):
    scn.xp3  <  patch_extra.xp3  <  patch.xp3  <  adult.xp3

ยืนยันด้วย tools/check_shadowing.ps1 (รันจริงกับโฟลเดอร์เกมนี้):
  * ไม่มี adult.xp3            -> patch.xp3 ส่ง 86/86 บท   = PASS (ไทยขึ้น)
  * มี R18 patch_extra อย่างเดียว -> patch.xp3 ส่ง 86/86 บท   = PASS (ไทยยังขึ้น)
  * มี adult.xp3               -> patch.xp3 ส่ง  0/86 บท   = FAIL (ไทยหายเกลี้ยง)

adult.xp3 มีชื่อไฟล์จริงชุดเดียวกันกับบทที่ pipeline_cn.py เขียนทับใน patch.xp3
บทพูดทุกบรรทัดจึงถูกอ่านจาก adult.xp3 ซึ่ง CN slot ยังเป็นภาษาจีน -> ไทยหายหมด

วิธีแก้ = เอาไทยไปใส่ "สคริปต์ R18" ใน adult.xp3 แทนที่จะใส่ใน patch.xp3

ปัญหาของการ map ตรงๆ
---------------------
สคริปต์ R18 = สคริปต์ all-ages + บล็อกฉาก H ที่ถูกแทรกกลับเข้ามา
→ **ลำดับ index ของบล็อกเลื่อน** (โดยรวมเนื้อหา +11.7%, บางบท +230%)
thai_work/th/*.tsv เก็บเป็น `idx<TAB>th` ล้วนๆ ถ้า import ตาม index จะเพี้ยนทั้งบท

จึงต้อง align ด้วย **ข้อความ JP ต้นฉบับ** โดยใช้ difflib.SequenceMatcher
(รักษาลำดับ + ทนต่อการแทรก) แทนการ map ด้วย index

Workflow
--------
  # 0) GARbro: extract สคริปต์ทั้ง 2 ชุดออกมาเป็น plaintext (ชื่อไฟล์จริง)
  #      patch.xp3   -> patch_extract\     (all-ages ; ใช้เป็น origPlain ของ pipeline เดิม)
  #      adult.xp3   -> adult_extract\     (R18      ; ใช้เป็น origPlain ของไฟล์นี้)
  #
  # 1) สร้าง strings_cn.csv ของฝั่ง all-ages ให้มีคอลัมน์ th ครบก่อน (ของเดิม)
  python tools/pipeline_cn.py decompile patch_extract
  python tools/pipeline_cn.py export
  python tools/tsv.py merge 001   # ...วนทุก prefix ใน thai_work/th/
  #
  # 2) ฝั่ง R18
  python tools/port_r18.py decompile adult_extract    # -> thai_work/json_r18
  python tools/port_r18.py align                      # -> thai_work/strings_r18.csv (+รายงาน coverage)
  python tools/port_r18.py report                     # ดูว่าบทไหนต้องแปลเพิ่มเท่าไร
  #    <<< แปลแถวที่ th ว่าง (คอลัมน์ src = NEW) ในไฟล์ strings_r18.csv >>>
  python tools/port_r18.py import
  python tools/qc.py all                              # gate เดิมใช้ได้
  python tools/port_r18.py recompile                  # -> thai_work/psb_r18
  python tools/port_r18.py pack adult.xp3 adult_extract          # <-- อันที่จำเป็น
  python tools/port_r18.py pack patch_extra.xp3 adult_extract    # optional (ไว้กันเหนียว)
  #    ทั้งสอง archive เก็บบทเดียวกันและ adlr ตรงกัน (เช็คแล้ว: 001 = 812d4ee3 ทั้งคู่)
  #    -> psb ชุดเดียวแพ็กได้ทั้งสองไฟล์ ไม่ต้อง decompile ซ้ำ
  #
  # ตรวจผลก่อนเข้าเกม:
  #   powershell -File tools/check_shadowing.ps1 -GameDir "E:\...\SenrenBanka"

หมายเหตุ
--------
* 6 บทมีเฉพาะฝั่ง R18 (ไม่มีใน patch.xp3 เลย) ต้องแปลใหม่ทั้งบท:
    115・芳乃－ａｆｔｅｒ / 211・茉子－ａｆｔｅｒ / 317・ムラサメちゃんおまけルート
    429レナ・いらっしゃい / 513・サブ－小春（ａｆｔｅｒ） / 523・サブ－芦花（ａｆｔｅｒ）
* บรรทัดที่ align ไม่ติด จะปล่อยว่าง → ในเกมจะเห็นเป็นภาษาจีนเดิม (ไม่พัง ไม่ค้าง)
* pack ใช้ keystream method เดิม (ks = origEnc XOR origPlain) — ไม่ต้องรู้คีย์
"""
import os, sys, csv, json, glob, struct, zlib, shutil, subprocess, difflib

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10 ** 9)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
CN = 2                                            # CN language slot index


# ---------------------------------------------------------------- PSB walkers
# (เหมือน pipeline_cn.py ทุกประการ — คัดลอกมาเพื่อให้ไฟล์นี้รันได้เดี่ยวๆ)

def is_block(x):
    # all-ages (patch.xp3) = 4 ภาษา [JP, EN, CN, TW]
    # R18 (adult.xp3)      = 5 ภาษา [JP, EN, CN, TW, KO]  <-- เกาหลีถูกเพิ่มเข้ามา
    #   (นี่คือสาเหตุหลักที่ไฟล์ R18 ใหญ่กว่า ~11.7% ไม่ใช่ฉาก H อย่างเดียว)
    # เงื่อนไข "ทุก element เป็น str/None" กัน false positive จาก node อย่าง
    #   [["bgm","bgm",{...}], ["lse","loopse",{...}], ...] ซึ่งบังเอิญมี 4 ช่องเหมือนกัน
    return (isinstance(x, list) and len(x) in (4, 5)
            and all(isinstance(e, list) and len(e) >= 2
                    and (e[0] is None or isinstance(e[0], str)) and isinstance(e[1], str)
                    and all(v is None or isinstance(v, str) for v in e)
                    for e in x))


def walk(node, cb):
    if isinstance(node, list):
        if is_block(node): cb(node)
        for e in node: walk(e, cb)
    elif isinstance(node, dict):
        for k in node: walk(node[k], cb)


def is_choice(x):
    lang = x.get("language") if isinstance(x, dict) else None
    return (isinstance(lang, list) and len(lang) in (4, 5)      # R18 = +KO
            and isinstance(lang[2], dict) and "text" in lang[2])


def walk_choices(node, cb):
    if isinstance(node, dict):
        if is_choice(node): cb(node)
        for k in node: walk_choices(node[k], cb)
    elif isinstance(node, list):
        for e in node: walk_choices(e, cb)


def json_files(d):
    return sorted(p for p in glob.glob(os.path.join(d, "*.ks.json"))
                  if not p.endswith(".resx.json"))


# ---------------------------------------------------------------- 1. decompile

def cmd_decompile():
    srcdir = sys.argv[2]
    os.makedirs(P.JSON_R18, exist_ok=True)
    files = sorted(glob.glob(os.path.join(srcdir, "*.ks.scn")))
    print(f"decompiling {len(files)} R18 scenarios from {srcdir}")
    for fp in files:
        subprocess.run([P.PSB_DECOMPILE, os.path.abspath(fp)], capture_output=True)
        base = os.path.basename(fp)[:-4]
        for ext in (".json", ".resx.json"):
            s = os.path.join(srcdir, base + ext)
            if os.path.exists(s):
                shutil.move(s, os.path.join(P.JSON_R18, base + ext))
    print("done ->", P.JSON_R18)


# ---------------------------------------------------------------- 2. align

def _load_cn_csv():
    """strings_cn.csv (ฝั่ง all-ages) -> {file: {'blocks': [rows in order], 'choices': [rows]}}"""
    if not os.path.exists(P.CSV_CN):
        sys.exit(f"[ERROR] ไม่พบ {P.CSV_CN}\n"
                 f"        รัน pipeline_cn.py decompile/export + tsv.py merge ให้ครบก่อน")
    per = {}
    with open(P.CSV_CN, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            e = per.setdefault(r["file"], {"blocks": [], "choices": []})
            (e["choices"] if r["idx"].startswith("ch") else e["blocks"]).append(r)
    # export() เขียนตามลำดับ walk อยู่แล้ว แต่กันไว้อีกชั้น
    for e in per.values():
        e["blocks"].sort(key=lambda r: int(r["idx"]))
        e["choices"].sort(key=lambda r: int(r["idx"][2:]))
    return per


def _align(src_keys, dst_keys):
    """คืน {dst_index: src_index} จากการ align สองลิสต์ข้อความ (รักษาลำดับ)"""
    sm = difflib.SequenceMatcher(a=src_keys, b=dst_keys, autojunk=False)
    m = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                m[j1 + k] = i1 + k
    return m


def cmd_align():
    cn = _load_cn_csv()
    rows, stats = [], []
    for jf in json_files(P.JSON_R18):
        name = os.path.basename(jf)
        d = json.load(open(jf, encoding="utf-8"))

        # ---- เก็บบล็อกฝั่ง R18 ตามลำดับ walk (ต้องตรงกับตอน import เป๊ะๆ) ----
        dst_blocks = []
        walk(d, lambda b: dst_blocks.append(b))
        dst_choices = []
        walk_choices(d, lambda x: dst_choices.append(x))

        src = cn.get(name)
        # export() ของ pipeline เดิม "ข้าม" บล็อกที่ jp และ en ว่างทั้งคู่
        # จึงต้อง rebuild ลิสต์ฝั่ง dst ด้วยกติกาเดียวกัน ก่อนเอาไป align
        dst_idx_kept, dst_keys = [], []
        for i, b in enumerate(dst_blocks):
            jp, en = b[0][1], b[1][1]
            if jp.strip() or en.strip():
                dst_idx_kept.append(i)
                dst_keys.append(jp + "\x00" + (b[1][0] or ""))   # jp + ชื่อผู้พูด

        if src:
            src_keys = [r["jp"] + "\x00" + r["speaker_en"] for r in src["blocks"]]
            amap = _align(src_keys, dst_keys)
        else:
            src_keys, amap = [], {}

        matched = 0
        for k, bi in enumerate(dst_idx_kept):
            b = dst_blocks[bi]
            jp, en, cn_txt = b[0][1], b[1][1], b[CN][1]
            th, origin = "", "NEW"
            if k in amap:
                r = src["blocks"][amap[k]]
                if r.get("th", "").strip():
                    th, origin = r["th"], r["idx"]
                    matched += 1
                else:
                    origin = "UNTRANSLATED"
            rows.append([name, bi, b[1][0] or "", jp, en, cn_txt, th, origin])

        # ---- choices: align ด้วยข้อความ CN (ฝั่ง all-ages export ก็ใช้ CN เป็น 'jp') ----
        src_ch = [r["jp"] for r in src["choices"]] if src else []
        dst_ch = [x["language"][CN]["text"] for x in dst_choices]
        cmap = _align(src_ch, dst_ch)
        cmatched = 0
        for k, x in enumerate(dst_choices):
            en = x["language"][1]["text"] if isinstance(x["language"][1], dict) else ""
            cn_txt = x["language"][CN]["text"]
            th, origin = "", "NEW"
            if k in cmap:
                r = src["choices"][cmap[k]]
                if r.get("th", "").strip():
                    th, origin = r["th"], r["idx"]
                    cmatched += 1
                else:
                    origin = "UNTRANSLATED"
            rows.append([name, "ch%d" % k, "(choice)", cn_txt, en, cn_txt, th, origin])

        total = len(dst_idx_kept) + len(dst_choices)
        got   = matched + cmatched
        stats.append((name, got, total))
        flag = "" if got == total else "   <-- ต้องแปลเพิ่ม %d" % (total - got)
        print(f"  {name:<48} {got:5}/{total:<5} ({(got/total*100 if total else 100):5.1f}%){flag}")

    with open(P.CSV_R18, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "idx", "speaker_en", "jp", "en", "cn", "th", "src"])
        w.writerows(rows)

    tot = sum(t for _, _, t in stats)
    got = sum(g for _, g, _ in stats)
    pct = (got / tot * 100) if tot else 0.0
    print(f"\nรวม: reuse ได้ {got}/{tot} บรรทัด ({pct:.1f}%) — ต้องแปลใหม่ {tot-got} บรรทัด")
    print("เขียน ->", P.CSV_R18)


def cmd_report():
    """พิมพ์สถานะรายไฟล์ + เขียน thai_work/PROGRESS_R18.md เป็น dashboard"""
    if not os.path.exists(P.CSV_R18):
        sys.exit(f"[ERROR] ยังไม่มี {P.CSV_R18} — รัน `port_r18.py align` ก่อน")
    per, newonly = {}, {}
    with open(P.CSV_R18, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            e = per.setdefault(r["file"], [0, 0])
            e[1] += 1
            if r["th"].strip():
                e[0] += 1
            elif r["src"] == "NEW":
                newonly[r["file"]] = 1 + newonly.get(r["file"], 0)

    print(f"{'file':<50}{'done':>8}{'total':>8}{'todo':>8}")
    for k in sorted(per):
        d, t = per[k]
        print(f"{k[:48]:<50}{d:>8}{t:>8}{t - d:>8}")
    D = sum(v[0] for v in per.values()); T = sum(v[1] for v in per.values())
    print(f"{'TOTAL':<50}{D:>8}{T:>8}{T - D:>8}")

    # ---- dashboard ----
    done_files = sum(1 for v in per.values() if v[0] == v[1])
    md = [
        "# Senren Banka — Thai on R18 (adult.xp3) Progress",
        "",
        f"**{D:,}/{T:,} บรรทัด ({D / T * 100:.1f}%) · {done_files}/{len(per)} ไฟล์ครบ**",
        "",
        "บรรทัดที่ยังไม่แปลจะแสดงเป็นภาษาจีนเดิมในเกม (ไม่พัง) แก้ที่คอลัมน์ `th` ใน",
        "`thai_work/strings_r18.csv` แล้วรัน `import` → `recompile` → `pack`",
        "",
        "| file | done | total | todo | R18-only |",
        "|---|--:|--:|--:|--:|",
    ]
    for k in sorted(per, key=lambda x: (per[x][0] - per[x][1], x)):
        d, t = per[k]
        mark = "" if d == t else f" {t - d}"
        md.append(f"| {k.replace('.ks.json', '')} | {d} | {t} | {'✅' if d == t else mark} | {newonly.get(k, 0)} |")
    out = P.PROGRESS_R18_MD
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\nเขียน dashboard ->", out)


# ---------------------------------------------------------------- 3. import

def cmd_import():
    sub = sys.argv[2] if len(sys.argv) > 2 else None
    blk, cho = {}, {}
    with open(P.CSV_R18, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r["th"] = r["th"].replace("～", "〜")   # FF5E -> 301C (มี glyph ในฟอนต์)
            i = r["idx"]
            if i.startswith("ch"):
                cho.setdefault(r["file"], {})[int(i[2:])] = r
            else:
                blk.setdefault(r["file"], {})[int(i)] = r

    tot = ctot = 0
    for jf in json_files(P.JSON_R18):
        name = os.path.basename(jf)
        if sub and sub not in name: continue
        d = json.load(open(jf, encoding="utf-8"))
        changed = False

        be = blk.get(name)
        if be:
            blocks = []
            walk(d, lambda b: blocks.append(b))
            n = 0
            for i, b in enumerate(blocks):          # idx ในไฟล์นี้ = index ของ walk เต็ม
                r = be.get(i)
                if r and r["th"].strip():
                    b[CN][1] = r["th"]
                    if r["speaker_en"].strip(): b[CN][0] = r["speaker_en"]
                    n += 1
            tot += n; changed = changed or n > 0

        ce = cho.get(name)
        if ce:
            chs = []
            walk_choices(d, lambda x: chs.append(x))
            n = 0
            for i, x in enumerate(chs):
                r = ce.get(i)
                if r and r["th"].strip():
                    for k in ("searchtext", "speechtext", "text"):
                        if k in x["language"][CN]: x["language"][CN][k] = r["th"]
                    n += 1
            ctot += n; changed = changed or n > 0

        if changed:
            json.dump(d, open(jf, "w", encoding="utf-8"), ensure_ascii=False)

    print(f"imported {tot} Thai lines + {ctot} choice options into CN slot ({P.JSON_R18})")


# ---------------------------------------------------------------- 4. recompile

def cmd_recompile():
    os.makedirs(P.PSB_R18, exist_ok=True)
    sub = sys.argv[2] if len(sys.argv) > 2 else None
    for jf in json_files(P.JSON_R18):
        if sub and sub not in os.path.basename(jf): continue
        subprocess.run([P.PSB_BUILD, os.path.abspath(jf)], cwd=P.PSB_R18, capture_output=True)
        base = os.path.basename(jf)[:-5]            # *.ks
        for cand in (base + ".pure.scn", base + ".psb"):
            pc = os.path.join(P.PSB_R18, cand)
            if os.path.exists(pc):
                shutil.move(pc, os.path.join(P.PSB_R18, base + ".scn")); break
    print("recompiled ->", P.PSB_R18)


# ---------------------------------------------------------------- 5. pack

def parse_index(d):
    ofs = struct.unpack("<Q", d[11:19])[0]
    real = struct.unpack("<Q", d[ofs + 9:ofs + 17])[0] if d[ofs] == 0x80 else ofs
    comp = struct.unpack("<Q", d[real + 1:real + 9])[0]
    return zlib.decompress(d[real + 17:real + 17 + comp])


def cmd_pack():
    """เหมือน pipeline_cn.py pack ทุกอย่าง ต่างแค่อ่าน psb จาก thai_work/psb_r18"""
    archive = P.game_file(sys.argv[2]); extract = sys.argv[3]
    orig = archive + ".orig"
    if not os.path.exists(orig): shutil.copy(archive, orig)
    d = open(orig, "rb").read()
    idx = parse_index(d)
    sp = idx.find(b"sen:")
    sen = idx[sp + 12: sp + 12 + struct.unpack("<Q", idx[sp + 4:sp + 12])[0]]
    blob_off = struct.unpack("<I", sen[0:4])[0]
    blob = d[blob_off: blob_off + struct.unpack("<I", sen[12:16])[0]]
    first = idx.find(b"File"); prefix = bytearray(idx[:first])

    plain_by_size = {}
    for p in glob.glob(os.path.join(extract, "*.ks.scn")):
        plain_by_size.setdefault(os.path.getsize(p), []).append(p)
    psb_by_name = {os.path.basename(p): p for p in glob.glob(os.path.join(P.PSB_R18, "*.ks.scn"))}

    p = first; ents = []
    while p < len(idx) and idx[p:p + 4] == b"File":
        p += 4; cs = struct.unpack("<Q", idx[p:p + 8])[0]; p += 8
        chunk = idx[p:p + cs]; p += cs
        q = 0; subs = []; nm = off = size = None
        while q < len(chunk):
            tag = chunk[q:q + 4]; q += 4
            ss = struct.unpack("<Q", chunk[q:q + 8])[0]; q += 8
            sd = bytearray(chunk[q:q + ss]); q += ss; subs.append([tag, sd])
            if tag == b"info":
                nl = struct.unpack("<H", sd[20:22])[0]
                nm = sd[22:22 + nl * 2].decode("utf-16-le", "replace")
            if tag == b"segm":
                off = struct.unpack("<Q", sd[4:12])[0]
                size = struct.unpack("<Q", sd[12:20])[0]
        ents.append({"subs": subs, "name": nm, "off": off, "size": size})

    enc_map = {}; nrepl = 0; skipped = []
    for e in ents:
        cands = plain_by_size.get(e["size"], [])
        if len(cands) != 1: continue
        realname = os.path.basename(cands[0])
        myscn = psb_by_name.get(realname)
        if not myscn: continue
        origE = d[e["off"]:e["off"] + e["size"]]
        origP = open(cands[0], "rb").read()
        mydata = open(myscn, "rb").read()
        if len(mydata) > e["size"]:
            skipped.append((realname, len(mydata), e["size"])); continue
        mydata += b"\x00" * (e["size"] - len(mydata))
        # keystream = origEnc XOR origPlain ; newEnc = myData XOR keystream
        # ทำผ่าน big-int XOR (เร็วกว่า loop ทีละไบต์เป็นร้อยเท่า สำหรับไฟล์ระดับ MB)
        n = e["size"]
        ks_int = int.from_bytes(origE, "big") ^ int.from_bytes(origP, "big")
        enc_map[e["name"]] = (int.from_bytes(mydata, "big") ^ ks_int).to_bytes(n, "big")
        nrepl += 1
    print(f"{sys.argv[2]}: matched+encrypted {nrepl} scenarios")
    for n, got, cap in skipped:
        print(f"  SKIP {n}: recompiled {got} > orig {cap}")

    buf = bytearray(d[0:40])
    for e in ents:
        payload = enc_map.get(e["name"], d[e["off"]:e["off"] + e["size"]])
        e["newoff"] = len(buf); buf += payload
    nbo = len(buf); buf += blob; iofs = len(buf)
    struct.pack_into("<I", prefix, prefix.find(b"sen:") + 12, nbo)
    nidx = bytearray(prefix)
    for e in ents:
        for tag, sd in e["subs"]:
            if tag == b"segm": sd[4:12] = struct.pack("<Q", e["newoff"])
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
    {"decompile": cmd_decompile, "align": cmd_align, "report": cmd_report,
     "import": cmd_import, "recompile": cmd_recompile, "pack": cmd_pack
     }.get(cmd, lambda: print(__doc__))()
