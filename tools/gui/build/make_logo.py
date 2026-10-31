#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import imgtool as I                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
GUI = os.path.dirname(HERE)
sys.path.insert(0, GUI)

import assets                                              # noqa: E402

LOGO_SIZES = assets.LOGO_SIZES
ICON_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="ไฟล์ภาพต้นฉบับ (.jpg/.png)")
    ap.add_argument("--out", default=os.path.join(GUI, "ui"))
    ap.add_argument("--focus", default="0.52,0.06",
                    help="จุดที่อยากให้อยู่กลางกรอบสี่เหลี่ยมจัตุรัส (0-1 แนวนอน,แนวตั้ง)")
    ap.add_argument("--zoom", type=float, default=1.18,
                    help="ยิ่งมากยิ่งครอปชิด (1 = สูงเต็มภาพ)")
    a = ap.parse_args()

    focus = tuple(float(v) for v in a.focus.split(","))
    os.makedirs(a.out, exist_ok=True)

    with I.Gdip() as g:
        g.open(os.path.abspath(a.source))
        print("ต้นฉบับ : %d x %d" % (g.sw, g.sh))
        box = I.cover_box(g.sw, g.sh, 1, 1, focus, a.zoom)
        print("ครอป    : x=%d y=%d %dx%d" % box)

        for s in LOGO_SIZES:
            buf = I.bgra_to_rgba(g.render(box, s, s), s, s)
            p = os.path.join(a.out, "logo@%d.png" % s)
            I.write_png_rgba(p, s, s, buf)
        print("โลโก้   : logo@%s.png" % ", logo@".join(str(s) for s in LOGO_SIZES))

        images = []
        for s in ICON_SIZES:
            buf = I.bgra_to_rgba(g.render(box, s, s), s, s)
            images.append((s, I.png_rgba(s, s, buf)))
        ico = os.path.join(a.out, "icon.ico")
        I.write_ico(ico, images)
        I.dispose(g._src)

    print("ไอคอน   : %s  (%s px, %.0f KB)"
          % (ico, "/".join(str(s) for s in ICON_SIZES),
             os.path.getsize(ico) / 1024))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
