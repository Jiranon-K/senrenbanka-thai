#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
widgets.py — คอมโพเนนต์จากระบบดีไซน์ Modernist ทำเป็น Tk widget

ทุกตัวเป็น widget ของ Windows จริง ไม่มี HTML/เบราว์เซอร์เข้ามาเกี่ยว
`.btn` ในดีไซน์เป็นสี่เหลี่ยมแบนไม่มีมุมโค้ง จึงยกมาเป็น Label ที่ผูก
<Enter>/<Leave>/<Button-1> เองได้ตรงเป๊ะ และคุมสี hover/active ได้ครบทุกสถานะ
(tk.Button ของ Windows ใส่ขอบนูนของระบบมาให้ ซึ่งขัดกับดีไซน์)

การเคลื่อนไหวทุกตัวเดินผ่าน anim.py (ตัวจับเวลากลางตัวเดียว) และผูก key ไว้กับ
id ของ widget เสมอ เพื่อให้ทวีนตัวใหม่ล้มตัวเก่าทิ้ง — ไม่งั้นเมาส์กวาดเข้า-ออก
เร็วๆ จะมีทวีนสองตัวแย่งกันเขียนสีเดียวกัน แล้วสีค้างผิด
"""
from __future__ import annotations

import tkinter as tk

import anim as A
import theme as T

HOVER = 0.13          # เมาส์เข้า/ออก — สั้นพอที่จะยังรู้สึกว่าปุ่มตอบทันที
POP = 0.26            # กล่องติ๊ก


def _tint(w, option, target, dur=HOVER, ease=A.out_quad, tag="c"):
    """ไล่สีของ option หนึ่งไปหาเป้า (background / foreground)"""
    start = w.cget(option)
    if start == target:
        return
    A.tween(dur, lambda v: w.config(**{option: T.mix(start, target, v)}),
            ease=ease, key=(tag, option, id(w)))


def _blend(fg: str, bg: str, alpha: float) -> str:
    return T.mix(bg, fg, alpha)


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
        A.cancel(("c", "background", id(self)))
        # .btn:disabled { opacity: .45 } — Tk ไม่มี alpha จึงผสมสีกับพื้นเอง
        self.config(fg=fg if on else _blend(fg, bg, 0.45), bg=bg)

    def _on_enter(self, _):
        if self._enabled:
            _tint(self, "background", self._palette[2])

    def _on_leave(self, _):
        if self._enabled:
            _tint(self, "background", self._palette[1])

    def _on_press(self, _):
        # ตอนกดต้องเปลี่ยนทันที ไม่ทวีน — หน่วงตรงนี้คือความรู้สึก "ปุ่มหนืด"
        if self._enabled:
            A.cancel(("c", "background", id(self)))
            self.config(bg=self._palette[3])

    def _on_release(self, e):
        if not self._enabled:
            return
        inside = 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height()
        _tint(self, "background", self._palette[2] if inside else self._palette[1])
        if inside and self._command:
            self._command()


class WindowButton(tk.Canvas):
    """ปุ่มย่อ/ปิดบนแถบหัวที่วาดเอง — 46x44 วาดเส้นเอง ไม่ใช้ฟอนต์สัญลักษณ์

    ดีไซน์กำหนด hover ของปุ่มปิดเป็นพื้น accent + เส้นสีกระดาษ
    (ฟอนต์สัญลักษณ์ของ Windows ไม่มีบนทุกเครื่อง จึงวาดด้วย Canvas แทน)
    """

    def __init__(self, master, kind="close", command=None, danger=False, **kw):
        w, h = T.S(46), T.S(44)
        super().__init__(master, width=w, height=h, bg=T.BG,
                         highlightthickness=0, bd=0, **kw)
        self._command = command
        self._danger = danger
        self._kind = kind
        self._w2, self._h2 = w, h
        self._fg = T.TEXT
        self._draw(T.TEXT)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_click)

    def _draw(self, fg):
        self.delete("glyph")
        w, h = self._w2, self._h2
        cx, cy, r = w / 2, h / 2, T.S(6)
        t = max(1, T.S(1.4))
        if self._kind == "minimize":
            self.create_line(cx - r, cy, cx + r, cy, fill=fg, width=t, tags="glyph")
        else:
            self.create_line(cx - r, cy - r, cx + r, cy + r, fill=fg, width=t, tags="glyph")
            self.create_line(cx + r, cy - r, cx - r, cy + r, fill=fg, width=t, tags="glyph")

    def _to(self, bg, fg):
        b0, f0 = self.cget("bg"), self._fg
        if b0 == bg and f0 == fg:
            return

        def step(v):
            self.config(bg=T.mix(b0, bg, v))
            self._fg = T.mix(f0, fg, v)
            self.itemconfig("glyph", fill=self._fg)
        A.tween(HOVER, step, ease=A.out_quad, key=("wb", id(self)))

    def _on_enter(self, _):
        self._to(T.ACCENT, T.BG) if self._danger else self._to(T.HOVER_SOFT, T.TEXT)

    def _on_leave(self, _):
        self._to(T.BG, T.TEXT)

    def _on_click(self, e):
        if 0 <= e.x < self._w2 and 0 <= e.y < self._h2 and self._command:
            self._command()


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
        changed = text != self.cget("text")
        self.config(text=text)
        if changed:
            # ข้อความเปลี่ยน = ผลตรวจเปลี่ยน ไล่สีเข้าหากันแทนการกระพริบ
            _tint(self, "background", bg, dur=0.2, tag="tag")
            _tint(self, "foreground", fg, dur=0.2, tag="tag")
        else:
            self.config(fg=fg, bg=bg)


class Entry(tk.Entry):
    """.input"""

    def __init__(self, master, **kw):
        super().__init__(master, font=T.F(14), fg=T.TEXT, bg=T.SURFACE,
                         insertbackground=T.ACCENT, relief="flat",
                         highlightthickness=T.S(1), highlightbackground=T.DIVIDER,
                         highlightcolor=T.ACCENT, bd=0, **kw)


class Rule(tk.Frame):
    """ขีดหน้าชื่อขั้นในแถบซ้าย — ขั้นที่กำลังทำจะยืดออกและเปลี่ยนเป็นสี accent"""

    W = 14
    W_ON = 22

    def __init__(self, master, **kw):
        super().__init__(master, width=T.S(self.W), height=T.S(2), bg=T.DIVIDER, **kw)
        self.pack_propagate(False)
        self._px = float(T.S(self.W))

    def to(self, color, active: bool):
        c0, w0 = self.cget("bg"), self._px
        w1 = float(T.S(self.W_ON if active else self.W))
        if c0 == color and abs(w0 - w1) < 0.5:
            return

        def step(v):
            self._px = w0 + (w1 - w0) * v
            self.config(bg=T.mix(c0, color, v), width=max(1, round(self._px)))
        A.tween(0.34, step, ease=A.out_cubic, key=("rule", id(self)))


class ProgressBar(tk.Canvas):
    """แถบสูง 2px: พื้น divider, ส่วนที่เดินแล้วเป็น accent

    ค่าที่รับเข้ามาเป็นค่าจริงจาก xdelta3 ซึ่งกระโดดเป็นช่วงๆ (ทีละไฟล์)
    การไล่เข้าหาเป้าทำให้ตาอ่านทิศทางออก โดยไม่ได้โกหกว่าคืบหน้าเกินจริง —
    ปลายทางยังเป็นตัวเลขเดียวกับที่ core รายงานเสมอ
    """

    def __init__(self, master, width, on_value=None, **kw):
        super().__init__(master, width=width, height=T.S(2), bg=T.DIVIDER,
                         highlightthickness=0, bd=0, **kw)
        # ห้ามใช้ชื่อ self._w — tkinter เก็บ path ของ widget ไว้ในนั้น
        # ทับแล้วทุกคำสั่ง Tcl จะยิงไปที่ชื่อ command ผิด
        self._px = width
        self._cur = 0.0
        self._on_value = on_value
        self._fill = self.create_rectangle(0, 0, 0, T.S(2), fill=T.ACCENT, width=0)

    def _paint(self, pct):
        self._cur = pct
        self.coords(self._fill, 0, 0,
                    self._px * max(0.0, min(1.0, pct / 100.0)), T.S(2))
        if self._on_value:
            self._on_value(pct)

    def set(self, pct: float):
        a, b = self._cur, float(pct)
        if abs(b - a) < 0.05:
            return
        A.tween(0.28, lambda v: self._paint(a + (b - a) * v),
                ease=A.out_cubic, key=("bar", id(self)))

    def reset(self, pct=0.0):
        A.cancel(("bar", id(self)))
        self._paint(float(pct))

    @property
    def value(self) -> float:
        return self._cur


class CheckMark(tk.Canvas):
    """กล่องติ๊ก 15px: ขอบ accent 1.5px + เว้นขาว + ใจกลาง accent 9x9

    (ในดีไซน์คือ background:accent + box-shadow: inset 0 0 0 3px var(--color-bg))
    ตอนติ๊ก จุดกลางจะโตเลยขนาดจริงนิดนึงแล้วยุบกลับ (easing out_back)
    """

    def __init__(self, master, on=True, command=None, **kw):
        s = T.S(15)
        super().__init__(master, width=s, height=s, bg=T.BG,
                         highlightthickness=0, bd=0, **kw)
        self._s = s
        b = T.S(1.5)
        self._box = self.create_rectangle(b / 2, b / 2, s - b / 2, s - b / 2,
                                          outline=T.DIVIDER, width=b, fill=T.BG)
        self._dot = self.create_rectangle(0, 0, 0, 0, fill=T.BG, width=0)
        self._on = on
        self._t = 1.0 if on else 0.0
        self._paint(self._t)
        if command:
            self.bind("<Button-1>", lambda _e: command())

    def _paint(self, t):
        self._t = t
        s = self._s
        c = s / 2.0
        half = (s / 2.0 - T.S(3)) * max(0.0, t)
        self.itemconfig(self._box, outline=T.mix(T.DIVIDER, T.ACCENT, min(1.0, t * 1.6)))
        if half < 0.4:
            self.coords(self._dot, 0, 0, 0, 0)
            self.itemconfig(self._dot, fill=T.BG)
        else:
            self.coords(self._dot, c - half, c - half, c + half, c + half)
            self.itemconfig(self._dot, fill=T.ACCENT)

    def set(self, on: bool, animate=True):
        self._on = on
        a, b = self._t, 1.0 if on else 0.0
        if not animate:
            A.cancel(("chk", id(self)))
            return self._paint(b)
        if abs(a - b) < 0.001:
            return
        A.tween(POP, lambda v: self._paint(a + (b - a) * v),
                ease=A.out_back if on else A.out_cubic, key=("chk", id(self)))

    def pop_in(self, delay=0.0):
        """ใช้ตอนแถวรายการปรากฏขึ้นครั้งแรก"""
        b = self._t
        A.tween(POP, lambda v: self._paint(b * v), ease=A.out_back,
                delay=delay, key=("chk", id(self)))

    @property
    def checked(self) -> bool:
        return self._on


def _trim(pts, u):
    """จุดของเส้นที่ลากไปแล้ว u ส่วนของความยาวรวม (ไว้วาดเครื่องหมายถูกทีละนิด)"""
    segs = [((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
            for (x1, y1), (x2, y2) in zip(pts, pts[1:])]
    want = max(0.0, u) * sum(segs)
    out = [pts[0]]
    for (x1, y1), (x2, y2), L in zip(pts, pts[1:], segs):
        if want >= L:
            out.append((x2, y2))
            want -= L
        else:
            k = (want / L) if L else 0.0
            out.append((x1 + (x2 - x1) * k, y1 + (y2 - y1) * k))
            break
    return out


class Badge(tk.Canvas):
    """สี่เหลี่ยม 28px มีเครื่องหมายถูก (สำเร็จ) หรือกากบาท (ล้มเหลว)

    เส้นถูกลากทีละนิดเหมือนเขียนด้วยมือ — 380 ms พอให้ตาจับได้ว่ามันเพิ่งเกิดขึ้น
    """

    def __init__(self, master, **kw):
        s = T.S(28)
        super().__init__(master, width=s, height=s, bg=T.ACCENT,
                         highlightthickness=0, bd=0, **kw)
        self._s = s
        self._ok = True
        self.set_ok(True, animate=False)

    def _paint(self, u):
        self.delete("mark")
        s, w = self._s, T.S(3)
        if self._ok:
            pts = [(s * 0.24, s * 0.52), (s * 0.42, s * 0.70), (s * 0.78, s * 0.30)]
            p = _trim(pts, u)
            if len(p) > 1:
                self.create_line(*[c for xy in p for c in xy], fill=T.BG, width=w,
                                 capstyle="round", joinstyle="round", tags="mark")
        else:
            for i, pts in enumerate([[(s * 0.28, s * 0.28), (s * 0.72, s * 0.72)],
                                     [(s * 0.72, s * 0.28), (s * 0.28, s * 0.72)]]):
                # เส้นที่สองเริ่มตอนเส้นแรกไปได้ราวครึ่งทาง
                v = max(0.0, min(1.0, (u - i * 0.42) / 0.58))
                p = _trim(pts, v)
                if len(p) > 1:
                    self.create_line(*[c for xy in p for c in xy], fill=T.BG,
                                     width=w, capstyle="round", tags="mark")

    def set_ok(self, ok: bool, animate=True):
        self._ok = ok
        self.config(bg=T.ACCENT if ok else T.DANGER)
        if not animate:
            A.cancel(("badge", id(self)))
            return self._paint(1.0)
        A.tween(0.38, self._paint, ease=A.out_cubic, key=("badge", id(self)))


def label(master, text="", size=13, bold=False, fg=T.TEXT, bg=T.BG, wrap=None, **kw):
    w = tk.Label(master, text=text, font=T.F(size, bold), fg=fg, bg=bg,
                 justify="left", anchor="w",
                 wraplength=(T.S(wrap) if wrap else 0), **kw)
    w._fg0 = fg          # สีจริงของมัน — ไว้ให้อนิเมชันเปลี่ยนหน้าจอคืนค่าให้ถูก
    return w


def tint_tree(w, t: float, bg=T.BG):
    """ไล่สีตัวหนังสือทั้งกิ่ง จากสีพื้น (t=0) ไปสีจริง (t=1)

    Tk ไม่มี alpha ต่อ widget จะเฟดทั้งเฟรมตรงๆ ไม่ได้ — แต่พื้นหลังเป็นสีเดียว
    ทั้งจอ การไล่สีตัวหนังสือเข้าหาสีพื้นจึงให้ผลตาเหมือนกันเป๊ะ
    """
    if isinstance(w, tk.Label):
        base = getattr(w, "_fg0", None)
        if base:
            try:
                w.config(fg=T.mix(bg, base, t))
            except tk.TclError:
                return
    for c in w.winfo_children():
        tint_tree(c, t, bg)
