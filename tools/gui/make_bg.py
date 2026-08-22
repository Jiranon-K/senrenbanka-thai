#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
make_bg.py — แปลงภาพต้นฉบับเป็นแผงพื้นหลังแบบกระจกฝ้าของตัวติดตั้ง

    python tools/gui/make_bg.py "...\ภาพ.jpg"

ทำงาน **ตอน build เท่านั้น** ผลลัพธ์คือ `ui/bg.png` (RGBA) ที่ฝังการไล่จางไว้
ในช่อง alpha เรียบร้อยแล้ว ตัวแอปจึงแค่วางภาพลง canvas ไม่ต้องคำนวณอะไรเลย

ทำไมต้องแปลงก่อน ไม่โหลด .jpg ตรงๆ:
  * Tk อ่านได้แค่ PNG / GIF / PPM — ไม่มี JPEG
  * ห้ามลาก Pillow เข้ามาเพื่องานนี้งานเดียว (`.exe` จะโตขึ้นหลาย MB)
  * การไล่จาง/เบลอ/ลดความอิ่มสี ถ้าทำตอนรันคือเสียเวลาเปิดโปรแกรมฟรีๆ
    ทั้งที่ผลลัพธ์เหมือนเดิมทุกครั้ง

ถอดรหัส JPEG ด้วย GDI+ ผ่าน ctypes — มีอยู่ในทุกเครื่อง Windows ไม่ต้องลงอะไร
และให้ GDI+ ย่อ/ขยายแบบ bicubic ให้ด้วย (เร็วกว่าเขียนเองใน Python มาก)

หมายเหตุเรื่องลิขสิทธิ์: ภาพ CG เป็นของผู้พัฒนาเกม สคริปต์นี้จึงรับ path
จากภายนอก ไม่เก็บไฟล์ต้นฉบับไว้ในที่เก็บโค้ด
"""
from __future__ import annotations

import argparse
import ctypes
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
gdip = ctypes.windll.gdiplus

PF_32BPP_ARGB = 0x0026200A
UNIT_PIXEL = 2
INTERP_HQ_BICUBIC = 7
PIXEL_OFFSET_HQ = 4
SMOOTHING_HQ = 2
LOCK_READ = 1


class _StartupInput(ctypes.Structure):
    _fields_ = [("GdiplusVersion", ctypes.c_uint32),
                ("DebugEventCallback", ctypes.c_void_p),
                ("SuppressBackgroundThread", ctypes.c_int),
                ("SuppressExternalCodecs", ctypes.c_int)]


class _BitmapData(ctypes.Structure):
    _fields_ = [("Width", ctypes.c_uint), ("Height", ctypes.c_uint),
                ("Stride", ctypes.c_int), ("PixelFormat", ctypes.c_int),
                ("Scan0", ctypes.c_void_p), ("Reserved", ctypes.c_void_p)]


class _Rect(ctypes.Structure):
    _fields_ = [("X", ctypes.c_int), ("Y", ctypes.c_int),
                ("Width", ctypes.c_int), ("Height", ctypes.c_int)]


def _ck(status, what):
    if status != 0:
        raise SystemExit("GDI+ %s ล้มเหลว (status=%d)" % (what, status))


class Gdip:
    """ครอบ GDI+ ให้เรียกง่ายและปิดทรัพยากรครบ"""

    def __enter__(self):
        self._token = ctypes.c_void_p()
        si = _StartupInput(1, None, 0, 0)
        _ck(gdip.GdiplusStartup(ctypes.byref(self._token), ctypes.byref(si), None),
            "startup")
        return self

    def __exit__(self, *_e):
        gdip.GdiplusShutdown(self._token)

    def load(self, path):
        img = ctypes.c_void_p()
        _ck(gdip.GdipCreateBitmapFromFile(ctypes.c_wchar_p(path), ctypes.byref(img)),
            "อ่านไฟล์ภาพ")
        w, h = ctypes.c_uint(), ctypes.c_uint()
        gdip.GdipGetImageWidth(img, ctypes.byref(w))
        gdip.GdipGetImageHeight(img, ctypes.byref(h))
        return img, w.value, h.value

    def blank(self, w, h):
        bmp = ctypes.c_void_p()
        _ck(gdip.GdipCreateBitmapFromScan0(w, h, 0, PF_32BPP_ARGB, None,
                                           ctypes.byref(bmp)), "สร้าง bitmap")
        return bmp

    def draw(self, dst, dw, dh, src, box, dx=0, dy=0, dw2=None, dh2=None):
        """วาด src (ครอปตาม box) ลง dst"""
        gfx = ctypes.c_void_p()
        _ck(gdip.GdipGetImageGraphicsContext(dst, ctypes.byref(gfx)), "graphics")
        gdip.GdipSetInterpolationMode(gfx, INTERP_HQ_BICUBIC)
        gdip.GdipSetPixelOffsetMode(gfx, PIXEL_OFFSET_HQ)
        gdip.GdipSetSmoothingMode(gfx, SMOOTHING_HQ)
        sx, sy, sw, sh = box
        _ck(gdip.GdipDrawImageRectRectI(
            gfx, src, int(dx), int(dy), int(dw2 or dw), int(dh2 or dh),
            int(sx), int(sy), int(sw), int(sh), UNIT_PIXEL, None, None, None), "วาด")
        gdip.GdipDeleteGraphics(gfx)

    def pixels(self, bmp, w, h):
        """คืน bytearray แบบ BGRA เรียงบรรทัดบนลงล่าง"""
        data = _BitmapData()
        rect = _Rect(0, 0, w, h)
        _ck(gdip.GdipBitmapLockBits(bmp, ctypes.byref(rect), LOCK_READ,
                                    PF_32BPP_ARGB, ctypes.byref(data)), "lock bits")
        out = bytearray(w * h * 4)
        for y in range(h):
            src = ctypes.string_at(data.Scan0 + y * data.Stride, w * 4)
            out[y * w * 4:(y + 1) * w * 4] = src
        gdip.GdipBitmapUnlockBits(bmp, ctypes.byref(data))
        return out


# ───────────────────────────────────────────────────────── การไล่จาง

def smoothstep(t: float) -> float:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def write_png_rgba(path, w, h, buf):
    raw = bytearray()
    for y in range(h):
        raw.append(0)                                  # filter type 0
        raw += buf[y * w * 4:(y + 1) * w * 4]

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
                + chunk(b"IEND", b""))


def cover_box(sw, sh, tw, th, focus, zoom):
    """เลือกกรอบครอปจากภาพต้นฉบับให้เต็มกรอบเป้าหมายพอดี (แบบ CSS object-fit: cover)"""
    scale = max(tw / sw, th / sh) * zoom
    cw, ch = min(sw, tw / scale), min(sh, th / scale)
    cx = (sw - cw) * focus[0]
    cy = (sh - ch) * focus[1]
    return (round(cx), round(cy), round(cw), round(ch))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="ไฟล์ภาพต้นฉบับ (.jpg/.png)")
    ap.add_argument("--out", default=os.path.join(HERE, "ui", "bg.png"))
    ap.add_argument("--size", default="280x482", help="ขนาดแผง (พิกเซลตามดีไซน์)")
    ap.add_argument("--focus", default="0.34,0.30",
                    help="จุดที่อยากให้อยู่กลางกรอบ (0-1 ตามแนวนอน,แนวตั้ง)")
    ap.add_argument("--zoom", type=float, default=1.15)
    ap.add_argument("--peak", type=float, default=0.80,
                    help="ความทึบสูงสุดที่ขอบขวา")
    ap.add_argument("--clear", type=float, default=0.24,
                    help="สัดส่วนด้านซ้ายที่ต้องใสสนิท (คอลัมน์เนื้อหาทับอยู่)")
    ap.add_argument("--ramp", type=float, default=0.55,
                    help="ไล่จากใสถึงทึบสุดภายในกี่ส่วนของที่เหลือ (ที่เหลือทึบเต็ม)")
    ap.add_argument("--fade-top", type=int, default=90)
    ap.add_argument("--fade-bottom", type=int, default=150)
    ap.add_argument("--blur", type=float, default=2.4, help="1 = ไม่เบลอ")
    ap.add_argument("--wash", type=float, default=0.14, help="ผสมขาวเข้าไปเท่าไร")
    ap.add_argument("--desat", type=float, default=0.22)
    a = ap.parse_args()

    tw, th = (int(v) for v in a.size.lower().split("x"))
    focus = tuple(float(v) for v in a.focus.split(","))

    with Gdip() as g:
        src, sw, sh = g.load(os.path.abspath(a.source))
        print("ต้นฉบับ  : %d x %d" % (sw, sh))
        box = cover_box(sw, sh, tw, th, focus, a.zoom)
        print("ครอป     : x=%d y=%d %dx%d" % box)

        # เบลอด้วยการย่อแล้วขยายกลับ — GDI+ ทำ bicubic ให้ ได้ฝ้านุ่มๆ แทบไม่มีต้นทุน
        if a.blur > 1.01:
            mw, mh = max(2, round(tw / a.blur)), max(2, round(th / a.blur))
            small = g.blank(mw, mh)
            g.draw(small, mw, mh, src, box)
            dst = g.blank(tw, th)
            g.draw(dst, tw, th, small, (0, 0, mw, mh))
            gdip.GdipDisposeImage(small)
        else:
            dst = g.blank(tw, th)
            g.draw(dst, tw, th, src, box)

        buf = g.pixels(dst, tw, th)
        gdip.GdipDisposeImage(dst)
        gdip.GdipDisposeImage(src)

    # ── แปลง BGRA -> RGBA พร้อมล้างสี ลดความอิ่ม แล้วฝังการไล่จางลง alpha
    #    fx: ใสสนิทด้านซ้าย (คอลัมน์เนื้อหาทับอยู่) แล้วค่อยเข้มขึ้นไปทางขวา
    #    fy: จางหายที่ขอบบน (ใต้แถบหัว) และขอบล่าง (เหนือปุ่ม) ไม่ให้มีรอยตัด
    clear_px = tw * a.clear
    ramp_px = max(1.0, (tw - 1 - clear_px) * a.ramp)
    fx = [a.peak * smoothstep((x - clear_px) / ramp_px) for x in range(tw)]
    fy = [smoothstep(y / a.fade_top) * smoothstep((th - 1 - y) / a.fade_bottom)
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
    write_png_rgba(a.out, tw, th, out)
    print("เขียน    : %s  (%d x %d, %.0f KB)"
          % (a.out, tw, th, os.path.getsize(a.out) / 1024))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
