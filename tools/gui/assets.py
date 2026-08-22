#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
assets.py — หาไฟล์ใน ui/ (ฟอนต์ · โลโก้ · ไอคอน · ภาพพื้นหลัง)

แยกออกจาก theme.py เพราะเป็นคนละเรื่อง: theme บอกว่า "สีอะไร ตัวหนังสือเท่าไร"
ส่วนไฟล์นี้บอกว่า "ไฟล์อยู่ที่ไหน" — และเปลี่ยนด้วยเหตุผลคนละอย่าง
(theme เปลี่ยนตามดีไซน์ ไฟล์นี้เปลี่ยนตามวิธี build)

ไฟล์ใน ui/ สร้างตอน build ด้วย tools/gui/build/make_logo.py และ make_bg.py
ถ้าไม่มีสักไฟล์ แอปยังรันได้ปกติ แค่ถอยไปใช้ดีไซน์เปล่าๆ
"""
from __future__ import annotations

import os
import sys

# ขนาดโลโก้ที่มีให้ใช้ — **แหล่งเดียว** ทั้งฝั่งแอปและฝั่ง build
# (make_logo.py import ค่านี้ไปสร้างไฟล์ เดิมประกาศไว้สองที่แล้ว sync ด้วยมือ)
LOGO_SIZES = (20, 25, 30, 40)

FONT_FILES = ("Sarabun-Regular.ttf", "Sarabun-SemiBold.ttf",
              "Sarabun-ExtraBold.ttf")


def ui_dir() -> str:
    """โฟลเดอร์ทรัพยากรหน้าตา — ตอน build เป็น .exe จะถูกแตกไว้ใน _MEIPASS"""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ui")


def fonts_dir() -> str:
    return os.path.join(ui_dir(), "fonts")


def font_files() -> list[str]:
    return [p for p in (os.path.join(fonts_dir(), f) for f in FONT_FILES)
            if os.path.isfile(p)]


def logo_file(px: int) -> str | None:
    """ไฟล์โลโก้ที่ขนาดใกล้ px ที่สุด — None ถ้าไม่ได้ bundle มา

    Tk ย่อภาพได้แค่หารด้วยจำนวนเต็มแบบ nearest-neighbour ซึ่งขอบจะแตกทันที
    จึงเตรียมไฟล์ไว้หลายขนาดตอน build แล้วหยิบใช้ตรงๆ ไม่ย่อเลย
    """
    best, gap = None, None
    for s in LOGO_SIZES:
        f = os.path.join(ui_dir(), "logo@%d.png" % s)
        if os.path.isfile(f) and (gap is None or abs(s - px) < gap):
            best, gap = f, abs(s - px)
    return best


def icon_file() -> str | None:
    """ไอคอนหน้าต่าง/taskbar — None ถ้าไม่ได้ bundle มา

    เดิมไฟล์นี้ (ตอนยังอยู่ใน theme.py) เขียน .ico สำรองเป็นสี่เหลี่ยมส้มเอง
    ซึ่งลาก zlib/struct กับตัวเขียน PNG ฉบับที่สองของโปรเจกต์เข้ามาอยู่ในตัว
    แอป ทั้งที่เป็นงานตอน build ล้วนๆ — ย้ายไป build/imgtool.py แล้ว
    """
    f = os.path.join(ui_dir(), "icon.ico")
    return f if os.path.isfile(f) else None


def backdrop_file() -> str | None:
    f = os.path.join(ui_dir(), "bg.png")
    return f if os.path.isfile(f) else None
