#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Target:

    file: str
    orig: str
    delta: str
    label: str
    required: bool
    r18: bool
    var: str

    @property
    def bak(self) -> str:
        return self.file + ".bak"


TARGETS = [
    Target("patch.xp3", "patch.xp3.bak", "thai-patch.xdelta",
           "บทพูด (all-ages)", required=True, r18=False, var="PATCH"),
    Target("data.xp3", "data.xp3.bak", "thai-data.xdelta",
           "ฟอนต์ + ข้อความเมนู", required=True, r18=False, var="DATA"),
    Target("adult.xp3", "adult.xp3.orig", "thai-adult.xdelta",
           "บทพูดฝั่ง R18", required=False, r18=True, var="ADULT"),
    Target("patch_extra.xp3", "patch_extra.xp3.orig", "thai-patchextra.xdelta",
           "บทพูดฝั่ง R18 (ชุดสำรอง)", required=False, r18=True, var="PEXTRA"),
]

DISABLE_ON_ALL_AGES = ["adult.xp3", "adult2.xp3"]

KEEP_ON_ALL_AGES = ["patch_extra.xp3"]


def by_file(name: str) -> Target | None:
    return next((t for t in TARGETS if t.file == name), None)


def bat_required_files() -> str:
    return " ".join(["xdelta3.exe"] + [t.delta for t in TARGETS])


def bat_hash_vars(hashes: dict) -> str:
    zero = "0" * 64
    lines = []
    for t in TARGETS:
        orig, thai = hashes.get(t.file, (zero, zero))
        lines.append('set "ORIG_%s=%s"' % (t.var, orig))
        lines.append('set "THAI_%s=%s"' % (t.var, thai))
    return "\n".join(lines)


def _restore_line(t: Target, tail: str = "") -> str:
    return ('if exist "%s" (del /q "%s" 2>nul & move /y "%s" "%s" >nul%s)'
            % (t.bak, t.file, t.bak, t.file, tail))


def bat_rollback() -> str:
    return "\n".join(_restore_line(t) for t in TARGETS)


def bat_uninstall_found() -> str:
    return "\n".join('if exist "%s" set "FOUND=1"' % t.bak for t in TARGETS)


def bat_uninstall_restore() -> str:
    note = {"adult.xp3": " ^(ฉาก R18 ยังอยู่ครบ แค่กลับเป็นภาษาเดิม^)"}
    return "\n".join(
        _restore_line(t, " & echo       - %-11s คืนแล้ว%s" % (t.file, note.get(t.file, "")))
        for t in TARGETS)


def check_bat_mentions_every_target(text: str, what: str):
    missing = [t.file for t in TARGETS if t.file not in text]
    if missing:
        raise SystemExit(
            "%s ไม่ได้พูดถึงไฟล์เหล่านี้เลย: %s\n"
            "เพิ่มลง tools/targets.py แล้วต้องเพิ่มขั้นตอนใน .bat ด้วย"
            % (what, ", ".join(missing)))
