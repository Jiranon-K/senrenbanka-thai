#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import glob
import os
import struct
import zlib

HEADER = 40
_V2_MARK = 0x80


class Entry:

    __slots__ = ("name", "offset", "size", "stored", "subs")

    def __init__(self, name, offset, size, stored, subs):
        self.name = name
        self.offset = offset
        self.size = size
        self.stored = stored
        self.subs = subs

    @property
    def compressed(self) -> bool:
        return self.stored != self.size

    def __repr__(self):
        return "Entry(%r, size=%d%s)" % (
            self.name, self.size, ", compressed" if self.compressed else "")


class Archive:

    def __init__(self, raw: bytes, entries: list[Entry], prefix: bytearray,
                 blob: bytes):
        self._raw = raw
        self._prefix = prefix
        self._blob = blob
        self._new: dict[str, bytes] = {}
        self.entries = entries


    @classmethod
    def read(cls, path: str) -> "Archive":
        with open(path, "rb") as f:
            raw = f.read()
        index = cls._index_of(raw)

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
                    stored = (struct.unpack("<Q", data[20:28])[0]
                              if len(data) >= 28 else length)
            out.append(Entry(name, offset, length, stored, subs))
        return out


    def find(self, name: str) -> Entry | None:
        return next((e for e in self.entries if e.name == name), None)

    def match_by_size(self, extract_dir: str, pattern: str = "*.ks.scn") -> dict:
        by_size: dict[int, list[str]] = {}
        for p in glob.glob(os.path.join(extract_dir, pattern)):
            by_size.setdefault(os.path.getsize(p), []).append(p)
        return {e: by_size[e.size][0] for e in self.entries
                if len(by_size.get(e.size, ())) == 1}


    def encrypted(self, entry: Entry) -> bytes:
        return self._raw[entry.offset:entry.offset + entry.stored]

    def replace(self, entry: Entry, new_plain: bytes, orig_plain: bytes) -> bool:
        if entry.compressed:
            raise ValueError("%s: entry ถูกบีบอัดไว้ ยังไม่รองรับการแทนที่"
                             % entry.name)
        if len(orig_plain) != entry.stored:
            raise ValueError(
                "%s: ไบต์ต้นฉบับยาว %d แต่ช่องใน archive ยาว %d — จับคู่ผิดไฟล์"
                % (entry.name, len(orig_plain), entry.stored))
        if len(new_plain) > entry.stored:
            return False

        new_plain = new_plain + b"\x00" * (entry.stored - len(new_plain))
        ks = int.from_bytes(self.encrypted(entry), "big") ^ int.from_bytes(orig_plain, "big")
        self._new[entry.name] = (int.from_bytes(new_plain, "big") ^ ks).to_bytes(
            entry.stored, "big")
        return True

    def replace_sized(self, entry: Entry, new_plain: bytes, keystream: bytes) -> int:
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


    def build(self) -> bytes:
        buf = bytearray(self._raw[0:HEADER])
        new_offsets, seen = [], {}
        for e in self.entries:
            if e.name in self._new:
                new_offsets.append(len(buf))
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
    import shutil
    orig = path + suffix
    if not os.path.exists(orig):
        shutil.copy(path, orig)
    return orig
