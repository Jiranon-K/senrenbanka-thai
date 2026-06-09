#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the Thai message font:
  1. Merge CJK punctuation glyphs (「」『』、。・〜♪！？) from SourceHanSansSC (CFF)
     into Sarabun (glyf) via cu2qu (UPM 1000 == 1000, no scaling). -> Sarabun-merged.ttf
  2. Make 3 SC variants carrying each SourceHanSansSC-{Regular,Bold,Heavy} name table
     + weight so Windows GDI face-matching works. -> thai_work/fonts/variants/
"""
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FD   = os.path.join(GAME, "thai_work", "fonts")
SHS_DIR = os.path.join(GAME, "dataxp3", "font")
CODEPOINTS = [0x300C, 0x300D, 0x300E, 0x300F, 0x3010, 0x3011, 0x3001, 0x3002, 0x30FB, 0x301C,
              0x266A, 0xFF01, 0xFF1F, 0xFF08, 0xFF09,    # 【】(name brackets cn) + （）(chapter)
              0x2026, 0x2015, 0x2014, 0xFF5E]            # … ― —  ～  (Noto Thai base lacks these; Sarabun had them)

BASE = "NotoSansThai-Regular.ttf"   # Thai message font base (was Sarabun-Regular.ttf). UPM must == 1000.

def merge_glyphs():
    src = TTFont(os.path.join(SHS_DIR, "SourceHanSansSC-Regular.otf"))
    dst = TTFont(os.path.join(FD, BASE))
    assert src["head"].unitsPerEm == dst["head"].unitsPerEm == 1000
    scmap = src.getBestCmap(); sgs = src.getGlyphSet()
    glyf = dst["glyf"]; hmtx = dst["hmtx"]
    order = dst.getGlyphOrder()
    added = []
    for cp in CODEPOINTS:
        if cp not in scmap:
            print("  WARN source missing", hex(cp)); continue
        sname = scmap[cp]; newname = "uni%04X" % cp
        pen = TTGlyphPen(None)                                  # contour-only glyphs
        sgs[sname].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyf[newname] = pen.glyph()
        hmtx[newname] = (int(round(sgs[sname].width)), 0)
        if newname not in order: order.append(newname)
        added.append((cp, newname))
    dst.setGlyphOrder(order)
    # add to every unicode cmap subtable
    for t in dst["cmap"].tables:
        if t.isUnicode():
            for cp, nm in added: t.cmap[cp] = nm
    # CRITICAL (krkrz GDI fix): remove U+25CC dotted-circle from cmap.
    # krkrz advances the pen by GetTextExtentPoint32(char,1). For an isolated Thai
    # combining mark, Uniscribe inserts a dotted circle (U+25CC, adv ~594) -> the
    # mark reports a positive advance -> gap after every mark. Fonts WITHOUT a 25CC
    # glyph (e.g. Sarabun) report advance 0 -> no gap. So strip 25CC. Verified via GDI.
    removed25 = 0
    for t in dst["cmap"].tables:
        if 0x25CC in t.cmap:
            del t.cmap[0x25CC]; removed25 += 1
    print(f"  removed U+25CC from {removed25} cmap subtable(s) (krkrz mark-advance fix)")
    out = os.path.join(FD, "Sarabun-merged.ttf")
    dst.save(out)
    print(f"merged {len(added)} glyphs -> {out}")
    # verify
    chk = TTFont(out); cm = chk.getBestCmap()
    miss = [hex(cp) for cp in CODEPOINTS if cp not in cm]
    print("  verify cmap missing:", miss or "none",
          "| sample 300C contours:", len(chk['glyf']['uni300C'].coordinates) if 'uni300C' in chk['glyf'].glyphs else "N/A")

def make_variants():
    vdir = os.path.join(FD, "variants"); os.makedirs(vdir, exist_ok=True)
    merged = os.path.join(FD, "Sarabun-merged.ttf")
    for w in ("Regular", "Bold", "Heavy"):
        o = TTFont(os.path.join(SHS_DIR, f"SourceHanSansSC-{w}.otf"), lazy=True)
        s = TTFont(merged)
        s["name"].names = [n for n in o["name"].names]
        s["OS/2"].usWeightClass = o["OS/2"].usWeightClass
        s["OS/2"].fsSelection   = o["OS/2"].fsSelection
        s["head"].macStyle      = o["head"].macStyle
        out = os.path.join(vdir, f"SourceHanSansSC-{w}.ttf")
        s.save(out)
        fam = TTFont(out)["name"].getDebugName(1)
        print(f"  variant {w}: {out}  family={fam!r}")

if __name__ == "__main__":
    merge_glyphs()
    make_variants()
