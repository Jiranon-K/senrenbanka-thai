#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
core.py — ตรรกะการติดตั้งทั้งหมด ไม่มีส่วน UI เลย

แยกออกมาจาก app.py เพื่อให้เทสได้โดยไม่ต้องเปิดหน้าต่าง และเพื่อให้เห็นชัดว่า
GUI กับ install.bat ทำ "สิ่งเดียวกัน" — ลำดับขั้นตอนตรงกับ install.bat ที่
tools/test_installer.sh เทสไว้แล้ว 6 เคส:

  1. ต้องไม่มี .bak ค้างอยู่          (มี = ติดตั้งไปแล้ว)
  2. เช็ค SHA256 ก่อนแตะไฟล์ใดๆ
       - ตรงกับ hash ของไฟล์ที่แปะไทยแล้ว -> ติดตั้งแล้ว
       - ไม่ตรงกับ hash ต้นฉบับ           -> เวอร์ชันไม่รองรับ ยกเลิกทั้งชุด
  3. สำรองด้วยการ "เปลี่ยนชื่อ" ไม่ใช่ก็อปปี้ (adult.xp3 = 855 MB)
  4. xdelta3 -d ทีละไฟล์
  5. ล้มกลางคัน -> คืนทุกไฟล์ที่ rename ไปแล้ว

เจตนาสำคัญ: **ไม่แปะครึ่งเดียว** ถ้า adult.xp3 มีอยู่แต่แปะไม่ได้ ต้องล้มทั้งชุด
เพราะ adult.xp3 ทับบทพูดใน patch.xp3 อยู่ (ดู tools/R18_COMPAT.md)
แปะครึ่งเดียว = เกมขึ้นภาษาจีนเงียบๆ ซึ่งหาสาเหตุยากที่สุด
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

CHUNK = 1 << 22  # 4 MiB


# --------------------------------------------------------------- ที่อยู่ไฟล์

def resource_dir() -> str:
    """โฟลเดอร์ที่มี manifest.json / *.xdelta / xdelta3.exe / ui/

    onefile ของ PyInstaller แตกไฟล์ไว้ที่ sys._MEIPASS — แต่ยอมให้ไฟล์ที่วางไว้
    "ข้างๆ .exe" ชนะเสมอ เพื่อให้ระหว่างพัฒนาแก้ไฟล์แล้วรันใหม่ได้โดยไม่ต้อง build

    ระหว่างพัฒนา ตั้ง SBTP_RES ชี้ไปที่โฟลเดอร์ที่ build_release.py สร้าง
    จะได้ไม่ต้องก็อป .xdelta 26 MB เข้ามาไว้ใน repo
    """
    env = os.environ.get("SBTP_RES")
    if env and os.path.isfile(os.path.join(env, "manifest.json")):
        return env
    exe_dir = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
               else os.path.dirname(os.path.abspath(__file__)))
    if os.path.isfile(os.path.join(exe_dir, "manifest.json")):
        return exe_dir
    return getattr(sys, "_MEIPASS", exe_dir)


def load_manifest(base: str | None = None) -> dict:
    base = base or resource_dir()
    with open(os.path.join(base, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------- หาโฟลเดอร์เกม

def _steam_libraries() -> list[str]:
    """อ่าน libraryfolders.vdf เพื่อหา Steam library ทุกไดรฟ์"""
    roots: list[str] = []
    steam = None
    try:
        import winreg
        for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                          (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
            try:
                with winreg.OpenKey(hive, key) as k:
                    steam = winreg.QueryValueEx(k, "SteamPath" if hive == winreg.HKEY_CURRENT_USER
                                                else "InstallPath")[0]
                    break
            except OSError:
                continue
    except ImportError:
        pass
    if not steam:
        return roots

    roots.append(steam)
    vdf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    try:
        with open(vdf, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return roots
    # ไม่ pull parser vdf เข้ามาเพื่อ field เดียว — ดึง "path" ตรงๆ พอ
    for m in re.finditer(r'"path"\s*"([^"]+)"', text):
        roots.append(m.group(1).replace("\\\\", "\\"))
    return roots


def find_game_dirs() -> list[str]:
    """คืนโฟลเดอร์เกมที่เจอ เรียงตามความน่าจะใช่ ไม่ซ้ำกัน"""
    found: list[str] = []

    def add(d):
        if not d:
            return
        d = os.path.abspath(d)
        if os.path.isfile(os.path.join(d, "SenrenBanka.exe")) and d not in found:
            found.append(d)

    # 1) โฟลเดอร์ที่ตัวติดตั้งวางอยู่ (และแม่ของมัน) — วิธีที่คนแตกซิปทับมักทำ
    here = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    add(here)
    add(os.path.dirname(here))
    add(os.path.dirname(os.path.dirname(here)))

    # 2) ทุก Steam library
    for root in _steam_libraries():
        add(os.path.join(root, "steamapps", "common", "SenrenBanka"))

    return found


# ------------------------------------------------------------------- แฮช

def sha256(path: str, on_bytes=None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            if on_bytes:
                on_bytes(len(b))
    return h.hexdigest()


# ------------------------------------------------------------------ แผนงาน

class Aborted(Exception):
    """ผู้ใช้กดยกเลิก"""


class Target:
    """ไฟล์เกมหนึ่งไฟล์ที่แพตช์แตะ"""

    def __init__(self, game: str, spec: dict):
        self.name = spec["file"]              # patch.xp3
        self.delta = spec["delta"]            # thai-patch.xdelta
        self.label = spec["label"]            # "บทพูด"
        self.required = spec["required"]
        self.orig = spec["sha_orig"]
        self.thai = spec["sha_thai"]
        self.path = os.path.join(game, self.name)
        self.bak = self.path + ".bak"
        self.size = os.path.getsize(self.path) if os.path.isfile(self.path) else 0
        self.present = os.path.isfile(self.path)
        self.state = "unknown"               # pristine | patched | unsupported | missing


class Plan:
    """สถานะของโฟลเดอร์เกมหนึ่งโฟลเดอร์ + สิ่งที่จะทำกับมัน"""

    def __init__(self, game: str, res: str | None = None):
        self.game = os.path.abspath(game)
        self.res = res or resource_dir()
        self.mf = load_manifest(self.res)
        self.targets = [Target(self.game, s) for s in self.mf["targets"]]
        self.verified = False

    # ---- ไฟล์ประกอบ ----
    @property
    def xdelta_exe(self) -> str:
        return os.path.join(self.res, "xdelta3.exe")

    def delta_path(self, t: Target) -> str:
        return os.path.join(self.res, t.delta)

    # ---- สถานะ ----
    @property
    def active(self) -> list[Target]:
        """ไฟล์ที่จะแตะจริง — ตัวที่ไม่บังคับและไม่มีอยู่ ถือว่าไม่เกี่ยว"""
        return [t for t in self.targets if t.present]

    @property
    def mode(self) -> str:
        return "R18" if any(t.name == "adult.xp3" and t.present for t in self.targets) else "all-ages"

    @property
    def has_backups(self) -> bool:
        return any(os.path.isfile(t.bak) for t in self.targets)

    def missing_pieces(self) -> list[str]:
        """ไฟล์ในชุดติดตั้งที่หายไป"""
        miss = []
        if not os.path.isfile(self.xdelta_exe):
            miss.append("xdelta3.exe")
        for t in self.active:
            if not os.path.isfile(self.delta_path(t)):
                miss.append(t.delta)
        return miss

    def missing_game_files(self) -> list[str]:
        return [t.name for t in self.targets if t.required and not t.present]

    # ---- ตรวจ ----
    def verify(self, progress=None, cancel=None) -> str:
        """คำนวณ SHA256 ทุกไฟล์ที่เกี่ยวข้อง แล้วสรุปสถานะรวม

        คืน: "ready" | "installed" | "unsupported"
        """
        total = sum(t.size for t in self.active) or 1
        done = 0

        for t in self.active:
            def bump(n, _t=t):
                nonlocal done
                if cancel and cancel():
                    raise Aborted()
                done += n
                if progress:
                    progress(done / total, _t.name)

            h = sha256(t.path, bump)
            if h == t.thai:
                t.state = "patched"
            elif h == t.orig:
                t.state = "pristine"
            else:
                t.state = "unsupported"

        self.verified = True
        states = {t.state for t in self.active}
        if "patched" in states:
            return "installed"
        if "unsupported" in states:
            return "unsupported"
        return "ready"

    def unsupported_files(self) -> list[str]:
        return [t.name for t in self.active if t.state == "unsupported"]

    # ---- ติดตั้ง ----
    def install(self, progress=None, cancel=None):
        """rename -> xdelta -> ล้มเมื่อไหร่คืนทุกอย่าง

        progress(fraction, stage_text)
        """
        assert self.verified, "ต้อง verify() ก่อน install()"
        targets = self.active
        total = sum(t.size for t in targets) or 1
        done = 0
        renamed: list[Target] = []

        def rollback():
            for t in renamed:
                try:
                    if os.path.isfile(t.path):
                        os.remove(t.path)
                    if os.path.isfile(t.bak):
                        os.replace(t.bak, t.path)
                except OSError:
                    pass

        try:
            if progress:
                progress(0.0, "stage.backup")
            for t in targets:
                if cancel and cancel():
                    raise Aborted()
                os.replace(t.path, t.bak)      # same volume -> O(1)
                renamed.append(t)

            for t in targets:
                if cancel and cancel():
                    raise Aborted()
                base = done
                if progress:
                    progress(base / total, "stage.apply:" + t.name)
                self._decode(t, lambda n: progress and progress(min(1.0, (base + n) / total),
                                                               "stage.apply:" + t.name),
                             cancel)
                done += t.size

            if progress:
                progress(1.0, "stage.done")
        except BaseException:
            rollback()
            raise

    def _decode(self, t: Target, on_bytes, cancel):
        """xdelta3 -d -f -s <bak> <delta> <target>  + รายงานความคืบหน้าจากขนาดไฟล์ผลลัพธ์

        xdelta3 ไม่มี progress ให้อ่าน จึงดูขนาดไฟล์ปลายทางที่โตขึ้นแทน
        ซึ่งเป็นความคืบหน้าจริง ไม่ใช่ progress bar ปลอม
        """
        cmd = [self.xdelta_exe, "-d", "-f", "-s", t.bak, self.delta_path(t), t.path]
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             creationflags=flags)

        stop = threading.Event()

        def watch():
            while not stop.wait(0.15):
                try:
                    on_bytes(os.path.getsize(t.path))
                except OSError:
                    pass

        w = threading.Thread(target=watch, daemon=True)
        w.start()
        try:
            while p.poll() is None:
                if cancel and cancel():
                    p.terminate()
                    raise Aborted()
                time.sleep(0.05)
        finally:
            stop.set()
            w.join(timeout=1)

        out = (p.stdout.read() or b"").decode("utf-8", "replace").strip() if p.stdout else ""
        if p.returncode != 0:
            raise RuntimeError("xdelta3 ล้มเหลวกับ %s (exit %s)\n%s" % (t.name, p.returncode, out))

    # ---- ถอน ----
    def uninstall(self, progress=None):
        restored = []
        items = [t for t in self.targets if os.path.isfile(t.bak)]
        for i, t in enumerate(items):
            if os.path.isfile(t.path):
                os.remove(t.path)
            os.replace(t.bak, t.path)
            restored.append(t.name)
            if progress:
                progress((i + 1) / len(items), t.name)
        return restored


# ------------------------------------------------------------------ เปิดเกม

def launch_game(game: str) -> bool:
    exe = os.path.join(game, "SenrenBanka.exe")
    if not os.path.isfile(exe):
        return False
    subprocess.Popen([exe], cwd=game, close_fds=True)
    return True


def open_folder(path: str):
    if os.path.isdir(path):
        subprocess.Popen(["explorer", os.path.normpath(path)])


def free_space(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0
