#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
window.py — เปลือกหน้าต่างแบบไม่มีแถบหัวของระบบ

แยกออกมาจาก app.py ซึ่งเป็นคลาสเดียว 800 บรรทัดที่ทำสี่เรื่องไม่เกี่ยวกัน
(เปลือกหน้าต่าง · ประกอบหน้าจอ · เดินสถานะ · เธรดกับงานจริง) เรื่องแรก
ไม่เกี่ยวกับ "การติดตั้งแพตช์" เลยสักนิด — มันจะเหมือนกันหมดไม่ว่าหน้าต่างนี้
จะเอาไปทำอะไร

ที่อยู่หลัง interface นี้: การสร้าง Tk, ตัวคูณ DPI, การถอดแถบหัวด้วย Win32,
การจัดกลางจอ, การหักขนาดกรอบที่ Tk จำไว้, ไล่ความทึบเข้า/ออก, ลากหน้าต่างเอง
ด้วย SetWindowPos, สั่นตอนล้มเหลว, โลโก้ที่เลือกไฟล์ตาม DPI และแผงภาพพื้นหลัง

ผู้เรียกเห็นแค่:

    win = Window("ชื่อ", (880, 600), on_close=...)
    win.root                      Tk root ตัวจริง
    win.appear() / win.close()
    win.shake()
    win.drag_from(widget, ...)
    win.mark(parent)              เครื่องหมายมุมบนซ้าย
    win.backdrop(parent, box)     แผงภาพด้านขวา
    win.slide_backdrop(dx, dur)
"""
from __future__ import annotations

import math
import tkinter as tk

import anim as A
import assets
import theme as T
import winui


class Window:
    """หน้าต่างที่วาดแถบหัวเอง แต่ยังเป็น top-level ปกติทุกอย่าง"""

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
        # โปร่งใสไว้ก่อน **ตั้งแต่ยังไม่ map** เพื่อไม่ให้เห็นหน้าต่างตอนที่ยัง
        # วางผังไม่เสร็จ แล้วขยับไปมาเอง (จัดกลาง / หักขนาดกรอบ) — เดิมเห็นเป็น
        # หน้าต่างเปล่ากระพริบแล้วเด้งตำแหน่ง เข้ามาค่อยไล่ความทึบขึ้นทีเดียว
        self.root.attributes("-alpha", 0.0)
        self.root.title(title)
        self.root.configure(bg=T.BG)
        self.root.resizable(False, False)
        self._set_icon()
        # ต้องถอดแถบหัวออก **ก่อน** ตั้ง geometry: Tk คิดขนาดหน้าต่างจาก
        # "พื้นที่ใน + ขนาดกรอบ" ถ้าตั้งตอนยังมีกรอบแล้วค่อยถอด หน้าต่างจะ
        # ใหญ่เกินไป 16x39 px (ขนาดกรอบเดิม)
        winui.strip_caption(self.root)
        self._center()

        self._drag = None
        self._logo_img = None
        self.bg = self._bg_img = self._bg_item = None

    # ────────────────────────────────────────────────────── ขนาด/ตำแหน่ง

    def _center(self):
        w, h = T.S(self.design[0]), T.S(self.design[1])
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    def fix_size(self):
        """บังคับให้หน้าต่างเท่าขนาดในดีไซน์เป๊ะ

        Tk จำ "ขนาดกรอบ" ไว้ตั้งแต่ตอน map หน้าต่างครั้งแรก การถอด WS_CAPTION/
        WS_THICKFRAME ทีหลังไม่ล้างค่าที่จำไว้ หน้าต่างเลยกว้างเกินมา 16 px
        วัดแล้วหักออกครั้งเดียวจบ ไม่ต้องเดาว่ากรอบของ Windows รุ่นไหนกว้างเท่าไร
        """
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
            return                    # ไม่ได้ bundle มา -> ใช้ไอคอนเริ่มต้นของ Tk
        try:
            self.root.iconbitmap(default=ico)
        except Exception:
            pass                      # ไอคอนหายไม่ใช่เหตุให้เปิดโปรแกรมไม่ได้

    # ───────────────────────────────────────────────── เข้า/ออก/สั่น

    def appear(self):
        """ไล่ความทึบ 0 -> 1 ครั้งเดียวตอนเปิด"""
        A.tween(0.20, lambda v: self.root.attributes("-alpha", v),
                ease=A.out_quad, done=self._appeared, key="alpha")

    def _appeared(self):
        self.root.attributes("-alpha", 1.0)

    def close(self):
        """จางออกแล้วค่อยปิด — กันปิดซ้ำและมีตัวกันเหนียวเผื่อทวีนสะดุด"""
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
        """สั่นซ้าย-ขวาเบาๆ ตอนล้มเหลว — บอกว่า 'หยุดตรงนี้' โดยไม่ต้องมีเสียง"""
        if not A.enabled() or not self.root.winfo_viewable():
            return
        x, y, _w, _h = winui.window_rect(self.root)
        amp = T.S(7)

        def step(v):
            winui.move_window(
                self.root, x + round(amp * (1 - v) * math.sin(v * math.pi * 6)), y)
        A.tween(0.42, step, ease=A.linear, key="shake",
                done=lambda: winui.move_window(self.root, x, y))

    # ────────────────────────────────────────────── ลากหน้าต่างจากแถบหัว
    #
    # จำ "ระยะจากมุมหน้าต่างถึงเมาส์" ตอนกด แล้วทุกเฟรมสั่งไปที่
    # (ตำแหน่งเมาส์ - ระยะนั้น) ตรงๆ ไม่สะสมค่า จึงไม่มีทางเลื่อนสะสม
    # เหตุผลที่ไม่ยกให้ Windows ลากเองอยู่ใน winui.py

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

    # ──────────────────────────────────────────── เครื่องหมายมุมบนซ้าย

    def mark(self, parent):
        """โลโก้ที่ bundle มา ถ้าไม่มีก็สี่เหลี่ยมส้มตามดีไซน์

        คืน (widget, ความสูงเป็น px ตามดีไซน์) เพื่อให้คำนวณตำแหน่งกึ่งกลาง
        แถบหัวได้ถูกทั้งสองกรณี
        """
        self._logo_img = None            # เริ่มใหม่ทุกครั้ง ไม่ใช้ของรอบก่อน
        f = assets.logo_file(T.S(self.logo_px))
        if f:
            try:
                self._logo_img = tk.PhotoImage(file=f)
            except tk.TclError:
                self._logo_img = None
        if self._logo_img is None:
            return tk.Frame(parent, bg=T.ACCENT, width=T.S(18),
                            height=T.S(18)), 18
        # ต้องถือ reference ไว้เอง — Tk เก็บแค่ตัวชี้ ภาพจะหายถ้าถูกเก็บกวาด
        return tk.Label(parent, image=self._logo_img, bg=T.BG, bd=0,
                        highlightthickness=0), self.logo_px

    # ─────────────────────────────────────────────────── แผงภาพด้านขวา

    def backdrop(self, parent, box):
        """วางภาพพื้นหลังลง canvas ของตัวเอง — box = (x, y, w, h) ตามดีไซน์

        ต้องเป็น canvas แยกที่ไม่ทับ widget ไหนเลย เพราะ Tk ไม่มีความโปร่งใส
        ระหว่าง widget วางทับข้อความเมื่อไหร่คือบังทันที

        การไล่จางถูกฝังไว้ในช่อง alpha ของ bg.png ตั้งแต่ตอน build แล้ว
        (ดู build/make_bg.py) ตรงนี้จึงเหลือแค่วางกับเลื่อน
        """
        p = assets.backdrop_file()
        if not p:
            return None                 # ไม่มีภาพก็ยังใช้งานได้ครบทุกอย่าง
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
        # เลื่อนเข้ามาจากขวาตอนเปิด ให้รู้สึกว่าแผงนี้เป็นชั้นของมันเอง
        self.slide_backdrop(T.S(72), 0.95, ease=A.out_expo, delay=0.18)
        return cv

    def slide_backdrop(self, dx, dur, ease=A.out_cubic, delay=0.0):
        if not self.bg:
            return
        x1, cy = self._bg_w, self._bg_h // 2

        def step(v):
            self.bg.coords(self._bg_item, x1 + dx * (1 - v), cy)
        A.tween(dur, step, ease=ease, delay=delay, key="bg")
