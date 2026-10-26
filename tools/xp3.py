#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xp3.py — อ่าน/เขียน archive .xp3 ของ KiriKiri (แบบที่ Yuzusoft ใช้)

เดิมโค้ดชุดนี้ถูกก็อปไว้ **สามที่** — `pipeline_cn.cmd_pack`, `port_r18.cmd_pack`
และ `rebuild_fonts.main` — แล้วสามฉบับก็ห่างกันไปเรื่อยๆ ฉบับหนึ่งมี assert กัน
header ผิดรุ่น อีกฉบับมี XOR แบบ big-int ที่เร็วกว่าเป็นร้อยเท่า อีกฉบับไม่มี
ทั้งคู่ ใครแก้ฝั่งไหนอีกสองฝั่งไม่ได้ตาม

ทั้งสามทำเรื่องเดียวกันเป๊ะ: "เอาไฟล์ใหม่ยัดกลับเข้า archive โดยไม่ต้องรู้คีย์"

    ar = xp3.Archive.read(game_file("adult.xp3"))
    for e in ar.entries:
        ar.replace(e, ไบต์ใหม่, ไบต์เดิมที่ถอดรหัสแล้ว)
    ar.save(game_file("adult.xp3"))

รูปแบบไฟล์ (เท่าที่ต้องรู้)
--------------------------
    [0:40]      header v2  (ไบต์ที่ 32-40 = offset ของ index)
    ...         เนื้อไฟล์แต่ละตัว เรียงต่อกัน (เข้ารหัสไว้)
    ...         'sen:' blob — ก้อนพิเศษของ Yuzu ที่ต้องขนไปด้วย ไม่งั้นเกมไม่โหลด
    [iofs:]     index บีบด้วย zlib — ต่อกันเป็นชุด 'File' + ความยาว + chunk
                chunk ข้างในเป็นชุด tag ('info' = ชื่อ, 'segm' = offset+size,
                'adlr' = id ที่ห้ามแตะ) + ความยาว + ข้อมูล

keystream (ไม่ต้องรู้คีย์)
--------------------------
    keystream = ไบต์ที่เข้ารหัสอยู่ XOR ไบต์จริงตัวเดิม
    ไบต์ที่จะเขียน = ไฟล์ใหม่ (pad ให้ยาวเท่าเดิม) XOR keystream

เกมสร้าง keystream เดิมขึ้นมาใหม่จาก `adlr` ที่เราไม่แตะ จึงถอดออกมาได้เป็น
ไฟล์ใหม่ ข้อจำกัดเดียว: **ไฟล์ใหม่ต้องไม่ใหญ่กว่าช่องเดิม**

สองเรื่องที่โค้ดชุดเดิมพลาด (เพิ่งเห็นตอนเอามาเทสได้)
------------------------------------------------------
1. `segm` ยาว 28 ไบต์เก็บ **สองขนาด**: หลังคลายบีบอัด กับที่เก็บจริง โค้ดเดิม
   อ่านแต่ตัวแรกมาใช้เป็นจำนวนไบต์ที่จะก็อป — data.xp3 มี 318 จาก 1,278 entry
   ที่บีบอัดไว้ ทุกครั้งที่ประกอบใหม่จึงลากเนื้อของ entry ข้างเคียงติดมาด้วย
2. entry หลายตัวชี้ไปที่ **ช่วงเดียวกัน** ได้ (data.xp3 มี 13 ช่วง = 26 MB)
   โค้ดเดิมก็อปแยกให้ทุกตัว ไฟล์จึงโตขึ้นฟรี

ผลรวมของสองข้อ: `data.xp3` ที่แพตช์แล้วโตกว่าต้นฉบับ 35 MB โดยไม่มีเหตุผล
ตอนนี้ประกอบกลับได้ขนาดเท่าเดิม (±ไม่กี่สิบไบต์จากการบีบ index) และเนื้อทุก
ไฟล์ตรงกันไบต์ต่อไบต์ — มีเทสคุมไว้ใน tools/test_pipeline.py

ดู CONTEXT.md หัวข้อ keystream packing
"""
from __future__ import annotations

import glob
import os
import struct
import zlib

HEADER = 40                     # v2 header ที่ต้องขนไปทั้งก้อน
_V2_MARK = 0x80


class Entry:
    """หนึ่งไฟล์ใน archive

    `name` มาจาก tag 'info' — สำหรับ **ฟอนต์** เป็นชื่อจริง แต่สำหรับ
    **บทพูด** ไม่ใช่ชื่อไฟล์ที่ GARbro แตกออกมา จึงจับคู่ด้วยชื่อไม่ได้
    ต้องจับด้วยขนาดที่ไม่ซ้ำใคร (ดู match_by_size)

    `size` = ขนาดหลังคลายบีบอัด · `stored` = จำนวนไบต์ที่นอนอยู่ใน archive จริงๆ
    สองค่านี้เท่ากันเมื่อ entry ไม่ได้ถูกบีบอัด ซึ่งเป็นกรณีของบทพูดกับฟอนต์
    ทั้งหมดที่แพตช์นี้แตะ แต่ **ไม่ใช่ทุก entry** — data.xp3 มี 318 จาก 1,278
    ที่บีบอัดไว้ โค้ดชุดเดิม (ทั้งสามฉบับ) อ่าน `size` มาใช้เป็นจำนวนไบต์ที่จะ
    ก็อป จึงลากเนื้อของ entry ถัดไปติดมาด้วยทุกครั้งที่ประกอบ data.xp3 ใหม่
    """

    __slots__ = ("name", "offset", "size", "stored", "subs")

    def __init__(self, name, offset, size, stored, subs):
        self.name = name
        self.offset = offset
        self.size = size          # ขนาดหลังคลายบีบอัด
        self.stored = stored      # จำนวนไบต์ที่อยู่ใน archive
        self.subs = subs          # [[tag, bytearray], ...] — ใช้ตอนประกอบ index ใหม่

    @property
    def compressed(self) -> bool:
        return self.stored != self.size

    def __repr__(self):
        return "Entry(%r, size=%d%s)" % (
            self.name, self.size, ", compressed" if self.compressed else "")


class Archive:
    """archive หนึ่งไฟล์ ที่แก้ไฟล์ข้างในได้โดยไม่ต้องรู้คีย์"""

    def __init__(self, raw: bytes, entries: list[Entry], prefix: bytearray,
                 blob: bytes):
        self._raw = raw
        self._prefix = prefix            # ส่วนหัวของ index ก่อนชุด 'File' แรก
        self._blob = blob                # 'sen:' blob
        self._new: dict[str, bytes] = {}  # name -> ไบต์ที่เข้ารหัสแล้ว
        self.entries = entries

    # ────────────────────────────────────────────────────────────── อ่าน

    @classmethod
    def read(cls, path: str) -> "Archive":
        with open(path, "rb") as f:
            raw = f.read()
        index = cls._index_of(raw)

        # 'sen:' blob — ก้อนของ Yuzu ที่ต้องขนไปด้วยทั้งดุ้น
        sp = index.find(b"sen:")
        if sp < 0:
            raise ValueError("%s: ไม่พบ 'sen:' blob — ไม่ใช่ archive ของ Yuzu?" % path)
        sen_len = struct.unpack("<Q", index[sp + 4:sp + 12])[0]
        sen = index[sp + 12:sp + 12 + sen_len]
        blob_off = struct.unpack("<I", sen[0:4])[0]
        blob_len = struct.unpack("<I", sen[12:16])[0]
        blob = raw[blob_off:blob_off + blob_len]

        first = index.find(b"File")
        if first < 0:
            raise ValueError("%s: index ไม่มีชุด 'File' เลย" % path)
        return cls(raw, cls._entries(index, first), bytearray(index[:first]), blob)

    @staticmethod
    def _index_of(raw: bytes) -> bytes:
        """แกะ index ที่บีบด้วย zlib ออกมา"""
        ofs = struct.unpack("<Q", raw[11:19])[0]
        if raw[ofs] != _V2_MARK:
            raise ValueError("ไม่ใช่ header v2 (คาด 0x80 ที่ %d ได้ 0x%02x)"
                             % (ofs, raw[ofs]))
        real = struct.unpack("<Q", raw[ofs + 9:ofs + 17])[0]
        comp = struct.unpack("<Q", raw[real + 1:real + 9])[0]
        return zlib.decompress(raw[real + 17:real + 17 + comp])

    @staticmethod
    def _entries(index: bytes, first: int) -> list[Entry]:
        out, p = [], first
        while p < len(index) and index[p:p + 4] == b"File":
            p += 4
            size = struct.unpack("<Q", index[p:p + 8])[0]
            p += 8
            chunk = index[p:p + size]
            p += size

            q, subs = 0, []
            name = offset = length = stored = None
            while q < len(chunk):
                tag = chunk[q:q + 4]
                q += 4
                n = struct.unpack("<Q", chunk[q:q + 8])[0]
                q += 8
                data = bytearray(chunk[q:q + n])
                q += n
                subs.append([tag, data])
                if tag == b"info":
                    nl = struct.unpack("<H", data[20:22])[0]
                    name = data[22:22 + nl * 2].decode("utf-16-le", "replace")
                elif tag == b"segm":
                    offset = struct.unpack("<Q", data[4:12])[0]
                    length = struct.unpack("<Q", data[12:20])[0]
                    # segm ยาว 28 ไบต์จะมีขนาด "ตามที่เก็บจริง" ต่อท้ายมาด้วย
                    # ต่างจาก size เมื่อ entry นั้นถูกบีบอัดไว้
                    stored = (struct.unpack("<Q", data[20:28])[0]
                              if len(data) >= 28 else length)
            out.append(Entry(name, offset, length, stored, subs))
        return out

    # ────────────────────────────────────────────────────────────── ค้น

    def find(self, name: str) -> Entry | None:
        return next((e for e in self.entries if e.name == name), None)

    def match_by_size(self, extract_dir: str, pattern: str = "*.ks.scn") -> dict:
        """จับคู่ entry กับไฟล์จริงที่ GARbro แตกไว้ ด้วย "ขนาดที่ไม่ซ้ำใคร"

        คืน {Entry: path ของไฟล์จริง} — ตัวที่ขนาดชนกันตั้งแต่สองไฟล์ขึ้นไป
        จะถูกข้ามทิ้ง เพราะเดาไม่ได้ว่าอันไหนคืออันไหน และเดาผิดหมายถึงเขียน
        บทหนึ่งทับอีกบทหนึ่ง
        """
        by_size: dict[int, list[str]] = {}
        for p in glob.glob(os.path.join(extract_dir, pattern)):
            by_size.setdefault(os.path.getsize(p), []).append(p)
        return {e: by_size[e.size][0] for e in self.entries
                if len(by_size.get(e.size, ())) == 1}

    # ────────────────────────────────────────────────────────────── แก้

    def encrypted(self, entry: Entry) -> bytes:
        """ไบต์ที่ยังเข้ารหัสอยู่ของ entry นี้ (ตามที่อยู่ใน archive)"""
        return self._raw[entry.offset:entry.offset + entry.stored]

    def replace(self, entry: Entry, new_plain: bytes, orig_plain: bytes) -> bool:
        """เอา new_plain ไปแทน entry คืน False ถ้าใหญ่เกินช่องเดิม (ไม่แตะอะไร)

        orig_plain = ไบต์จริงตัวเดิมของ entry นี้ (ที่ GARbro แตกออกมา)
        ใช้สร้าง keystream ต้องยาวเท่า entry.stored เป๊ะ
        """
        if entry.compressed:
            # ต้องบีบอัดใหม่แล้วแก้ทั้งสองช่องขนาดใน segm ซึ่งยังไม่มีใครต้องใช้
            # (บทพูดกับฟอนต์ที่แพตช์นี้แตะ ไม่ได้ถูกบีบอัดสักตัว)
            raise ValueError("%s: entry ถูกบีบอัดไว้ ยังไม่รองรับการแทนที่"
                             % entry.name)
        if len(orig_plain) != entry.stored:
            raise ValueError(
                "%s: ไบต์ต้นฉบับยาว %d แต่ช่องใน archive ยาว %d — จับคู่ผิดไฟล์"
                % (entry.name, len(orig_plain), entry.stored))
        if len(new_plain) > entry.stored:
            return False

        new_plain = new_plain + b"\x00" * (entry.stored - len(new_plain))
        # XOR ทีเดียวทั้งก้อนด้วย big-int — เร็วกว่าวนทีละไบต์เป็นร้อยเท่า
        # บนไฟล์ระดับ MB (ซึ่งเป็นขนาดปกติของบทพูดในเกมนี้)
        ks = int.from_bytes(self.encrypted(entry), "big") ^ int.from_bytes(orig_plain, "big")
        self._new[entry.name] = (int.from_bytes(new_plain, "big") ^ ks).to_bytes(
            entry.stored, "big")
        return True

    def replace_sized(self, entry: Entry, new_plain: bytes, keystream: bytes) -> int:
        """Replace an entry with content of any size; returns the stored size.

        `keystream` comes from xp3_keystream.ps1 (cx is a pure XOR, so decrypting
        zeros gives it at any length) and must be at least len(new_plain).
        build() already lays entries out one after another, so only the size
        fields have to change: segm (flags, unpacked, stored) and info (unpacked,
        stored). An entry the original stored zlib-compressed stays compressed —
        compression wraps the encrypted bytes, as the engine expects.
        """
        if len(keystream) < len(new_plain):
            raise ValueError("%s: keystream %d < data %d" % (entry.name, len(keystream), len(new_plain)))
        enc = (int.from_bytes(new_plain, "big")
               ^ int.from_bytes(keystream[:len(new_plain)], "big")).to_bytes(len(new_plain), "big")
        stored = zlib.compress(enc, 9) if entry.compressed else enc
        for tag, data in entry.subs:
            if tag == b"segm":
                if len(data) != 28:
                    raise ValueError("%s: %d segments — not supported" % (entry.name, len(data) // 28))
                data[12:20] = struct.pack("<Q", len(new_plain))
                data[20:28] = struct.pack("<Q", len(stored))
            elif tag == b"info":
                data[4:12] = struct.pack("<Q", len(new_plain))
                data[12:20] = struct.pack("<Q", len(stored))
        entry.size, entry.stored = len(new_plain), len(stored)
        self._new[entry.name] = stored
        return len(stored)

    @property
    def replaced(self) -> int:
        return len(self._new)

    # ────────────────────────────────────────────────────────────── เขียน

    def build(self) -> bytes:
        """ประกอบ archive ใหม่ทั้งก้อน

        ขนาดของทุก entry เท่าเดิมเสมอ (ของใหม่ถูก pad ไว้แล้ว) จึงมีแค่
        **offset** ที่ต้องแก้ใน index — `adlr` ไม่ถูกแตะ keystream จึงยังตรง
        """
        # entry ที่ชี้ไปที่ช่วงเดียวกันใน archive ต้นฉบับ = เนื้อเดียวกันที่ถูก
        # ใช้ร่วมกัน (data.xp3 มี 13 ช่วงแบบนี้ = 26 MB) ถ้าก็อปแยกให้ทุกตัว
        # ไฟล์จะโตขึ้นฟรีๆ ทุกครั้งที่แพ็กใหม่ — ของเดิมทำแบบนั้นอยู่
        buf = bytearray(self._raw[0:HEADER])
        new_offsets, seen = [], {}
        for e in self.entries:
            if e.name in self._new:            # ตัวที่ถูกแทน = ก็อปของตัวเองเสมอ
                new_offsets.append(len(buf))   # (ห้ามให้ตัวที่ไม่ได้แทนมาใช้ร่วม)
                buf += self._new[e.name]
                continue
            key = (e.offset, e.stored)
            if key in seen:
                new_offsets.append(seen[key])
                continue
            seen[key] = len(buf)
            new_offsets.append(len(buf))
            buf += self.encrypted(e)

        blob_at = len(buf)
        buf += self._blob
        index_at = len(buf)

        prefix = bytearray(self._prefix)
        struct.pack_into("<I", prefix, prefix.find(b"sen:") + 12, blob_at)

        index = bytearray(prefix)
        for e, off in zip(self.entries, new_offsets):
            for tag, data in e.subs:
                if tag == b"segm":
                    data[4:12] = struct.pack("<Q", off)
            chunk = bytearray()
            for tag, data in e.subs:
                chunk += tag + struct.pack("<Q", len(data)) + data
            index += b"File" + struct.pack("<Q", len(chunk)) + chunk

        packed = zlib.compress(bytes(index), 6)
        buf += b"\x01" + struct.pack("<Q", len(packed)) + struct.pack("<Q", len(index))
        buf += packed
        buf[32:40] = struct.pack("<Q", index_at)
        return bytes(buf)

    def save(self, path: str):
        with open(path, "wb") as f:
            f.write(self.build())


def backup_once(path: str, suffix: str = ".orig") -> str:
    """ก็อปต้นฉบับไว้ครั้งแรกครั้งเดียว คืน path ของต้นฉบับ

    ทุกครั้งที่แพ็กใหม่ต้องอ่านจาก **ต้นฉบับ** ไม่ใช่จากผลลัพธ์รอบก่อน
    ไม่งั้น keystream จะถูกคำนวณจากไฟล์ที่ถูกแก้ไปแล้ว
    """
    import shutil
    orig = path + suffix
    if not os.path.exists(orig):
        shutil.copy(path, orig)
    return orig
