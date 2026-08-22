#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_core.py — เทส core.py ด้วยเคสชุดเดียวกับ tools/test_installer.sh

    set SBTP_RES=...\thai_work\dist\senrenbanka-thai-patch-v1.1
    python tools/gui/test_core.py

GUI กับ install.bat ต้องทำสิ่งเดียวกันเป๊ะ ถ้าเทสสองชุดนี้ให้ผลต่างกัน
แปลว่ามีตัวใดตัวหนึ่งผิด — จึงจงใจให้เคสตรงกัน

โฟลเดอร์ทดสอบใช้ **hard link** ไปยัง archive ต้นฉบับจริง: ไม่ต้องก็อป 2 GB
และ os.replace() ที่ core ใช้ก็แค่เปลี่ยนชื่อ link ไม่แตะไฟล์จริง
(เคสสุดท้ายยืนยันซ้ำว่าต้นฉบับไม่เปลี่ยน)
"""
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")
import core                                                   # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GAME = REPO
while not os.path.isfile(os.path.join(GAME, "SenrenBanka.exe")):
    parent = os.path.dirname(GAME)
    if parent == GAME:
        sys.exit("หาโฟลเดอร์เกมไม่เจอ")
    GAME = parent
SANDBOX = os.path.join(GAME, "_gui_test")

PRISTINE = {"patch.xp3": "patch.xp3.bak", "data.xp3": "data.xp3.bak",
            "adult.xp3": "adult.xp3.orig"}

fails = []


def chk(label, got, want):
    if got == want:
        print("    PASS  %s" % label)
    else:
        print("    FAIL  %s\n          want %r\n          got  %r" % (label, want, got))
        fails.append(label)


def hardlink(dst, src):
    subprocess.run(["cmd", "/c", "mklink", "/H", dst, src],
                   check=True, capture_output=True)


def setup(name, mode):
    d = os.path.join(SANDBOX, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    open(os.path.join(d, "SenrenBanka.exe"), "wb").close()
    files = ["patch.xp3", "data.xp3"] + (["adult.xp3"] if mode == "r18" else [])
    for f in files:
        hardlink(os.path.join(d, f), os.path.join(GAME, PRISTINE[f]))
    return d


def hashes(plan):
    return {t.name: core.sha256(t.path) for t in plan.active}


def expect(plan, which):
    """which = 'orig' | 'thai'"""
    return {t.name: (t.orig if which == "orig" else t.thai) for t in plan.active}


def full_cycle(name, mode):
    print("=" * 70)
    print("เคส: %s (%s)" % (name, mode))
    d = setup(name, mode)
    p = core.Plan(d)
    chk("mode", p.mode, "R18" if mode == "r18" else "all-ages")
    chk("ชุดติดตั้งครบ", p.missing_pieces(), [])
    chk("ไฟล์เกมครบ", p.missing_game_files(), [])
    chk("ยังไม่มี .bak", p.has_backups, False)

    t0 = time.time()
    chk("verify", p.verify(), "ready")
    print("          (verify %.1fs)" % (time.time() - t0))

    stages = []
    t0 = time.time()
    p.install(progress=lambda f, s: stages.append(s))
    print("          (install %.1fs)" % (time.time() - t0))
    chk("หลังติดตั้ง = ไฟล์ไทย", hashes(p), expect(p, "thai"))
    chk("มี .bak ครบ", all(os.path.isfile(t.bak) for t in p.active), True)
    chk("รายงาน stage ครบทุกไฟล์",
        sorted({s.split(":", 1)[1] for s in stages if s.startswith("stage.apply:")}),
        sorted(t.name for t in p.active))

    p2 = core.Plan(d)
    chk("ตรวจซ้ำ -> installed", p2.verify(), "installed")

    restored = p.uninstall()
    chk("ถอดคืนครบ", sorted(restored), sorted(t.name for t in p.active))
    chk("หลังถอด = ไฟล์ต้นฉบับ", hashes(p), expect(p, "orig"))
    chk("ไม่มี .bak เหลือ", any(os.path.isfile(t.bak) for t in p.active), False)


def case_bad_adult():
    print("=" * 70)
    print("เคส: adult.xp3 คนละ build (ต้องไม่แตะอะไรเลย)")
    d = setup("badadult", "allages")
    with open(os.path.join(d, "adult.xp3"), "wb") as f:
        f.write(b"\0" * 1_000_000)
    p = core.Plan(d)
    chk("mode", p.mode, "R18")
    chk("verify", p.verify(), "unsupported")
    chk("ชี้ตัวที่ผิดได้", p.unsupported_files(), ["adult.xp3"])
    chk("ไม่มี .bak", p.has_backups, False)
    chk("patch.xp3 ไม่ถูกแตะ",
        core.sha256(os.path.join(d, "patch.xp3")),
        [t for t in p.targets if t.name == "patch.xp3"][0].orig)


def case_missing_delta():
    print("=" * 70)
    print("เคส: ชุดติดตั้งไม่ครบ")
    d = setup("incomplete", "r18")
    res = os.path.join(SANDBOX, "res-broken")
    shutil.rmtree(res, ignore_errors=True)
    shutil.copytree(core.resource_dir(), res,
                    ignore=shutil.ignore_patterns("thai-data.xdelta", "*.zip"))
    p = core.Plan(d, res=res)
    chk("ตรวจเจอว่าขาดอะไร", p.missing_pieces(), ["thai-data.xdelta"])


def case_not_a_game():
    print("=" * 70)
    print("เคส: ไม่ใช่โฟลเดอร์เกม")
    d = os.path.join(SANDBOX, "nowhere")
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    p = core.Plan(d)
    chk("ไฟล์เกมที่ขาด", sorted(p.missing_game_files()), ["data.xp3", "patch.xp3"])
    chk("ไม่มีอะไรให้แตะ", p.active, [])


def case_rollback():
    print("=" * 70)
    print("เคส: xdelta ล้มกลางคัน -> ต้องคืนไฟล์ทุกตัว")
    d = setup("rollback", "r18")
    res = os.path.join(SANDBOX, "res-corrupt")
    shutil.rmtree(res, ignore_errors=True)
    shutil.copytree(core.resource_dir(), res, ignore=shutil.ignore_patterns("*.zip"))
    # ทำให้ diff ตัวสุดท้ายเสีย -> ต้องล้มหลังจาก rename ไปแล้วทั้ง 3 ไฟล์
    with open(os.path.join(res, "thai-adult.xdelta"), "r+b") as f:
        f.seek(64)
        f.write(b"\xff" * 4096)

    p = core.Plan(d, res=res)
    chk("verify", p.verify(), "ready")
    try:
        p.install()
        chk("ต้อง raise", "ไม่ raise", "raise")
    except RuntimeError as e:
        chk("raise พร้อมบอกไฟล์ที่ล้ม", "adult.xp3" in str(e), True)
    chk("คืนไฟล์ครบ = ต้นฉบับ", hashes(p), expect(p, "orig"))
    chk("ไม่มี .bak ค้าง", any(os.path.isfile(t.bak) for t in p.active), False)


def case_originals_intact():
    print("=" * 70)
    print("เคส: ไฟล์ต้นฉบับจริงต้องไม่ถูกแตะ")
    p = core.Plan(GAME)
    by = {t.name: t for t in p.targets}
    for name, pristine in PRISTINE.items():
        path = os.path.join(GAME, pristine)
        if os.path.isfile(path):
            chk(pristine, core.sha256(path), by[name].orig)


if __name__ == "__main__":
    if not os.environ.get("SBTP_RES") and not os.path.isfile(
            os.path.join(core.resource_dir(), "manifest.json")):
        sys.exit("ตั้ง SBTP_RES ให้ชี้ไปที่โฟลเดอร์ชุดติดตั้งที่ build_release.py สร้างก่อน")
    print("resource_dir: %s" % core.resource_dir())
    print("game        : %s\n" % GAME)
    try:
        full_cycle("r18", "r18")
        full_cycle("allages", "allages")
        case_bad_adult()
        case_missing_delta()
        case_not_a_game()
        case_rollback()
        case_originals_intact()
    finally:
        shutil.rmtree(SANDBOX, ignore_errors=True)

    print("=" * 70)
    if fails:
        print("ตก %d เคส: %s" % (len(fails), ", ".join(fails)))
        sys.exit(1)
    print("ผ่านทั้งหมด")
