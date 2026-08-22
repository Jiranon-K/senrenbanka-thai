#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — หน้าต่างติดตั้งแพตช์แปลไทย (Windows native, tkinter)

    python tools/gui/app.py
    python tools/gui/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

เป็นโปรแกรมหน้าต่างจริงๆ: widget ของ Windows ล้วน มีปุ่มบน taskbar
ไม่มีเบราว์เซอร์ ไม่มี HTTP server ไม่เปิดพอร์ต ไม่ต้องพึ่ง WebView2

หน้าตายกมาจาก Claude Design — โปรเจกต์ "Fan-translation mod installer",
ไฟล์ `Mod Installer.dc.html`, ระบบดีไซน์ **Modernist**
(โทเคนอยู่ใน theme.py, คอมโพเนนต์อยู่ใน widgets.py)

ตรรกะทั้งหมดอยู่ใน core.py — ไฟล์นี้เป็นแค่หน้าจอกับการเดินสถานะ
"""
from __future__ import annotations

import math
import os
import queue
import sys
import threading
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk                                          # noqa: E402
from tkinter import filedialog                                # noqa: E402

import anim as A                                              # noqa: E402
import core                                                   # noqa: E402
import theme as T                                             # noqa: E402
import widgets as W                                           # noqa: E402

WIN_W, WIN_H = 880, 600
STEPS = ["หาโฟลเดอร์เกม", "รายการติดตั้ง", "ติดตั้ง", "เสร็จสิ้น"]
CONTENT_W = 420          # max-width ของคอลัมน์เนื้อหาในไฟล์ดีไซน์
STEP_OF = {"locate": 0, "components": 1, "working": 2, "done": 3, "error": 3}

# แผงภาพด้านขวา — กินพื้นที่ที่ว่างอยู่แล้วพอดี ไม่ทับอะไรเลย:
#   แนวนอน  เริ่มที่ 212 (แถบซ้าย) + 30 (ระยะขอบ) + 420 (คอลัมน์เนื้อหา) = 662
#   แนวตั้ง  ใต้แถบหัว (44) ถึงเหนือแถวปุ่ม (600 - 74 = 526)
# ตัวภาพ bg.png กว้าง 280 แต่ 24% ทางซ้ายใสสนิท จึงวางชิดขวาแล้วให้ส่วนที่
# เกินออกไปทางซ้ายถูก canvas ตัดทิ้ง — ขอบซ้ายที่เห็นจึงจางเป็นศูนย์พอดี
LOGO_PX = 20             # เครื่องหมายมุมบนซ้าย (ดีไซน์เดิมเป็นสี่เหลี่ยม 18 px)
BG_X, BG_Y = 662, 44
BG_W, BG_H = 880 - 662, 600 - 74 - 44

# ปุ่มท้ายจอเปลี่ยนความหมายตามหน้า — ตารางเดียวจบ อ่านง่ายกว่ากระจาย if
FOOTER = {
    "locate":     ("ถัดไป",   "ปิด",     "",                        False),
    "components": ("ติดตั้ง", "ปิด",     "",                        True),
    "working":    ("",        "ยกเลิก", "ปิดเกมไว้ระหว่างติดตั้ง", False),
    "done":       ("เปิดเกม", "ปิด",     "",                        False),
    "error":      ("ลองใหม่", "ปิด",     "",                        False),
}


# บอกให้ครบว่า "ใครทำ" กับ "ไม่ใช่ของใคร" ในบรรทัดเดียว โดยไม่ใส่ชื่อคนแปล
CREDIT = "งานแปลโดยแฟนเกม · ไม่ใช่ฉบับทางการ"


def mb(n: int) -> str:
    if not n:
        return ""
    m = n / 1048576
    return "%.1f GB" % (m / 1024) if m >= 1024 else "%d MB" % round(m)


class Installer:
    def __init__(self):
        T.dpi_aware()
        T.taskbar_identity()
        T.load_fonts()

        self.root = tk.Tk()
        T.init(self.root, (WIN_W, WIN_H))
        A.setup(self.root)
        # โปร่งใสไว้ก่อน **ตั้งแต่ยังไม่ map** เพื่อไม่ให้เห็นหน้าต่างตอนที่ยัง
        # วางผังไม่เสร็จ แล้วขยับไปมาเอง (_center / _fix_size) — เดิมเห็นเป็น
        # หน้าต่างเปล่ากระพริบแล้วเด้งตำแหน่ง เข้ามาค่อยไล่ความทึบขึ้นทีเดียว
        self.root.attributes("-alpha", 0.0)
        self.root.title("Senren Banka — แพตช์แปลไทย")
        self.root.configure(bg=T.BG)
        self.root.resizable(False, False)
        self._set_icon()
        # ต้องถอดแถบหัวออก **ก่อน** ตั้ง geometry: Tk คิดขนาดหน้าต่างจาก
        # "พื้นที่ใน + ขนาดกรอบ" ถ้าตั้งตอนยังมีกรอบแล้วค่อยถอด หน้าต่างจะ
        # ใหญ่เกินไป 16x39 px (ขนาดกรอบเดิม)
        T.strip_caption(self.root)
        self._center(T.S(WIN_W), T.S(WIN_H))

        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.plan: core.Plan | None = None
        self.info: dict | None = None
        self.screen = None         # ยังไม่มีหน้าไหนถูกแสดง -> หน้าแรกได้อนิเมชันด้วย
        self.job: str | None = None
        self.busy = False
        self.installed = False
        self.r18_locked = False    # adult.xp3 เป็น build ที่ไม่รองรับ -> ลงได้แค่ all-ages
        self.w_r18_row = None
        self._debounce = None
        self._drag = None
        self._closing = False

        self._build()
        self._fix_size()
        self.root.after(40, self._pump)
        self.root.after(0, self.boot)
        self.root.after(1, self._appear)

    # ------------------------------------------------------------ พื้นฐาน
    def _center(self, w, h):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry("%dx%d+%d+%d" % (w, h, (sw - w) // 2, (sh - h) // 3))

    def _fix_size(self):
        """บังคับให้หน้าต่างเท่าขนาดในดีไซน์เป๊ะ

        Tk จำ "ขนาดกรอบ" ไว้ตั้งแต่ตอน map หน้าต่างครั้งแรก การถอด WS_CAPTION/
        WS_THICKFRAME ทีหลังไม่ล้างค่าที่จำไว้ หน้าต่างเลยกว้างเกินมา 16 px
        วัดแล้วหักออกครั้งเดียวจบ ไม่ต้องเดาว่ากรอบของ Windows รุ่นไหนกว้างเท่าไร
        """
        self.root.update_idletasks()
        dw = self.root.winfo_width() - T.S(WIN_W)
        dh = self.root.winfo_height() - T.S(WIN_H)
        if dw or dh:
            self.root.geometry("%dx%d" % (T.S(WIN_W) - dw, T.S(WIN_H) - dh))
            self.root.update_idletasks()

    # ------------------------------------------------- เข้า/ออกของหน้าต่าง
    def _appear(self):
        """ไล่ความทึบ 0 -> 1 ครั้งเดียวตอนเปิด"""
        A.tween(0.20, lambda v: self.root.attributes("-alpha", v),
                ease=A.out_quad, done=self._appeared, key="alpha")

    def _appeared(self):
        self.root.attributes("-alpha", 1.0)

    def _bye(self):
        """จางออกแล้วค่อยปิด — กันปิดซ้ำและมีตัวกันเหนียวเผื่อทวีนสะดุด"""
        if self._closing:
            return
        self._closing = True

        def kill():
            try:
                self.root.destroy()
            except Exception:
                pass
        if not A.enabled():
            return kill()
        T.make_layered(self.root)
        A.tween(0.12, lambda v: self.root.attributes("-alpha", 1.0 - v),
                ease=A.out_quad, done=kill, key="alpha")
        self.root.after(320, kill)

    def _shake(self):
        """สั่นซ้าย-ขวาเบาๆ ตอนล้มเหลว — บอกว่า 'หยุดตรงนี้' โดยไม่ต้องมีเสียง"""
        if not A.enabled() or not self.root.winfo_viewable():
            return
        x, y, _w, _h = T.window_rect(self.root)
        amp = T.S(7)

        def step(v):
            T.move_window(self.root, x + round(amp * (1 - v) * math.sin(v * math.pi * 6)), y)
        A.tween(0.42, step, ease=A.linear, key="shake",
                done=lambda: T.move_window(self.root, x, y))

    def _set_icon(self):
        try:
            self.root.iconbitmap(default=T.icon_file())
        except Exception:
            pass                      # ไอคอนหายไม่ใช่เหตุให้เปิดโปรแกรมไม่ได้

    def _pump(self):
        """งานจาก worker thread เข้ามาทาง queue — Tk แตะได้จาก thread เดียวเท่านั้น"""
        while True:
            try:
                fn = self.q.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                self.fail("เกิดข้อผิดพลาดในหน้าจอ", "", traceback.format_exc())
        self.root.after(40, self._pump)

    def post(self, fn):
        self.q.put(fn)

    def work(self, fn):
        """รันงานหนักบน thread แยก ไม่ให้หน้าต่างค้าง"""
        def wrap():
            try:
                fn()
            except core.Aborted:
                self.post(self.on_cancelled)
            except Exception as e:
                detail = traceback.format_exc()
                self.post(lambda: self.fail(
                    "ทำงานไม่สำเร็จ",
                    "%s — ไฟล์ต้นฉบับถูกคืนกลับให้แล้ว เกมยังเล่นได้ปกติ" % e, detail))
            finally:
                self.busy = False
        self.busy = True
        threading.Thread(target=wrap, daemon=True).start()

    # ------------------------------------------------------------ โครงจอ
    def _build(self):
        # กรอบ 1px รอบหน้าต่าง — ในดีไซน์คือ border: 1px solid rgba(43,33,27,.35)
        # จำเป็นเมื่อไม่มีแถบหัวของระบบ ไม่งั้นหน้าต่างจะกลืนกับพื้นหลังสีขาว
        r = tk.Frame(self.root, bg=T.BG, highlightthickness=1,
                     highlightbackground=T.BORDER, highlightcolor=T.BORDER)
        r.pack(fill="both", expand=True)
        self.shell = r
        r.grid_rowconfigure(1, weight=1)
        r.grid_columnconfigure(0, weight=1)

        # ── แถบหัวที่วาดเอง: เครื่องหมาย + ชื่อ + เวอร์ชัน + ย่อ/ปิด
        head = tk.Frame(r, bg=T.BG, height=T.S(44))
        head.grid(row=0, column=0, sticky="ew")
        head.grid_propagate(False)
        mark, side = self._make_mark(head)
        self._mark = mark
        mark.place(x=T.S(14), y=T.S((44 - side) // 2))
        title = W.label(head, "Senren Banka — แพตช์แปลไทย", 13, bold=True)
        title.place(x=T.S(42), y=T.S(12))
        self.w_version = W.label(head, "", 12, fg=T.TEXT_55)
        head.update_idletasks()
        self.w_version.place(x=T.S(42) + title.winfo_reqwidth() + T.S(8), y=T.S(13))

        wb = tk.Frame(head, bg=T.BG)
        wb.place(relx=1.0, x=0, y=0, anchor="ne", relheight=1.0)
        self.b_min = W.WindowButton(wb, "minimize", self.root.iconify)
        self.b_close = W.WindowButton(wb, "close", self.on_cancel, danger=True)
        self.b_min.pack(side="left")
        self.b_close.pack(side="left")

        # ลากหน้าต่างจากแถบหัว (เว้นปุ่ม) เหมือนแถบหัวของระบบ
        for w in (head, mark, title, self.w_version):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)

        body = tk.Frame(r, bg=T.BG)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── แถบซ้าย: 4 ขั้น + เครดิต
        rail = tk.Frame(body, bg=T.BG, width=T.S(212))
        rail.grid(row=0, column=0, sticky="nsw")
        rail.grid_propagate(False)
        self.w_steps = []
        for i, name in enumerate(STEPS):
            row = tk.Frame(rail, bg=T.BG)
            row.place(x=T.S(26), y=T.S(26 + i * 28))
            rule = W.Rule(row)
            rule.pack(side="left")
            lab = W.label(row, name, 13, fg=T.TEXT_42)
            lab.pack(side="left", padx=(T.S(12), 0))
            self.w_steps.append((rule, lab))

        main = tk.Frame(body, bg=T.BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=1)
        main.grid_columnconfigure(0, weight=1)

        content = tk.Frame(main, bg=T.BG)
        content.grid(row=0, column=0, sticky="nsew", padx=(T.S(30), T.S(30)),
                     pady=(T.S(26), 0))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self.screens = {
            "locate": self._screen_locate(content),
            "components": self._screen_components(content),
            "working": self._screen_working(content),
            "done": self._screen_done(content),
            "error": self._screen_error(content),
        }
        # ใช้ place ไม่ใช่ grid: อนิเมชันเลื่อนขึ้นตอนเปลี่ยนหน้าขยับแค่ลูกตัวเอง
        # ถ้าใช้ grid แล้วขยับ pady ทุกเฟรม Tk จะคำนวณผังทั้งหน้าต่างใหม่ทุกเฟรม
        for f in self.screens.values():
            f.place(x=0, y=0, relwidth=1.0, relheight=1.0)
            f.place_forget()

        # ── ท้ายจอ
        foot = tk.Frame(main, bg=T.BG, height=T.S(74))
        foot.grid(row=1, column=0, sticky="ew")
        foot.grid_propagate(False)
        self.w_note = W.label(foot, "", 12, fg=T.TEXT_55)
        self.w_note.place(x=T.S(30), rely=0.5, anchor="w")

        acts = tk.Frame(foot, bg=T.BG)
        acts.place(relx=1.0, x=-T.S(30), rely=0.5, anchor="e")
        self.b_back = W.Button(acts, "ย้อนกลับ", "ghost", self.on_back)
        self.b_cancel = W.Button(acts, "ปิด", "secondary", self.on_cancel)
        self.b_primary = W.Button(acts, "ถัดไป", "primary", self.on_primary)
        self.b_back.pack(side="left", padx=(0, T.S(8)))
        self.b_cancel.pack(side="left", padx=(0, T.S(8)))
        self.b_primary.pack(side="left")

        # เครดิตอยู่ล่างสุดของหน้าต่าง ไม่ใช่ลอยกลางแถบซ้าย — มันเป็นข้อความกำกับ
        # ไม่ใช่เนื้อหา จึงควรพ้นทางสายตาที่กำลังไล่อ่านขั้นตอนอยู่
        # วางบน body ไม่ใช่ใน rail: rail กว้างตายตัว 212 px ถ้าเครื่องไหน
        # เรนเดอร์ฟอนต์กว้างกว่านี้ ข้อความจะโดนตัดหาย
        self.w_credit = W.label(body, CREDIT, 11, fg=T.TEXT_45)
        self.w_credit.place(x=T.S(26), rely=1.0, y=-T.S(16), anchor="sw")

        self._build_backdrop(r)

        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.root.bind("<Escape>", lambda _e: self.on_cancel())

    def _make_mark(self, head):
        """เครื่องหมายมุมบนซ้าย — โลโก้ที่ bundle มา ถ้าไม่มีก็สี่เหลี่ยมส้มตามดีไซน์

        คืน (widget, ความสูงเป็น px ตามดีไซน์) เพื่อให้คำนวณตำแหน่งกึ่งกลาง
        แถบหัวได้ถูกทั้งสองกรณี
        """
        self._logo_img = None
        f = T.logo_file(T.S(LOGO_PX))
        if f:
            try:
                self._logo_img = tk.PhotoImage(file=f)
            except tk.TclError:
                self._logo_img = None
        if self._logo_img is None:
            return tk.Frame(head, bg=T.ACCENT, width=T.S(18), height=T.S(18)), 18
        return tk.Label(head, image=self._logo_img, bg=T.BG, bd=0,
                        highlightthickness=0), LOGO_PX

    # ------------------------------------------------------- แผงภาพด้านขวา
    def _build_backdrop(self, parent):
        """ภาพประกอบแบบกระจกฝ้า ไล่จางหายไปทางคอลัมน์เนื้อหา

        สร้างเป็นลูกตัวสุดท้ายของ shell จึงอยู่บนสุด — มันทับเฉพาะพื้นที่ว่าง
        ทางขวาของคอลัมน์เนื้อหา ไม่มี widget ตัวไหนอยู่ตรงนั้น
        (Tk ไม่มีความโปร่งใสระหว่าง widget วางทับข้อความเมื่อไหร่คือบังทันที)

        การไล่จางถูกฝังไว้ในช่อง alpha ของ bg.png ตั้งแต่ตอน build แล้ว
        (ดู make_bg.py) ตรงนี้จึงเหลือแค่วางกับเลื่อน
        """
        self.bg = self._bg_img = self._bg_item = None
        p = os.path.join(T.ui_dir(), "bg.png")
        if not os.path.isfile(p):
            return                      # ไม่มีภาพก็ยังใช้งานได้ครบทุกอย่าง
        try:
            self._bg_img = tk.PhotoImage(file=p)
        except tk.TclError:
            self._bg_img = None
            return
        cv = tk.Canvas(parent, bg=T.BG, highlightthickness=0, bd=0,
                       width=T.S(BG_W), height=T.S(BG_H))
        cv.place(x=T.S(BG_X), y=T.S(BG_Y))
        # ชิดขวาและกึ่งกลางแนวตั้ง: จอ DPI สูงทำให้ canvas ใหญ่กว่าภาพ ช่องว่าง
        # ที่เหลือจะอยู่ด้านซ้าย/บน/ล่าง ซึ่งเป็นด้านที่ภาพจางเป็นศูนย์อยู่แล้ว
        self._bg_item = cv.create_image(T.S(BG_W), T.S(BG_H) // 2,
                                        image=self._bg_img, anchor="e")
        self.bg = cv
        self.slide_backdrop(T.S(72), 0.95, ease=A.out_expo, delay=0.18)

    def slide_backdrop(self, dx, dur, ease=A.out_cubic, delay=0.0):
        """เลื่อนภาพเข้าที่ — ขอบไล่จางกวาดผ่านทำให้ดูเหมือนกระจกเลื่อน"""
        if not self.bg:
            return
        x1, cy = T.S(BG_W), T.S(BG_H) // 2

        def step(v):
            self.bg.coords(self._bg_item, x1 + dx * (1 - v), cy)
        A.tween(dur, step, ease=ease, delay=delay, key="bg")

    # ------------------------------------------------- ลากหน้าต่างจากแถบหัว
    #
    # เดิมใช้ root.geometry("+x+y") ต่อหนึ่ง <B1-Motion> ซึ่งวัดได้ 30 ms ต่อครั้ง
    # (Tk รื้อผังหน้าต่างใหม่ทุกครั้งที่สั่ง) = เพดาน 33 fps ขณะที่เมาส์ส่ง event
    # มา 125-1000 Hz หน้าต่างจึงตามหลังเคอร์เซอร์เป็นเงา แล้วกระโดดตามทีเดียว
    # ตอนคิวระบาย — คือ "เห็น ghost แล้วแอปวาป" พอดี
    #
    # ทางแก้คือขยับหน้าต่างด้วย SetWindowPos ตรงๆ ซึ่งวัดได้ 0.49 ms/เฟรม
    # (~2000 fps) เร็วกว่าเดิม 60 เท่า และเร็วกว่าที่เมาส์จะส่ง event ทัน
    # ส่วนวิธี "ยกให้ Windows ลากเอง" ใช้กับ Tk ไม่ได้ — เหตุผลอยู่ใน theme.py

    def _drag_start(self, e):
        x, y, _w, _h = T.window_rect(self.root)
        self._drag = (e.x_root - x, e.y_root - y)

    def _drag_move(self, e):
        if not self._drag:
            return
        T.move_window(self.root, e.x_root - self._drag[0], e.y_root - self._drag[1])

    def _drag_end(self, _e):
        self._drag = None

    # ------------------------------------------------------------- แต่ละหน้า
    def _screen_locate(self, parent):
        f = tk.Frame(parent, bg=T.BG)
        W.label(f, "เลือกโฟลเดอร์เกม", 20, bold=True).pack(anchor="w")
        self.w_locate_sub = W.label(f, "กำลังค้นหา…", 13, fg=T.TEXT_55, wrap=CONTENT_W)
        self.w_locate_sub.pack(anchor="w", pady=(T.S(6), T.S(22)))

        W.label(f, "โฟลเดอร์เกม", 12, fg=T.TEXT_70).pack(anchor="w", pady=(0, T.S(5)))
        row = tk.Frame(f, bg=T.BG)
        row.pack(anchor="w", fill="x")
        self.var_path = tk.StringVar()
        self.var_path.trace_add("write", self._on_path_typed)
        self.w_path = W.Entry(row, textvariable=self.var_path, width=38)
        self.w_path.pack(side="left", ipady=T.S(6))
        W.Button(row, "เลือก…", "secondary", self.on_browse).pack(
            side="left", padx=(T.S(8), 0))

        note = tk.Frame(f, bg=T.BG)
        note.pack(anchor="w", pady=(T.S(18), 0))
        self.w_tag = W.Tag(note, "", "neutral")
        self.w_tag.pack(side="left")
        self.w_note_detail = W.label(note, "", 13, fg=T.TEXT_55)
        self.w_note_detail.pack(side="left", padx=(T.S(8), 0))
        return f

    def _screen_components(self, parent):
        f = tk.Frame(parent, bg=T.BG)
        W.label(f, "สิ่งที่จะติดตั้ง", 20, bold=True).pack(anchor="w")
        W.label(f, "ไฟล์ต้นฉบับถูกสำรองเป็น .bak ก่อนแปะ ถอดคืนได้ทุกเมื่อ",
                13, fg=T.TEXT_55, wrap=CONTENT_W).pack(anchor="w", pady=(T.S(6), T.S(18)))
        self.w_comps = tk.Frame(f, bg=T.BG)
        self.w_comps.pack(anchor="w", fill="x")
        self.w_comps_foot = W.label(f, "", 12, fg=T.TEXT_55, wrap=CONTENT_W)
        self.w_comps_foot.pack(anchor="w", pady=(T.S(18), 0))
        return f

    def _screen_working(self, parent):
        f = tk.Frame(parent, bg=T.BG)
        self.w_working_title = W.label(f, "กำลังติดตั้ง", 20, bold=True)
        self.w_working_title.pack(anchor="w")
        self.w_stage = W.label(f, "", 13, fg=T.TEXT_55, wrap=CONTENT_W)
        self.w_stage.pack(anchor="w", pady=(T.S(6), T.S(30)))
        self.w_pct = W.label(f, "0%", 38, bold=True)
        self.w_pct.pack(anchor="w", pady=(0, T.S(12)))
        # ตัวเลขเดินตามแถบเสมอ (แถบเป็นเจ้าของค่า) จะได้ไม่มีทางขัดกันเอง
        self.w_bar = W.ProgressBar(f, width=T.S(420), on_value=self._show_pct)
        self.w_bar.pack(anchor="w")
        return f

    def _show_pct(self, v):
        self.w_pct.config(text="%d%%" % round(v))

    def _screen_done(self, parent):
        f = tk.Frame(parent, bg=T.BG)
        self.w_done_badge = W.Badge(f)
        self.w_done_badge.pack(anchor="w", pady=(0, T.S(16)))
        self.w_done_title = W.label(f, "", 20, bold=True)
        self.w_done_title.pack(anchor="w")
        self.w_done_sub = W.label(f, "", 13, fg=T.TEXT_55, wrap=CONTENT_W)
        self.w_done_sub.pack(anchor="w", pady=(T.S(6), 0))
        return f

    def _screen_error(self, parent):
        f = tk.Frame(parent, bg=T.BG)
        b = W.Badge(f)
        b.set_ok(False)
        b.pack(anchor="w", pady=(0, T.S(16)))
        self.w_err_title = W.label(f, "", 20, bold=True)
        self.w_err_title.pack(anchor="w")
        self.w_err_sub = W.label(f, "", 13, fg=T.TEXT_55, wrap=CONTENT_W)
        self.w_err_sub.pack(anchor="w", pady=(T.S(6), 0))
        # กล่อง traceback: 420x132 ตามดีไซน์ (max-height:132px) ไม่ยืดเต็มจอ
        self.w_err_box = tk.Frame(f, bg=T.BG, width=T.S(CONTENT_W), height=T.S(132))
        self.w_err_box.pack_propagate(False)
        self.w_err_detail = tk.Text(self.w_err_box, font=T.F(11.5), fg=T.TEXT_55,
                                    bg=T.SURFACE, relief="flat", wrap="word",
                                    highlightthickness=T.S(1),
                                    highlightbackground=T.DIVIDER, bd=0,
                                    padx=T.S(10), pady=T.S(8))
        self.w_err_detail.pack(fill="both", expand=True)
        return f

    # ------------------------------------------------------------ เดินสถานะ
    def show(self, screen):
        first = self.screen != screen
        self.screen = screen
        for k, f in self.screens.items():
            if k != screen:
                f.place_forget()
        f = self.screens[screen]
        f.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        if first:
            self._enter(f)
            self.slide_backdrop(T.S(14), 0.55)      # ขยับตามนิดหน่อย ให้รู้สึกเป็นชั้นเดียวกัน

        idx = STEP_OF[screen]
        for i, (rule, lab) in enumerate(self.w_steps):
            rule.to(T.ACCENT if i == idx else T.ACCENT_300 if i < idx else T.DIVIDER,
                    active=(i == idx))
            fg = T.TEXT if i == idx else T.TEXT_42
            lab._fg0 = fg
            lab.config(font=T.F(13, bold=(i == idx)))
            W._tint(lab, "foreground", fg, dur=0.28, ease=A.out_cubic, tag="step")
        self._render_footer()

    def _enter(self, f):
        """หน้าใหม่เลื่อนขึ้น 14px พร้อมไล่สีตัวหนังสือขึ้นมาจากพื้น"""
        rise = T.S(14)

        def step(v):
            f.place_configure(y=round(rise * (1 - v)))
            W.tint_tree(f, v)
        A.tween(0.30, step, ease=A.out_cubic, key="screen")

    def _render_footer(self):
        primary, cancel, note, back = FOOTER[self.screen]
        if self.screen == "working":
            primary = "กำลังตรวจ…" if self.job == "verify" else "กำลังติดตั้ง…"
        self.b_primary.config(text=primary)
        self.b_primary.set_enabled(not self.busy)
        self.b_cancel.config(text=cancel)
        self.w_note.config(text=note)

        show_back = back
        if self.screen == "done" and self.installed:
            show_back, label = True, "ถอดแพตช์"       # ดีไซน์มีปุ่ม ghost ช่องนี้อยู่แล้ว
        else:
            label = "ย้อนกลับ"
        self.b_back.config(text=label)
        if show_back:
            self.b_back.pack(side="left", padx=(0, T.S(8)), before=self.b_cancel)
        else:
            self.b_back.pack_forget()

    def progress(self, pct, stage=None, jump=False):
        self.w_bar.reset(pct) if jump else self.w_bar.set(pct)
        if stage is not None:
            self.w_stage.config(text=stage)

    def stage_text(self, s: str) -> str:
        if s == "stage.backup":
            return "สำรองไฟล์ต้นฉบับ"
        if s == "stage.done":
            return "เสร็จสิ้น"
        if s.startswith("stage.apply:"):
            f = s[12:]
            t = next((t for t in (self.plan.targets if self.plan else []) if t.name == f), None)
            return "แปะแพตช์ %s%s" % (f, " — " + t.label if t else "")
        if s.startswith("stage.disable:"):
            return "ปิด " + s[14:] + " (เปลี่ยนชื่อเป็น .off)"
        if s.startswith("stage.restore:"):
            return "คืนไฟล์ต้นฉบับ " + s[14:]
        return s

    def fail(self, title, sub, detail=""):
        self.busy = False
        self.job = None
        self.w_err_title.config(text=title)
        self.w_err_sub.config(text=sub)
        if detail:
            self.w_err_detail.config(state="normal")
            self.w_err_detail.delete("1.0", "end")
            self.w_err_detail.insert("1.0", detail.strip())
            self.w_err_detail.config(state="disabled")
            self.w_err_box.pack(anchor="w", pady=(T.S(14), 0))
        else:
            self.w_err_box.pack_forget()
        self.show("error")
        self._shake()

    def goto_done(self, installed, title, sub):
        self.busy = False
        self.job = None
        self.installed = installed
        self.w_done_badge.set_ok(True)
        self.w_done_title.config(text=title)
        self.w_done_sub.config(text=sub)
        self.show("done")

    def on_cancelled(self):
        self.busy = False
        self.job = None
        self.show("locate")
        self.refresh_detect()

    # ------------------------------------------------------------- ขั้นที่ 1
    def boot(self):
        try:
            self.info = {"mf": core.load_manifest(), "dirs": core.find_game_dirs()}
        except FileNotFoundError:
            return self.fail("ไม่พบ manifest.json",
                             "ตัวติดตั้งต้องอยู่โฟลเดอร์เดียวกับ manifest.json, "
                             "xdelta3.exe และไฟล์ .xdelta — แตกไฟล์ zip ให้ครบทุกไฟล์")
        self.w_version.config(text="v" + self.info["mf"]["version"])
        dirs = self.info["dirs"]
        if dirs:
            self.var_path.set(dirs[0])
            self.w_path.xview_moveto(1.0)      # path ยาวกว่าช่อง — โชว์หางไว้
            self.w_locate_sub.config(
                text="พบเกม 1 ชุด ยืนยันโฟลเดอร์เพื่อไปต่อ" if len(dirs) == 1
                else "พบเกม %d ชุด เลือกชุดที่ต้องการ" % len(dirs))
        else:
            self.w_locate_sub.config(
                text="หาโฟลเดอร์เกมอัตโนมัติไม่เจอ — กด “เลือก…” "
                     "แล้วชี้ไปที่โฟลเดอร์ที่มี SenrenBanka.exe")
        self.refresh_detect()
        self.show("locate")

    def _on_path_typed(self, *_):
        if self._debounce:
            self.root.after_cancel(self._debounce)
        self._debounce = self.root.after(350, self.refresh_detect)

    def refresh_detect(self):
        d = self.var_path.get().strip()
        if not d:
            self.plan = None
            self.w_tag.set("", "neutral")
            self.w_note_detail.config(text="")
            return
        try:
            self.plan = core.Plan(d)
        except FileNotFoundError:
            self.plan = None
            self.w_tag.set("อ่าน manifest.json ไม่ได้", "danger")
            self.w_note_detail.config(text="")
            return

        p = self.plan
        if p.missing_game_files():
            self.w_tag.set("ไม่ใช่โฟลเดอร์เกม", "danger")
            self.w_note_detail.config(text="ไม่พบ " + ", ".join(p.missing_game_files()))
        elif p.missing_pieces():
            self.w_tag.set("ชุดติดตั้งไม่ครบ", "danger")
            self.w_note_detail.config(text="ขาด " + ", ".join(p.missing_pieces()))
        else:
            r18 = p.mode == "R18"
            self.w_tag.set("พบแพตช์ R18" if r18 else "Steam ล้วน",
                           "accent" if r18 else "neutral")
            self.w_note_detail.config(
                text="ติดตั้งแพตช์ไทยไว้แล้ว" if p.has_backups
                else "พื้นที่ว่าง %.1f GB" % (core.free_space(p.game) / 2 ** 30))

    def on_browse(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์เกม Senren Banka",
                                    mustexist=True, parent=self.root)
        if d:
            self.var_path.set(os.path.normpath(d))
            self.w_path.xview_moveto(1.0)
            self.refresh_detect()

    # ------------------------------------------------------------ ตรวจ/ติดตั้ง
    def begin_verify(self):
        self.job = "verify"
        self.cancel.clear()
        self.w_working_title.config(text="กำลังตรวจไฟล์เกม")
        self.progress(0, "อ่านไฟล์เพื่อคำนวณ SHA256", jump=True)
        self.show("working")
        p = self.plan

        def job():
            status = p.verify(
                progress=lambda f, name: self.post(
                    lambda: self.progress(round(f * 100), "ตรวจ " + name)),
                cancel=self.cancel.is_set)
            self.post(lambda: self.on_verified(status))
        self.work(job)
        self._render_footer()

    def on_verified(self, status):
        self.busy = False
        self.job = None
        p = self.plan
        if status == "unsupported":
            bad = p.unsupported_files()
            if bad == ["adult.xp3"]:
                # เฉพาะ adult.xp3 ที่ build ไม่ตรง — patch.xp3/data.xp3 ยังแปะได้
                # จึงยังลงเวอร์ชัน all-ages ได้ ดีกว่าบอกว่า "ลงไม่ได้" แล้วจบ
                p.include_r18 = False
                self.r18_locked = True
                self.render_components()
                self.show("components")
                return
            self.fail(
                "เวอร์ชันเกมไม่ตรงกับแพตช์นี้",
                "ไฟล์ที่ไม่ตรง: %s — สาเหตุที่พบบ่อยคือ Steam อัปเดตเกมมาใหม่ "
                "ไฟล์เกมยังไม่ถูกแก้ไข ปลอดภัย" % ", ".join(bad))
        elif status == "installed":
            self.goto_done(
                p.has_backups, "ติดตั้งแพตช์ไทยไว้แล้ว",
                "เปิดเกมแล้วตั้ง Language เป็น “Chinese (Simplified)” เพื่อดูภาษาไทย"
                if p.has_backups else
                "ไฟล์เกมเป็นเวอร์ชันแปลไทยอยู่แล้ว แต่ไม่พบไฟล์สำรอง .bak "
                "จึงถอดคืนอัตโนมัติไม่ได้")
        else:
            self.render_components()
            self.show("components")

    def render_components(self):
        """แถวรายการ + ตัวเลือกเดียวที่เลือกได้จริง: จะเอาฉาก R18 ด้วยไหม

        ไฟล์บทพูดกับฟอนต์ล็อกไว้ ติ๊กออกไม่ได้ — ไม่ใช่ตัวเลือก แต่เป็นของที่ต้องมี
        """
        for w in self.w_comps.winfo_children():
            w.destroy()
        p = self.plan

        def row_frame():
            f = tk.Frame(self.w_comps, bg=T.BG, width=T.S(CONTENT_W), height=T.S(33))
            f.pack(anchor="w")
            f.pack_propagate(False)
            return f

        for t in p.targets:
            if not t.present or t.name == "adult.xp3":
                continue
            row = row_frame()
            W.CheckMark(row, on=True).pack(side="left")
            W.label(row, "%s — %s" % (t.label, t.name), 13.5).pack(
                side="left", padx=(T.S(12), 0))
            W.label(row, mb(t.size), 12, fg=T.TEXT_50).pack(side="right")

        boxes = [w for r in self.w_comps.winfo_children()
                 for w in r.winfo_children() if isinstance(w, W.CheckMark)]

        self.w_r18_row = None
        if p.r18_available:
            adult = next(t for t in p.targets if t.name == "adult.xp3")
            row = row_frame()
            box = W.CheckMark(row, on=p.include_r18, command=self.toggle_r18)
            box.pack(side="left")
            lab = W.label(row, "ฉาก R18 — adult.xp3", 13.5)
            lab.pack(side="left", padx=(T.S(12), 0))
            size = W.label(row, mb(adult.size), 12, fg=T.TEXT_50)
            size.pack(side="right")
            for w in (lab, row):
                w.bind("<Button-1>", lambda _e: self.toggle_r18())
            self.w_r18_row = (box, lab, size)
            boxes.append(box)
        # ติ๊กไล่กันทีละตัว (stagger ของ anime.js) — ตาไล่อ่านรายการทันพอดี
        A.stagger(boxes, lambda _i, b, d: b.pop_in(d), gap=0.055, start=0.14)
        self._render_r18_state()

    def _render_r18_state(self):
        p = self.plan
        if self.w_r18_row:
            box, lab, size = self.w_r18_row
            box.set(p.include_r18)
            fg = T.TEXT if p.include_r18 else T.TEXT_42
            fg2 = T.TEXT_50 if p.include_r18 else T.TEXT_42
            # ทวีนเปลี่ยนหน้าไล่สีจาก _fg0 อยู่ ต้องจบมันก่อนแล้วอัปเดตสีเป้าหมาย
            # ไม่งั้นแถวจะสว่างกลับเองตอนทวีนเดินถึงเฟรมสุดท้าย
            A.finish("screen")
            lab._fg0, size._fg0 = fg, fg2
            W._tint(lab, "foreground", fg, dur=0.18, tag="r18")
            W._tint(size, "foreground", fg2, dur=0.18, tag="r18")

        if not p.r18_available:
            self.w_comps_foot.config(
                text="เครื่องนี้ไม่ได้ลงแพตช์ R18 — ติดตั้งเป็นเวอร์ชัน all-ages")
        elif self.r18_locked:
            self.w_comps_foot.config(
                text="adult.xp3 ในเครื่องนี้เป็นแพตช์ R18 คนละ build จึงแปะไทยให้ไม่ได้ "
                     "— ลงเวอร์ชัน all-ages ได้ตามปกติ (จะปิด adult.xp3 ไว้)")
        elif p.include_r18:
            self.w_comps_foot.config(
                text="เวอร์ชัน R18 — ฉาก R18 จะเป็นภาษาไทยด้วย")
        else:
            self.w_comps_foot.config(
                text="เวอร์ชัน all-ages — จะปิด %s ไว้ด้วยการเปลี่ยนชื่อเป็น .off "
                     "(ไม่ลบ กด “ถอดแพตช์” แล้วได้คืนครบ)"
                     % " และ ".join(p.disable_list or ["adult.xp3"]))

    def toggle_r18(self):
        p = self.plan
        if not p or not p.r18_available or self.r18_locked:
            return
        p.include_r18 = not p.include_r18
        p.verified = True          # โหมด all-ages ไม่ต้องแฮช adult.xp3
        self._render_r18_state()

    def begin_install(self):
        self.job = "install"
        self.cancel.clear()
        self.w_working_title.config(text="กำลังติดตั้ง")
        self.progress(0, "เตรียมการ", jump=True)
        self.show("working")
        p = self.plan

        def job():
            p.install(
                progress=lambda f, s: self.post(
                    lambda: self.progress(round(f * 100), self.stage_text(s))),
                cancel=self.cancel.is_set)
            r18 = p.r18_available and p.include_r18
            self.post(lambda: self.goto_done(
                True, "ติดตั้งสำเร็จ (เวอร์ชัน %s)" % ("R18" if r18 else "all-ages"),
                "เปิดเกมแล้วตั้ง Language เป็น “Chinese (Simplified)” เพื่อดูภาษาไทย"
                + (" — และอย่ารันตัวติดตั้งแพตช์ R18 ซ้ำอีก มันจะเขียนทับ adult.xp3"
                   if r18 else "")))
        self.work(job)
        self._render_footer()

    def begin_uninstall(self):
        self.job = "uninstall"
        self.w_working_title.config(text="กำลังถอดแพตช์")
        self.progress(0, "คืนไฟล์ต้นฉบับ", jump=True)
        self.show("working")
        p = self.plan

        def job():
            restored = p.uninstall(
                progress=lambda f, name: self.post(
                    lambda: self.progress(round(f * 100), "คืนไฟล์ต้นฉบับ " + name)))
            self.post(lambda: self.goto_done(
                False, "ถอดแพตช์แล้ว", "คืนไฟล์ต้นฉบับเรียบร้อย: " + ", ".join(restored)))
        self.work(job)
        self._render_footer()

    # ---------------------------------------------------------------- ปุ่ม
    def on_cancel(self):
        if self.busy:
            self.cancel.set()
        else:
            self._bye()

    def on_back(self):
        if self.screen == "done" and self.installed:
            self.begin_uninstall()
        else:
            self.r18_locked = False
            if self.plan:
                self.plan.include_r18 = True
            self.show("locate")

    def on_primary(self):
        if self.busy:
            return
        if self.screen == "locate":
            self.refresh_detect()
            p = self.plan
            if not p:
                return
            if p.missing_game_files():
                return self.fail("ไม่ใช่โฟลเดอร์เกม",
                                 "ไม่พบ %s ในโฟลเดอร์นี้" % ", ".join(p.missing_game_files()))
            if p.missing_pieces():
                return self.fail("ชุดติดตั้งไม่ครบ",
                                 "ขาดไฟล์ %s — แตกไฟล์ zip ให้ครบทุกไฟล์"
                                 % ", ".join(p.missing_pieces()))
            if p.has_backups:
                return self.goto_done(True, "ติดตั้งแพตช์ไทยไว้แล้ว",
                                      "ถ้าต้องการติดตั้งใหม่ ให้กด “ถอดแพตช์” ก่อน")
            self.begin_verify()
        elif self.screen == "components":
            self.begin_install()
        elif self.screen == "done":
            if core.launch_game(self.plan.game):
                self._bye()
            else:
                self.fail("เปิดเกมไม่สำเร็จ", "ไม่พบ SenrenBanka.exe ในโฟลเดอร์ที่เลือก")
        elif self.screen == "error":
            self.show("locate")
            self.refresh_detect()

    def run(self):
        self.root.mainloop()


def _log_dir() -> str:
    return (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))


def main():
    Installer().run()


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # build เป็น --windowed จึงไม่มี console: ถ้าไม่เขียนลงไฟล์
        # ผู้เล่นจะเห็นแค่ "ดับเบิลคลิกแล้วไม่มีอะไรเกิดขึ้น"
        log = os.path.join(_log_dir(), "installer-error.log")
        try:
            with open(log, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
        except OSError:
            log = "(เขียนไฟล์ log ไม่ได้)"
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "ตัวติดตั้งเปิดไม่ขึ้น\n\nรายละเอียดถูกบันทึกไว้ที่:\n%s\n\n"
                "ระหว่างนี้ใช้ install.bat แทนได้ ผลลัพธ์เหมือนกันทุกอย่าง" % log,
                "Senren Banka — แพตช์แปลไทย", 0x10)
        except Exception:
            pass
        raise
