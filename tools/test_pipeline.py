#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_pipeline.py — เทส tools/xp3.py กับ tools/scenario.py

    python tools/test_pipeline.py

**ไม่ต้องมีเกม ไม่ต้องมีไฟล์ .xp3** — สร้าง archive จิ๋วขึ้นมาในหน่วยความจำเอง
นี่คือเหตุผลที่แยกสองโมดูลนี้ออกมา: ตอนที่โค้ดพวกนี้ยังฝังอยู่ใน cmd_pack()
ที่อ่าน sys.argv เองและเขียนทับ archive 855 MB เอง มันเทสไม่ได้เลยสักบรรทัด

ถ้ามี archive จริงอยู่ในเครื่อง จะเทสเพิ่มอีกชุด (ข้ามเองถ้าไม่มี)
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import paths as P                                             # noqa: E402
import scenario                                               # noqa: E402
import xp3                                                    # noqa: E402

fails = []
skipped = []


def chk(label, got, want):
    if got == want:
        print("    PASS  %s" % label)
    else:
        print("    FAIL  %s\n          want %r\n          got  %r" % (label, want, got))
        fails.append(label)


def chk_true(label, cond):
    chk(label, bool(cond), True)


def skip(label, why):
    print("    SKIP  %s — %s" % (label, why))
    skipped.append(label)


# ═════════════════════════════════════════════════ archive จิ๋วไว้เทส

def build_archive(files, blob=b"BLOB-KEEP-ME") -> bytes:
    """ประกอบ .xp3 ขั้นต่ำที่ xp3.Archive อ่านได้ — ไว้เทสโดยไม่ต้องมีเกม

    วางผังเหมือนของจริง: header 40 -> เนื้อไฟล์ -> sen: blob -> index (zlib)

    files = [(ชื่อ, ไบต์)] หรือ dict เพื่อคุมกรณีพิเศษ:
        {"name":…, "data":…}              ธรรมดา
        {"name":…, "data":…, "size": n}   บีบอัดไว้ (size = ขนาดหลังคลาย)
        {"name":…, "share": i}            ใช้เนื้อร่วมกับ entry ที่ i
    """
    body = bytearray(b"\x00" * 40)
    struct.pack_into("<Q", body, 11, 23)      # ตัวชี้ v2
    body[23] = 0x80

    placed = []
    for f in files:
        if isinstance(f, tuple):
            f = {"name": f[0], "data": f[1]}
        if "share" in f:
            _n, off, size, stored = placed[f["share"]]
            placed.append((f["name"], off, size, stored))
            continue
        data = f["data"]
        placed.append((f["name"], len(body), f.get("size", len(data)), len(data)))
        body += data
    blob_at = len(body)
    body += blob
    index_at = len(body)

    # prefix ของ index: ต้องมี 'sen:' ที่ field0 = offset ของ blob, field3 = ความยาว
    sen = bytearray(16)
    struct.pack_into("<I", sen, 0, blob_at)
    struct.pack_into("<I", sen, 12, len(blob))
    prefix = b"sen:" + struct.pack("<Q", len(sen)) + bytes(sen)

    index = bytearray(prefix)
    for name, off, size, stored in placed:
        nm = name.encode("utf-16-le")
        info = bytearray(22) + nm
        struct.pack_into("<H", info, 20, len(name))
        segm = bytearray(28)
        struct.pack_into("<Q", segm, 4, off)
        struct.pack_into("<Q", segm, 12, size)
        struct.pack_into("<Q", segm, 20, stored)
        chunk = bytearray()
        for tag, data in ((b"info", bytes(info)), (b"segm", bytes(segm)),
                          (b"adlr", b"\xde\xad\xbe\xef")):
            chunk += tag + struct.pack("<Q", len(data)) + data
        index += b"File" + struct.pack("<Q", len(chunk)) + chunk

    packed = zlib.compress(bytes(index), 6)
    body += b"\x01" + struct.pack("<Q", len(packed)) + struct.pack("<Q", len(index))
    body += packed
    body[32:40] = struct.pack("<Q", index_at)
    return bytes(body)


def encrypt(plain: bytes, key: bytes) -> bytes:
    """เลียนแบบการเข้ารหัสของเกม — XOR กับ keystream ที่ผูกกับ adlr"""
    ks = (key * (len(plain) // len(key) + 1))[:len(plain)]
    return bytes(a ^ b for a, b in zip(plain, ks))


# ═════════════════════════════════════════════════════ xp3: อ่าน/เขียน

def test_xp3_roundtrip():
    print("=" * 70)
    print("xp3 — อ่าน archive จิ๋ว แล้วประกอบกลับ")

    plain_a = b"scenario A plaintext " * 40
    plain_b = b"B" * 300
    raw = build_archive([("a.ks.scn", encrypt(plain_a, b"\x11\x22\x33")),
                         ("b.ks.scn", encrypt(plain_b, b"\x77"))])

    d = tempfile.mkdtemp(prefix="sbtp-xp3-")
    src = os.path.join(d, "test.xp3")
    with open(src, "wb") as f:
        f.write(raw)

    ar = xp3.Archive.read(src)
    chk("อ่านชื่อไฟล์ครบ", [e.name for e in ar.entries], ["a.ks.scn", "b.ks.scn"])
    chk("ขนาดตรง", [e.size for e in ar.entries], [len(plain_a), len(plain_b)])
    chk("ยังไม่ได้แทนอะไร", ar.replaced, 0)

    # ประกอบกลับโดยไม่แทนอะไรเลย -> เนื้อทุกไฟล์ต้องเหมือนเดิมไบต์ต่อไบต์
    out = os.path.join(d, "same.xp3")
    ar.save(out)
    ar2 = xp3.Archive.read(out)
    chk("ประกอบกลับแล้วชื่อยังครบ", [e.name for e in ar2.entries],
        [e.name for e in ar.entries])
    chk("ประกอบกลับแล้วเนื้อไม่เปลี่ยน",
        [ar2.encrypted(e) for e in ar2.entries],
        [ar.encrypted(e) for e in ar.entries])

    # แทนไฟล์ a ด้วยเนื้อใหม่ แล้วต้องถอดกลับออกมาได้เท่าที่ใส่ไป
    ar3 = xp3.Archive.read(src)
    new_plain = "คำแปลไทย".encode("utf-8") * 30
    entry = ar3.find("a.ks.scn")
    chk_true("แทนได้", ar3.replace(entry, new_plain, plain_a))
    chk("นับจำนวนที่แทน", ar3.replaced, 1)
    out2 = os.path.join(d, "patched.xp3")
    ar3.save(out2)

    ar4 = xp3.Archive.read(out2)
    e4 = ar4.find("a.ks.scn")
    # ถอดด้วย keystream เดิม (เกมทำแบบนี้ เพราะ adlr ไม่ถูกแตะ)
    ks = bytes(x ^ y for x, y in zip(ar.encrypted(entry), plain_a))
    got = bytes(x ^ y for x, y in zip(ar4.encrypted(e4), ks))
    chk("ถอดกลับได้เนื้อใหม่", got[:len(new_plain)], new_plain)
    chk("ส่วนที่เหลือถูก pad ด้วยศูนย์", set(got[len(new_plain):]), {0})
    chk("ไฟล์อื่นไม่ถูกแตะ", ar4.encrypted(ar4.find("b.ks.scn")),
        ar.encrypted(ar.find("b.ks.scn")))
    chk("adlr ไม่ถูกแตะ",
        [dict(e.subs).get(b"adlr") for e in ar4.entries],
        [dict(e.subs).get(b"adlr") for e in ar.entries])


def test_xp3_guards():
    print("=" * 70)
    print("xp3 — เงื่อนไขที่ต้องไม่ยอมให้ผ่าน")

    plain = b"x" * 100
    raw = build_archive([("a.ks.scn", encrypt(plain, b"\x05"))])
    d = tempfile.mkdtemp(prefix="sbtp-xp3g-")
    src = os.path.join(d, "t.xp3")
    with open(src, "wb") as f:
        f.write(raw)

    ar = xp3.Archive.read(src)
    e = ar.entries[0]
    chk("ไฟล์ใหญ่เกินช่อง -> คืน False ไม่ใช่เขียนทับ",
        ar.replace(e, b"y" * 101, plain), False)
    chk("ของเดิมไม่ถูกแตะเมื่อ replace ไม่ผ่าน", ar.replaced, 0)

    try:
        ar.replace(e, b"y", b"wrong length")
        chk("จับคู่ผิดไฟล์ต้อง raise", "ไม่ raise", "raise")
    except ValueError as ex:
        chk_true("จับคู่ผิดไฟล์ raise พร้อมบอกขนาด", "100" in str(ex))

    bad = bytearray(raw)
    bad[23] = 0x00                       # ทำให้ไม่ใช่ header v2
    p = os.path.join(d, "bad.xp3")
    with open(p, "wb") as f:
        f.write(bytes(bad))
    try:
        xp3.Archive.read(p)
        chk("header ผิดรุ่นต้อง raise", "ไม่ raise", "raise")
    except (ValueError, zlib.error, struct.error):
        chk("header ผิดรุ่น raise", True, True)


def test_xp3_match_by_size():
    print("=" * 70)
    print("xp3 — จับคู่ entry กับไฟล์จริงด้วยขนาด")

    a, b, c = b"a" * 111, b"b" * 222, b"c" * 222     # b กับ c ขนาดชนกัน
    raw = build_archive([("one", a), ("two", b), ("three", c)])
    d = tempfile.mkdtemp(prefix="sbtp-xp3m-")
    src = os.path.join(d, "t.xp3")
    with open(src, "wb") as f:
        f.write(raw)
    ext = os.path.join(d, "extract")
    os.makedirs(ext)
    for nm, data in (("A.ks.scn", a), ("B.ks.scn", b), ("C.ks.scn", c)):
        with open(os.path.join(ext, nm), "wb") as f:
            f.write(data)

    ar = xp3.Archive.read(src)
    m = ar.match_by_size(ext)
    chk("จับคู่เฉพาะตัวที่ขนาดไม่ซ้ำใคร",
        sorted(os.path.basename(v) for v in m.values()), ["A.ks.scn"])
    chk("ตัวที่ขนาดชนกันถูกข้าม (เดาผิด = เขียนทับผิดบท)", len(m), 1)


def test_xp3_compressed():
    print("=" * 70)
    print("xp3 — entry ที่ถูกบีบอัดไว้ (segm เก็บสองขนาด)")

    stored = zlib.compress(b"hello " * 500)
    raw = build_archive([{"name": "plain", "data": b"P" * 64},
                         {"name": "packed", "data": stored, "size": 3000}])
    d = tempfile.mkdtemp(prefix="sbtp-cmp-")
    src = os.path.join(d, "t.xp3")
    with open(src, "wb") as f:
        f.write(raw)

    ar = xp3.Archive.read(src)
    packed = ar.find("packed")
    chk("รู้ว่า entry นี้ถูกบีบอัด", packed.compressed, True)
    chk("ขนาดหลังคลาย", packed.size, 3000)
    chk("จำนวนไบต์ที่เก็บจริง", packed.stored, len(stored))
    # นี่คือบั๊กที่โค้ดชุดเดิมมี: ก็อป size ไบต์ = ลากของ entry ถัดไปติดมาด้วย
    chk("อ่านมาแค่ไบต์ที่เก็บจริง ไม่ลากของข้างเคียง",
        ar.encrypted(packed), stored)
    chk("entry ธรรมดาไม่ถูกหมายว่าบีบอัด", ar.find("plain").compressed, False)

    try:
        ar.replace(packed, b"x", b"y")
        chk("แทน entry ที่บีบอัดต้อง raise", "ไม่ raise", "raise")
    except ValueError as ex:
        chk_true("แทน entry ที่บีบอัด raise พร้อมบอกเหตุ", "บีบอัด" in str(ex))

    out = os.path.join(d, "r.xp3")
    ar.save(out)
    ar2 = xp3.Archive.read(out)
    chk("ประกอบกลับแล้วยังบีบอัดอยู่เหมือนเดิม",
        (ar2.find("packed").size, ar2.find("packed").stored),
        (3000, len(stored)))
    chk("ประกอบกลับแล้วเนื้อยังถูก", ar2.encrypted(ar2.find("packed")), stored)


def test_xp3_shared_payload():
    print("=" * 70)
    print("xp3 — entry ที่ใช้เนื้อร่วมกัน (archive จริงทำแบบนี้ 13 ช่วงใน data.xp3)")

    body = b"S" * 5000
    raw = build_archive([{"name": "one", "data": body},
                         {"name": "two", "share": 0},
                         {"name": "other", "data": b"O" * 100}])
    d = tempfile.mkdtemp(prefix="sbtp-shr-")
    src = os.path.join(d, "t.xp3")
    with open(src, "wb") as f:
        f.write(raw)

    ar = xp3.Archive.read(src)
    chk("สอง entry ชี้ที่เดียวกัน",
        ar.find("one").offset, ar.find("two").offset)

    out = os.path.join(d, "r.xp3")
    ar.save(out)
    chk("ประกอบกลับแล้วไม่โตขึ้น (ไม่ก็อปแยก)",
        os.path.getsize(out) <= len(raw) + 64, True)
    ar2 = xp3.Archive.read(out)
    chk("ยังใช้เนื้อร่วมกันอยู่", ar2.find("one").offset, ar2.find("two").offset)
    chk("อ่านได้เนื้อเดิมทั้งคู่",
        (ar2.encrypted(ar2.find("one")), ar2.encrypted(ar2.find("two"))),
        (body, body))

    # แทนตัวหนึ่ง อีกตัวที่ใช้ร่วมกันต้องยังได้ของเดิม
    ar3 = xp3.Archive.read(src)
    new = b"N" * 5000
    chk_true("แทนตัวแรกได้", ar3.replace(ar3.find("one"), new, body))
    out2 = os.path.join(d, "r2.xp3")
    ar3.save(out2)
    ar4 = xp3.Archive.read(out2)
    chk("ตัวที่ถูกแทนกับตัวที่ใช้ร่วม ต้องแยกออกจากกันแล้ว",
        ar4.find("one").offset != ar4.find("two").offset, True)
    chk("ตัวที่ไม่ได้แทน ยังได้เนื้อเดิม",
        ar4.encrypted(ar4.find("two")), body)


def test_xp3_real_archive():
    print("=" * 70)
    print("xp3 — archive ของจริง (ถ้ามีในเครื่อง)")
    try:
        game = P.game_dir()
    except SystemExit:
        return skip("archive จริง", "หาโฟลเดอร์เกมไม่เจอ")

    found = [os.path.join(game, n) for n in
             ("patch.xp3.bak", "data.xp3.bak", "adult.xp3.orig")
             if os.path.isfile(os.path.join(game, n))]
    if not found:
        return skip("archive จริง", "ไม่มี .xp3 ในโฟลเดอร์เกม")
    for src in found:
        _check_real(src)


def _check_real(src):

    ar = xp3.Archive.read(src)
    print("    %s — %d entries" % (os.path.basename(src), len(ar.entries)))
    chk_true("อ่านได้หลาย entry", len(ar.entries) > 1)
    chk("ทุก entry มีชื่อ", [e for e in ar.entries if not e.name], [])
    chk("ทุก entry มี offset/size", [e for e in ar.entries
                                     if e.offset is None or e.size is None], [])

    rebuilt = ar.build()
    d = tempfile.mkdtemp(prefix="sbtp-real-")
    out = os.path.join(d, "rebuilt.xp3")
    with open(out, "wb") as f:
        f.write(rebuilt)
    ar2 = xp3.Archive.read(out)
    chk("ประกอบกลับ: จำนวน entry เท่าเดิม", len(ar2.entries), len(ar.entries))
    chk("ประกอบกลับ: ชื่อเรียงเหมือนเดิม",
        [e.name for e in ar2.entries], [e.name for e in ar.entries])
    chk("ประกอบกลับ: ขนาดเหมือนเดิม",
        [e.size for e in ar2.entries], [e.size for e in ar.entries])
    same = all(ar2.encrypted(x) == ar.encrypted(y)
               for x, y in zip(ar2.entries, ar.entries))
    chk("ประกอบกลับ: เนื้อทุกไฟล์เหมือนเดิมไบต์ต่อไบต์", same, True)
    os.remove(out)


# ═══════════════════════════════════════════════ scenario: สอง layout

# node ที่ ALL_AGES นับเป็นบทพูดแต่ R18 ไม่นับ — ตัวการที่ทำให้เลข idx
# ของสองสายไม่ตรงกัน 70 จาก 86 บท (46,303 vs 45,208 บล็อก)
NESTED_4 = [["bgm", "bgm", {"v": 1}], ["lse", "loopse", {"v": 2}],
            ["se", "se", {"v": 3}], ["vo", "voice", {"v": 4}]]
PLAIN_4 = [["さくら", "ข้อความ JP"], [None, "EN text"],
           [None, "ข้อความไทย"], [None, "TW"]]
PLAIN_5 = PLAIN_4 + [[None, "KO"]]


def test_layouts_differ():
    print("=" * 70)
    print("scenario — สอง layout ต้องต่างกันตามที่บันทึกไว้ (ห้ามรวมเป็นตัวเดียว)")

    chk("ALL_AGES นับ node ที่มี dict ปนเป็นบทพูด",
        scenario.ALL_AGES.is_block(NESTED_4), True)
    chk("R18 ไม่นับ (นี่คือ guard ที่ ALL_AGES ไม่มี)",
        scenario.R18.is_block(NESTED_4), False)
    chk("ALL_AGES ไม่รับ 5 ช่อง", scenario.ALL_AGES.is_block(PLAIN_5), False)
    chk("R18 รับ 5 ช่อง (เกาหลีถูกเพิ่มเข้ามา)",
        scenario.R18.is_block(PLAIN_5), True)
    chk("ทั้งคู่รับบทพูด 4 ช่องธรรมดา",
        (scenario.ALL_AGES.is_block(PLAIN_4), scenario.R18.is_block(PLAIN_4)),
        (True, True))
    chk("ช่องที่คำแปลไทยไปอยู่คือช่องที่ 2", scenario.CN, 2)


def test_walk_order():
    print("=" * 70)
    print("scenario — ลำดับที่เดิน = ลำดับที่ idx ถูกนับไว้ใน CSV")

    doc = {"scenes": [PLAIN_4, {"inner": [PLAIN_4, PLAIN_4]}], "tail": PLAIN_4}
    got = list(scenario.ALL_AGES.blocks(doc))
    chk("เจอครบทุกบล็อก", len(got), 4)
    chk("เป็นตัวเดียวกัน ไม่ใช่ก็อป", all(g is PLAIN_4 for g in got), True)

    # ลำดับต้องเป็น "พ่อก่อนลูก ซ้ายไปขวา" ตามที่ CSV ถูกนับไว้
    def blk(tag):
        return [[tag, "jp-" + tag], [None, "en"], [None, "cn"], [None, "tw"]]
    doc3 = {"first": blk("A"), "mid": [blk("B"), {"deep": blk("C")}],
            "last": blk("D")}
    chk("ลำดับ: พ่อก่อนลูก ซ้ายไปขวา",
        [b[0][0] for b in scenario.ALL_AGES.blocks(doc3)], ["A", "B", "C", "D"])

    ch = {"language": [{"text": "jp"}, {"text": "en"}, {"text": "cn"}, {"text": "tw"}]}
    doc2 = {"a": [ch], "b": {"c": ch}}
    chk("เดินตัวเลือกเจอครบ", len(list(scenario.ALL_AGES.choices(doc2))), 2)
    chk("R18 ก็เจอตัวเลือก 4 ช่องเหมือนกัน",
        len(list(scenario.R18.choices(doc2))), 2)

    ch5 = {"language": [{"text": "jp"}, {"text": "en"}, {"text": "cn"},
                        {"text": "tw"}, {"text": "ko"}]}
    chk("ตัวเลือก 5 ช่อง: R18 เจอ / ALL_AGES ไม่เจอ",
        (len(list(scenario.R18.choices({"x": ch5}))),
         len(list(scenario.ALL_AGES.choices({"x": ch5})))), (1, 0))


def test_json_files():
    print("=" * 70)
    print("scenario — เลือกไฟล์สคริปต์")
    d = tempfile.mkdtemp(prefix="sbtp-jf-")
    for n in ("b.ks.json", "a.ks.json", "a.resx.json", "note.txt"):
        open(os.path.join(d, n), "w").close()
    chk("ตัด .resx.json กับไฟล์อื่นทิ้ง แล้วเรียงชื่อ",
        [os.path.basename(p) for p in scenario.json_files(d)],
        ["a.ks.json", "b.ks.json"])


# ═════════════════════════════════════════════════════════════ main

def main():
    test_layouts_differ()
    test_walk_order()
    test_json_files()
    test_xp3_roundtrip()
    test_xp3_guards()
    test_xp3_match_by_size()
    test_xp3_real_archive()

    print("=" * 70)
    if skipped:
        print("ข้าม %d เคส: %s" % (len(skipped), ", ".join(skipped)))
    if fails:
        print("ตก %d เคส:" % len(fails))
        for f in fails:
            print("  -", f)
        sys.exit(1)
    print("ผ่านทั้งหมด")


if __name__ == "__main__":
    main()
