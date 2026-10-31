#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

    def decompile(self, src: str, out_dir: str | None = None, raw: bool = False) -> str:
        src = os.path.abspath(src)
        stem = os.path.splitext(src)[0]
        self._call([self.decompile_exe] + (["-raw"] if raw else []) + [src])
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
        js = os.path.abspath(js)
        os.makedirs(out_dir, exist_ok=True)
        base = os.path.basename(js)[:-5]
        self._call([self.build_exe, js], cwd=out_dir)
        dst = os.path.join(out_dir, base + ext)
        for cand in (base + ".pure" + ext, base + ".pure.scn", base + ".psb"):
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
    import paths as P
    return FreeMote(P.PSB_DECOMPILE, P.PSB_BUILD)
