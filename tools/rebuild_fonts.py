#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild data.xp3 from data.xp3.orig: replace SourceHanSansSC-{Regular,Bold,Heavy}
with the merged Sarabun variants (Thai + CJK punctuation glyphs).

Uses the same keystream trick as the scenario packers — see tools/xp3.py.
Fonts are the one case where the archive's own entry name IS the real filename,
so these are matched by name instead of by size.
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
import targets as T
import xp3

VAR = P.FONT_VARIANTS
SHS = os.path.join(P.EXTRACT_DATA, "font")
# ชื่อใน archive -> (ไฟล์ variant ที่ merge ไทยแล้ว, ไฟล์ต้นฉบับที่ถอดรหัสแล้ว)
EDITS = {
    "5fe64cd667860a8436ceae6bbaf1f5ce": ("SourceHanSansSC-Regular.ttf", "SourceHanSansSC-Regular.otf"),
    "eb936bac69df4fe4dbdc6dd191044be0": ("SourceHanSansSC-Bold.ttf",    "SourceHanSansSC-Bold.otf"),
    "ec5a25946224844562dd5e43b255f916": ("SourceHanSansSC-Heavy.ttf",   "SourceHanSansSC-Heavy.otf"),
}


def main():
    # ชื่อไฟล์ต้นฉบับมาจากตารางเดียวกับ installer — data.xp3 สำรองเป็น .bak
    # ไม่ใช่ .orig (adult.xp3 ต่างหากที่ใช้ .orig) ตรงนี้เคยเดาเอาเองว่า .orig
    # ทั้งคู่ แล้ว assert ตกทุกครั้งที่รัน
    t = T.by_file("data.xp3")
    dst = P.game_file(t.file)
    orig = P.game_file(t.orig)
    assert os.path.exists(orig), "%s missing" % t.orig

    ar = xp3.Archive.read(orig)
    for name, (vfile, pfile) in EDITS.items():
        entry = ar.find(name)
        assert entry is not None, f"ไม่พบ {name} ใน data.xp3"
        with open(os.path.join(VAR, vfile), "rb") as f: variant = f.read()
        with open(os.path.join(SHS, pfile), "rb") as f: plain = f.read()
        assert ar.replace(entry, variant, plain), f"{vfile} ใหญ่เกินช่องเดิม"

    assert ar.replaced == 3, f"matched {ar.replaced}/3 SC fonts"
    ar.save(dst)
    print(f"data.xp3 rebuilt: 3 SC fonts -> merged Sarabun, "
          f"size={os.path.getsize(dst)}")


main()
