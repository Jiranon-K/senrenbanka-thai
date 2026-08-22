#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
targets.py — ตารางไฟล์ที่แพตช์แตะ **ที่เดียวในโปรเจกต์**

เดิมตารางนี้อยู่ 5 ที่ และเพิ่ม archive สักไฟล์ต้องแก้ครบทุกที่ ใน 2 ภาษา:

    1. TARGETS (tuple 5 ช่อง) ใน build_release.py
    2. บล็อก set ที่ hardcode ชื่อตัวแปร ORIG_/THAI_ x PATCH/DATA/ADULT
    3. รายชื่อไฟล์ใน INSTALL_BODY (for %%F in (...)) + บล็อก rollback
    4. UNINSTALL_BODY
    5. core.Plan.R18_FILES — ซึ่งมี adult2.xp3 ที่ไม่มีในข้อ 1 เลย

ลืมที่ใดที่หนึ่ง = `.bat` กับ GUI ทำคนละอย่างกัน ซึ่งเป็นบั๊กประเภทที่ผู้เล่น
เจอแต่คนพัฒนาไม่เจอ (คนพัฒนารัน GUI ผู้เล่นดับเบิลคลิก .bat)

ตอนนี้ทุกอย่างงอกออกจากตารางนี้: manifest.json ที่ตัวติดตั้ง GUI อ่าน และ
ชิ้นส่วนของ install.bat/uninstall.bat ที่เป็นรายการซ้ำๆ ต่อไฟล์

**ส่วนที่ยังไม่ได้ generate**: ลำดับขั้นตอนใน .bat (เช็ค -> สำรอง -> แปะ)
ยังเขียนไว้ตรงๆ เพราะมีเงื่อนไขเฉพาะของ R18 ที่ไม่เหมือนไฟล์อื่น และมี
tools/test_installer.sh คุมอยู่แล้ว 6 เคส — แต่ build_release.py จะ assert
ว่า .bat พูดถึงทุกไฟล์ในตารางนี้ครบ ถ้าเพิ่ม target แล้วลืมแก้ .bat จะ
**build ไม่ผ่าน** แทนที่จะปล่อยแพตช์ครึ่งเดียวออกไป
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:
    """archive หนึ่งไฟล์ที่แพตช์ไทยเขียนทับ"""

    file: str          # ชื่อไฟล์ในโฟลเดอร์เกม        patch.xp3
    orig: str          # ต้นฉบับที่เอามาทำ diff        patch.xp3.bak
    delta: str         # ไฟล์ diff ในชุดติดตั้ง        thai-patch.xdelta
    label: str         # ป้ายไทยที่ผู้ใช้เห็น
    required: bool     # ไม่มีไฟล์นี้ = ไม่ใช่โฟลเดอร์เกม
    r18: bool          # ไฟล์นี้มากับแพตช์ R18
    var: str           # ชื่อตัวแปรใน .bat  ->  ORIG_PATCH / THAI_PATCH

    @property
    def bak(self) -> str:
        return self.file + ".bak"


TARGETS = [
    Target("patch.xp3", "patch.xp3.bak", "thai-patch.xdelta",
           "บทพูด (all-ages)", required=True, r18=False, var="PATCH"),
    Target("data.xp3", "data.xp3.bak", "thai-data.xdelta",
           "ฟอนต์ Sarabun", required=True, r18=False, var="DATA"),
    Target("adult.xp3", "adult.xp3.orig", "thai-adult.xdelta",
           "บทพูดฝั่ง R18", required=False, r18=True, var="ADULT"),
]

# ไฟล์ที่แพตช์ R18 เอามาวาง และต้องถูก "ปิด" (เปลี่ยนชื่อเป็น .off ไม่ใช่ลบ)
# เมื่อผู้เล่นเลือกเวอร์ชัน all-ages — adult2.xp3 ไม่มี diff ของตัวเอง แต่ก็
# ต้องปิดด้วย ไม่งั้นมันทับบทพูดอยู่ดี
DISABLE_ON_ALL_AGES = ["adult.xp3", "adult2.xp3"]


def by_file(name: str) -> Target | None:
    return next((t for t in TARGETS if t.file == name), None)


# ────────────────────────────────────────── ชิ้นส่วนที่ generate ลง .bat

def bat_required_files() -> str:
    """รายชื่อไฟล์ที่ต้องมีในซิป — ใส่ใน for %%F in (...)"""
    return " ".join(["xdelta3.exe"] + [t.delta for t in TARGETS])


def bat_hash_vars(hashes: dict) -> str:
    """บล็อก set "ORIG_x=..." / "THAI_x=..." สำหรับทุก target

    hashes = {ชื่อไฟล์: (sha ต้นฉบับ, sha หลังแปะไทย)}
    ไฟล์ที่ไม่ได้ build รอบนี้จะได้ศูนย์ 64 ตัว ซึ่งไม่มีทางตรงกับของจริง
    """
    zero = "0" * 64
    lines = []
    for t in TARGETS:
        orig, thai = hashes.get(t.file, (zero, zero))
        lines.append('set "ORIG_%s=%s"' % (t.var, orig))
        lines.append('set "THAI_%s=%s"' % (t.var, thai))
    return "\n".join(lines)


def bat_rollback() -> str:
    """คืนไฟล์ทุกตัวที่อาจถูก rename ไปแล้ว — ใช้ทั้งใน install และ uninstall"""
    return "\n".join(
        'if exist "%s" (del /q "%s" 2>nul & move /y "%s" "%s" >nul)'
        % (t.bak, t.file, t.bak, t.file) for t in TARGETS)


def bat_uninstall_found() -> str:
    return "\n".join('if exist "%s" set "FOUND=1"' % t.bak for t in TARGETS)


def bat_uninstall_restore() -> str:
    note = {"adult.xp3": " ^(ฉาก R18 ยังอยู่ครบ แค่กลับเป็นภาษาเดิม^)"}
    return "\n".join(
        'if exist "%s" (del /q "%s" 2>nul & move /y "%s" "%s" >nul & echo       - %-11s คืนแล้ว%s)'
        % (t.bak, t.file, t.bak, t.file, t.file, note.get(t.file, ""))
        for t in TARGETS)


def check_bat_mentions_every_target(text: str, what: str):
    """กันลืม: เพิ่ม target แล้วไม่ได้แก้ .bat ต้อง build ไม่ผ่าน"""
    missing = [t.file for t in TARGETS if t.file not in text]
    if missing:
        raise SystemExit(
            "%s ไม่ได้พูดถึงไฟล์เหล่านี้เลย: %s\n"
            "เพิ่มลง tools/targets.py แล้วต้องเพิ่มขั้นตอนใน .bat ด้วย"
            % (what, ", ".join(missing)))
