#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
make_bg.py — แปลงภาพต้นฉบับเป็นแผงพื้นหลังแบบกระจกฝ้าของตัวติดตั้ง

    python tools/gui/build/make_bg.py "...\ภาพ.jpg"

ทำงาน **ตอน build เท่านั้น** ผลลัพธ์คือ `ui/bg.png` (RGBA) ที่ฝังการไล่จางไว้
ในช่อง alpha เรียบร้อยแล้ว ตัวแอปจึงแค่วางภาพลง canvas ไม่ต้องคำนวณอะไรเลย

ทำไมต้องแปลงก่อน ไม่โหลด .jpg ตรงๆ:
  * Tk อ่านได้แค่ PNG / GIF / PPM — ไม่มี JPEG
  * ห้ามลาก Pillow เข้ามาเพื่องานนี้งานเดียว (`.exe` จะโตขึ้นหลาย MB)
  * การไล่จาง/เบลอ/ลดความอิ่มสี ถ้าทำตอนรันคือเสียเวลาเปิดโปรแกรมฟรีๆ
    ทั้งที่ผลลัพธ์เหมือนเดิมทุกครั้ง

หมายเหตุเรื่องลิขสิทธิ์: ภาพ CG เป็นของผู้พัฒนาเกม สคริปต์นี้จึงรับ path
จากภายนอก ไม่เก็บไฟล์ต้นฉบับไว้ในที่เก็บโค้ด
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import imgtool as I                                          # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))          # tools/gui/build
GUI = os.path.dirname(HERE)                                # tools/gui


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="ไฟล์ภาพต้นฉบับ (.jpg/.png)")
    ap.add_argument("--out", default=os.path.join(GUI, "ui", "bg.png"))
    ap.add_argument("--size", default="280x482", help="ขนาดแผง (พิกเซลตามดีไซน์)")
    ap.add_argument("--focus", default="0.20,0.02",
                    help="จุดที่อยากให้อยู่กลางกรอบ (0-1 ตามแนวนอน,แนวตั้ง)")
    ap.add_argument("--zoom", type=float, default=1.35)
    ap.add_argument("--peak", type=float, default=0.88,
                    help="ความทึบสูงสุดที่ขอบขวา")
    ap.add_argument("--clear", type=float, default=0.30,
                    help="สัดส่วนด้านซ้ายที่ต้องใสสนิท (คอลัมน์เนื้อหาทับอยู่)")
    ap.add_argument("--ramp", type=float, default=0.55,
                    help="ไล่จากใสถึงทึบสุดภายในกี่ส่วนของที่เหลือ (ที่เหลือทึบเต็ม)")
    ap.add_argument("--fade-top", type=int, default=90)
    ap.add_argument("--fade-bottom", type=int, default=150)
    ap.add_argument("--blur", type=float, default=2.7, help="1 = ไม่เบลอ")
    ap.add_argument("--wash", type=float, default=0.09, help="ผสมขาวเข้าไปเท่าไร")
    ap.add_argument("--desat", type=float, default=0.16)
    a = ap.parse_args()

    tw, th = (int(v) for v in a.size.lower().split("x"))
    focus = tuple(float(v) for v in a.focus.split(","))

    with I.Gdip() as g:
        g.open(os.path.abspath(a.source))
        print("ต้นฉบับ  : %d x %d" % (g.sw, g.sh))
        box = I.cover_box(g.sw, g.sh, tw, th, focus, a.zoom)
        print("ครอป     : x=%d y=%d %dx%d" % box)
        # เบลอด้วยการย่อแล้วขยายกลับ — ได้ฝ้านุ่มๆ แทบไม่มีต้นทุน
        buf = g.render(box, tw, th, blur=a.blur)
        I.dispose(g._src)

    # ── แปลง BGRA -> RGBA พร้อมล้างสี ลดความอิ่ม แล้วฝังการไล่จางลง alpha
    #    fx: ใสสนิทด้านซ้าย (คอลัมน์เนื้อหาทับอยู่) แล้วค่อยเข้มขึ้นไปทางขวา
    #    fy: จางหายที่ขอบบน (ใต้แถบหัว) และขอบล่าง (เหนือปุ่ม) ไม่ให้มีรอยตัด
    clear_px = tw * a.clear
    ramp_px = max(1.0, (tw - 1 - clear_px) * a.ramp)
    fx = [a.peak * I.smoothstep((x - clear_px) / ramp_px) for x in range(tw)]
    fy = [I.smoothstep(y / a.fade_top) * I.smoothstep((th - 1 - y) / a.fade_bottom)
          for y in range(th)]

    out = bytearray(tw * th * 4)
    for y in range(th):
        ay = fy[y]
        row = y * tw * 4
        for x in range(tw):
            i = row + x * 4
            b, gg, r = buf[i], buf[i + 1], buf[i + 2]
            lum = (r * 299 + gg * 587 + b * 114) // 1000
            r = r + (lum - r) * a.desat
            gg = gg + (lum - gg) * a.desat
            b = b + (lum - b) * a.desat
            out[i] = round(r + (255 - r) * a.wash)
            out[i + 1] = round(gg + (255 - gg) * a.wash)
            out[i + 2] = round(b + (255 - b) * a.wash)
            out[i + 3] = round(255 * fx[x] * ay)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    I.write_png_rgba(a.out, tw, th, out)
    print("เขียน    : %s  (%d x %d, %.0f KB)"
          % (a.out, tw, th, os.path.getsize(a.out) / 1024))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
