#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.stdout.reconfigure(encoding="utf-8")
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P
FD = P.FONTS
SHS_DIR = os.path.join(P.EXTRACT_DATA, "font")
PUNCT = [0x300C, 0x300D, 0x300E, 0x300F, 0x3010, 0x3011, 0x3001, 0x3002, 0x30FB, 0x301C,
         0x266A, 0xFF01, 0xFF1F, 0xFF08, 0xFF09,
         0x2026, 0x2015, 0x2014, 0xFF5E]

BASE = "NotoSansThai-Regular.ttf"

def target_codepoints(scmap):
    cps = set(PUNCT)
    cps |= set(range(0x3040, 0x3100))
    for cp in range(0x4E00, 0xA000):
        try:
            chr(cp).encode("gb2312"); cps.add(cp)
        except Exception:
            pass
    return [cp for cp in sorted(cps) if cp in scmap]

def merge_glyphs():
    src = TTFont(os.path.join(SHS_DIR, "SourceHanSansSC-Regular.otf"))
    dst = TTFont(os.path.join(FD, BASE))
    assert src["head"].unitsPerEm == dst["head"].unitsPerEm == 1000
    scmap = src.getBestCmap(); sgs = src.getGlyphSet()
    glyf = dst["glyf"]; hmtx = dst["hmtx"]
    order = dst.getGlyphOrder()
    dcmap = dst.getBestCmap()
    added = []
    for cp in target_codepoints(scmap):
        if cp in dcmap:
            continue
        sname = scmap[cp]; newname = "uni%04X" % cp
        pen = TTGlyphPen(None)
        sgs[sname].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyf[newname] = pen.glyph()
        hmtx[newname] = (int(round(sgs[sname].width)), 0)
        if newname not in order: order.append(newname)
        added.append((cp, newname))
    dst.setGlyphOrder(order)
    for t in dst["cmap"].tables:
        if t.isUnicode():
            for cp, nm in added: t.cmap[cp] = nm
    removed25 = 0
    for t in dst["cmap"].tables:
        if 0x25CC in t.cmap:
            del t.cmap[0x25CC]; removed25 += 1
    print(f"  removed U+25CC from {removed25} cmap subtable(s) (krkrz mark-advance fix)")
    out = os.path.join(FD, "Sarabun-merged.ttf")
    dst.save(out)
    sz = os.path.getsize(out)
    print(f"merged {len(added)} glyphs (punct+kana+GB2312 Han) -> {out} ({sz/1048576:.2f} MB)")
    chk = TTFont(out); cm = chk.getBestCmap()
    def cnt(lo, hi): return sum(1 for c in cm if lo <= c <= hi)
    print(f"  cmap: Thai={cnt(0x0E00,0x0E7F)} Han={cnt(0x4E00,0x9FFF)} "
          f"kana={cnt(0x3040,0x30FF)} total={len(cm)} | U+25CC={'IN(!)' if 0x25CC in cm else 'gone'}")
    miss = [hex(cp) for cp in (0x65B0, 0x6E38, 0x5B58, 0x3042, 0x30A2, 0x266A, 0x300C) if cp not in cm]
    print("  spot-check (新游存 あ ア ♪ 「) missing:", miss or "none")

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
