#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
winui.py — สิ่งที่ต้องคุยกับ Windows ตรงๆ ผ่าน ctypes

แยกออกจาก theme.py เพราะคนละเรื่องกันโดยสิ้นเชิง: theme คือโทเคนดีไซน์
(สี ฟอนต์ ระยะ) ส่วนไฟล์นี้คือปลั๊กเข้าระบบปฏิบัติการ ก่อนหน้านี้อยู่ปนกัน
ในไฟล์ชื่อ "theme.py" ซึ่งคนเปิดเข้ามาหาสีจะเจอ ctypes ของ Win32 แทน

ผลพลอยได้ที่สำคัญ: `import theme` ตอนนี้ไม่ลาก ctypes ตามมา เทส widgets
จึงรันได้โดยไม่ต้องมี Windows

ตั้งชื่อ winui ไม่ใช่ win32 เพราะ pywin32 จองชื่อ `win32` ไว้แล้ว
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes

_FR_PRIVATE = 0x10


# ─────────────────────────────────────────────────────── ฟอนต์ + DPI

def load_fonts(paths) -> bool:
    """ลงทะเบียนฟอนต์ให้เฉพาะ process นี้ ไม่ต้องติดตั้งลงเครื่องผู้เล่น"""
    ok = 0
    for p in paths:
        ok += bool(ctypes.windll.gdi32.AddFontResourceExW(p, _FR_PRIVATE, 0))
    return ok > 0


def dpi_aware():
    """ไม่งั้นบนจอ scaling 125/150% Windows จะขยายภาพให้แบบเบลอ"""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)      # per-monitor v1
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def taskbar_identity(app_id="Jiranon-K.SenrenBanka.ThaiPatch"):
    """ให้ taskbar จัดกลุ่มและใช้ไอคอนของเราเอง ไม่ใช่ไอคอน python.exe"""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


# ── ถอดแถบหัวของ Windows ออก แต่ยังเป็นหน้าต่างปกติทุกอย่าง ────────────

GWL_STYLE = -16
WS_CAPTION = 0x00C00000          # แถบหัว + ขอบ
WS_THICKFRAME = 0x00040000       # ขอบลากปรับขนาด
SWP_FLAGS = 0x0002 | 0x0001 | 0x0004 | 0x0020   # NOMOVE|NOSIZE|NOZORDER|FRAMECHANGED

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
    """เอาแถบหัวของระบบออกโดย **ไม่** ใช้ overrideredirect

    overrideredirect(True) ทำให้หน้าต่างหลุดจากการจัดการของ window manager:
    ปุ่มบน taskbar หาย Alt-Tab หาย iconify() เพี้ยน
    การถอดเฉพาะบิต WS_CAPTION/WS_THICKFRAME ทิ้งไว้แค่หน้าตา — ตัวหน้าต่าง
    ยังเป็น top-level ปกติ (taskbar / Alt-Tab / ย่อ-ขยาย ใช้ได้ครบ)
    """
    root.update_idletasks()
    try:
        hwnd = hwnd_of(root)
        _set_style(hwnd, _get_style(hwnd) & ~WS_CAPTION & ~WS_THICKFRAME)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FLAGS)
        return True
    except Exception:
        return False


def has_caption(root) -> bool:
    """ไว้ให้เทสยืนยันว่าแถบหัวถูกถอดจริง"""
    try:
        return bool(_get_style(hwnd_of(root)) & WS_CAPTION)
    except Exception:
        return True


# ─────────────────────────────────────────── ย้ายหน้าต่างด้วย Win32 ตรงๆ
#
# `wm geometry "+x+y"` ของ Tk วัดได้ **30 ms ต่อครั้ง** บนเครื่องทดสอบ
# (Tk รื้อผังหน้าต่างใหม่ทุกครั้งที่สั่ง) เท่ากับเพดาน 33 fps ขณะลาก
# เมาส์ส่ง event มา 125-1000 Hz หน้าต่างจึงตามไม่ทัน เห็นเป็นเงาลากตาม
# แล้วกระโดดตามทีเดียวเมื่อคิวระบาย — SetWindowPos ตรงๆ ใช้ 1.4 ms (เร็วกว่า 22 เท่า)

_SWP_MOVE = 0x0001 | 0x0004 | 0x0010 | 0x0400   # NOSIZE|NOZORDER|NOACTIVATE|NOOWNERZORDER


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def hwnd_of(root) -> int:
    return int(root.wm_frame(), 16)


def window_rect(root):
    """(x, y, w, h) ของจริงบนจอ — ไม่ผ่านค่าที่ Tk จำไว้ (ซึ่งเพี้ยนหลังถอดกรอบ)"""
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(hwnd_of(root), ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def move_window(root, x: int, y: int):
    ctypes.windll.user32.SetWindowPos(hwnd_of(root), 0, int(x), int(y), 0, 0, _SWP_MOVE)


# ── ทำไมไม่ยกการลากให้ Windows จัดการ (WM_NCLBUTTONDOWN/HTCAPTION) ──────
#
# นั่นเป็นวิธีมาตรฐานของโปรแกรมที่วาดแถบหัวเอง และได้ Aero Snap มาฟรี
# ลองแล้วใช้ไม่ได้กับ Tk เพราะลูปย้ายหน้าต่างของ Windows เป็น modal loop:
#
#   SendMessage  — ไม่คืนค่าจนกว่าจะลากเสร็จ เราจึงค้างอยู่ในสาย ctypes ที่
#                  ปล่อย GIL ทิ้งไว้ ระหว่างนั้นลูปยิงข้อความกลับเข้า window
#                  proc ของ Tk ซึ่งเรียก Tcl_ServiceAll() ต่อ แล้ววิ่งเข้าโค้ด
#                  Python ทั้งที่ไม่มี GIL -> ล่ามตายคาที่
#                  "Fatal Python error: PyEval_RestoreThread"
#   PostMessage  — คืนทันที GIL ปลอดภัย แต่ลูปจะเริ่มในรอบ event ถัดไป
#                  ถ้าผู้ใช้คลิกเร็วจนปล่อยปุ่มไปก่อน ลูปจะเริ่มตอนไม่มีปุ่มถูกกด
#                  แล้วสลับเป็นโหมดย้ายด้วยปุ่มลูกศร = หน้าต่างติดหนึบตามเมาส์
#                  จนกว่าจะคลิกหรือกด Esc ซึ่งแย่กว่าอาการเดิม
#
# ลากเองด้วย SetWindowPos จบง่ายกว่าและวัดได้ 0.49 ms/เฟรม (~2000 fps)
# เร็วกว่าที่เมาส์รุ่นไหนจะส่ง event ได้อยู่แล้ว ที่เสียไปคือ Aero Snap อย่างเดียว

_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000


def make_layered(root) -> bool:
    """เปิด WS_EX_LAYERED เอง ก่อนจะสั่ง -alpha

    Tk เปิดบิตนี้ให้ตอนสร้าง wrapper เท่านั้น ไม่ได้เปิดให้ใหม่ทุกครั้งที่ตั้ง
    -alpha ถ้าบิตถูกปิดไปแล้ว SetLayeredWindowAttributes จะเงียบๆ ไม่มีผล
    (วัดแล้วหน้าต่างซ้อนชั้นไม่ได้ทำให้วาดช้าลงเลย: 2.31 vs 2.30 ms/เฟรม
    จึงปล่อยให้เปิดค้างไว้ ไม่ต้องเก็บคืน)
    """
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
