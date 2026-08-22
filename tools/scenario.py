#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scenario.py — เดินสคริปต์บทพูดที่ decompile ออกมาเป็น json

บทพูดหนึ่งบรรทัดเก็บเป็น "ช่องภาษาเรียงกัน":

    [[ชื่อผู้พูด|null, ข้อความ, ...], ...]   ← JP, EN, CN, TW  (+ KO ฝั่ง R18)

แพตช์นี้เอาคำแปลไทยไปทับ **ช่อง CN** (index 2) ดู CONTEXT.md

═══════════════════════════════════════════════════════════════════════
  ทำไมมี Layout สองตัว และทำไมห้ามรวมเป็นตัวเดียว
═══════════════════════════════════════════════════════════════════════
สายงานสองสายนับ "อะไรคือบล็อกบทพูด" ไม่เหมือนกัน:

    ALL_AGES   4 ช่อง · ยอมให้สมาชิกในช่องเป็นอย่างอื่นนอกจากข้อความได้
    R18        4 หรือ 5 ช่อง · ทุกสมาชิกต้องเป็นข้อความหรือ null เท่านั้น

วัดกับสคริปต์จริง 86 บท: **นับได้ไม่เท่ากัน 70 บท** (46,303 vs 45,208 บล็อก)

นั่นไม่ใช่ "ฉบับหนึ่งถูก อีกฉบับผิด" แต่แปลว่า **เลข idx คนละระบบ**
และ `thai_work/th/*.tsv` กับ `strings_cn.csv` (คำแปล 45,182 บรรทัด) ถูก
เก็บเป็น `idx<TAB>คำแปล` โดยนับด้วย ALL_AGES ไว้แล้ว

ถ้าเผลอเอา R18 ไปใช้กับสาย all-ages: เลขเลื่อนทั้งเกม คำแปลไปโผล่ผิดคน
ทั้ง 45,182 บรรทัด และ**ไม่มีอะไรพัง ไม่มี error** — เห็นตอนเล่นอย่างเดียว

ตัวที่ ALL_AGES รับแต่ R18 ไม่รับ คือ node อย่าง
    [["bgm","bgm",{...}], ["lse","loopse",{...}], ...]
ซึ่งบังเอิญมี 4 ช่องเหมือนบทพูด — เป็น false positive จริง แต่มันถูกนับไป
แล้วตอนสร้าง CSV จะแก้ได้ก็ต่อเมื่อ export ใหม่ทั้งชุดพร้อมย้ายคำแปลตาม
(ไม่ใช่งานของการจัดระเบียบโค้ด)

จึงตั้งชื่อตาม **คลังคำแปลที่มันนับไว้** ไม่ใช่ตามความถูกต้อง — ที่จุดเรียก
จะได้อ่านออกทันทีว่ากำลังนับด้วยระบบไหน
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass

CN = 2                  # ช่องที่คำแปลไทยไปอยู่
JP, EN = 0, 1


@dataclass(frozen=True)
class Layout:
    """กติกาว่าอะไรนับเป็นบล็อกบทพูด — อ่านหัวไฟล์ก่อนแก้"""

    name: str
    slots: tuple[int, ...]      # จำนวนช่องภาษาที่ยอมรับ
    text_only: bool             # ทุกสมาชิกในช่องต้องเป็น str/None ไหม

    def is_block(self, x) -> bool:
        if not isinstance(x, list) or len(x) not in self.slots:
            return False
        for e in x:
            if not (isinstance(e, list) and len(e) >= 2):
                return False
            if not (e[0] is None or isinstance(e[0], str)):
                return False
            if not isinstance(e[1], str):
                return False
            if self.text_only and not all(v is None or isinstance(v, str) for v in e):
                return False
        return True

    def is_choice(self, x) -> bool:
        """ตัวเลือกที่ผู้เล่นกด เก็บคนละที่กับบทพูด"""
        lang = x.get("language") if isinstance(x, dict) else None
        return (isinstance(lang, list) and len(lang) in self.slots
                and isinstance(lang[CN], dict) and "text" in lang[CN])

    # ลำดับที่ yield ออกมา = ลำดับที่ idx ถูกนับไว้ใน CSV — ห้ามเปลี่ยน
    # (บล็อกที่เจอแล้วยัง recurse เข้าไปข้างในต่อ เหมือนเดิมทุกประการ)
    def blocks(self, node):
        if isinstance(node, list):
            if self.is_block(node):
                yield node
            for e in node:
                yield from self.blocks(e)
        elif isinstance(node, dict):
            for v in node.values():
                yield from self.blocks(v)

    def choices(self, node):
        if isinstance(node, dict):
            if self.is_choice(node):
                yield node
            for v in node.values():
                yield from self.choices(v)
        elif isinstance(node, list):
            for e in node:
                yield from self.choices(e)


ALL_AGES = Layout("all-ages", (4,), text_only=False)
R18 = Layout("r18", (4, 5), text_only=True)


def json_files(d: str) -> list[str]:
    """สคริปต์ทุกบทในโฟลเดอร์ (ตัด *.resx.json ที่เป็นตารางทรัพยากรทิ้ง)"""
    return sorted(p for p in glob.glob(os.path.join(d, "*.ks.json"))
                  if not p.endswith(".resx.json"))
