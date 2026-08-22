#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_gui.py — build tools/gui/ เป็น .exe เดี่ยวด้วย PyInstaller

    python tools/gui/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

สิ่งที่ **อยู่ใน** .exe: Python runtime, tkinter, ฟอนต์ Sarabun
สิ่งที่ **ไม่อยู่ใน** .exe: manifest.json, *.xdelta, xdelta3.exe

ทำไมไม่ยัด .xdelta เข้าไปด้วย: ชุดติดตั้งมี install.bat ที่ใช้ไฟล์ชุดเดียวกันอยู่แล้ว
ยัดเข้าไปอีกชุด = ซิปโตขึ้น 26 MB โดยได้อะไรกลับมาแค่ "ไฟล์เดียว"
ตัว GUI หาโฟลเดอร์เกมเองได้อยู่แล้ว ผู้เล่นจึงแตกซิปไว้ที่ไหนก็ได้ ไม่ต้องแตกทับเกม
"""
import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import theme  # noqa: E402  (ใช้ make_icon ตัวเดียวกับที่แอปใช้)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="โฟลเดอร์ชุดติดตั้งที่จะวาง .exe ลงไป")
    ap.add_argument("--name", default="SenrenBanka-Thai-Patch")
    a = ap.parse_args()

    build = os.path.join(REPO, "thai_work", "dist", "_gui_build")
    os.makedirs(build, exist_ok=True)
    # ไอคอนที่ make_logo.py สร้างไว้ ถ้ายังไม่มีค่อยใช้สี่เหลี่ยมส้มสำรอง
    icon = os.path.join(HERE, "ui", "icon.ico")
    if not os.path.isfile(icon):
        icon = os.path.join(build, "app.ico")
        theme.make_icon(icon)
    print("icon: %s" % icon)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", a.name,
        "--icon", icon,
        "--distpath", os.path.join(build, "dist"),
        "--workpath", os.path.join(build, "work"),
        "--specpath", build,
        # ทั้งโฟลเดอร์ ui/ = ฟอนต์ Sarabun + ภาพพื้นหลัง bg.png
        "--add-data", os.path.join(HERE, "ui") + os.pathsep + "ui",
        "--exclude-module", "webview",
        "--exclude-module", "PIL",
        "--exclude-module", "clr",
        "--exclude-module", "pythonnet",
        os.path.join(HERE, "app.py"),
    ]
    print("$ " + " ".join(cmd))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        sys.exit("PyInstaller ล้มเหลว")

    src = os.path.join(build, "dist", a.name + ".exe")
    dst = os.path.join(os.path.abspath(a.out), a.name + ".exe")
    shutil.copy2(src, dst)
    print("\n%s  (%.1f MB)" % (dst, os.path.getsize(dst) / 2 ** 20))


if __name__ == "__main__":
    main()
