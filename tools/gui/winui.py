#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import ctypes.wintypes

_FR_PRIVATE = 0x10


def load_fonts(paths) -> bool:
    ok = 0
    for p in paths:
        ok += bool(ctypes.windll.gdi32.AddFontResourceExW(p, _FR_PRIVATE, 0))
    return ok > 0


def dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def taskbar_identity(app_id="Jiranon-K.SenrenBanka.ThaiPatch"):
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


GWL_STYLE = -16
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0020

_64BIT = ctypes.sizeof(ctypes.c_void_p) == 8


def _get_style(hwnd, which=GWL_STYLE) -> int:
    fn = (ctypes.windll.user32.GetWindowLongPtrW if _64BIT
          else ctypes.windll.user32.GetWindowLongW)
    return fn(hwnd, which)


def _set_style(hwnd, value, which=GWL_STYLE):
    fn = (ctypes.windll.user32.SetWindowLongPtrW if _64BIT
          else ctypes.windll.user32.SetWindowLongW)
    return fn(hwnd, which, value)


def strip_caption(root) -> bool:
    root.update_idletasks()
    try:
        hwnd = hwnd_of(root)
        _set_style(hwnd, _get_style(hwnd) & ~WS_CAPTION & ~WS_THICKFRAME)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        return True
    except Exception:
        return False


def has_caption(root) -> bool:
    try:
        return bool(_get_style(hwnd_of(root)) & WS_CAPTION)
    except Exception:
        return True


_SWP_MOVE = 0x0001 | 0x0004 | 0x0010 | 0x0400


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def hwnd_of(root) -> int:
    return int(root.wm_frame(), 16)


def window_rect(root):
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(hwnd_of(root), ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def move_window(root, x: int, y: int):
    ctypes.windll.user32.SetWindowPos(hwnd_of(root), 0, int(x), int(y), 0, 0, _SWP_MOVE)


_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000


def make_layered(root) -> bool:
    try:
        h = hwnd_of(root)
        ex = _get_style(h, _GWL_EXSTYLE)
        if not ex & _WS_EX_LAYERED:
            _set_style(h, ex | _WS_EX_LAYERED, _GWL_EXSTYLE)
        return True
    except Exception:
        return False


def is_layered(root) -> bool:
    try:
        return bool(_get_style(hwnd_of(root), _GWL_EXSTYLE) & _WS_EX_LAYERED)
    except Exception:
        return False
