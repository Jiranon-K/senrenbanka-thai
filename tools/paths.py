#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paths.py — ที่อยู่ของทุกอย่างในโปรเจกต์ ประกาศไว้ที่เดียว

เดิมทุกสคริปต์ใน tools/ ประกาศเองว่า

    GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ซึ่งพังไปแล้วสองชั้น:

1. **ชื่อโกหก** — ค่านั้นคือ *โฟลเดอร์ repo* ไม่ใช่โฟลเดอร์เกม เห็นได้จาก
   `os.path.join(GAME, "tools", "FreeMote", ...)` ส่วนคำว่า "game" ที่
   tools/gui/core.py ใช้ หมายถึงโฟลเดอร์ที่ผู้เล่นลงเกมไว้จริงๆ — คนละอย่าง
   กันคนละฝั่ง repo แต่ชื่อเดียวกัน

2. **สมมติฐานหมดอายุ** — หัว .gitignore เขียนไว้ว่า "This repo lives inside
   the GAME directory" ซึ่งเคยจริง ตอนนี้ repo ย้ายลงมาลึกอีกสองชั้นแล้ว
   (…/SenrenBanka/senrenbanka-thai-patch-v1.0/senrenbanka-thai/) ทำให้
   `join(GAME, "data.xp3")` ชี้ไปที่ที่ไม่มีไฟล์ — pipeline_cn.py pack,
   port_r18.py pack และ rebuild_fonts.py จึงหาไฟล์ไม่เจอทั้งหมด

ตกลงกันใหม่ ใช้สองคำนี้เท่านั้น (ดู CONTEXT.md):

    REPO         โฟลเดอร์ repo — ที่อยู่ของ tools/ กับ thai_work/
    game_dir()   โฟลเดอร์ที่ผู้เล่นลงเกมไว้ — ที่อยู่ของ *.xp3 กับ SenrenBanka.exe

หมายเหตุ: **tools/gui/ ไม่ import ไฟล์นี้** ตัวติดตั้งถูก build เป็น .exe
เดี่ยวๆ ไปอยู่บนเครื่องผู้เล่นที่ไม่มี repo อยู่เลย มันจึงต้องหาโฟลเดอร์เกม
ด้วยวิธีของมันเอง (core.find_game_dirs — อ่าน Steam library เพิ่มด้วย)
"""
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TOOLS = os.path.join(REPO, "tools")
WORK = os.path.join(REPO, "thai_work")

# ─────────────────────────────────────────── งานแปล: สาย all-ages (CN slot)

CSV_CN = os.path.join(WORK, "strings_cn.csv")      # ตารางแม่ jp/en/th ของ all-ages
JSON_CN = os.path.join(WORK, "json_cn")            # สคริปต์ที่ decompile แล้ว
PSB_CN = os.path.join(WORK, "psb_cn")              # สคริปต์ที่ recompile แล้ว

# ─────────────────────────────────────────────────── งานแปล: สาย R18

CSV_R18 = os.path.join(WORK, "strings_r18.csv")
JSON_R18 = os.path.join(WORK, "json_r18")
PSB_R18 = os.path.join(WORK, "psb_r18")

# ──────────────────────────────────────────────────────── งานแปล: ร่วม

TH_DIR = os.path.join(WORK, "th")                  # คำแปลรายฉาก <stem>.tsv
GLOSSARY = os.path.join(WORK, "glossary.csv")

# ชื่อ "scenarios.json" ไม่ใช่ "manifest.json" — ในโปรเจกต์นี้มีไฟล์ชื่อ
# manifest.json อยู่แล้วหนึ่งตัว คือตารางไฟล์+แฮชที่ build_release.py สร้าง
# ให้ตัวติดตั้งอ่าน คนละเรื่องกันคนละไฟล์ ใช้ชื่อซ้ำกันไม่ได้
SCENARIOS = os.path.join(WORK, "scenarios.json")   # รายชื่อฉาก + route + จำนวนบล็อก
PROGRESS = os.path.join(WORK, "progress.json")     # ธง packed/verified รายฉาก
PROGRESS_MD = os.path.join(WORK, "PROGRESS.md")
PROGRESS_R18_MD = os.path.join(WORK, "PROGRESS_R18.md")

# ────────────────────────────────────────────────────────────── ฟอนต์

FONTS = os.path.join(WORK, "fonts")
FONT_MERGED = os.path.join(FONTS, "Sarabun-merged.ttf")
FONT_VARIANTS = os.path.join(FONTS, "variants")

# ───────────────────────────────────────────── ของที่แตกออกมาจาก archive
#
# เดิมคาดว่าจะอยู่ข้าง ๆ ตัวเกม (สมัยที่ repo วางอยู่ในโฟลเดอร์เกม) ย้ายมาไว้
# ใต้ thai_work/ ให้อยู่รวมกับของระหว่างทางอันอื่น — .gitignore คุมไว้แล้ว
# และไม่ไปเขียนอะไรลงโฟลเดอร์เกมของผู้เล่นโดยไม่ตั้งใจ

EXTRACT_DATA = os.path.join(WORK, "dataxp3")       # data.xp3 ที่แตกแล้ว (ฟอนต์)
EXTRACT_SCN = os.path.join(WORK, "scnxp3")         # scn.xp3 ที่แตกแล้ว

DIST = os.path.join(WORK, "dist")                  # ชุดติดตั้งที่ build ออกมา

# ────────────────────────────────────────────────────── เครื่องมือภายนอก
# (ไม่ได้ commit ลง repo — ดู tools/THAI_TRANSLATION_GUIDE.md)

FREEMOTE = os.path.join(TOOLS, "FreeMote")
PSB_DECOMPILE = os.path.join(FREEMOTE, "PsbDecompile.exe")
PSB_BUILD = os.path.join(FREEMOTE, "PsBuild.exe")
XDELTA = os.path.join(TOOLS, "xdelta", "xdelta3.exe")

_GAME_EXE = "SenrenBanka.exe"


def game_dir(start: str | None = None) -> str:
    """โฟลเดอร์ที่ผู้เล่นลงเกมไว้ — ที่อยู่ของ *.xp3

    หาโดยไต่ขึ้นไปจาก repo จนเจอ SenrenBanka.exe เพราะ repo มักถูกวางไว้
    ข้างในโฟลเดอร์เกม (หรือลึกลงไปอีกชั้นสองชั้น) ข้ามได้ด้วย SBTP_GAME

    ตั้งใจให้ **ระเบิดพร้อมบอกวิธีแก้** ไม่ใช่คืน path มั่วๆ แล้วไปพังตอน
    เขียนทับ archive — ซึ่งเป็นสิ่งที่โค้ดชุดเก่าทำ
    """
    env = os.environ.get("SBTP_GAME")
    if env:
        if not os.path.isfile(os.path.join(env, _GAME_EXE)):
            raise SystemExit("SBTP_GAME ชี้ไปที่ %s แต่ไม่มี %s อยู่ในนั้น"
                             % (env, _GAME_EXE))
        return os.path.abspath(env)

    d = os.path.abspath(start or REPO)
    while True:
        if os.path.isfile(os.path.join(d, _GAME_EXE)):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit(
                "หาโฟลเดอร์เกมไม่เจอ — ไต่ขึ้นไปจาก %s แล้วไม่พบ %s\n"
                "ถ้า repo ไม่ได้อยู่ในโฟลเดอร์เกม ให้ตั้ง SBTP_GAME ชี้ไปเอง"
                % (start or REPO, _GAME_EXE))
        d = parent


def game_file(name: str, start: str | None = None) -> str:
    """path ของ archive สักตัวในโฟลเดอร์เกม เช่น game_file("patch.xp3")"""
    return os.path.join(game_dir(start), name)
