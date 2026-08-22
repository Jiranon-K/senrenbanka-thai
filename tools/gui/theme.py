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

**ไฟล์นี้มีแต่โทเคน ไม่มีอย่างอื่น** — เดิมมีปลั๊ก Win32 กับตัวเขียนไฟล์ PNG
ปนอยู่ด้วย รวมเป็น 333 บรรทัด ทำให้คนที่เปิดมาหา "สี" เจอ ctypes แทน
  * ปลั๊กเข้าระบบปฏิบัติการ -> winui.py
  * หาไฟล์ใน ui/           -> assets.py
  * เขียน PNG/ICO           -> build/imgtool.py (ทำตอน build เท่านั้น)
"""
from __future__ import annotations

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

# ────────────────────────────────────────────────────────── ฟอนต์ + ขนาด

FAMILY = "Sarabun"
FAMILY_BOLD = "Sarabun ExtraBold"     # --font-heading-weight: 800

scale = 1.0                            # ตั้งค่าจริงใน init()


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


# ───────────────────────────────────────────────────── ผสมสี (ไว้ใช้ทวีน)

def rgb(c: str):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a: str, b: str, t: float) -> str:
    """a เมื่อ t=0 → b เมื่อ t=1 (ผสมแบบเชิงเส้นในปริภูมิ sRGB เหมือน CSS)"""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    x, y = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(x[i] + (y[i] - x[i]) * t) for i in range(3))
