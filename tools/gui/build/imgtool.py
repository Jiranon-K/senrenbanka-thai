#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
imgtool.py — งานภาพที่ทำ **ตอน build เท่านั้น** (ตัวแอปไม่ได้ import ไฟล์นี้)

ถอดรหัส/ย่อขยายภาพด้วย GDI+ ผ่าน ctypes — มีอยู่ในทุกเครื่อง Windows ไม่ต้องลง
อะไรเพิ่ม และคุณภาพการย่อขยายดีกว่าเขียน bicubic เองใน Python มาก (เร็วกว่าด้วย)

ทำไมไม่ใช้ Pillow: `.exe` จะโตขึ้นหลาย MB เพื่องานที่ทำครั้งเดียวตอน build
ส่วนตัวแอปเองอ่าน PNG ด้วย Tk ได้อยู่แล้ว

ใช้โดย make_bg.py (แผงพื้นหลัง) และ make_logo.py (โลโก้ + ไอคอน)
"""
from __future__ import annotations

import ctypes
import struct
import zlib

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
    """ครอบ GDI+ ให้เรียกง่ายและปิดทรัพยากรครบ — ใช้เป็น context manager"""

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

    def draw(self, dst, dw, dh, src, box):
        """วาด src (ครอปตาม box = x,y,w,h) ลงเต็ม dst"""
        gfx = ctypes.c_void_p()
        _ck(gdip.GdipGetImageGraphicsContext(dst, ctypes.byref(gfx)), "graphics")
        gdip.GdipSetInterpolationMode(gfx, INTERP_HQ_BICUBIC)
        gdip.GdipSetPixelOffsetMode(gfx, PIXEL_OFFSET_HQ)
        gdip.GdipSetSmoothingMode(gfx, SMOOTHING_HQ)
        sx, sy, sw, sh = box
        _ck(gdip.GdipDrawImageRectRectI(
            gfx, src, 0, 0, int(dw), int(dh),
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
            out[y * w * 4:(y + 1) * w * 4] = ctypes.string_at(
                data.Scan0 + y * data.Stride, w * 4)
        gdip.GdipBitmapUnlockBits(bmp, ctypes.byref(data))
        return out

    def render(self, box, w, h, blur=1.0):
        """ครอป -> ย่อขยายเป็น w x h -> คืน BGRA (blur > 1 = ย่อแล้วขยายกลับ)"""
        if blur > 1.01:
            mw, mh = max(2, round(w / blur)), max(2, round(h / blur))
            small = self.blank(mw, mh)
            self.draw(small, mw, mh, self._src, box)
            dst = self.blank(w, h)
            self.draw(dst, w, h, small, (0, 0, mw, mh))
            gdip.GdipDisposeImage(small)
        else:
            dst = self.blank(w, h)
            self.draw(dst, w, h, self._src, box)
        buf = self.pixels(dst, w, h)
        gdip.GdipDisposeImage(dst)
        return buf

    def open(self, path):
        self._src, self.sw, self.sh = self.load(path)
        return self


def dispose(img):
    gdip.GdipDisposeImage(img)


# ────────────────────────────────────────────────────────────── ตัวช่วย

def smoothstep(t: float) -> float:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return t * t * (3 - 2 * t)


def cover_box(sw, sh, tw, th, focus, zoom=1.0):
    """กรอบครอปที่เต็มกรอบเป้าหมายพอดี (แบบ CSS object-fit: cover)"""
    scale = max(tw / sw, th / sh) * zoom
    cw, ch = min(sw, tw / scale), min(sh, th / scale)
    return (round((sw - cw) * focus[0]), round((sh - ch) * focus[1]),
            round(cw), round(ch))


def bgra_to_rgba(buf, w, h, opaque=True):
    """สลับช่องสี BGRA -> RGBA (GDI+ คืนมาแบบ BGRA เสมอ)"""
    out = bytearray(len(buf))
    for i in range(0, len(buf), 4):
        out[i] = buf[i + 2]
        out[i + 1] = buf[i + 1]
        out[i + 2] = buf[i]
        out[i + 3] = 255 if opaque else buf[i + 3]
    return out


def png_rgba(w, h, buf) -> bytes:
    raw = bytearray()
    for y in range(h):
        raw.append(0)                                  # filter type 0
        raw += buf[y * w * 4:(y + 1) * w * 4]

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def write_png_rgba(path, w, h, buf):
    with open(path, "wb") as f:
        f.write(png_rgba(w, h, buf))


def write_ico(path, images):
    """images = [(ขนาด, ไบต์ของ PNG), ...]

    ตั้งแต่ Vista เป็นต้นมา Windows อ่านไอคอนที่เก็บเป็น PNG ข้างในได้
    จึงไม่ต้องเขียน BMP + AND mask เอง (และได้ขอบโปร่งใสฟรี)
    """
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for size, data in images:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0,
                               1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)) + entries + blobs)


def write_placeholder_icon(path, accent="#f2802b"):
    """ไอคอน**สำรอง**: สี่เหลี่ยมส้มบนกระดาษขาว ตามเครื่องหมายในไฟล์ดีไซน์

    ใช้เมื่อยังไม่ได้รัน make_logo.py (เช่น build จาก source เปล่าๆ)

    เดิมอยู่ใน theme.py ของตัวแอป พร้อมตัวเขียน PNG อีกฉบับหนึ่งของโปรเจกต์
    ทั้งที่เป็นงานตอน build ล้วนๆ ตัวแอปไม่เคยต้องเขียนไฟล์ .ico เลย
    """
    r, g, b = (int(accent[i:i + 2], 16) for i in (1, 3, 5))
    sizes = (16, 32, 48, 64, 128, 256)
    images = []
    for s in sizes:
        pad = max(1, round(s * 0.22))
        buf = bytearray(s * s * 4)
        for y in range(s):
            for x in range(s):
                i = (y * s + x) * 4
                inside = pad <= x < s - pad and pad <= y < s - pad
                buf[i:i + 4] = bytes((r, g, b, 255) if inside else (255, 255, 255, 255))
        images.append((s, png_rgba(s, s, buf)))
    write_ico(path, images)
