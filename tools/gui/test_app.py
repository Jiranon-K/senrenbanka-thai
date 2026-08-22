#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
test_app.py — เทสหน้าจอ (tkinter) โดยไม่ต้องมองจอ

    set SBTP_RES=...\thai_work\dist\senrenbanka-thai-patch-v1.1
    python tools/gui/test_app.py

หน้าต่างถูก withdraw ไว้ตลอด ไม่เด้งขึ้นมากวน — ตรวจจาก widget tree ตรงๆ
สิ่งที่เทสนี้กันไว้:
  * ฟอนต์ไทยที่ bundle มาต้องลงทะเบียนได้ และ Tk ต้องซ้อนสระ/วรรณยุกต์ถูก
    (ถ้าวันหนึ่ง Tk เปลี่ยน text engine แล้วไทยแตก เทสนี้จะจับได้ทันที)
  * โปรแกรมต้อง **ไม่เปิดพอร์ต TCP** — เวอร์ชันก่อนหน้าใช้ pywebview
    ซึ่งแอบตั้ง HTTP server ที่ 127.0.0.1 แล้วโหลดหน้าเว็บผ่านมัน
  * แถบหัวของ Windows ต้องถูกถอดออกจริง แต่หน้าต่างยังเป็น top-level ปกติ
  * ตัวเลือก all-ages / R18 ต้องเปลี่ยนสิ่งที่จะทำกับไฟล์จริงๆ
  * สถานะปุ่ม/ขั้นตอน/หน้าจอ เดินถูกตามตาราง
"""
import os
import subprocess
import sys
import tkinter.font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

import app as gui                                             # noqa: E402
import core                                                   # noqa: E402
import theme as T                                             # noqa: E402

results, failed = [], []


def chk(label, got, want):
    ok = got == want
    (results if ok else failed).append(label)
    print("    %s  %s" % ("PASS" if ok else "FAIL", label))
    if not ok:
        print("          want %r\n          got  %r" % (want, got))


def chk_true(label, got):
    chk(label, bool(got), True)


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


def main():
    print("=" * 70)
    print("ฟอนต์และการเรียงตัวอักษรไทย")
    chk_true("ลงทะเบียนฟอนต์ Sarabun ได้", T.load_fonts())

    inst = gui.Installer()
    inst.root.withdraw()
    inst.root.update()

    fams = [f for f in tkfont.families() if "sarabun" in f.lower()]
    chk_true("Tk เห็นตระกูล Sarabun", fams)
    f = tkfont.Font(family=T.FAMILY, size=-15)
    # สระ/วรรณยุกต์ไทยเป็น combining mark กว้าง 0 -> ต้องซ้อน ไม่ใช่เรียงต่อกัน
    for base, full in [("ท", "ที่"), ("ก", "กุ๊"), ("ป", "ปั๊")]:
        chk("ซ้อนสระ/วรรณยุกต์ %r" % full, f.measure(full) <= f.measure(base) * 1.35, True)

    print("=" * 70)
    print("ไม่ใช่ web app")
    ports = listening_ports(os.getpid())
    chk("ไม่เปิดพอร์ต TCP เลย", ports, [])
    chk("ไม่ได้ import webview", "webview" in sys.modules, False)
    chk_true("หน้าต่างเป็น Tk ของจริง", inst.root.winfo_class() == "Toplevel"
             or inst.root.winfo_toplevel() is inst.root)

    print("=" * 70)
    print("แถบหัวที่วาดเอง")
    chk("ถอดแถบหัวของ Windows แล้ว", T.has_caption(inst.root), False)
    chk("ไม่ได้ใช้ overrideredirect (ไม่งั้น taskbar/Alt-Tab หาย)",
        bool(inst.root.overrideredirect()), False)
    chk_true("มีปุ่มย่อ/ปิดของตัวเอง", inst.b_min and inst.b_close)
    chk_true("แถบหัวลากได้", callable(getattr(inst, "_drag_start", None)))
    chk("ขนาดหน้าต่างตรงดีไซน์",
        (inst.root.winfo_width(), inst.root.winfo_height()), (T.S(880), T.S(600)))
    credits = [t for t in _all_text(inst.shell) if "ไม่เป็นทางการ" in t]
    chk("เครดิตเหลือบรรทัดเดียว", credits, ["งานแปลไม่เป็นทางการ"])
    chk("ไม่มีชื่อผู้แปลบนหน้าจอ",
        [t for t in _all_text(inst.shell) if "Jiranon" in t], [])

    print("=" * 70)
    print("สถานะตอนเปิดโปรแกรม")
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
    chk("ขั้นที่ 4 ยังไม่ถึง", inst.w_steps[3][0].cget("bg"), T.DIVIDER)
    print("          โหมดที่ตรวจได้: %s | .bak: %s"
          % (inst.plan.mode, inst.plan.has_backups))

    print("=" * 70)
    print("เดินหน้าจอ")
    inst.plan.state = None
    inst.render_components()
    inst.show("components")
    inst.root.update()
    rows = [w for w in inst.w_comps.winfo_children()]
    chk("หน้ารายการแสดงครบทุกไฟล์ที่มี", len(rows), len(inst.plan.active))
    chk("ปุ่มหลักเขียนว่า 'ติดตั้ง'", inst.b_primary.cget("text"), "ติดตั้ง")

    if inst.plan.r18_available:
        chk_true("มีตัวเลือก R18 ให้ติ๊ก", inst.w_r18_row is not None)
        chk("ค่าเริ่มต้น = เอาฉาก R18", inst.plan.include_r18, True)
        chk("R18 อยู่ในรายการที่จะแปะ",
            "adult.xp3" in [t.name for t in inst.plan.active], True)
        chk("ยังไม่ต้องปิดไฟล์อะไร", inst.plan.disable_list, [])

        inst.toggle_r18()
        inst.root.update()
        chk("ติ๊กออกแล้วไม่แปะ adult.xp3",
            "adult.xp3" in [t.name for t in inst.plan.active], False)
        chk("ติ๊กออกแล้วสั่งปิดไฟล์ R18",
            inst.plan.disable_list, ["adult.xp3", "adult2.xp3"])
        chk_true("บอกผู้ใช้ว่าปิดแบบเปลี่ยนชื่อ ไม่ลบ",
                 "ไม่ลบ" in inst.w_comps_foot.cget("text"))
        inst.toggle_r18()
        chk("ติ๊กกลับได้", inst.plan.include_r18, True)

        inst.r18_locked = True
        inst.toggle_r18()
        chk("ล็อกแล้วติ๊กไม่ได้ (adult.xp3 คนละ build)", inst.plan.include_r18, True)
        inst.r18_locked = False
    chk("ปุ่มย้อนกลับโผล่", inst.b_back.winfo_manager(), "pack")
    chk("ขั้นที่ 1 กลายเป็น 'ผ่านแล้ว'", inst.w_steps[0][0].cget("bg"), T.ACCENT_300)

    inst.job = "install"
    inst.show("working")
    inst.progress(64, inst.stage_text("stage.apply:patch.xp3"))
    inst.root.update()
    chk("เปอร์เซ็นต์ขึ้นถูก", inst.w_pct.cget("text"), "64%")
    chk_true("ข้อความขั้นตอนแปลเป็นไทย",
             inst.w_stage.cget("text").startswith("แปะแพตช์ patch.xp3"))
    inst.job = None

    inst.goto_done(True, "ติดตั้งสำเร็จ", "…")
    inst.root.update()
    chk("หน้าเสร็จ: ปุ่มหลัก = 'เปิดเกม'", inst.b_primary.cget("text"), "เปิดเกม")
    chk("หน้าเสร็จ: ปุ่ม ghost = 'ถอดแพตช์'", inst.b_back.cget("text"), "ถอดแพตช์")

    inst.fail("หัวข้อผิดพลาด", "รายละเอียด", "traceback บรรทัดเดียว")
    inst.root.update()
    chk("หน้าผิดพลาดขึ้น", inst.screen, "error")
    chk("กล่อง traceback โผล่", inst.w_err_box.winfo_manager(), "pack")
    chk("ปุ่มหลัก = 'ลองใหม่'", inst.b_primary.cget("text"), "ลองใหม่")

    inst.root.destroy()

    print("=" * 70)
    if failed:
        print("ตก %d เคส: %s" % (len(failed), ", ".join(failed)))
        sys.exit(1)
    print("ผ่านทั้งหมด (%d เคส)" % len(results))


if __name__ == "__main__":
    main()
