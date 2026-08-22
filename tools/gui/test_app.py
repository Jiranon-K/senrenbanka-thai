#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
test_app.py — เทสหน้าจอ (tkinter) โดยไม่ต้องมองจอ

    set SBTP_RES=...\thai_work\dist\senrenbanka-thai-patch-v1.1
    python tools/gui/test_app.py
    python tools/gui/test_app.py --no-input     # ข้ามเคสที่ขยับเมาส์จริง

หน้าต่างถูก withdraw ไว้ตลอด ไม่เด้งขึ้นมากวน — ตรวจจาก widget tree ตรงๆ
ยกเว้นเคสลากหน้าต่างด้วยเมาส์จริง ซึ่งต้องโชว์หน้าต่างจริงๆ ราว 1 วินาที

สิ่งที่เทสนี้กันไว้:
  * ฟอนต์ไทยที่ bundle มาต้องลงทะเบียนได้ และ Tk ต้องซ้อนสระ/วรรณยุกต์ถูก
    (ถ้าวันหนึ่ง Tk เปลี่ยน text engine แล้วไทยแตก เทสนี้จะจับได้ทันที)
  * โปรแกรมต้อง **ไม่เปิดพอร์ต TCP** — เวอร์ชันก่อนหน้าใช้ pywebview
    ซึ่งแอบตั้ง HTTP server ที่ 127.0.0.1 แล้วโหลดหน้าเว็บผ่านมัน
  * แถบหัวของ Windows ต้องถูกถอดออกจริง แต่หน้าต่างยังเป็น top-level ปกติ
  * **ลากหน้าต่างต้องเร็ว** — เดิมใช้ root.geometry() ซึ่งกิน 30 ms ต่อเฟรม
    (เพดาน 33 fps) หน้าต่างเลยตามเมาส์ไม่ทัน เห็นเป็นเงาแล้วกระโดดตาม
  * ตัวเลือก all-ages / R18 ต้องเปลี่ยนสิ่งที่จะทำกับไฟล์จริงๆ
  * สถานะปุ่ม/ขั้นตอน/หน้าจอ เดินถูกตามตาราง

หมายเหตุเรื่องอนิเมชัน: ค่าบนจอระหว่างทวีนยังไม่ใช่ค่าปลายทาง เทสจึงเรียก
A.flush() (จบทุกทวีนทันที) ก่อนตรวจ "สถานะที่ควรจะเป็น" เสมอ ส่วนตัวอนิเมชัน
เองมีหัวข้อเทสของมันแยกต่างหาก
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import anim as A                                              # noqa: E402
import app as gui                                             # noqa: E402
import core                                                   # noqa: E402
import theme as T                                             # noqa: E402
import widgets as W                                           # noqa: E402

results, failed, skipped = [], [], []


def chk(label, got, want):
    ok = got == want
    (results if ok else failed).append(label)
    print("    %s  %s" % ("PASS" if ok else "FAIL", label))
    if not ok:
        print("          want %r\n          got  %r" % (want, got))


def chk_true(label, got):
    chk(label, bool(got), True)


def chk_near(label, got, want, tol):
    ok = abs(got - want) <= tol
    (results if ok else failed).append(label)
    print("    %s  %s  (%.3f ~ %.3f ±%.3f)" % ("PASS" if ok else "FAIL", label,
                                               got, want, tol))


def skip(label, why):
    skipped.append(label)
    print("    SKIP  %s — %s" % (label, why))


def _all_text(w, out=None):
    out = [] if out is None else out
    try:
        t = w.cget("text")
        if t:
            out.append(str(t))
    except Exception:
        pass
    for c in w.winfo_children():
        _all_text(c, out)
    return out


def listening_ports(pid: int):
    out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                         capture_output=True, text=True).stdout
    return [l.split()[1] for l in out.splitlines()
            if "LISTENING" in l and l.split()[-1] == str(pid)]


def settle(inst):
    """ประมวลผล event ค้าง แล้วดันทวีนทุกตัวไปเฟรมสุดท้าย"""
    inst.root.update()
    A.flush()
    inst.root.update()


class FakeEvent:
    def __init__(self, xr, yr):
        self.x_root, self.y_root = xr, yr
        self.x = self.y = 0


# ───────────────────────────────────────────── ลากหน้าต่างด้วยเมาส์ของจริง

u32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
GA_ROOT = 2


def _root_window_at(x, y) -> int:
    h = u32.WindowFromPoint(wt.POINT(x, y))
    return u32.GetAncestor(h, GA_ROOT) if h else 0


def real_mouse_drag(inst, dx, dy):
    """กดปุ่มซ้ายบนแถบหัวจริงๆ แล้วลาก — เส้นทางเดียวกับที่ผู้ใช้ทำ

    event ปลอมเทสได้แค่สูตรคำนวณ อันนี้เทสทั้งเส้น: Windows ส่ง input ->
    Tk แปลงเป็น <B1-Motion> -> handler -> หน้าต่างขยับจริงบนจอ

    ระวังไว้สองชั้น: (1) เช็กว่าจุดที่จะกดเป็นหน้าต่างของเราเองก่อนเสมอ
    (2) ปล่อยปุ่มใน finally ไม่ว่าจะเกิดอะไรขึ้น แล้วคืนตำแหน่งเคอร์เซอร์เดิม
    """
    root = inst.root
    root.deiconify()
    root.lift()
    root.update()
    A.flush()
    root.update()

    x, y, _w, _h = T.window_rect(root)
    px, py = x + T.S(300), y + T.S(20)          # กลางแถบหัว ไม่โดนปุ่มย่อ/ปิด
    if _root_window_at(px, py) != T.hwnd_of(root):
        root.withdraw()
        return None, "จุดที่จะกดไม่ใช่หน้าต่างของเรา (มีหน้าต่างอื่นบัง)"

    home = wt.POINT()
    u32.GetCursorPos(ctypes.byref(home))
    hwnd = T.hwnd_of(root)          # เก็บไว้ให้เธรดขับใช้ (GetWindowRect เรียกข้ามเธรดได้)
    done = threading.Event()
    got = {}

    def raw_rect():
        r = wt.RECT()
        u32.GetWindowRect(wt.HWND(hwnd), ctypes.byref(r))
        return r.left, r.top

    def driver():
        """ขยับเมาส์จริงแล้ววัด **ตอนยังกดปุ่มค้างอยู่**

        ถ้าไปวัดหลังปล่อยปุ่ม จะแข่งกับคิว input ของ Windows: SetCursorPos มีผล
        ทันทีแต่ mouse_event เข้าคิว ลำดับจึงสลับกันได้ แล้ววัดได้ขาดไปไม่กี่ px
        ทั้งที่ตอนลากจริงไม่มีปัญหา — วัดตอนยังลากอยู่จึงตรงกับสิ่งที่อยากรู้
        (หน้าต่างตามเมาส์ทันไหม) และไม่มีการแข่งกันเลย
        """
        try:
            time.sleep(0.15)
            u32.SetCursorPos(px, py)
            time.sleep(0.06)
            u32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            for i in range(1, 13):
                time.sleep(0.012)
                u32.SetCursorPos(px + dx * i // 12, py + dy * i // 12)
            u32.SetCursorPos(px + dx, py + dy)
            time.sleep(0.25)                    # ให้ Tk ตามให้ทันก่อนวัด
            cur = wt.POINT()
            u32.GetCursorPos(ctypes.byref(cur))
            wx, wy = raw_rect()
            got["moved"] = (wx - x, wy - y)
            got["lag"] = (cur.x - wx - grab[0], cur.y - wy - grab[1])
        finally:
            u32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            u32.SetCursorPos(home.x, home.y)
            done.set()

    grab = (px - x, py - y)
    threading.Thread(target=driver, daemon=True).start()
    t0 = time.perf_counter()
    while not done.is_set() and time.perf_counter() - t0 < 6.0:
        root.update()
        time.sleep(0.003)
    root.update()
    T.move_window(root, x, y)
    root.withdraw()
    root.update()
    if "moved" not in got:
        return None, "เธรดขับเมาส์ทำงานไม่จบ"
    return got, None


# ─────────────────────────────────────────────────────────────── หัวข้อเทส

def test_fonts(inst):
    print("=" * 70)
    print("ฟอนต์และการเรียงตัวอักษรไทย")
    fams = [f for f in tkfont.families() if "sarabun" in f.lower()]
    chk_true("Tk เห็นตระกูล Sarabun", fams)
    f = tkfont.Font(family=T.FAMILY, size=-15)
    # สระ/วรรณยุกต์ไทยเป็น combining mark กว้าง 0 -> ต้องซ้อน ไม่ใช่เรียงต่อกัน
    for base, full in [("ท", "ที่"), ("ก", "กุ๊"), ("ป", "ปั๊")]:
        chk("ซ้อนสระ/วรรณยุกต์ %r" % full, f.measure(full) <= f.measure(base) * 1.35, True)


def test_not_web(inst):
    print("=" * 70)
    print("ไม่ใช่ web app")
    chk("ไม่เปิดพอร์ต TCP เลย", listening_ports(os.getpid()), [])
    chk("ไม่ได้ import webview", "webview" in sys.modules, False)
    chk_true("หน้าต่างเป็น Tk ของจริง", inst.root.winfo_class() == "Toplevel"
             or inst.root.winfo_toplevel() is inst.root)


def test_chrome(inst):
    print("=" * 70)
    print("แถบหัวที่วาดเอง")
    chk("ถอดแถบหัวของ Windows แล้ว", T.has_caption(inst.root), False)
    chk("ไม่ได้ใช้ overrideredirect (ไม่งั้น taskbar/Alt-Tab หาย)",
        bool(inst.root.overrideredirect()), False)
    chk_true("มีปุ่มย่อ/ปิดของตัวเอง", inst.b_min and inst.b_close)
    chk("ขนาดหน้าต่างตรงดีไซน์",
        (inst.root.winfo_width(), inst.root.winfo_height()), (T.S(880), T.S(600)))
    chk("ไม่มีชื่อผู้แปลบนหน้าจอ",
        [t for t in _all_text(inst.shell) if "Jiranon" in t], [])


PNG_MAGIC = bytes([137, 80, 78, 71, 13, 10, 26, 10])


def ico_frames(path):
    """คืน [(ขนาด, เป็น PNG ไหม), ...] ที่อยู่ในไฟล์ .ico"""
    d = open(path, "rb").read()
    n = struct.unpack("<H", d[4:6])[0]
    out = []
    for i in range(n):
        e = 6 + 16 * i
        ln, off = struct.unpack("<II", d[e + 8:e + 16])
        out.append(((d[e] or 256), d[off:off + 8] == PNG_MAGIC))
    return out


def test_logo(inst):
    print("=" * 70)
    print("โลโก้และไอคอน")
    img = inst._logo_img
    chk_true("โหลดโลโก้ได้", img is not None)
    if img is not None:
        chk("ขนาดโลโก้ตรงกับที่ขอ (ไม่ได้ให้ Tk ย่อเอง)",
            (img.width(), img.height()), (T.S(gui.LOGO_PX),) * 2)
        chk("เครื่องหมายเป็นภาพ ไม่ใช่สี่เหลี่ยมสีเดียว",
            inst._mark.winfo_class(), "Label")
        top = inst._mark.winfo_y()
        chk("วางกึ่งกลางแถบหัวพอดี", top * 2 + img.height(), T.S(44))

    # เตรียมไว้หลายขนาดเพราะ Tk ย่อภาพได้แค่หารจำนวนเต็มแบบ nearest
    for want, px in ((20, 21), (25, 24), (30, 31), (40, 55)):
        f = T.logo_file(px)
        chk("ขอ %2d px -> ได้ logo@%d" % (px, want),
            os.path.basename(f or ""), "logo@%d.png" % want)

    ico = T.icon_file()
    chk("ใช้ไอคอนที่ bundle มา ไม่ใช่ตัวสำรอง",
        os.path.basename(os.path.dirname(ico)), "ui")
    frames = ico_frames(ico)
    chk("ไอคอนมีครบทุกขนาดที่ Windows ใช้",
        [s for s, _ in frames], [16, 20, 24, 32, 48, 64, 128, 256])
    chk("ทุกขนาดเก็บเป็น PNG (มีช่อง alpha)",
        all(png for _, png in frames), True)

    # ถ้าไม่มีไฟล์โลโก้ ต้องถอยไปใช้สี่เหลี่ยมตามดีไซน์ ไม่ใช่ล้ม
    real = T.logo_file
    T.logo_file = lambda _px: None
    try:
        w, side = inst._make_mark(inst.shell)
        chk("ไม่มีโลโก้ -> ถอยไปใช้สี่เหลี่ยมตามดีไซน์",
            (w.winfo_class(), side), ("Frame", 18))
        w.destroy()
    finally:
        T.logo_file = real
        inst._logo_img = img


def test_credit(inst):
    print("=" * 70)
    print("เครดิตท้ายหน้าต่าง")
    c = inst.w_credit
    body = c.master
    chk("มีบรรทัดเดียว", [t for t in _all_text(inst.shell) if "แฟนเกม" in t],
        [gui.CREDIT])
    chk_true("บอกว่าใครทำ", "แฟนเกม" in gui.CREDIT)
    chk_true("บอกว่าไม่ใช่ของทางการ", "ไม่ใช่ฉบับทางการ" in gui.CREDIT)
    chk("ไม่มีชื่อคนแปล", any(ch.isascii() and ch.isalpha() for ch in gui.CREDIT), False)
    gap = body.winfo_height() - (c.winfo_y() + c.winfo_height())
    print("          ห่างจากขอบล่าง %d px | กว้าง %d px" % (gap, c.winfo_reqwidth()))
    chk("อยู่ล่างสุดของหน้าต่าง", gap <= T.S(24), True)
    chk("อยู่ต่ำกว่าขั้นตอนทุกขั้นในแถบซ้าย",
        c.winfo_rooty() > inst.w_steps[-1][1].winfo_rooty(), True)
    # ถ้ายาวเกินจะไปชนข้อความในแถวปุ่ม (โผล่ตอนหน้า "กำลังติดตั้ง")
    chk("สั้นพอที่จะไม่ชนข้อความในแถวปุ่ม",
        T.S(26) + c.winfo_reqwidth() <= T.S(242), True)


def test_backdrop(inst):
    print("=" * 70)
    print("แผงภาพพื้นหลัง")
    cv, img = inst.bg, inst._bg_img
    chk_true("โหลด bg.png ได้", cv is not None and img is not None)
    if not cv:
        return
    chk("ขนาดตรงกับที่ make_bg.py สร้าง", (img.width(), img.height()), (280, 482))
    # ตรวจว่าการไล่จางถูกฝังใน alpha จริง ไม่ใช่ภาพทึบทั้งใบ
    chk_true("ขอบซ้ายใสสนิท", img.transparency_get(0, 240))
    chk_true("ขอบขวาไม่ใส", not img.transparency_get(279, 240))
    chk_true("ขอบบนสุดใส (ไม่ชนแถบหัว)", img.transparency_get(279, 0))
    chk_true("ขอบล่างสุดใส (ไม่ชนแถวปุ่ม)", img.transparency_get(279, 481))

    chk("แผงเริ่มตรงขอบขวาของคอลัมน์เนื้อหาพอดี",
        gui.BG_X, 212 + 30 + gui.CONTENT_W)
    # เทียบกับ body ไม่ใช่มุมหน้าต่าง — shell มีกรอบ 1 px ทุกอย่างจึงเลื่อนไป 1
    body = inst.w_credit.master
    chk("วางถูกตำแหน่ง",
        (cv.winfo_x() - body.winfo_x(), cv.winfo_y() - body.winfo_y()),
        (T.S(gui.BG_X), 0))
    chk("ไม่ล้ำลงไปในแถวปุ่ม",
        gui.BG_Y + gui.BG_H <= gui.WIN_H - 74, True)

    A.flush()
    home = T.S(gui.BG_W)
    chk("เลื่อนเข้าที่แล้วชิดขอบขวาพอดี", round(cv.coords(inst._bg_item)[0]), home)
    inst.slide_backdrop(T.S(40), 0.5)
    chk_true("สั่งเลื่อนแล้วขยับจริง", cv.coords(inst._bg_item)[0] > home)
    A.flush()
    chk("เลื่อนจบแล้วกลับเข้าที่เดิม",
        round(cv.coords(inst._bg_item)[0]), home)

    saved = inst.bg
    inst.bg = None
    inst.slide_backdrop(T.S(20), 0.2)      # เครื่องที่ไม่มี bg.png ต้องไม่ล้ม
    A.flush()
    chk("ไม่มีภาพก็ยังทำงานได้", inst.bg, None)
    inst.bg = saved


def test_drag(inst, allow_input=True):
    print("=" * 70)
    print("ลากหน้าต่าง")
    root = inst.root
    x0, y0, w0, h0 = T.window_rect(root)

    # ── สูตรคำนวณตำแหน่ง
    inst._drag_start(FakeEvent(x0 + 300, y0 + 20))
    chk("จำระยะจากมุมหน้าต่างถึงเมาส์ได้", inst._drag, (300, 20))
    inst._drag_move(FakeEvent(x0 + 300 + 137, y0 + 20 + 61))
    x1, y1, w1, h1 = T.window_rect(root)
    chk("เมาส์ขยับเท่าไร หน้าต่างขยับเท่านั้นเป๊ะ", (x1 - x0, y1 - y0), (137, 61))
    chk("ขนาดไม่เปลี่ยนระหว่างลาก", (w1, h1), (w0, h0))
    inst._drag_end(None)
    chk("ปล่อยปุ่มแล้วเลิกลาก", inst._drag, None)
    inst._drag_move(FakeEvent(x0 + 999, y0 + 999))
    chk("ปล่อยแล้วขยับเมาส์ หน้าต่างต้องอยู่นิ่ง",
        T.window_rect(root)[:2], (x1, y1))

    # ── ความเร็ว: ของเดิมวัดได้ 30.6 ms/เฟรม = 33 fps ซึ่งคือต้นเหตุอาการเงา
    inst._drag_start(FakeEvent(x1 + 300, y1 + 20))
    N = 60
    t = time.perf_counter()
    for i in range(N):
        inst._drag_move(FakeEvent(x1 + 300 + (i % 30), y1 + 20))
        root.update()
    ms = (time.perf_counter() - t) * 1000 / N
    inst._drag_end(None)
    T.move_window(root, x0, y0)
    print("          วัดได้ %.2f ms/เฟรม (%.0f fps) — ของเดิม 30.6 ms (33 fps)"
          % (ms, 1000 / ms))
    chk("หนึ่งเฟรมต้องต่ำกว่า 8 ms", ms < 8.0, True)

    # ── ที่เหลือต้องให้หน้าต่างโผล่จริง (Tk ไม่อ่าน WM_MOVE ตอนถูก withdraw)
    if not allow_input:
        skip("Tk ตามตำแหน่งทัน", "สั่ง --no-input ไว้")
        return skip("ลากด้วยเมาส์จริง", "สั่ง --no-input ไว้")

    root.deiconify()
    root.update()
    xa, ya, _w, _h = T.window_rect(root)
    inst._drag_start(FakeEvent(xa + 300, ya + 20))
    inst._drag_move(FakeEvent(xa + 300 + 90, ya + 20 + 45))
    inst._drag_end(None)
    root.update()
    xb, yb, _w, _h = T.window_rect(root)
    chk("Tk รู้ตำแหน่งใหม่ด้วย", (root.winfo_x(), root.winfo_y()), (xb, yb))
    root.iconify()
    root.update()
    root.deiconify()
    root.update()
    chk("ย่อแล้วเรียกคืน หน้าต่างไม่เด้งกลับที่เดิม", T.window_rect(root)[:2], (xb, yb))
    T.move_window(root, xa, ya)
    root.update()

    # ── ของจริง: กดเมาส์จริงแล้วลาก ต้องเข้าลูปย้ายหน้าต่างของ Windows
    got, why = real_mouse_drag(inst, T.S(140), T.S(70))
    if why:
        return skip("ลากด้วยเมาส์จริง", why)
    print("          หน้าต่างขยับ %s | ห่างจากที่ควรอยู่ %s px" % (got["moved"], got["lag"]))
    chk("ลากด้วยเมาส์จริง: หน้าต่างอยู่ตรงกับเมาส์เป๊ะ", got["lag"], (0, 0))
    chk_near("ลากด้วยเมาส์จริง: แกน X ไปตามที่ลาก", got["moved"][0], T.S(140), 2)
    chk_near("ลากด้วยเมาส์จริง: แกน Y ไปตามที่ลาก", got["moved"][1], T.S(70), 2)


def test_anim(inst):
    print("=" * 70)
    print("เครื่องยนต์อนิเมชัน")
    for name in ("linear", "out_quad", "out_cubic", "out_quart", "out_quint",
                 "out_expo", "in_out_cubic", "out_back", "out_elastic"):
        f = getattr(A, name)
        chk("easing %-12s เริ่ม 0 จบ 1" % name,
            (round(f(0.0), 6), round(f(1.0), 6)), (0.0, 1.0))
    chk_true("out_back เลยเป้าแล้วดีดกลับ", A.out_back(0.72) > 1.0)

    chk("mix ปลายซ้าย", T.mix("#000000", "#ffffff", 0.0), "#000000")
    chk("mix ปลายขวา", T.mix("#000000", "#ffffff", 1.0), "#ffffff")
    chk("mix กลางทาง", T.mix("#000000", "#ffffff", 0.5), "#808080")
    chk("mix ไม่หลุดขอบเมื่อ easing เลยเป้า",
        T.mix("#000000", "#ffffff", 1.4), "#ffffff")

    seen = []
    A.tween(0.05, seen.append, key="unit-a")
    A.tween(0.05, lambda v: None, key="unit-b")
    chk("ทวีนสองตัวเดินพร้อมกันได้", A.running(), 2)
    chk_true("ใช้ตัวจับเวลากลางตัวเดียว", A._job is not None)
    A.tween(0.05, lambda v: None, key="unit-b")
    chk("key เดิมแทนที่ตัวเก่า ไม่ซ้อนกัน", A.running(), 2)
    A.flush()
    chk("flush แล้วไม่เหลือทวีนค้าง", A.running(), 0)
    chk("ไม่มีงานแล้วตัวจับเวลาหยุด (ไม่ปลุก CPU ทิ้งไว้)", A._job, None)
    chk("คืนความละเอียดตัวจับเวลาให้ระบบ", A._hires, False)
    chk("เฟรมสุดท้ายเป็น 1.0 เสมอ", seen[-1], 1.0)

    done = []
    A.tween(0.0, lambda v: None, done=lambda: done.append(1), key="unit-c")
    A.flush()
    chk("เรียก done ตอนจบ", done, [1])

    # เดินจริงบนนาฬิกาจริง: 0.18 วิ ต้องได้อย่างน้อย 40 fps และจบตรงเวลา
    frames, t0 = [], time.perf_counter()
    A.tween(0.18, lambda v: frames.append(v), ease=A.linear, key="unit-d",
            done=inst.root.quit)
    inst.root.after(900, inst.root.quit)
    inst.root.mainloop()
    el = time.perf_counter() - t0
    fps = len(frames) / el if el else 0
    print("          เดินจริง %d เฟรมใน %.0f ms = %.0f fps" % (len(frames), el * 1000, fps))
    chk("จบตรงเวลาที่สั่ง (±120 ms)", abs(el - 0.18) < 0.12, True)
    chk("ได้อย่างน้อย 40 fps", fps >= 40, True)
    chk("ค่าที่ส่งให้เดินหน้าเสมอ", frames == sorted(frames), True)

    A.setup(inst.root, enabled=False)
    v = []
    A.tween(1.0, v.append, key="unit-e")
    chk("ปิดอนิเมชันแล้วกระโดดถึงปลายทางทันที (เคารพค่าของ Windows)", v, [1.0])
    chk("ปิดแล้วไม่มีทวีนค้าง", A.running(), 0)
    A.setup(inst.root, enabled=True)


def test_widgets(inst):
    print("=" * 70)
    print("อนิเมชันของคอมโพเนนต์")
    root = inst.root
    bar = W.ProgressBar(root, width=T.S(420))
    bar.set(64)
    chk_true("แถบยังไม่ถึงเป้าระหว่างทาง", bar.value < 64)
    A.flush()
    chk("แถบจบที่ค่าจริงเป๊ะ ไม่ปัดเอง", bar.value, 64.0)
    bar.reset(0)
    chk("reset กระโดดทันที ไม่ทวีน", (bar.value, A.running()), (0.0, 0))

    box = W.CheckMark(root, on=True)
    chk("ติ๊กไว้ = จุดกลางเต็มขนาด", round(box._t, 3), 1.0)
    box.set(False)
    A.flush()
    chk("ติ๊กออกแล้วจุดกลางหาย", round(box._t, 3), 0.0)
    box.set(True)
    A.flush()
    chk("ติ๊กกลับแล้วเต็มเหมือนเดิม", round(box._t, 3), 1.0)

    # event_generate ส่ง <Enter> ให้ widget ที่ยังไม่ปรากฏบนจอไม่ได้ (root ถูก
    # withdraw อยู่) จึงตรวจสองชั้นแทน: ผูก binding ไว้จริงไหม + handler ทำถูกไหม
    b = W.Button(root, "x", "primary")
    chk_true("ผูก <Enter>/<Leave> ไว้จริง", b.bind("<Enter>") and b.bind("<Leave>"))
    b._on_enter(None)
    chk_true("สีค่อยๆ ไล่ ไม่กระโดด", b.cget("bg") != T.ACCENT_600)
    A.flush()
    chk("เมาส์เข้าแล้วสีพื้นเป็นสี hover", b.cget("bg"), T.ACCENT_600)
    b._on_leave(None)
    A.flush()
    chk("เมาส์ออกแล้วสีกลับเดิม", b.cget("bg"), T.ACCENT)
    b._on_press(None)
    chk("กดแล้วเปลี่ยนทันที ไม่หน่วง", b.cget("bg"), T.ACCENT_700)

    badge = W.Badge(root)
    badge.set_ok(True)
    A.flush()
    chk_true("เครื่องหมายถูกวาดครบ", badge.find_withtag("mark"))
    badge.set_ok(False)
    A.flush()
    chk("กากบาทมีสองเส้น", len(badge.find_withtag("mark")), 2)
    chk("พื้นเปลี่ยนเป็นสีเตือน", badge.cget("bg"), T.DANGER)

    for w in (bar, box, b, badge):
        w.destroy()
    chk_true("ทวีนของ widget ที่ถูกทำลายไปแล้วไม่ทำให้ล้ม",
             (A.tween(0.05, lambda v: bar.set(v), key="dead"), A.flush(), True)[-1])


def test_window_fx(inst):
    print("=" * 70)
    print("เข้า-ออกของหน้าต่าง")
    root = inst.root
    root.attributes("-alpha", 0.0)
    inst._appear()
    A.flush()
    chk("เฟดเข้าจบที่ทึบเต็ม", float(root.attributes("-alpha")), 1.0)
    # Tk เปิด WS_EX_LAYERED ให้ตอนสร้าง wrapper เท่านั้น ถ้าบิตหลุดไป
    # -alpha จะเงียบไปเฉยๆ (เฟดตอนปิดจะไม่ทำงาน) — จึงต้องเปิดเองให้แน่
    chk("ตั้งความทึบได้จริง (บิตหน้าต่างซ้อนชั้นยังอยู่)",
        T.make_layered(root) and T.is_layered(root), True)
    root.attributes("-alpha", 0.4)
    root.update()
    chk_near("ค่าที่ตั้งมีผลจริง", float(root.attributes("-alpha")), 0.4, 0.01)
    root.attributes("-alpha", 1.0)

    x, y, _w, _h = T.window_rect(root)
    inst._shake()                       # หน้าต่างถูก withdraw อยู่ -> ต้องไม่ทำอะไร
    A.flush()
    chk("ไม่สั่นตอนหน้าต่างยังไม่โผล่", T.window_rect(root)[:2], (x, y))


def test_flow(inst):
    print("=" * 70)
    print("สถานะตอนเปิดโปรแกรม")
    settle(inst)
    chk("เริ่มที่หน้าเลือกโฟลเดอร์", inst.screen, "locate")
    chk("แสดงเวอร์ชันจาก manifest", inst.w_version.cget("text"),
        "v" + core.load_manifest()["version"])
    chk_true("เติม path ให้อัตโนมัติ", inst.var_path.get())
    chk_true("สร้าง Plan จาก path นั้นได้", inst.plan is not None)
    chk("ปุ่มหลักเขียนว่า 'ถัดไป'", inst.b_primary.cget("text"), "ถัดไป")
    # winfo_ismapped() เป็น 0 เสมอตอน root ถูก withdraw -> ใช้ winfo_manager() แทน
    # ("" = ไม่ได้ถูก pack ไว้เลย, "pack" = อยู่ในผัง)
    chk("ปุ่มย้อนกลับถูกซ่อน", inst.b_back.winfo_manager(), "")
    chk("ขั้นที่ 1 ถูกไฮไลต์", inst.w_steps[0][0].cget("bg"), T.ACCENT)
    chk("ขีดของขั้นที่ทำอยู่ยืดออก", inst.w_steps[0][0].cget("width"), T.S(W.Rule.W_ON))
    chk("ขั้นที่ 4 ยังไม่ถึง", inst.w_steps[3][0].cget("bg"), T.DIVIDER)
    chk("หน้าจอเลื่อนเข้าที่แล้ว", inst.screens["locate"].winfo_y(), 0)
    print("          โหมดที่ตรวจได้: %s | .bak: %s"
          % (inst.plan.mode, inst.plan.has_backups))

    print("=" * 70)
    print("เดินหน้าจอ")
    inst.plan.state = None
    inst.render_components()
    inst.show("components")
    settle(inst)
    rows = [w for w in inst.w_comps.winfo_children()]
    chk("หน้ารายการแสดงครบทุกไฟล์ที่มี", len(rows), len(inst.plan.active))
    chk("ปุ่มหลักเขียนว่า 'ติดตั้ง'", inst.b_primary.cget("text"), "ติดตั้ง")
    chk("หน้าเดิมถูกเอาออกจากผัง", inst.screens["locate"].winfo_manager(), "")

    if inst.plan.r18_available:
        chk_true("มีตัวเลือก R18 ให้ติ๊ก", inst.w_r18_row is not None)
        chk("ค่าเริ่มต้น = เอาฉาก R18", inst.plan.include_r18, True)
        chk("R18 อยู่ในรายการที่จะแปะ",
            "adult.xp3" in [t.name for t in inst.plan.active], True)
        chk("ยังไม่ต้องปิดไฟล์อะไร", inst.plan.disable_list, [])
        chk("กล่องติ๊กของ R18 เต็มขนาด", round(inst.w_r18_row[0]._t, 3), 1.0)

        inst.toggle_r18()
        settle(inst)
        chk("ติ๊กออกแล้วไม่แปะ adult.xp3",
            "adult.xp3" in [t.name for t in inst.plan.active], False)
        chk("ติ๊กออกแล้วสั่งปิดไฟล์ R18",
            inst.plan.disable_list, ["adult.xp3", "adult2.xp3"])
        chk("กล่องติ๊กว่างจริง", round(inst.w_r18_row[0]._t, 3), 0.0)
        chk("แถวหรี่ลง", inst.w_r18_row[1].cget("fg"), T.TEXT_42)
        chk_true("บอกผู้ใช้ว่าปิดแบบเปลี่ยนชื่อ ไม่ลบ",
                 "ไม่ลบ" in inst.w_comps_foot.cget("text"))
        inst.toggle_r18()
        settle(inst)
        chk("ติ๊กกลับได้", inst.plan.include_r18, True)
        chk("แถวสว่างกลับ", inst.w_r18_row[1].cget("fg"), T.TEXT)

        inst.r18_locked = True
        inst.toggle_r18()
        chk("ล็อกแล้วติ๊กไม่ได้ (adult.xp3 คนละ build)", inst.plan.include_r18, True)
        inst.r18_locked = False
    chk("ปุ่มย้อนกลับโผล่", inst.b_back.winfo_manager(), "pack")
    chk("ขั้นที่ 1 กลายเป็น 'ผ่านแล้ว'", inst.w_steps[0][0].cget("bg"), T.ACCENT_300)
    chk("ขีดของขั้นที่ผ่านแล้วหดกลับ", inst.w_steps[0][0].cget("width"), T.S(W.Rule.W))

    inst.job = "install"
    inst.show("working")
    inst.progress(0, "เตรียมการ", jump=True)
    chk("เริ่มงานใหม่ เปอร์เซ็นต์กลับไป 0 ทันที", inst.w_pct.cget("text"), "0%")
    inst.progress(64, inst.stage_text("stage.apply:patch.xp3"))
    settle(inst)
    chk("เปอร์เซ็นต์ขึ้นถูก", inst.w_pct.cget("text"), "64%")
    chk("แถบกับตัวเลขเป็นค่าเดียวกันเสมอ", round(inst.w_bar.value), 64)
    chk_true("ข้อความขั้นตอนแปลเป็นไทย",
             inst.w_stage.cget("text").startswith("แปะแพตช์ patch.xp3"))
    inst.job = None

    inst.goto_done(True, "ติดตั้งสำเร็จ", "…")
    settle(inst)
    chk("หน้าเสร็จ: ปุ่มหลัก = 'เปิดเกม'", inst.b_primary.cget("text"), "เปิดเกม")
    chk("หน้าเสร็จ: ปุ่ม ghost = 'ถอดแพตช์'", inst.b_back.cget("text"), "ถอดแพตช์")
    chk_true("ตราสำเร็จวาดเครื่องหมายถูกแล้ว",
             inst.w_done_badge.find_withtag("mark"))

    inst.fail("หัวข้อผิดพลาด", "รายละเอียด", "traceback บรรทัดเดียว")
    settle(inst)
    chk("หน้าผิดพลาดขึ้น", inst.screen, "error")
    chk("กล่อง traceback โผล่", inst.w_err_box.winfo_manager(), "pack")
    chk("ปุ่มหลัก = 'ลองใหม่'", inst.b_primary.cget("text"), "ลองใหม่")
    chk("สีตัวหนังสือกลับมาเต็มหลังอนิเมชันจบ",
        inst.w_err_title.cget("fg"), T.TEXT)


def main():
    allow_input = "--no-input" not in sys.argv
    print("=" * 70)
    print("ฟอนต์")
    chk_true("ลงทะเบียนฟอนต์ Sarabun ได้", T.load_fonts())

    inst = gui.Installer()
    inst.root.withdraw()
    inst.root.update()

    test_fonts(inst)
    test_not_web(inst)
    test_chrome(inst)
    test_logo(inst)
    test_credit(inst)
    test_backdrop(inst)
    test_flow(inst)
    test_anim(inst)
    test_widgets(inst)
    test_window_fx(inst)
    test_drag(inst, allow_input)

    inst.root.destroy()

    print("=" * 70)
    if skipped:
        print("ข้าม %d เคส: %s" % (len(skipped), ", ".join(skipped)))
    if failed:
        print("ตก %d เคส: %s" % (len(failed), ", ".join(failed)))
        sys.exit(1)
    print("ผ่านทั้งหมด (%d เคส)" % len(results))


if __name__ == "__main__":
    main()
