#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tsv.py — งานประจำวันกับ thai_work/th/<stem>.tsv (ไฟล์ที่คนแปลนั่งพิมพ์จริง)

    python tools/tsv.py dump  <prefix>    เขียน th/<prefix>.src.tsv ให้เอาไปแปล
    python tools/tsv.py merge <prefix>    เอาคำแปลกลับเข้า strings_cn.csv
    python tools/tsv.py align <prefix>    เช็คว่าบทพูด/บรรยาย ตรงกับต้นฉบับไหม

เดิมเป็นสามไฟล์แยกกัน ชื่อ `_dump_src.py` `_merge.py` `_align_check.py`
รวมมาไว้ที่เดียวด้วยเหตุผลสองข้อ:

* ขีดล่างนำหน้าใน Python แปลว่า "ของภายในโมดูล อย่า import" แต่ทั้งสามตัวเป็น
  **คำสั่งที่ต้องรันตรงๆ** ซึ่งตรงข้ามกับที่ชื่อบอก
* ทั้งสามอ่านตารางเดียวกัน (strings_cn.csv) คู่กับไฟล์เดียวกัน (th/<stem>.tsv)
  และใช้ในรอบงานเดียวกัน — dump แล้วแปล แล้ว align แล้ว merge

`align` เดิมล็อกฉาก 010 ไว้ในโค้ด ตอนนี้รับ prefix เหมือนอีกสองคำสั่ง
"""
from __future__ import annotations

import csv
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths as P                                             # noqa: E402

csv.field_size_limit(10 ** 9)


def _rows(prefix: str) -> list[dict]:
    with open(P.CSV_CN, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["file"].startswith(prefix)]


def _read_th(prefix: str) -> dict[str, str]:
    """อ่าน th/<prefix>.tsv -> {idx: คำแปล}"""
    out: dict[str, str] = {}
    with open(os.path.join(P.TH_DIR, prefix + ".tsv"), encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            i, t = line.split("\t", 1)
            out[i] = t
    return out


def is_control(row: dict) -> bool:
    """แถวคำสั่ง/เอฟเฟกต์ — ไม่มีตัวอักษร CJK เลยแปลว่าไม่ใช่บทพูด"""
    return not any(ord(c) > 0x3000 for c in row["jp"])


def kind(s: str) -> str:
    """"D" = บทพูด (ขึ้นต้นด้วยวงเล็บญี่ปุ่น) · "N" = บรรยาย"""
    s = re.sub(r"^(%\d+;)+", "", s.lstrip())      # %184; = font-size tag, not text
    return "D" if s.startswith("「") or s.startswith("『") else "N"


# ────────────────────────────────────────────────────────────── คำสั่ง

def cmd_dump(prefix: str) -> int:
    """เขียน th/<prefix>.src.tsv (idx, ผู้พูด, jp, en) ตัดแถวคำสั่งออก"""
    rows = _rows(prefix)
    control = [r for r in rows if is_control(r)]
    text = [r for r in rows if not is_control(r)]
    nums = sorted(int(r["idx"]) for r in text if r["idx"].isdigit())
    choices = [r["idx"] for r in text if not r["idx"].isdigit()]

    out = os.path.join(P.TH_DIR, prefix + ".src.tsv")
    os.makedirs(P.TH_DIR, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t")
        for r in text:
            w.writerow([r["idx"], r["speaker_en"], r["jp"], r["en"]])

    print("แถวทั้งหมด %d · คำสั่ง %d · แปลได้ %d · idx %s..%s · ตัวเลือก %s"
          % (len(rows), len(control), len(text),
             nums[0] if nums else "-", nums[-1] if nums else "-", choices))
    print("เขียน %s" % out)
    return 0


def cmd_merge(prefix: str) -> int:
    """เอา th/<prefix>.tsv กลับเข้าคอลัมน์ th ของ strings_cn.csv"""
    th = _read_th(prefix)
    with open(P.CSV_CN, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        sys.exit("%s ว่าง" % P.CSV_CN)
    fields = list(rows[0].keys())

    applied = 0
    for r in rows:
        if r["file"].startswith(prefix) and r["idx"] in th:
            r["th"] = th[r["idx"]]
            applied += 1

    with open(P.CSV_CN, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print("รวม prefix=%s: ใส่ได้ %d / มีคำแปล %d -> %s"
          % (prefix, applied, len(th), P.CSV_CN))
    return 0


def cmd_align(prefix: str) -> int:
    """เตือน idx ที่โครงสร้างวงเล็บของคำแปลไม่ตรงกับต้นฉบับ

    บทพูดที่กลายเป็นบรรยาย (หรือกลับกัน) มักแปลว่าเลื่อนบรรทัดกันไปแล้ว
    ซึ่งในเกมจะเห็นเป็นคำแปลไปโผล่ผิดคน — จับตอนนี้ถูกกว่าจับตอนเล่น
    """
    th = _read_th(prefix)
    bad = []
    for r in _rows(prefix):
        i = r["idx"]
        if i in ("0", "1") or not i.isdigit() or i not in th:
            continue
        a, b = kind(r["jp"]), kind(th[i])
        if a != b:
            bad.append((i, a, b, r["jp"][:30], th[i][:30]))

    print("โครงสร้างไม่ตรง: %d" % len(bad))
    for i, a, b, jp, t in bad:
        print("[%s] ต้นฉบับ=%s แปล=%s | JP=%s | TH=%s" % (i, a, b, jp, t))
    return 1 if bad else 0


COMMANDS = {"dump": cmd_dump, "merge": cmd_merge, "align": cmd_align}


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[sys.argv[1]](sys.argv[2])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
