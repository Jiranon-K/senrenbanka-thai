#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
verify_thai.py - นับ "สตริงภาษาไทย" ในไฟล์ .ks.scn ที่ถอดรหัสแล้ว

ใช้เป็นตัวตัดสิน PASS/FAIL แบบตรงอาการ: เกมจะแสดงไทยได้ก็ต่อเมื่อ
สคริปต์ใน archive ที่ชนะลำดับโหลด (adult.xp3) มีข้อความไทยอยู่จริง

วิธีใช้
  # ถอด archive ที่จะตรวจออกมาก่อน
  powershell -File tools\garbro_extract.ps1 -Archive "...\adult.xp3" -OutDir "...\check_extract" -Filter "*.ks.scn"
  python tools/verify_thai.py "...\check_extract"

อ่าน string table ของ PSB v3 ตรงๆ (OffsetStringsData .. OffsetChunkOffsets)
ไม่ต้อง decompile ด้วย FreeMote จึงเร็วมาก
"""
import sys, os, glob, struct

sys.stdout.reconfigure(encoding="utf-8")

THAI_LO, THAI_HI = 0x0E00, 0x0E7F


def psb_strings(path):
    b = open(path, "rb").read()
    if b[:4] != b"PSB\x00":
        raise ValueError(f"{os.path.basename(path)}: ไม่ใช่ PSB (magic={b[:4]!r}) — ถอดรหัสยังไม่ถูก")
    (ver, enc, hlen, onames, ostrings, ostrdata,
     ocho, ochl, ochd, oent) = struct.unpack_from("<HHIIIIIIII", b, 4)
    blob = b[ostrdata:ocho]
    return [s for s in blob.split(b"\x00") if s]


def main():
    d = sys.argv[1]
    files = sorted(glob.glob(os.path.join(d, "*.ks.scn")))
    if not files:
        sys.exit(f"ไม่พบ *.ks.scn ใน {d}")

    tot_thai = tot_str = 0
    per_file = []
    for p in files:
        try:
            strs = psb_strings(p)
        except ValueError as e:
            print("  !!", e)
            continue
        thai = 0
        for s in strs:
            try:
                t = s.decode("utf-8")
            except UnicodeDecodeError:
                continue
            if any(THAI_LO <= ord(c) <= THAI_HI for c in t):
                thai += 1
        per_file.append((os.path.basename(p), thai, len(strs)))
        tot_thai += thai
        tot_str += len(strs)

    per_file.sort(key=lambda r: r[1])
    print(f"{'file':<50}{'thai':>8}{'strings':>10}")
    for n, th, tot in per_file:
        print(f"{n[:48]:<50}{th:>8}{tot:>10}")
    empty = sum(1 for _, th, _ in per_file if th == 0)
    print(f"\n{len(per_file)} ไฟล์ · สตริงไทยรวม {tot_thai:,} / {tot_str:,} · ไฟล์ที่ไม่มีไทยเลย {empty}")
    if tot_thai == 0:
        print("VERDICT: FAIL — ไม่มีข้อความไทยในสคริปต์ชุดนี้เลย")
        sys.exit(1)
    if empty:
        print(f"VERDICT: PARTIAL — ยังมี {empty} ไฟล์ที่ไม่มีไทย")
        sys.exit(2)
    print("VERDICT: PASS — ทุกไฟล์มีข้อความไทย")
    sys.exit(0)


if __name__ == "__main__":
    main()
