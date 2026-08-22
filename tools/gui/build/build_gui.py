#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gui.py — build tools/gui/ เป็น .exe เดี่ยวด้วย PyInstaller

    python tools/gui/build/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

สิ่งที่ **อยู่ใน** .exe: Python runtime, tkinter, ฟอนต์ Sarabun
สิ่งที่ **ไม่อยู่ใน** .exe: manifest.json, *.xdelta, xdelta3.exe และทุกอย่าง
ในโฟลเดอร์ build/ นี้ (เครื่องมือทำ asset — ทำงานตอน build เท่านั้น)

ทำไมไม่ยัด .xdelta เข้าไปด้วย: ชุดติดตั้งมี install.bat ที่ใช้ไฟล์ชุดเดียวกันอยู่แล้ว
ยัดเข้าไปอีกชุด = ซิปโตขึ้น 26 MB โดยได้อะไรกลับมาแค่ "ไฟล์เดียว"
ตัว GUI หาโฟลเดอร์เกมเองได้อยู่แล้ว ผู้เล่นจึงแตกซิปไว้ที่ไหนก็ได้ ไม่ต้องแตกทับเกม
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))          # tools/gui/build
GUI = os.path.dirname(HERE)                                # tools/gui
REPO = os.path.dirname(os.path.dirname(GUI))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import imgtool  # noqa: E402

# โมดูลในโฟลเดอร์ build/ ต้องไม่หลุดเข้าไปใน .exe — ตอนที่มันวางปนอยู่กับตัวแอป
# ใน tools/gui/ เรื่องนี้ถูกกันไว้ด้วยคำเตือนใน docstring อย่างเดียว ซึ่งบังคับ
# อะไรไม่ได้เลย ตอนนี้แยกโฟลเดอร์แล้วจึง assert ได้ตรงๆ หลัง build
BUILD_ONLY = ("imgtool", "make_bg", "make_logo", "build_gui")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="โฟลเดอร์ชุดติดตั้งที่จะวาง .exe ลงไป")
    ap.add_argument("--name", default="SenrenBanka-Thai-Patch")
    a = ap.parse_args()

    build = os.path.join(REPO, "thai_work", "dist", "_gui_build")
    os.makedirs(build, exist_ok=True)
    # ไอคอนที่ make_logo.py สร้างไว้ ถ้ายังไม่มีค่อยใช้สี่เหลี่ยมส้มสำรอง
    icon = os.path.join(GUI, "ui", "icon.ico")
    if not os.path.isfile(icon):
        icon = os.path.join(build, "app.ico")
        imgtool.write_placeholder_icon(icon)
    print("icon: %s" % icon)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", a.name,
        "--icon", icon,
        "--distpath", os.path.join(build, "dist"),
        "--workpath", os.path.join(build, "work"),
        "--specpath", build,
        # ทั้งโฟลเดอร์ ui/ = ฟอนต์ Sarabun + โลโก้ + ไอคอน + ภาพพื้นหลัง
        "--add-data", os.path.join(GUI, "ui") + os.pathsep + "ui",
        "--exclude-module", "webview",
        "--exclude-module", "PIL",
        "--exclude-module", "clr",
        "--exclude-module", "pythonnet",
    ]
    for m in BUILD_ONLY:
        cmd += ["--exclude-module", m]
    cmd.append(os.path.join(GUI, "app.py"))

    print("$ " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("PyInstaller ล้มเหลว")

    check_build_only_excluded(os.path.join(build, "work", a.name))

    src = os.path.join(build, "dist", a.name + ".exe")
    dst = os.path.join(os.path.abspath(a.out), a.name + ".exe")
    copy_over(src, dst)
    print("\n%s  (%.1f MB)" % (dst, os.path.getsize(dst) / 2 ** 20))


def copy_over(src, dst, tries=6):
    """ทับไฟล์ปลายทาง ทนต่อการที่ Windows ยังจับไฟล์ค้างอยู่ชั่วครู่

    .exe ที่เพิ่งเขียนเสร็จมักถูก Defender เปิดสแกน หรือ Explorer เปิดอ่าน
    ไอคอน อยู่พักหนึ่ง — copy ทับตอนนั้นจะได้ WinError 32 ทั้งที่ไม่มีใคร
    "รัน" มันอยู่ รอสักครู่แล้วลองใหม่จบเรื่อง ดีกว่าให้ทั้ง build ล้ม
    """
    for i in range(tries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            # ย้ายตัวเก่าออกไปก่อน (rename ทำได้แม้ยังมีคนเปิดอ่านอยู่)
            try:
                os.replace(dst, dst + ".old")
            except OSError:
                pass
            print("  ปลายทางถูกจับไว้ รออีกครั้ง (%d/%d)" % (i + 1, tries))
            time.sleep(1.0)


def check_build_only_excluded(workdir):
    """ยืนยันจากรายการโมดูลจริงที่ถูกเก็บลง .exe ว่า build/ ไม่หลุดเข้าไป

    ต้องอ่าน **PYZ-00.toc** ซึ่งเป็นรายชื่อโมดูล Python ที่ถูกแพ็กจริงๆ
    ไม่ใช่ Analysis-00.toc ที่มีรายการ excludedimports ปนอยู่ด้วย
    (อ่านผิดไฟล์แล้วจะฟ้องว่าหลุดทั้งที่กันไว้เรียบร้อย)
    """
    toc = os.path.join(workdir, "PYZ-00.toc")
    if not os.path.isfile(toc):
        print("ข้ามการตรวจ: ไม่พบ %s" % toc)
        return
    with open(toc, encoding="utf-8", errors="replace") as f:
        text = f.read()
    leaked = [m for m in BUILD_ONLY if "'%s'" % m in text]
    if leaked:
        sys.exit("โมดูลตอน build หลุดเข้าไปใน .exe: %s" % ", ".join(leaked))
    print("ตรวจแล้ว: ไม่มีโมดูลจาก build/ อยู่ใน .exe")


if __name__ == "__main__":
    main()
