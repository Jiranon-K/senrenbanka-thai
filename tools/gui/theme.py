#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme.py — โทเคนสีและขนาดของตัวติดตั้ง หน้าตาแบบ shadcn/ui แปลงเป็น Tk

ที่มา: ค่าสีกลางคือชุด **zinc** ของ Tailwind (ตัวเดียวกับธีมตั้งต้นของ shadcn/ui)
ส่วนสีส้มเก็บไว้ใช้เฉพาะ action หลัก ขั้นปัจจุบัน และของที่ "ถูกเลือก"
— ตรงกับหลักของ shadcn ที่ให้สีหลักโผล่น้อยที่สุด

เดิมใช้ระบบ "Modernist" จาก Claude Design (มุมฉาก ไม่มีขอบโค้ง) ชื่อโทเคนยังคง
ชื่อเดิมไว้ (TEXT_55, HOVER_SOFT, ...) เพื่อไม่ต้องไล่แก้ทุกที่ที่ใช้ ค่าข้างในเปลี่ยน

shadcn ใช้ alpha หลายจุด (`bg-primary/20` ฯลฯ) — Tk ไม่มี alpha บนพื้นทึบ จึงคำนวณ
ล่วงหน้าเป็น hex โดยผสมกับพื้นขาว ได้ผลตาเดียวกัน

**ไฟล์นี้มีแต่โทเคน ไม่มีอย่างอื่น**
  * ปลั๊กเข้าระบบปฏิบัติการ -> winui.py
  * หาไฟล์ใน ui/           -> assets.py
  * วาดรูปทรงมุมโค้ง        -> shape.py
  * เขียน PNG/ICO           -> build/imgtool.py (ทำตอน build เท่านั้น)
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────── สี

ACCENT      = "#f2802b"      # primary — ส้มเดิมของแพตช์ (เข้ากับภาพในเกม)
ACCENT_100  = "#fff4ea"      # พื้น badge accent
ACCENT_300  = "#ffcaa5"      # ขั้นที่ผ่านแล้ว / ring ของช่องกรอก
ACCENT_600  = "#dd6b17"      # primary:hover
ACCENT_700  = "#b8530f"      # primary:active
ACCENT_800  = "#8d3d09"      # ตัวหนังสือบน badge accent
ACCENT_TRACK = "#fce6d5"     # ราง progress = primary/20 บนขาว

BG          = "#ffffff"      # --background / --card
SIDEBAR     = "#fafafa"      # zinc-50  แถบซ้าย
MUTED       = "#f4f4f5"      # zinc-100 --muted / --accent ของ shadcn
SURFACE     = "#ffffff"      # พื้นช่องกรอก (shadcn: โปร่ง = พื้นการ์ด)
DIVIDER     = "#e4e4e7"      # zinc-200 --border / --input
TEXT        = "#09090b"      # zinc-950 --foreground

TEXT_70     = "#27272a"      # label ของ field (font-medium)
TEXT_65     = "#3f3f46"      # ตัวหนังสือใน badge neutral
TEXT_55     = "#71717a"      # zinc-500 --muted-foreground
TEXT_50     = "#71717a"      # คอลัมน์ขนาดไฟล์
TEXT_45     = "#a1a1aa"      # zinc-400 เครดิตมุมล่างซ้าย
TEXT_42     = "#a1a1aa"      # ขั้นที่ยังไม่ถึง / แถวที่ติ๊กออก

HOVER_SOFT  = "#f4f4f5"      # outline button:hover  (bg-accent)
HOVER_PRESS = "#e4e4e7"      # outline button:active
HOVER_GHOST = "#f4f4f5"      # ghost button:hover
TAG_NEUTRAL = "#f4f4f5"      # badge secondary

BORDER      = "#d4d4d8"      # zinc-300 กรอบรอบหน้าต่าง (เข้มกว่า border ปกติ ไม่งั้นกลืนกับเดสก์ท็อปขาว)
CARD_HOVER  = "#d4d4d8"      # ขอบการ์ดที่คลิกได้ตอนเมาส์ชี้

DANGER      = "#dc2626"      # red-600 --destructive
DANGER_100  = "#fef2f2"
DANGER_800  = "#991b1b"

# ─────────────────────────────────────────────────────────────── มุมโค้ง

RADIUS      = 8              # --radius: 0.5rem — การ์ด
RADIUS_MD   = 6              # ปุ่ม / ช่องกรอก (radius - 2px)
RADIUS_SM   = 4              # กล่องติ๊ก

# ────────────────────────────────────────────────────────── ฟอนต์ + ขนาด

FAMILY = "Sarabun"
FAMILY_BOLD = "Sarabun SemiBold"      # shadcn ใช้ font-semibold (600) กับหัวข้อและปุ่ม

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
