#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
make_logo.py — ทำโลโก้มุมบนซ้าย + ไอคอนหน้าต่าง/taskbar จากภาพต้นฉบับ

    python tools/gui/build/make_logo.py "...\ภาพ.jpg"

ทำงาน **ตอน build เท่านั้น** ได้ออกมาสองอย่าง:

    ui/logo@20.png .. logo@40.png   เครื่องหมายมุมบนซ้ายของหน้าต่าง
    ui/icon.ico                     ไอคอนหน้าต่าง / taskbar / ตัว .exe

ทำไมต้องมีหลายขนาด: Tk ย่อภาพได้แค่หารด้วยจำนวนเต็มแบบ nearest-neighbour
ซึ่งขอบจะแตกทันทีที่ย่อ จอ 125%/150%/200% จึงต้องมีไฟล์ของตัวเอง สร้างไว้
ล่วงหน้าด้วย bicubic ของ GDI+ แล้วให้แอปหยิบขนาดที่ใกล้ที่สุดไปใช้ตรงๆ

ไอคอนเก็บเป็น PNG ข้างใน .ico (รูปแบบที่ Windows อ่านได้ตั้งแต่ Vista)
จึงไม่ต้องเขียน BMP + AND mask เอง

หมายเหตุเรื่องลิขสิทธิ์: ภาพเป็นของผู้พัฒนาเกม สคริปต์นี้จึงรับ path จากภายนอก
ไม่เก็บไฟล์ต้นฉบับไว้ในที่เก็บโค้ด
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import imgtool as I                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))          # tools/gui/build
GUI = os.path.dirname(HERE)                                # tools/gui
sys.path.insert(0, GUI)

import assets                                              # noqa: E402

# ขนาดโลโก้: 20 px ตามดีไซน์ คูณด้วย DPI ที่พบบ่อย (100/125/150/200%)
# **เอามาจาก assets.py** ที่ตัวแอปใช้หาไฟล์ — เดิมประกาศไว้ทั้งสองที่พร้อม
# คอมเมนต์ว่า "ตรงกับที่ make_logo.py สร้างไว้" คือยอมรับว่าต้อง sync ด้วยมือ
LOGO_SIZES = assets.LOGO_SIZES
# ชุดที่ Windows หยิบไปใช้: taskbar 32, รายการไฟล์เล็ก 16, Alt-Tab 48, ไทล์ใหญ่ 256
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
        box = I.cover_box(g.sw, g.sh, 1, 1, focus, a.zoom)   # จัตุรัส -> tw=th=1
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
