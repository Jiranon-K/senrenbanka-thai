#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
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
import freemote                                               # noqa: E402

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


def build_archive(files, blob=b"BLOB-KEEP-ME") -> bytes:
    body = bytearray(b"\x00" * 40)
    struct.pack_into("<Q", body, 11, 23)
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
    ks = (key * (len(plain) // len(key) + 1))[:len(plain)]
    return bytes(a ^ b for a, b in zip(plain, ks))


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

    out = os.path.join(d, "same.xp3")
    ar.save(out)
    ar2 = xp3.Archive.read(out)
    chk("ประกอบกลับแล้วชื่อยังครบ", [e.name for e in ar2.entries],
        [e.name for e in ar.entries])
    chk("ประกอบกลับแล้วเนื้อไม่เปลี่ยน",
        [ar2.encrypted(e) for e in ar2.entries],
        [ar.encrypted(e) for e in ar.entries])

    ar3 = xp3.Archive.read(src)
    new_plain = "คำแปลไทย".encode("utf-8") * 30
    entry = ar3.find("a.ks.scn")
    chk_true("แทนได้", ar3.replace(entry, new_plain, plain_a))
    chk("นับจำนวนที่แทน", ar3.replaced, 1)
    out2 = os.path.join(d, "patched.xp3")
    ar3.save(out2)

    ar4 = xp3.Archive.read(out2)
    e4 = ar4.find("a.ks.scn")
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
    bad[23] = 0x00
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

    a, b, c = b"a" * 111, b"b" * 222, b"c" * 222
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


def test_corpus_layouts():
    print("=" * 70)
    print("corpus — แต่ละสายต้องผูกกับ layout ของตัวเอง (RULES.md R1)")
    import corpus
    import pipeline_cn
    import port_r18
    chk("ALL_AGES_CORPUS ใช้ scenario.ALL_AGES",
        corpus.ALL_AGES_CORPUS.layout is scenario.ALL_AGES, True)
    chk("R18_CORPUS ใช้ scenario.R18", corpus.R18_CORPUS.layout is scenario.R18, True)
    chk("ALL_AGES_CORPUS อ่าน/เขียน strings_cn.csv", corpus.ALL_AGES_CORPUS.csv, P.CSV_CN)
    chk("R18_CORPUS อ่าน/เขียน strings_r18.csv", corpus.R18_CORPUS.csv, P.CSV_R18)
    chk("pipeline_cn.py ใช้ ALL_AGES_CORPUS", pipeline_cn.CORPUS is corpus.ALL_AGES_CORPUS, True)
    chk("port_r18.py ใช้ R18_CORPUS", port_r18.CORPUS is corpus.R18_CORPUS, True)


def test_walk_order():
    print("=" * 70)
    print("scenario — ลำดับที่เดิน = ลำดับที่ idx ถูกนับไว้ใน CSV")

    doc = {"scenes": [PLAIN_4, {"inner": [PLAIN_4, PLAIN_4]}], "tail": PLAIN_4}
    got = list(scenario.ALL_AGES.blocks(doc))
    chk("เจอครบทุกบล็อก", len(got), 4)
    chk("เป็นตัวเดียวกัน ไม่ใช่ก็อป", all(g is PLAIN_4 for g in got), True)

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


def test_targets_table():
    print("=" * 70)
    print("targets — ตารางไฟล์ที่แพตช์แตะ")
    import targets as T

    chk("ไม่มีชื่อไฟล์ซ้ำ",
        len({t.file for t in T.TARGETS}), len(T.TARGETS))
    chk("ไม่มีชื่อ diff ซ้ำ",
        len({t.delta for t in T.TARGETS}), len(T.TARGETS))
    chk("ไม่มีชื่อตัวแปร .bat ซ้ำ (ORIG_x/THAI_x จะทับกัน)",
        len({t.var for t in T.TARGETS}), len(T.TARGETS))
    chk("ตัวแปร .bat เป็น A-Z ล้วน",
        [t.var for t in T.TARGETS if not t.var.isascii() or not t.var.isupper()], [])
    chk("ไฟล์ R18 ทุกตัวไม่บังคับ (เครื่องที่ไม่ลง R18 ต้องติดตั้งได้)",
        [t.file for t in T.TARGETS if t.r18 and t.required], [])
    chk("ทุก target ที่เป็น R18 ถูกระบุว่าจะปิดหรือปล่อยไว้ตอนเลือก all-ages",
        [t.file for t in T.TARGETS if t.r18 and t.file not in
         T.DISABLE_ON_ALL_AGES + T.KEEP_ON_ALL_AGES], [])

    for name, text in (("รายชื่อไฟล์ในซิป", T.bat_required_files()),
                       ("บล็อก rollback", T.bat_rollback()),
                       ("uninstall: หา .bak", T.bat_uninstall_found()),
                       ("uninstall: คืนไฟล์", T.bat_uninstall_restore())):
        missing = [t.file for t in T.TARGETS
                   if (t.delta if "ซิป" in name else t.file) not in text]
        chk("%s ครบทุก target" % name, missing, [])

    sets = T.bat_hash_vars({"patch.xp3": ("a" * 64, "b" * 64)})
    chk("target ที่ไม่ได้ build ได้ศูนย์ 64 ตัว (ไม่มีทางตรงกับของจริง)",
        sets.count("0" * 64), 2 * (len(T.TARGETS) - 1))
    chk("แฮชที่ส่งเข้าไปถูกใส่ลงตัวแปรถูกตัว",
        'set "THAI_PATCH=%s"' % ("b" * 64) in sets, True)

    try:
        T.check_bat_mentions_every_target("ไม่มีอะไรเลย", "เทส")
        chk(".bat ที่ไม่พูดถึง target ต้องหยุด build", "ไม่หยุด", "หยุด")
    except SystemExit as ex:
        chk_true(".bat ที่ไม่พูดถึง target หยุด build พร้อมบอกชื่อไฟล์",
                 "patch.xp3" in str(ex))


def test_generated_bat_matches_shipped():
    print("=" * 70)
    print("targets — .bat ที่ generate เทียบกับชุดติดตั้งที่ build ไว้")

    dist = os.environ.get("SBTP_RES")
    if not dist or not os.path.isfile(os.path.join(dist, "install.bat")):
        return skip("เทียบกับ .bat ที่ปล่อยไปแล้ว",
                    "ตั้ง SBTP_RES ชี้ไปที่โฟลเดอร์ชุดติดตั้งก่อน")

    import re
    import build_release as B
    import targets as T

    shipped = {}
    for n in ("install.bat", "uninstall.bat"):
        with open(os.path.join(dist, n), encoding="utf-8") as f:
            shipped[n] = f.read()

    with open(os.path.join(dist, "manifest.json"), encoding="utf-8") as f:
        ver = json.load(f)["version"]

    hashes = {}
    for t in T.TARGETS:
        o = re.search(r'set "ORIG_%s=(\w+)"' % t.var, shipped["install.bat"])
        h = re.search(r'set "THAI_%s=(\w+)"' % t.var, shipped["install.bat"])
        if o and h:
            hashes[t.file] = (o.group(1), h.group(1))

    def fill(body):
        return (body.replace("__VER__", ver)
                    .replace("__DELTAS__", T.bat_required_files())
                    .replace("__ROLLBACK__", T.bat_rollback())
                    .replace("__UNINSTALL_FOUND__", T.bat_uninstall_found())
                    .replace("__UNINSTALL_RESTORE__", T.bat_uninstall_restore()))

    made = {
        "install.bat": (B.BAT_HEAD % ("Installer", ver)) + "\n"
                       + T.bat_hash_vars(hashes) + "\n" + fill(B.INSTALL_BODY),
        "uninstall.bat": (B.BAT_HEAD % ("Uninstaller", ver))
                         + fill(B.UNINSTALL_BODY),
    }

    def norm(text):
        return [re.sub(r"[ \t]+", " ", ln.rstrip())
                for ln in text.replace("\r\n", "\n").split("\n")]

    for n, text in made.items():
        chk("%s ตรงกับที่ปล่อยไปแล้วทุกบรรทัด" % n,
            norm(shipped[n]), norm(text))
        try:
            T.check_bat_mentions_every_target(text, n)
            chk("%s ที่เติมค่าแล้วผ่านด่านกันลืม" % n, "ผ่าน", "ผ่าน")
        except SystemExit as ex:
            chk("%s ที่เติมค่าแล้วผ่านด่านกันลืม" % n, str(ex), "ผ่าน")


class _Done:
    def __init__(self, code, out=b""):
        self.returncode, self.stdout, self.stderr = code, out, b""


def _fake_run(code=0, write=True, build_name=".pure.scn"):
    def run(args, cwd=None, capture_output=True):
        exe, src = os.path.basename(args[0]), args[1]
        if write and code == 0:
            stem = os.path.splitext(src)[0]
            if exe == "dec":
                open(stem + ".json", "w").write("{}")
                open(stem + ".resx.json", "w").write("{}")
            else:
                base = os.path.basename(src)[:-5]
                open(os.path.join(cwd, base + build_name), "wb").write(b"PSB")
        return _Done(code, b"boom" if code else b"")
    return run


def test_freemote():
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "001.ks.scn"); open(src, "wb").write(b"x")
        out = os.path.join(d, "json")
        fm = freemote.FreeMote("dec", "bld", run=_fake_run())
        js = fm.decompile(src, out)
        chk("decompile คืน path ใน out_dir", js, os.path.join(out, "001.ks.json"))
        chk_true("resx.json ย้ายตามไปด้วย", os.path.exists(os.path.join(out, "001.ks.resx.json")))
        psb = os.path.join(d, "psb")
        chk("build .pure.scn -> .scn", fm.build(js, psb), os.path.join(psb, "001.ks.scn"))
        fm2 = freemote.FreeMote("dec", "bld", run=_fake_run(build_name=".psb"))
        chk_true("build .psb -> .scn", os.path.exists(fm2.build(js, os.path.join(d, "p2"))))

        for label, fake in (("exit code ไม่ใช่ 0", _fake_run(code=1)),
                            ("ไม่มีไฟล์ผลลัพธ์", _fake_run(write=False))):
            bad = freemote.FreeMote("dec", "bld", run=fake)
            for what, call in (("decompile", lambda: bad.decompile(src, out)),
                               ("build", lambda: bad.build(js, psb))):
                try:
                    call(); chk("%s: %s ต้อง raise" % (label, what), "ไม่ raise", "raise")
                except freemote.FreeMoteError:
                    chk("%s: %s ต้อง raise" % (label, what), "raise", "raise")


def main():
    test_layouts_differ()
    test_corpus_layouts()
    test_walk_order()
    test_json_files()
    test_targets_table()
    test_generated_bat_matches_shipped()
    test_xp3_roundtrip()
    test_xp3_guards()
    test_xp3_match_by_size()
    test_xp3_compressed()
    test_xp3_shared_payload()
    test_xp3_real_archive()
    test_freemote()

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
