#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
GUI = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(GUI))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8")

import imgtool  # noqa: E402

BUILD_ONLY = ("imgtool", "make_bg", "make_logo", "build_gui")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="โฟลเดอร์ชุดติดตั้งที่จะวาง .exe ลงไป")
    ap.add_argument("--name", default="SenrenBanka-Thai-Patch")
    a = ap.parse_args()

    build = os.path.join(REPO, "thai_work", "dist", "_gui_build")
    os.makedirs(build, exist_ok=True)
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
    for i in range(tries):
        try:
            shutil.copy2(src, dst)
            return
        except PermissionError:
            if i == tries - 1:
                raise
            try:
                os.replace(dst, dst + ".old")
            except OSError:
                pass
            print("  ปลายทางถูกจับไว้ รออีกครั้ง (%d/%d)" % (i + 1, tries))
            time.sleep(1.0)


def check_build_only_excluded(workdir):
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
