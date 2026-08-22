#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme.py — โทเคนของระบบดีไซน์ "Modernist" แปลงเป็น Tk

ที่มา: Claude Design → โปรเจกต์ "Fan-translation mod installer"
       → `Mod Installer.dc.html` + `_ds/modernist-*/styles.css`

ค่าสีที่ CSS เขียนเป็น `color-mix(in srgb, var(--color-text) 55%, transparent)`
ถูกคำนวณล่วงหน้าเป็น hex ตรงๆ ที่นี่ (Tk ไม่มี alpha บนพื้นทึบ) โดยผสมกับ
`--color-bg` (#ffffff) ซึ่งเป็นพื้นหลังจริงของ panel — ได้ผลตาเดียวกัน

ระบบนี้ใช้ `--radius: 0px` ทุกที่ ไม่มีเงาในตัว panel ไม่มี gradient
จึงยกมาเป็น native widget ได้ตรงๆ โดยไม่เสียรายละเอียดอะไรเลย
"""
from __future__ import annotations

import ctypes
import os
import struct
import sys
import zlib

# ─────────────────────────────────────────────────────────────────── สี

ACCENT      = "#f2802b"
ACCENT_100  = "#fff4ea"
ACCENT_300  = "#ffcaa5"
ACCENT_600  = "#dd6b17"
ACCENT_700  = "#b8530f"
ACCENT_800  = "#8d3d09"

BG          = "#ffffff"
SURFACE     = "#fffaf5"
DIVIDER     = "#e2cdbb"
TEXT        = "#2b211b"

TEXT_70     = "#6b645f"      # label ของ field
TEXT_65     = "#756f6b"      # ตัวหนังสือใน tag-neutral
TEXT_55     = "#8a8582"      # .text-muted
TEXT_50     = "#95908d"      # คอลัมน์ขนาดไฟล์
TEXT_45     = "#a09b98"      # เครดิตมุมล่างซ้าย
TEXT_42     = "#a6a29f"      # ขั้นที่ยังไม่ถึง

HOVER_SOFT  = "#f0efef"      # btn-secondary:hover  (text 7%)
HOVER_PRESS = "#e2e0e0"      # btn-secondary:active (text 14%)
HOVER_GHOST = "#fef2ea"      # btn-ghost:hover      (accent 10%)
TAG_NEUTRAL = "#eeeded"      # tag-neutral bg       (text 8%)

BORDER      = "#b5b1af"      # border ของ panel: rgba(43,33,27,.35) บนขาว

DANGER      = "#b3261e"
DANGER_100  = "#fdecea"
DANGER_800  = "#6d1712"

# ────────────────────────────────────────────────────────── ฟอนต์ + DPI

FAMILY = "Sarabun"
FAMILY_BOLD = "Sarabun ExtraBold"     # --font-heading-weight: 800
_FR_PRIVATE = 0x10

scale = 1.0                            # ตั้งค่าจริงใน init()


def fonts_dir() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ui", "fonts")


def load_fonts() -> bool:
    """ลงทะเบียนฟอนต์ให้เฉพาะ process นี้ ไม่ต้องติดตั้งลงเครื่องผู้เล่น"""
    d = fonts_dir()
    ok = 0
    for f in ("Sarabun-Regular.ttf", "Sarabun-SemiBold.ttf", "Sarabun-ExtraBold.ttf"):
        p = os.path.join(d, f)
        if os.path.isfile(p):
            ok += bool(ctypes.windll.gdi32.AddFontResourceExW(p, _FR_PRIVATE, 0))
    return ok > 0


def dpi_aware():
    """ไม่งั้นบนจอ scaling 125/150% Windows จะขยายภาพให้แบบเบลอ"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor v1
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ── ถอดแถบหัวของ Windows ออก แต่ยังเป็นหน้าต่างปกติทุกอย่าง ────────────
GWL_STYLE      = -16
WS_CAPTION     = 0x00C00000      # แถบหัว + ขอบ
WS_THICKFRAME  = 0x00040000      # ขอบลากปรับขนาด
SWP_FLAGS      = 0x0002 | 0x0001 | 0x0004 | 0x0020   # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED


def strip_caption(root):
    """เอาแถบหัวของระบบออกโดย **ไม่** ใช้ overrideredirect

    overrideredirect(True) ทำให้หน้าต่างหลุดจากการจัดการของ window manager:
    ปุ่มบน taskbar หาย Alt-Tab หาย iconify() เพี้ยน
    การถอดเฉพาะบิต WS_CAPTION/WS_THICKFRAME ทิ้งไว้แค่หน้าตา — ตัวหน้าต่าง
    ยังเป็น top-level ปกติ (taskbar / Alt-Tab / ย่อ-ขยาย ใช้ได้ครบ)
    """
    root.update_idletasks()
    try:
        hwnd = int(root.wm_frame(), 16)
        gwl = ctypes.windll.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8             else ctypes.windll.user32.GetWindowLongW
        swl = ctypes.windll.user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8             else ctypes.windll.user32.SetWindowLongW
        style = gwl(hwnd, GWL_STYLE)
        swl(hwnd, GWL_STYLE, style & ~WS_CAPTION & ~WS_THICKFRAME)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        return True
    except Exception:
        return False


def has_caption(root) -> bool:
    """ไว้ให้เทสยืนยันว่าแถบหัวถูกถอดจริง"""
    try:
        hwnd = int(root.wm_frame(), 16)
        gwl = ctypes.windll.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8             else ctypes.windll.user32.GetWindowLongW
        return bool(gwl(hwnd, GWL_STYLE) & WS_CAPTION)
    except Exception:
        return True


def taskbar_identity(app_id="Jiranon-K.SenrenBanka.ThaiPatch"):
    """ให้ taskbar จัดกลุ่มและใช้ไอคอนของเราเอง ไม่ใช่ไอคอน python.exe"""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def init(root, win=(880, 600)) -> float:
    """เรียกครั้งเดียวหลังสร้าง Tk() — คืนค่าตัวคูณ DPI

    เพดานสำคัญ: โน้ตบุ๊ก 1920x1080 ที่ตั้ง scaling 200% จะได้หน้าต่าง
    880x600 -> 1760x1200 ซึ่ง **สูงเกินจอ** ปุ่มท้ายจอจะหลุดออกไป
    จึงจำกัดไม่ให้เกิน 90% ของพื้นที่จอ
    """
    global scale
    try:
        dpi = root.winfo_fpixels("1i")
    except Exception:
        dpi = 96.0
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    scale = max(1.0, min(dpi / 96.0, sw * 0.9 / win[0], sh * 0.9 / win[1]))
    root.tk.call("tk", "scaling", 96.0 * scale / 72.0)
    return scale


def S(px: float) -> int:
    """px จากไฟล์ดีไซน์ -> พิกเซลจริงบนจอนี้"""
    return max(1, round(px * scale))


def F(px: float, bold: bool = False):
    """ขนาดฟอนต์: Tk ใช้ค่าลบ = หน่วยพิกเซล ตรงกับที่ CSS เขียนพอดี"""
    return (FAMILY_BOLD if bold else FAMILY, -S(px))


# ────────────────────────────────────────────────────────────── ไอคอน

def _png(size: int, pixels) -> bytes:
    raw = b"".join(b"\x00" + bytes(v for x in range(size) for v in pixels(x, y))
                   for y in range(size))

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def make_icon(path: str):
    """สี่เหลี่ยมส้มบนกระดาษขาว = เครื่องหมายมุมซ้ายบนของหน้าต่างในดีไซน์

    เขียน .ico เองแทนการลาก Pillow เข้ามาเพื่อไอคอนอันเดียว
    """
    rgb_a = tuple(int(ACCENT[i:i + 2], 16) for i in (1, 3, 5))
    sizes = (16, 32, 48, 64, 128, 256)
    images = []
    for s in sizes:
        pad = max(1, round(s * 0.22))

        def px(x, y, s=s, pad=pad):
            inside = pad <= x < s - pad and pad <= y < s - pad
            return (*(rgb_a if inside else (255, 255, 255)), 255)

        images.append(_png(s, px))

    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for s, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs += data
    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(images)) + entries + blobs)
