#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freemote.py — PSB <-> json ผ่าน FreeMote (PsbDecompile.exe / PsBuild.exe)

เดิม `subprocess.run(..., capture_output=True)` ถูกเขียนไว้ 5 ที่ แล้ว**ทิ้ง output**
ทุกที่ จากนั้นเดาเอาว่า FreeMote เขียนไฟล์ชื่ออะไร (`.pure.scn` หรือ `.psb`)
ถ้า build ไม่ผ่าน บทนั้นก็แค่หายไปจาก pack เงียบๆ — ไม่มี error สักบรรทัด

ตอนนี้ทุกที่เรียกผ่านตัวนี้ ซึ่ง raise `FreeMoteError` (พร้อม stdout/stderr)
เมื่อ exit code ไม่ใช่ 0 หรือหาไฟล์ผลลัพธ์ไม่เจอ

    fm = freemote.default()
    js  = fm.decompile("001.ks.scn", out_dir)     # -> out_dir/001.ks.json
    scn = fm.build(js, psb_dir)                   # -> psb_dir/001.ks.scn

พฤติกรรมของ FreeMote ที่ต้องรู้ (ซ่อนไว้ในนี้ทั้งหมด)
  * PsbDecompile เขียน `<stem>.json` (+ `<stem>.resx.json`) **ข้างไฟล์ต้นทาง**
  * PsBuild เขียนลง **CWD** เป็น `<stem>.pure.scn` หรือ `<stem>.psb`

`run` รับเข้ามาได้ เทสจึงใส่ตัวปลอมแทน exe จริงได้ (ดู test_pipeline.py)
"""
from __future__ import annotations

import os
import shutil
import subprocess


class FreeMoteError(RuntimeError):
    pass


class FreeMote:
    def __init__(self, decompile_exe: str, build_exe: str, run=subprocess.run):
        self.decompile_exe = decompile_exe
        self.build_exe = build_exe
        self._run = run

    def _call(self, args: list[str], cwd: str | None = None):
        p = self._run(args, cwd=cwd, capture_output=True)
        if p.returncode != 0:
            raise FreeMoteError("%s exited %d\n%s%s" % (
                os.path.basename(args[0]), p.returncode,
                _text(p.stdout), _text(p.stderr)))
        return p

    def decompile(self, src: str, out_dir: str | None = None) -> str:
        """`<stem>.<ext>` -> `<stem>.json` (ย้ายไป out_dir ถ้าให้มา) คืน path ของ json"""
        src = os.path.abspath(src)
        stem = os.path.splitext(src)[0]
        self._call([self.decompile_exe, src])
        js = stem + ".json"
        if not os.path.exists(js):
            raise FreeMoteError("PsbDecompile wrote no json for " + src)
        if out_dir is None:
            return js
        os.makedirs(out_dir, exist_ok=True)
        for made in (js, stem + ".resx.json"):
            if os.path.exists(made):
                shutil.move(made, os.path.join(out_dir, os.path.basename(made)))
        return os.path.join(out_dir, os.path.basename(js))

    def build(self, js: str, out_dir: str, ext: str = ".scn") -> str:
        """`<stem>.json` -> `out_dir/<stem><ext>` คืน path ของไฟล์ที่ได้"""
        js = os.path.abspath(js)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.basename(js)[:-5]               # ตัด .json
        self._call([self.build_exe, js], cwd=out_dir)
        dst = os.path.join(out_dir, base + ext)
        for cand in (base + ".pure.scn", base + ".psb"):
            made = os.path.join(out_dir, cand)
            if os.path.exists(made):
                shutil.move(made, dst)
                return dst
        raise FreeMoteError("PsBuild wrote nothing for " + js)


def _text(b) -> str:
    if not b:
        return ""
    return b.decode("utf-8", "replace") if isinstance(b, bytes) else str(b)


def default() -> FreeMote:
    """ตัวจริงจาก tools/FreeMote"""
    import paths as P
    return FreeMote(P.PSB_DECOMPILE, P.PSB_BUILD)
