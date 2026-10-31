#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import tkinter as tk

import anim as A
import assets
import theme as T
import winui


class Window:

    def __init__(self, title: str, size=(880, 600), logo_px: int = 20,
                 on_close=None):
        self.design = size
        self.logo_px = logo_px
        self.on_close = on_close
        self.closing = False

        winui.dpi_aware()
        winui.taskbar_identity()
        winui.load_fonts(assets.font_files())

        self.root = tk.Tk()
        T.init(self.root, size)
        A.setup(self.root)
        self.root.attributes("-alpha", 0.0)
        self.root.title(title)
        self.root.configure(bg=T.BG)
        self.root.resizable(False, False)
        self._set_icon()
        winui.strip_caption(self.root)
        self._center()

        self._drag = None
        self._logo_img = None
        self.bg = self._bg_img = self._bg_item = None


    def _center(self):
        w, h = T.S(self.design[0]), T.S(self.design[1])
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    def fix_size(self):
        self.root.update_idletasks()
        w, h = T.S(self.design[0]), T.S(self.design[1])
        dw = self.root.winfo_width() - w
        dh = self.root.winfo_height() - h
        if dw or dh:
            self.root.geometry("%dx%d" % (w - dw, h - dh))
            self.root.update_idletasks()

    def _set_icon(self):
        ico = assets.icon_file()
        if not ico:
            return
        try:
            self.root.iconbitmap(default=ico)
        except Exception:
            pass


    def appear(self):
        A.tween(0.20, lambda v: self.root.attributes("-alpha", v),
                ease=A.out_quad, done=self._appeared, key="alpha")

    def _appeared(self):
        self.root.attributes("-alpha", 1.0)

    def close(self):
        if self.closing:
            return
        self.closing = True

        def kill():
            try:
                self.root.destroy()
            except Exception:
                pass
        if not A.enabled():
            return kill()
        winui.make_layered(self.root)
        A.tween(0.12, lambda v: self.root.attributes("-alpha", 1.0 - v),
                ease=A.out_quad, done=kill, key="alpha")
        self.root.after(320, kill)

    def shake(self):
        if not A.enabled() or not self.root.winfo_viewable():
            return
        x, y, _w, _h = winui.window_rect(self.root)
        amp = T.S(7)

        def step(v):
            winui.move_window(
                self.root, x + round(amp * (1 - v) * math.sin(v * math.pi * 6)), y)
        A.tween(0.42, step, ease=A.linear, key="shake",
                done=lambda: winui.move_window(self.root, x, y))


    def drag_from(self, *widgets):
        for w in widgets:
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)

    def _drag_start(self, e):
        x, y, _w, _h = winui.window_rect(self.root)
        self._drag = (e.x_root - x, e.y_root - y)

    def _drag_move(self, e):
        if not self._drag:
            return
        winui.move_window(self.root, e.x_root - self._drag[0],
                          e.y_root - self._drag[1])

    def _drag_end(self, _e):
        self._drag = None


    def mark(self, parent):
        self._logo_img = None
        f = assets.logo_file(T.S(self.logo_px))
        if f:
            try:
                self._logo_img = tk.PhotoImage(file=f)
            except tk.TclError:
                self._logo_img = None
        if self._logo_img is None:
            return tk.Frame(parent, bg=T.ACCENT, width=T.S(18),
                            height=T.S(18)), 18
        return tk.Label(parent, image=self._logo_img, bg=T.BG, bd=0,
                        highlightthickness=0), self.logo_px


    def backdrop(self, parent, box):
        p = assets.backdrop_file()
        if not p:
            return None
        try:
            self._bg_img = tk.PhotoImage(file=p)
        except tk.TclError:
            self._bg_img = None
            return None

        x, y, w, h = box
        cv = tk.Canvas(parent, bg=T.BG, highlightthickness=0, bd=0,
                       width=T.S(w), height=T.S(h))
        cv.place(x=T.S(x), y=T.S(y))
        self._bg_item = cv.create_image(T.S(w), T.S(h) // 2, image=self._bg_img,
                                        anchor="e")
        self.bg = cv
        self._bg_w, self._bg_h = T.S(w), T.S(h)
        self.slide_backdrop(T.S(72), 0.95, ease=A.out_expo, delay=0.18)
        return cv

    def slide_backdrop(self, dx, dur, ease=A.out_cubic, delay=0.0):
        if not self.bg:
            return
        x1, cy = self._bg_w, self._bg_h // 2

        def step(v):
            self.bg.coords(self._bg_item, x1 + dx * (1 - v), cy)
        A.tween(dur, step, ease=ease, delay=delay, key="bg")
