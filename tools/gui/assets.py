#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys

LOGO_SIZES = (20, 25, 30, 40)

FONT_FILES = ("Sarabun-Regular.ttf", "Sarabun-SemiBold.ttf",
              "Sarabun-ExtraBold.ttf")


def ui_dir() -> str:
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "ui")


def fonts_dir() -> str:
    return os.path.join(ui_dir(), "fonts")


def font_files() -> list[str]:
    return [p for p in (os.path.join(fonts_dir(), f) for f in FONT_FILES)
            if os.path.isfile(p)]


def logo_file(px: int) -> str | None:
    best, gap = None, None
    for s in LOGO_SIZES:
        f = os.path.join(ui_dir(), "logo@%d.png" % s)
        if os.path.isfile(f) and (gap is None or abs(s - px) < gap):
            best, gap = f, abs(s - px)
    return best


def icon_file() -> str | None:
    f = os.path.join(ui_dir(), "icon.ico")
    return f if os.path.isfile(f) else None


def backdrop_file() -> str | None:
    f = os.path.join(ui_dir(), "bg.png")
    return f if os.path.isfile(f) else None
