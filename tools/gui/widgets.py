#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import anim as A
import shape
import theme as T

HOVER = 0.13
POP = 0.26


def _tint(w, option, target, dur=HOVER, ease=A.out_quad, tag="c"):
    start = w.cget(option)
    if start == target:
        return
    A.tween(dur, lambda v: w.config(**{option: T.mix(start, target, v)}),
            ease=ease, key=(tag, option, id(w)))


def _blend(fg: str, bg: str, alpha: float) -> str:
    return T.mix(bg, fg, alpha)


def _canvas_kw(master) -> dict:
    return dict(bg=master.cget("bg"), highlightthickness=0, bd=0)


class _Shape(tk.Canvas):

    def __init__(self, master, text, font, fg, fill, height, padx, radius,
                 border=None, hide_empty=False):
        super().__init__(master, height=height, **_canvas_kw(master))
        self._pbg = master.cget("bg")
        self._text, self._fg, self._fill, self._border = text, fg, fill, border
        self._font = tkfont.Font(root=master, font=font)
        self._hgt, self._padx, self._radius = height, padx, radius
        self._hide_empty = hide_empty
        self._img = None
        self._bgitem = self.create_image(0, 0, anchor="nw")
        self._txt = self.create_text(0, 0, font=font, anchor="center")
        self._draw()

    def _draw(self):
        if self._hide_empty and not self._text:
            tk.Canvas.configure(self, width=0)
            self.itemconfig(self._bgitem, image="")
            self.itemconfig(self._txt, text="")
            self._img = None
            return
        w = self._font.measure(self._text) + 2 * self._padx
        h = self._hgt
        tk.Canvas.configure(self, width=w)
        self._img = shape.rrect(self, w, h, self._radius, self._fill, self._pbg, self._border)
        self.itemconfig(self._bgitem, image=self._img)
        self.coords(self._txt, w / 2, h / 2 - T.S(0.5))
        self.itemconfig(self._txt, text=self._text, fill=self._fg)

    def configure(self, cnf=None, **kw):
        if cnf:
            kw.update(cnf)
        if not kw:
            return super().configure()
        mine = False
        if "text" in kw:
            self._text, mine = kw.pop("text"), True
        for k in ("bg", "background"):
            if k in kw:
                self._fill, mine = kw.pop(k), True
        for k in ("fg", "foreground"):
            if k in kw:
                self._fg, mine = kw.pop(k), True
        if kw:
            super().configure(**kw)
        if mine:
            self._draw()

    config = configure

    def cget(self, key):
        if key == "text":
            return self._text
        if key in ("bg", "background"):
            return self._fill
        if key in ("fg", "foreground"):
            return self._fg
        return super().cget(key)

    __getitem__ = cget


class Button(_Shape):

    STYLES = {
        "primary":   (T.BG,        T.ACCENT,       T.ACCENT_600,   T.ACCENT_700,   None),
        "secondary": (T.TEXT,      T.BG,           T.HOVER_SOFT,   T.HOVER_PRESS,  T.DIVIDER),
        "ghost":     (T.TEXT,      T.BG,           T.HOVER_GHOST,  T.HOVER_PRESS,  None),
    }

    def __init__(self, master, text="", variant="secondary", command=None, **kw):
        fg, bg, hov, act, border = self.STYLES[variant]
        self._palette = (fg, bg, hov, act)
        self._border0 = border
        self._variant = variant
        self._command = command
        self._enabled = True
        if variant == "ghost":
            bg = master.cget("bg")
            self._palette = (fg, bg, hov, act)
        super().__init__(master, text, T.F(14, bold=True), fg, bg,
                         height=T.S(36), padx=T.S(16), radius=T.S(T.RADIUS_MD),
                         border=border)
        if kw:
            tk.Canvas.configure(self, **kw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_enabled(self, on: bool):
        self._enabled = on
        fg, bg, _, _ = self._palette
        A.cancel(("c", "background", id(self)))
        p = self._pbg
        self._border = (self._border0 if on or not self._border0
                        else _blend(self._border0, p, 0.5))
        self.config(fg=fg if on else _blend(fg, p, 0.5),
                    bg=bg if on else _blend(bg, p, 0.5))

    def _on_enter(self, _):
        if self._enabled:
            _tint(self, "background", self._palette[2])

    def _on_leave(self, _):
        if self._enabled:
            _tint(self, "background", self._palette[1])

    def _on_press(self, _):
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
        self._to(T.DANGER, T.BG) if self._danger else self._to(T.HOVER_SOFT, T.TEXT)

    def _on_leave(self, _):
        self._to(T.BG, T.TEXT)

    def _on_click(self, e):
        if 0 <= e.x < self._w2 and 0 <= e.y < self._h2 and self._command:
            self._command()


class Tag(_Shape):

    STYLES = {
        "accent":  (T.ACCENT_800, T.ACCENT_100),
        "neutral": (T.TEXT_65,    T.TAG_NEUTRAL),
        "danger":  (T.DANGER_800, T.DANGER_100),
    }

    def __init__(self, master, text="", variant="neutral", **kw):
        fg, bg = self.STYLES[variant]
        h = T.S(22)
        super().__init__(master, text, T.F(12, bold=True), fg, bg,
                         height=h, padx=T.S(10), radius=h / 2, hide_empty=True)
        if kw:
            tk.Canvas.configure(self, **kw)

    def set(self, text, variant):
        fg, bg = self.STYLES[variant]
        changed = text != self.cget("text")
        self.config(text=text)
        if changed:
            _tint(self, "background", bg, dur=0.2, tag="tag")
            _tint(self, "foreground", fg, dur=0.2, tag="tag")
        else:
            self.config(fg=fg, bg=bg)


class Field(tk.Canvas):

    def __init__(self, master, width: int, **entry_kw):
        h = T.S(36)
        super().__init__(master, width=width, height=h, **_canvas_kw(master))
        self._pbg = master.cget("bg")
        self._fw, self._fh = width, h
        self._ring = T.DIVIDER
        self._img = None
        self._item = self.create_image(0, 0, anchor="nw")
        self.entry = tk.Entry(self, font=T.F(14), fg=T.TEXT, bg=T.SURFACE,
                              insertbackground=T.TEXT, relief="flat",
                              highlightthickness=0, bd=0,
                              selectbackground=T.ACCENT_300, selectforeground=T.TEXT,
                              **entry_kw)
        pad = T.S(12)
        self.create_window(pad, h / 2, window=self.entry, anchor="w", width=width - 2 * pad)
        self._paint(T.DIVIDER)
        self.entry.bind("<FocusIn>", lambda _e: self._to(T.ACCENT))
        self.entry.bind("<FocusOut>", lambda _e: self._to(T.DIVIDER))
        self.bind("<Button-1>", lambda _e: self.entry.focus_set())

    def _paint(self, color):
        self._ring = color
        self._img = shape.rrect(self, self._fw, self._fh, T.S(T.RADIUS_MD),
                                T.SURFACE, self._pbg, color)
        self.itemconfig(self._item, image=self._img)

    def _to(self, color):
        c0 = self._ring
        A.tween(HOVER, lambda v: self._paint(T.mix(c0, color, v)),
                ease=A.out_quad, key=("field", id(self)))


class Rule(tk.Frame):

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

    def __init__(self, master, width, on_value=None, **kw):
        h = T.S(8)
        super().__init__(master, width=width, height=h, **_canvas_kw(master), **kw)
        self._px, self._ph = width, h
        self._cur = 0.0
        self._on_value = on_value
        pbg = master.cget("bg")
        self._track = shape.rrect(self, width, h, h / 2, T.ACCENT_TRACK, pbg)
        self._full = shape.rrect(self, width, h, h / 2, T.ACCENT, pbg)
        self._img = tk.PhotoImage(master=self, width=width, height=h)
        self.create_image(0, 0, anchor="nw", image=self._img)
        self._fill_px = -1
        self._paint(0.0)

    def _paint(self, pct):
        self._cur = pct
        fw = round(self._px * max(0.0, min(1.0, pct / 100.0)))
        if fw != self._fill_px:
            self._fill_px = fw
            self.tk.call(self._img, "copy", self._track)
            if fw > 0:
                self.tk.call(self._img, "copy", self._full,
                             "-from", 0, 0, fw, self._ph, "-to", 0, 0)
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


def _trim(pts, u):
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


CHECK = [(0.24, 0.52), (0.42, 0.70), (0.78, 0.30)]


class CheckMark(tk.Canvas):

    def __init__(self, master, on=True, command=None, **kw):
        s = T.S(16)
        super().__init__(master, width=s, height=s, **_canvas_kw(master), **kw)
        self._s = s
        self._pbg = master.cget("bg")
        self._img = None
        self._item = self.create_image(0, 0, anchor="nw")
        self._on = on
        self._t = 1.0 if on else 0.0
        self._paint(self._t)
        if command:
            self.bind("<Button-1>", lambda _e: command())

    def _paint(self, t):
        self._t = t
        s = self._s
        k = max(0.0, min(1.0, t * 1.6))
        u = max(0.0, min(1.0, (t - 0.25) / 0.75))
        lines = [_trim([(x * s, y * s) for x, y in CHECK], u)] if u > 0 else []
        self._img = shape.marked(self, s, s, T.S(T.RADIUS_SM), T.mix(T.BG, T.ACCENT, k),
                                 self._pbg, lines, T.S(2), T.BG,
                                 border=T.mix(T.BORDER, T.ACCENT, k))
        self.itemconfig(self._item, image=self._img)

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
        b = self._t
        A.tween(POP, lambda v: self._paint(b * v), ease=A.out_back,
                delay=delay, key=("chk", id(self)))


class Badge(tk.Canvas):

    def __init__(self, master, **kw):
        s = T.S(40)
        super().__init__(master, width=s, height=s, **_canvas_kw(master), **kw)
        self._s = s
        self._pbg = master.cget("bg")
        self._ok = True
        self._fill = T.ACCENT
        self._img = None
        self._item = self.create_image(0, 0, anchor="nw")
        self.set_ok(True, animate=False)

    def _paint(self, u):
        s = self._s
        if self._ok:
            lines = [_trim([(x * s, y * s) for x, y in CHECK], u)]
        else:
            lines = []
            for i, pts in enumerate([[(s * 0.33, s * 0.33), (s * 0.67, s * 0.67)],
                                     [(s * 0.67, s * 0.33), (s * 0.33, s * 0.67)]]):
                v = max(0.0, min(1.0, (u - i * 0.42) / 0.58))
                if v > 0:
                    lines.append(_trim(pts, v))
        lines = [p for p in lines if len(p) > 1]
        self._img = shape.marked(self, s, s, s / 2, self._fill, self._pbg,
                                 lines, T.S(3), T.BG)
        self.itemconfig(self._item, image=self._img)
        self.delete("mark")
        for _ in lines:
            self.create_line(0, 0, 1, 1, state="hidden", tags="mark")

    def set_ok(self, ok: bool, animate=True):
        self._ok = ok
        self._fill = T.ACCENT if ok else T.DANGER
        if not animate:
            A.cancel(("badge", id(self)))
            return self._paint(1.0)
        A.tween(0.38, self._paint, ease=A.out_cubic, key=("badge", id(self)))

    def cget(self, key):
        if key in ("bg", "background"):
            return self._fill
        return super().cget(key)

    __getitem__ = cget


class Card(tk.Canvas):

    def __init__(self, master, width: int, height: int, padx: int = 16, pady: int = 4):
        super().__init__(master, width=width, height=height, **_canvas_kw(master))
        self._pbg = master.cget("bg")
        self._cw, self._ch = width, height
        self._border = T.DIVIDER
        self._img = None
        self._item = self.create_image(0, 0, anchor="nw")
        px, py = T.S(padx), T.S(pady)
        self.body = tk.Frame(self, bg=T.BG)
        self.create_window(px, py, window=self.body, anchor="nw",
                           width=width - 2 * px, height=height - 2 * py)
        self._paint(T.DIVIDER)

    def _paint(self, color):
        self._border = color
        self._img = shape.rrect(self, self._cw, self._ch, T.S(T.RADIUS), T.BG,
                                self._pbg, color)
        self.itemconfig(self._item, image=self._img)

    def set_border(self, color, animate=True):
        if not animate:
            A.cancel(("card", id(self)))
            return self._paint(color)
        c0 = self._border
        if c0 == color:
            return
        A.tween(0.18, lambda v: self._paint(T.mix(c0, color, v)),
                ease=A.out_quad, key=("card", id(self)))

    def pointer_inside(self) -> bool:
        x, y = self.winfo_pointerxy()
        x0, y0 = self.winfo_rootx(), self.winfo_rooty()
        return x0 <= x < x0 + self.winfo_width() and y0 <= y < y0 + self.winfo_height()


def label(master, text="", size=13, bold=False, fg=T.TEXT, bg=T.BG, wrap=None, **kw):
    w = tk.Label(master, text=text, font=T.F(size, bold), fg=fg, bg=bg,
                 justify="left", anchor="w",
                 wraplength=(T.S(wrap) if wrap else 0), **kw)
    w._fg0 = fg
    return w


def tint_tree(w, t: float, bg=T.BG):
    if isinstance(w, tk.Label):
        base = getattr(w, "_fg0", None)
        if base:
            try:
                w.config(fg=T.mix(bg, base, t))
            except tk.TclError:
                return
    for c in w.winfo_children():
        tint_tree(c, t, bg)
