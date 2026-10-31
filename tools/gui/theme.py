#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations


ACCENT      = "#f2802b"
ACCENT_100  = "#fff4ea"
ACCENT_300  = "#ffcaa5"
ACCENT_600  = "#dd6b17"
ACCENT_700  = "#b8530f"
ACCENT_800  = "#8d3d09"
ACCENT_TRACK = "#fce6d5"

BG          = "#ffffff"
SIDEBAR     = "#fafafa"
MUTED       = "#f4f4f5"
SURFACE     = "#ffffff"
DIVIDER     = "#e4e4e7"
TEXT        = "#09090b"

TEXT_70     = "#27272a"
TEXT_65     = "#3f3f46"
TEXT_55     = "#71717a"
TEXT_50     = "#71717a"
TEXT_45     = "#a1a1aa"
TEXT_42     = "#a1a1aa"

HOVER_SOFT  = "#f4f4f5"
HOVER_PRESS = "#e4e4e7"
HOVER_GHOST = "#f4f4f5"
TAG_NEUTRAL = "#f4f4f5"

BORDER      = "#d4d4d8"
CARD_HOVER  = "#d4d4d8"

DANGER      = "#dc2626"
DANGER_100  = "#fef2f2"
DANGER_800  = "#991b1b"


RADIUS      = 8
RADIUS_MD   = 6
RADIUS_SM   = 4


FAMILY = "Sarabun"
FAMILY_BOLD = "Sarabun SemiBold"

scale = 1.0


def init(root, win=(880, 600)) -> float:
    global scale
    try:
        dpi = root.winfo_fpixels("1i")
    except Exception:
        dpi = 96.0
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    scale = max(1.0, min(dpi / 96.0, sw * 0.9 / win[0], sh * 0.9 / win[1]))
    root.tk.call("tk", "scaling", 96.0 * scale / 72.0)
    return scale


def S(px: float) -> int:
    return max(1, round(px * scale))


def F(px: float, bold: bool = False):
    return (FAMILY_BOLD if bold else FAMILY, -S(px))


def rgb(c: str):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a: str, b: str, t: float) -> str:
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    x, y = rgb(a), rgb(b)
    return "#%02x%02x%02x" % tuple(round(x[i] + (y[i] - x[i]) * t) for i in range(3))
