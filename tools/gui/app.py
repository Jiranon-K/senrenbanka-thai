#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — หน้าต่างติดตั้งแพตช์แปลไทย (Windows native, tkinter)

    python tools/gui/app.py
    python tools/gui/build/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

เป็นโปรแกรมหน้าต่างจริงๆ: widget ของ Windows ล้วน มีปุ่มบน taskbar
ไม่มีเบราว์เซอร์ ไม่มี HTTP server ไม่เปิดพอร์ต ไม่ต้องพึ่ง WebView2

หน้าตาแบบ shadcn/ui (zinc + มุมโค้ง) — โครงหน้าจอเดิมมาจาก Claude Design
โปรเจกต์ "Fan-translation mod installer"
(โทเคนอยู่ใน theme.py, คอมโพเนนต์อยู่ใน widgets.py, รูปทรงโค้งอยู่ใน shape.py,
เปลือกหน้าต่างอยู่ใน window.py)

ตรรกะทั้งหมดอยู่ใน core.py — ไฟล์นี้เป็นแค่หน้าจอกับการเดินสถานะ
"""
from __future__ import annotations

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
import window                                                 # noqa: E402

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


# การ์ดในหน้ารายการ: บรรทัดอธิบายใต้ชื่อ (ชื่อมาจาก manifest ของแต่ละรุ่น)
COMP_DESC = {
    "patch.xp3": "บทพูดเนื้อเรื่องหลักทุกเส้นทาง",
    "data.xp3":  "ฟอนต์ไทยและไฟล์ระบบของเกม",
    "adult.xp3": "ให้ฉากของแพตช์ R18 เป็นภาษาไทยด้วย",
}
CARD_H = 62              # ความสูงการ์ดหนึ่งใบ
CARD_GAP = 8

# บอกให้ครบว่า "ใครทำ" กับ "ไม่ใช่ของใคร" ในบรรทัดเดียว โดยไม่ใส่ชื่อคนแปล
CREDIT = "งานแปลโดยแฟนเกม · ไม่ใช่ฉบับทางการ"

# core.Step -> ข้อความในแถบสถานะ ("%s" = ชื่อไฟล์)
# core ไม่รู้จักภาษาไทยสักคำ คำที่ผู้ใช้อ่านอยู่ที่นี่ที่เดียว
STEP_TEXT = {
    core.Step.HASH:    "ตรวจ %s",
    core.Step.BACKUP:  "สำรองไฟล์ต้นฉบับ",
    core.Step.APPLY:   "แปะแพตช์ %s",
    core.Step.DISABLE: "ปิด %s (เปลี่ยนชื่อเป็น .off)",
    core.Step.RESTORE: "คืนไฟล์ต้นฉบับ %s",
    core.Step.DONE:    "เสร็จสิ้น",
}


def mb(n: int) -> str:
    if not n:
        return ""
    m = n / 1048576
    return "%.1f GB" % (m / 1024) if m >= 1024 else "%d MB" % round(m)


class Installer:
    """เรื่องราวของการติดตั้ง — หาโฟลเดอร์เกม ตรวจ แปะ เสร็จ/ล้ม

    เปลือกหน้าต่าง (สร้าง Tk, ถอดแถบหัว, ลาก, เข้า/ออก, โลโก้, แผงภาพ)
    อยู่ใน window.py ทั้งหมด ไฟล์นี้เรียกผ่าน self.win
    """

    def __init__(self):
        self.win = window.Window("Senren Banka — แพตช์แปลไทย", (WIN_W, WIN_H),
                                 logo_px=LOGO_PX)
        self.root = self.win.root

        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.plan: core.Plan | None = None
        self.manifest: dict | None = None      # manifest.json ของชุดติดตั้ง
        self.game_dirs: list[str] = []         # โฟลเดอร์เกมที่หาเจอ
        self.screen = None         # ยังไม่มีหน้าไหนถูกแสดง -> หน้าแรกได้อนิเมชันด้วย
        self.job: str | None = None
        self.busy = False
        self.installed = False
        self.r18_locked = False    # adult.xp3 เป็น build ที่ไม่รองรับ -> ลงได้แค่ all-ages
        self.w_r18_row = None
        self._debounce = None

        self._build()
        self.win.fix_size()
        self.root.after(40, self._pump)
        self.root.after(0, self.boot)
        self.root.after(1, self.win.appear)

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
        self.border = r
        r.grid_rowconfigure(1, weight=1)
        r.grid_columnconfigure(0, weight=1)

        # ── แถบหัวที่วาดเอง: เครื่องหมาย + ชื่อ + เวอร์ชัน + ย่อ/ปิด
        head = tk.Frame(r, bg=T.BG, height=T.S(44))
        head.grid(row=0, column=0, sticky="ew")
        head.grid_propagate(False)
        mark, side = self.win.mark(head)
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
        self.win.drag_from(head, mark, title, self.w_version)

        body = tk.Frame(r, bg=T.BG)
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── แถบซ้าย: 4 ขั้น + เครดิต
        # แถบข้างแบบ <Sidebar> ของ shadcn: พื้น zinc-50 + เส้นขอบขวา 1px
        rail = tk.Frame(body, bg=T.SIDEBAR, width=T.S(212))
        rail.grid(row=0, column=0, sticky="nsw")
        rail.grid_propagate(False)
        tk.Frame(rail, bg=T.DIVIDER, width=1).place(relx=1.0, x=-1, y=0, relheight=1.0)
        self.w_steps = []
        for i, name in enumerate(STEPS):
            row = tk.Frame(rail, bg=T.SIDEBAR)
            row.place(x=T.S(26), y=T.S(26 + i * 28))
            rule = W.Rule(row)
            rule.pack(side="left")
            lab = W.label(row, name, 13, fg=T.TEXT_42, bg=T.SIDEBAR)
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
        self.w_credit = W.label(body, CREDIT, 11, fg=T.TEXT_45, bg=T.SIDEBAR)
        self.w_credit.place(x=T.S(26), rely=1.0, y=-T.S(16), anchor="sw")

        self.win.backdrop(r, (BG_X, BG_Y, BG_W, BG_H))

        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.root.bind("<Escape>", lambda _e: self.on_cancel())

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
        self.w_field = W.Field(row, T.S(CONTENT_W - 88), textvariable=self.var_path)
        self.w_field.pack(side="left")
        self.w_path = self.w_field.entry
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
        # กล่อง traceback: การ์ด 420x132 (max-height:132px) ไม่ยืดเต็มจอ
        self.w_err_box = W.Card(f, T.S(CONTENT_W), T.S(132), padx=12, pady=8)
        self.w_err_detail = tk.Text(self.w_err_box.body, font=T.F(11.5), fg=T.TEXT_55,
                                    bg=T.BG, relief="flat", wrap="word",
                                    highlightthickness=0, bd=0, padx=0, pady=0)
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
            self.win.slide_backdrop(T.S(14), 0.55)      # ขยับตามนิดหน่อย ให้รู้สึกเป็นชั้นเดียวกัน

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

    def step_text(self, step: core.Step) -> str:
        """core.Step -> ข้อความไทยที่ผู้ใช้เห็น

        ข้อความทุกบรรทัดที่โผล่ในแถบสถานะอยู่ในตาราง STEP_TEXT ตัวเดียว
        แก้คำหรือเพิ่มภาษาได้โดยไม่ต้องแตะ core.py เลย
        """
        text = STEP_TEXT.get(step.kind, step.kind)
        if "%s" not in text:
            return text
        name = step.file
        if step.kind == core.Step.APPLY:
            t = next((t for t in (self.plan.targets if self.plan else [])
                      if t.name == name), None)
            if t:
                name += " — " + t.label      # "patch.xp3 — บทพูด (all-ages)"
        return text % name

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
        self.win.shake()

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
            self.manifest = core.load_manifest()
            self.game_dirs = core.find_game_dirs()
        except FileNotFoundError:
            return self.fail("ไม่พบ manifest.json",
                             "ตัวติดตั้งต้องอยู่โฟลเดอร์เดียวกับ manifest.json, "
                             "xdelta3.exe และไฟล์ .xdelta — แตกไฟล์ zip ให้ครบทุกไฟล์")
        self.w_version.config(text="v" + self.manifest["version"])
        dirs = self.game_dirs
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
                else "พื้นที่ว่าง %.1f GB" % (core.free_space(p.game_dir) / 2 ** 30))

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
                progress=lambda f, s: self.post(
                    lambda: self.progress(round(f * 100), self.step_text(s))),
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
            r18_names = {t.name for t in p.targets if t.r18}
            if bad and set(bad) <= r18_names:
                # เฉพาะไฟล์ฝั่ง R18 ที่ build ไม่ตรง — patch.xp3/data.xp3 ยังแปะได้
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
        boxes = []

        def card(t, title, on, badge, variant, command=None):
            """การ์ดหนึ่งใบ: [กล่องติ๊ก] ชื่อ + ป้าย / คำอธิบาย ....... ขนาด / ชื่อไฟล์"""
            c = W.Card(self.w_comps, T.S(CONTENT_W), T.S(CARD_H))
            c.pack(anchor="w", pady=(0, T.S(CARD_GAP)))
            b = c.body
            box = W.CheckMark(b, on=on, command=command)
            box.pack(side="left")
            boxes.append(box)
            right = tk.Frame(b, bg=T.BG)
            right.pack(side="right")
            size = W.label(right, mb(t.size), 12, fg=T.TEXT_50)
            size.pack(anchor="e")
            fname = W.label(right, t.name, 11, fg=T.TEXT_45)
            fname.pack(anchor="e")
            mid = tk.Frame(b, bg=T.BG)
            mid.pack(side="left", padx=(T.S(14), 0))
            top = tk.Frame(mid, bg=T.BG)
            top.pack(anchor="w")
            lab = W.label(top, title, 14, bold=True)
            lab.pack(side="left")
            W.Tag(top, badge, variant).pack(side="left", padx=(T.S(8), 0))
            desc = W.label(mid, COMP_DESC.get(t.name, ""), 12, fg=T.TEXT_55)
            desc.pack(anchor="w")
            return c, box, lab, size, desc, (b, right, fname, mid, top)

        for t in p.targets:
            if not t.present or t.r18:      # ไฟล์ R18 รวมอยู่ในการ์ด "ฉาก R18" ใบเดียว
                continue
            card(t, t.label, True, "จำเป็น", "neutral")

        self.w_r18_row = None
        if p.r18_available:
            adult = next(t for t in p.targets if t.name == "adult.xp3")
            c, box, lab, size, desc, parts = card(
                adult, "ฉาก R18", p.include_r18, "ตัวเลือก", "accent",
                command=self.toggle_r18)
            # ทั้งใบคือที่กดติ๊ก (เหมือน <Label> ที่ครอบ checkbox ในเว็บ)
            for w in (c, lab, size, desc) + parts:
                w.bind("<Button-1>", lambda _e: self.toggle_r18())
            c.bind("<Enter>", lambda _e: self._hover_r18(True))
            c.bind("<Leave>", lambda _e: self._hover_r18(c.pointer_inside()))
            self.w_r18_row = (box, lab, size, desc, c)
        # ติ๊กไล่กันทีละตัว (stagger ของ anime.js) — ตาไล่อ่านรายการทันพอดี
        A.stagger(boxes, lambda _i, b, d: b.pop_in(d), gap=0.055, start=0.14)
        self._render_r18_state()

    def _r18_border(self, hover=False) -> str:
        """ขอบการ์ด R18: เลือกไว้ = สีหลัก · ไม่เลือก = ปกติ (เมาส์ชี้ = เข้มขึ้นนิด)"""
        if self.plan.include_r18 and not self.r18_locked:
            return T.ACCENT
        return T.CARD_HOVER if hover and not self.r18_locked else T.DIVIDER

    def _hover_r18(self, on):
        if self.w_r18_row:
            self.w_r18_row[4].set_border(self._r18_border(on))

    def _render_r18_state(self):
        p = self.plan
        if self.w_r18_row:
            box, lab, size, desc, c = self.w_r18_row
            box.set(p.include_r18)
            fg = T.TEXT if p.include_r18 else T.TEXT_42
            fg2 = T.TEXT_50 if p.include_r18 else T.TEXT_42
            fg3 = T.TEXT_55 if p.include_r18 else T.TEXT_42
            # ทวีนเปลี่ยนหน้าไล่สีจาก _fg0 อยู่ ต้องจบมันก่อนแล้วอัปเดตสีเป้าหมาย
            # ไม่งั้นแถวจะสว่างกลับเองตอนทวีนเดินถึงเฟรมสุดท้าย
            A.finish("screen")
            lab._fg0, size._fg0, desc._fg0 = fg, fg2, fg3
            W._tint(lab, "foreground", fg, dur=0.18, tag="r18")
            W._tint(size, "foreground", fg2, dur=0.18, tag="r18")
            W._tint(desc, "foreground", fg3, dur=0.18, tag="r18")
            c.set_border(self._r18_border())

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
                    lambda: self.progress(round(f * 100), self.step_text(s))),
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
                progress=lambda f, s: self.post(
                    lambda: self.progress(round(f * 100), self.step_text(s))))
            self.post(lambda: self.goto_done(
                False, "ถอดแพตช์แล้ว", "คืนไฟล์ต้นฉบับเรียบร้อย: " + ", ".join(restored)))
        self.work(job)
        self._render_footer()

    # ---------------------------------------------------------------- ปุ่ม
    def on_cancel(self):
        if self.busy:
            self.cancel.set()
        else:
            self.win.close()

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
            if core.launch_game(self.plan.game_dir):
                self.win.close()
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
