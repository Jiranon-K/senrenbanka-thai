#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

VAR = P.FONT_VARIANTS
SHS = os.path.join(P.EXTRACT_DATA, "font")
EDITS = {
    "5fe64cd667860a8436ceae6bbaf1f5ce": ("SourceHanSansSC-Regular.ttf", "SourceHanSansSC-Regular.otf"),
    "eb936bac69df4fe4dbdc6dd191044be0": ("SourceHanSansSC-Bold.ttf",    "SourceHanSansSC-Bold.otf"),
    "ec5a25946224844562dd5e43b255f916": ("SourceHanSansSC-Heavy.ttf",   "SourceHanSansSC-Heavy.otf"),
}


def apply_fonts(ar):
    before = ar.replaced
    for name, (vfile, pfile) in EDITS.items():
        entry = ar.find(name)
        assert entry is not None, f"ไม่พบ {name} ใน data.xp3"
        with open(os.path.join(VAR, vfile), "rb") as f: variant = f.read()
        with open(os.path.join(SHS, pfile), "rb") as f: plain = f.read()
        assert ar.replace(entry, variant, plain), f"{vfile} ใหญ่เกินช่องเดิม"
    assert ar.replaced - before == 3, f"matched {ar.replaced - before}/3 SC fonts"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    import ui_assets
    ui_assets.build_data()
