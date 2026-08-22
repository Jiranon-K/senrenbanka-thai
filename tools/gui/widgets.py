#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
widgets.py — คอมโพเนนต์จากระบบดีไซน์ Modernist ทำเป็น Tk widget

ทุกตัวเป็น widget ของ Windows จริง ไม่มี HTML/เบราว์เซอร์เข้ามาเกี่ยว
`.btn` ในดีไซน์เป็นสี่เหลี่ยมแบนไม่มีมุมโค้ง จึงยกมาเป็น Label ที่ผูก
<Enter>/<Leave>/<Button-1> เองได้ตรงเป๊ะ และคุมสี hover/active ได้ครบทุกสถานะ
(tk.Button ของ Windows ใส่ขอบนูนของระบบมาให้ ซึ่งขัดกับดีไซน์)
"""
from __future__ import annotations

import tkinter as tk

import theme as T


class Button(tk.Label):
    """.btn — variant: primary | secondary | ghost"""

    STYLES = {
        # (fg,        bg,          hover_bg,       active_bg,      border)
        "primary":   (T.BG,        T.ACCENT,       T.ACCENT_600,   T.ACCENT_700,   None),
        "secondary": (T.TEXT,      T.BG,           T.HOVER_SOFT,   T.HOVER_PRESS,  T.DIVIDER),
        "ghost":     (T.ACCENT,    T.BG,           T.HOVER_GHOST,  T.HOVER_GHOST,  None),
    }

    def __init__(self, master, text="", variant="secondary", command=None, **kw):
        fg, bg, hov, act, border = self.STYLES[variant]
        self._palette = (fg, bg, hov, act)
        self._variant = variant
        self._command = command
        self._enabled = True
        padx = T.S(4) if variant == "ghost" else T.S(14)
        super().__init__(master, text=text, font=T.F(14, bold=True),
                         fg=fg, bg=bg, padx=padx, pady=T.S(8),
                         highlightthickness=T.S(1) if border else 0,
                         highlightbackground=border or bg,
                         highlightcolor=border or bg,
                         bd=0, cursor="arrow", **kw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def configure_command(self, command):
        self._command = command

    def set_enabled(self, on: bool):
        self._enabled = on
        fg, bg, _, _ = self._palette
        # .btn:disabled { opacity: .45 } — Tk ไม่มี alpha จึงผสมสีกับพื้นเอง
        self.config(fg=fg if on else _blend(fg, bg, 0.45), bg=bg)

    def _on_enter(self, _):
        if self._enabled:
            self.config(bg=self._palette[2])

    def _on_leave(self, _):
        self.config(bg=self._palette[1])

    def _on_press(self, _):
        if self._enabled:
            self.config(bg=self._palette[3])

    def _on_release(self, e):
        if not self._enabled:
            return
        self.config(bg=self._palette[2])
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        if inside and self._command:
            self._command()


def _blend(fg: str, bg: str, alpha: float) -> str:
    f = tuple(int(fg[i:i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(bg[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(f[i] * alpha + b[i] * (1 - alpha)) for i in range(3))


class Tag(tk.Label):
    """.tag — accent | neutral | danger"""

    STYLES = {
        "accent":  (T.ACCENT_800, T.ACCENT_100),
        "neutral": (T.TEXT_65,    T.TAG_NEUTRAL),
        "danger":  (T.DANGER_800, T.DANGER_100),
    }

    def __init__(self, master, text="", variant="neutral", **kw):
        fg, bg = self.STYLES[variant]
        super().__init__(master, text=text, font=T.F(11), fg=fg, bg=bg,
                         padx=T.S(10), pady=T.S(3), **kw)

    def set(self, text, variant):
        fg, bg = self.STYLES[variant]
        self.config(text=text, fg=fg, bg=bg)


class Entry(tk.Entry):
    """.input"""

    def __init__(self, master, **kw):
        super().__init__(master, font=T.F(14), fg=T.TEXT, bg=T.SURFACE,
                         insertbackground=T.ACCENT, relief="flat",
                         highlightthickness=T.S(1), highlightbackground=T.DIVIDER,
                         highlightcolor=T.ACCENT, bd=0, **kw)


class Rule(tk.Frame):
    """ขีด 14x2 หน้าชื่อขั้นในแถบซ้าย"""

    def __init__(self, master, **kw):
        super().__init__(master, width=T.S(14), height=T.S(2), bg=T.DIVIDER, **kw)
        self.pack_propagate(False)


class ProgressBar(tk.Canvas):
    """แถบสูง 2px: พื้น divider, ส่วนที่เดินแล้วเป็น accent"""

    def __init__(self, master, width, **kw):
        super().__init__(master, width=width, height=T.S(2), bg=T.DIVIDER,
                         highlightthickness=0, bd=0, **kw)
        # ห้ามใช้ชื่อ self._w — tkinter เก็บ path ของ widget ไว้ในนั้น
        # ทับแล้วทุกคำสั่ง Tcl จะยิงไปที่ชื่อ command ผิด
        self._px = width
        self._fill = self.create_rectangle(0, 0, 0, T.S(2), fill=T.ACCENT, width=0)

    def set(self, pct: float):
        self.coords(self._fill, 0, 0, self._px * max(0.0, min(1.0, pct / 100.0)), T.S(2))


class CheckMark(tk.Canvas):
    """กล่องติ๊ก 15px: ขอบ accent 1.5px + เว้นขาว + ใจกลาง accent 9x9

    (ในดีไซน์คือ background:accent + box-shadow: inset 0 0 0 3px var(--color-bg))
    """

    def __init__(self, master, on=True, **kw):
        s = T.S(15)
        super().__init__(master, width=s, height=s, bg=T.BG,
                         highlightthickness=0, bd=0, **kw)
        b = T.S(1.5)
        self._box = self.create_rectangle(b / 2, b / 2, s - b / 2, s - b / 2,
                                          outline=T.ACCENT if on else T.DIVIDER,
                                          width=b, fill=T.BG)
        self._dot = self.create_rectangle(T.S(3), T.S(3), s - T.S(3), s - T.S(3),
                                          fill=T.ACCENT if on else T.BG, width=0)


class Badge(tk.Canvas):
    """สี่เหลี่ยม 28px มีเครื่องหมายถูก (สำเร็จ) หรือกากบาท (ล้มเหลว)"""

    def __init__(self, master, **kw):
        s = T.S(28)
        super().__init__(master, width=s, height=s, bg=T.ACCENT,
                         highlightthickness=0, bd=0, **kw)
        self._s = s
        self._items = []
        self.set_ok(True)

    def set_ok(self, ok: bool):
        for i in self._items:
            self.delete(i)
        self._items.clear()
        s, w = self._s, T.S(3)
        self.config(bg=T.ACCENT if ok else T.DANGER)
        if ok:
            self._items.append(self.create_line(
                s * 0.24, s * 0.52, s * 0.42, s * 0.70, s * 0.78, s * 0.30,
                fill=T.BG, width=w, capstyle="round", joinstyle="round"))
        else:
            self._items += [
                self.create_line(s * 0.28, s * 0.28, s * 0.72, s * 0.72,
                                 fill=T.BG, width=w, capstyle="round"),
                self.create_line(s * 0.72, s * 0.28, s * 0.28, s * 0.72,
                                 fill=T.BG, width=w, capstyle="round"),
            ]


def label(master, text="", size=13, bold=False, fg=T.TEXT, bg=T.BG, wrap=None, **kw):
    return tk.Label(master, text=text, font=T.F(size, bold), fg=fg, bg=bg,
                    justify="left", anchor="w",
                    wraplength=(T.S(wrap) if wrap else 0), **kw)
