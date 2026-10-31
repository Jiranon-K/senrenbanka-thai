#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
from dataclasses import dataclass

CHUNK = 1 << 22


def resource_dir() -> str:
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


def _steam_libraries() -> list[str]:
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
    for m in re.finditer(r'"path"\s*"([^"]+)"', text):
        roots.append(m.group(1).replace("\\\\", "\\"))
    return roots


def find_game_dirs() -> list[str]:
    found: list[str] = []

    def add(d):
        if not d:
            return
        d = os.path.abspath(d)
        if os.path.isfile(os.path.join(d, "SenrenBanka.exe")) and d not in found:
            found.append(d)

    here = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
            else os.path.dirname(os.path.abspath(__file__)))
    add(here)
    add(os.path.dirname(here))
    add(os.path.dirname(os.path.dirname(here)))

    for root in _steam_libraries():
        add(os.path.join(root, "steamapps", "common", "SenrenBanka"))

    return found


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


class Aborted(Exception):
    pass


@dataclass(frozen=True)
class Step:

    HASH = "hash"
    BACKUP = "backup"
    APPLY = "apply"
    DISABLE = "disable"
    RESTORE = "restore"
    DONE = "done"

    kind: str
    file: str = ""


class Target:

    def __init__(self, game_dir: str, spec: dict):
        self.name = spec["file"]
        self.delta = spec["delta"]
        self.label = spec["label"]
        self.required = spec["required"]
        self.r18 = spec.get("r18", self.name == "adult.xp3")
        self.orig = spec["sha_orig"]
        self.thai = spec["sha_thai"]
        self.path = os.path.join(game_dir, self.name)
        self.bak = self.path + ".bak"
        self.size = os.path.getsize(self.path) if os.path.isfile(self.path) else 0
        self.present = os.path.isfile(self.path)
        self.state = "unknown"


class Plan:

    R18_FILES = ("adult.xp3", "adult2.xp3")
    OFF = ".off"

    def __init__(self, game_dir: str, res: str | None = None, include_r18: bool = True):
        self.game_dir = os.path.abspath(game_dir)
        self.res = res or resource_dir()
        self.manifest = load_manifest(self.res)
        self.targets = [Target(self.game_dir, s) for s in self.manifest["targets"]]
        self.r18_files = tuple(self.manifest.get("disable_on_all_ages")
                               or self.R18_FILES)
        self.include_r18 = include_r18
        self.verified = False

    @property
    def xdelta_exe(self) -> str:
        return os.path.join(self.res, "xdelta3.exe")

    def delta_path(self, t: Target) -> str:
        return os.path.join(self.res, t.delta)

    @property
    def active(self) -> list[Target]:
        ts = [t for t in self.targets if t.present]
        if not self.include_r18:
            ts = [t for t in ts if t.name not in self.r18_files]
        if not (self.include_r18 and self.r18_available):
            ts = [t for t in ts if not t.r18]
        return ts

    @property
    def r18_available(self) -> bool:
        return os.path.isfile(os.path.join(self.game_dir, "adult.xp3"))

    @property
    def disable_list(self) -> list[str]:
        if self.include_r18 or not self.r18_available:
            return []
        return [f for f in self.r18_files
                if os.path.isfile(os.path.join(self.game_dir, f))]

    @property
    def disabled_now(self) -> list[str]:
        return [f for f in self.r18_files
                if os.path.isfile(os.path.join(self.game_dir, f + self.OFF))]

    @property
    def mode(self) -> str:
        return "R18" if self.r18_available else "all-ages"

    @property
    def has_backups(self) -> bool:
        return (any(os.path.isfile(t.bak) for t in self.targets)
                or bool(self.disabled_now))

    def missing_pieces(self) -> list[str]:
        miss = []
        if not os.path.isfile(self.xdelta_exe):
            miss.append("xdelta3.exe")
        for t in self.active:
            if not os.path.isfile(self.delta_path(t)):
                miss.append(t.delta)
        return miss

    def missing_game_files(self) -> list[str]:
        return [t.name for t in self.targets if t.required and not t.present]

    def verify(self, progress=None, cancel=None) -> str:
        total = sum(t.size for t in self.active) or 1
        done = 0

        for t in self.active:
            def bump(n, _t=t):
                nonlocal done
                if cancel and cancel():
                    raise Aborted()
                done += n
                if progress:
                    progress(done / total, Step(Step.HASH, _t.name))

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

    def install(self, progress=None, cancel=None):
        assert self.verified, "ต้อง verify() ก่อน install()"
        targets = self.active
        total = sum(t.size for t in targets) or 1
        done = 0
        renamed: list[Target] = []
        turned_off: list[str] = []

        def rollback():
            for f in turned_off:
                try:
                    os.replace(os.path.join(self.game_dir, f + self.OFF),
                               os.path.join(self.game_dir, f))
                except OSError:
                    pass
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
                progress(0.0, Step(Step.BACKUP))
            for t in targets:
                if cancel and cancel():
                    raise Aborted()
                os.replace(t.path, t.bak)
                renamed.append(t)

            for t in targets:
                if cancel and cancel():
                    raise Aborted()
                base = done
                step = Step(Step.APPLY, t.name)
                if progress:
                    progress(base / total, step)
                self._decode(t, lambda n: progress and progress(
                    min(1.0, (base + n) / total), step), cancel)
                done += t.size

            for f in self.disable_list:
                if progress:
                    progress(1.0, Step(Step.DISABLE, f))
                os.replace(os.path.join(self.game_dir, f),
                           os.path.join(self.game_dir, f + self.OFF))
                turned_off.append(f)

            if progress:
                progress(1.0, Step(Step.DONE))
        except BaseException:
            rollback()
            raise

    def _decode(self, t: Target, on_bytes, cancel):
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

    def uninstall(self, progress=None):
        restored = []
        items = [t.name for t in self.targets if os.path.isfile(t.bak)]
        items += self.disabled_now
        by_name = {t.name: t for t in self.targets}
        for i, name in enumerate(items):
            if name in by_name and os.path.isfile(by_name[name].bak):
                t = by_name[name]
                if os.path.isfile(t.path):
                    os.remove(t.path)
                os.replace(t.bak, t.path)
            else:
                os.replace(os.path.join(self.game_dir, name + self.OFF),
                           os.path.join(self.game_dir, name))
            restored.append(name)
            if progress:
                progress((i + 1) / len(items), Step(Step.RESTORE, name))
        return restored


def launch_game(game_dir: str) -> bool:
    exe = os.path.join(game_dir, "SenrenBanka.exe")
    if not os.path.isfile(exe):
        return False
    subprocess.Popen([exe], cwd=game_dir, close_fds=True)
    return True


def free_space(path: str) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0
