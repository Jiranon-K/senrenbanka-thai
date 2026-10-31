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
import os, sys, csv, json, glob, re, difflib

sys.stdout.reconfigure(encoding="utf-8")
csv.field_size_limit(10 ** 9)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
import scenario
import xp3
import freemote

# ระบบเลข idx ของฝั่ง R18 — รับ 5 ช่อง (มีเกาหลีเพิ่มเข้ามา) และเข้มกว่าฝั่ง
# all-ages ตรงที่ทุกสมาชิกต้องเป็นข้อความ **คนละระบบเลขกับ scenario.ALL_AGES**
# ห้ามสลับ (อ่านหัวไฟล์ tools/scenario.py)
LAYOUT = scenario.R18
CN = scenario.CN

json_files = scenario.json_files


# ---------------------------------------------------------------- 1. decompile

def cmd_decompile():
    srcdir = sys.argv[2]
    os.makedirs(P.JSON_R18, exist_ok=True)
    files = sorted(glob.glob(os.path.join(srcdir, "*.ks.scn")))
    print(f"decompiling {len(files)} R18 scenarios from {srcdir}")
    fm = freemote.default()
    for fp in files:
        fm.decompile(fp, P.JSON_R18)
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
        dst_blocks = list(LAYOUT.blocks(d))
        dst_choices = list(LAYOUT.choices(d))

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
            elif any("฀" <= c <= "๿" for c in cn_txt):
                # json_r18 was imported before, so this CN slot already holds Thai and
                # can't match the Chinese on the all-ages side — keep it, don't drop it
                th, origin = cn_txt, "KEPT"
                cmatched += 1
            rows.append([name, "ch%d" % k, "(choice)", cn_txt, en, cn_txt, th, origin])

        total = len(dst_idx_kept) + len(dst_choices)
        got   = matched + cmatched
        stats.append((name, got, total))
        flag = "" if got == total else "   <-- ต้องแปลเพิ่ม %d" % (total - got)
        print(f"  {name:<48} {got:5}/{total:<5} ({(got/total*100 if total else 100):5.1f}%){flag}")

    # Lines with no all-ages counterpart are translated separately (mt.py) and kept in
    # th_r18/<prefix>.tsv; overlay them so re-running align never drops them.
    over = {}
    for t in glob.glob(os.path.join(P.TH_R18_DIR, "*.tsv")):
        pf = os.path.basename(t)[:-4]
        for line in open(t, encoding="utf-8"):
            if line.strip():
                i, th = line.rstrip("\n").split("\t", 1)
                over[(pf, i)] = th
    kept = 0
    for row in rows:
        pf = re.match(r"^\d+[a-z]?", row[0]).group(0)
        if not row[6].strip() and (pf, str(row[1])) in over:
            row[6], row[7] = over[(pf, str(row[1]))], "TH_R18"
            kept += 1
    print("overlay th_r18/: %d lines" % kept)

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
            blocks = list(LAYOUT.blocks(d))
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
            chs = list(LAYOUT.choices(d))
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
    fm = freemote.default()
    for jf in json_files(P.JSON_R18):
        if sub and sub not in os.path.basename(jf): continue
        fm.build(jf, P.PSB_R18)
    print("recompiled ->", P.PSB_R18)


# ---------------------------------------------------------------- 5. pack

def cmd_pack():
    """เหมือน pipeline_cn.py pack ทุกอย่าง ต่างแค่อ่าน psb จาก thai_work/psb_r18"""
    name, extract = sys.argv[2], sys.argv[3]
    archive = P.game_file(name)
    ar = xp3.Archive.read(xp3.backup_once(archive))

    mine = {os.path.basename(p): p for p in glob.glob(os.path.join(P.PSB_R18, "*.ks.scn"))}
    skipped = []
    for entry, plain in ar.match_by_size(extract).items():
        myscn = mine.get(os.path.basename(plain))
        if not myscn:
            continue
        with open(plain, "rb") as f: orig = f.read()
        with open(myscn, "rb") as f: new = f.read()
        if not ar.replace(entry, new, orig):
            skipped.append((os.path.basename(plain), len(new), entry.size))

    print(f"{name}: matched+encrypted {ar.replaced} scenarios")
    for n, got, cap in skipped:
        print(f"  SKIP {n}: recompiled {got} > orig {cap}")
    ar.save(archive)
    print(f"  wrote {archive} ({os.path.getsize(archive)} bytes)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    {"decompile": cmd_decompile, "align": cmd_align, "report": cmd_report,
     "import": cmd_import, "recompile": cmd_recompile, "pack": cmd_pack
     }.get(cmd, lambda: print(__doc__))()
