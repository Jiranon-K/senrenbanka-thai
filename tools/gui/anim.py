#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anim.py — เครื่องยนต์ทวีนแบบ anime.js ขนาดพอดีมือ สำหรับ tkinter

แนวคิดเดียวกับ anime.js: บอก "ระยะเวลา + ฟังก์ชันผ่อน (easing) + สิ่งที่จะทำ
ในแต่ละเฟรม" แล้วปล่อยให้ตัวจับเวลากลางเดินให้

ทำไมต้องเขียนเอง ไม่ใช้ไลบรารี:
  * Tk ไม่มีระบบ animation ในตัว
  * ห้ามมี dependency เพิ่ม (`.exe` ต้องเล็กและ build ผ่านทุกเครื่อง)
  * ที่สำคัญคือต้องมี **ตัวจับเวลาตัวเดียว** สำหรับทวีนทุกตัว
    ถ้าปล่อยให้แต่ละอนิเมชันเรียก after() ของตัวเอง งานจะซ้อนกันจน Tk
    ประมวลผลไม่ทัน — เป็นสาเหตุเดียวกับที่ทำให้หน้าต่างลากแล้วกระตุก

กติกาสามข้อที่ยึดไว้:
  1. ตัวจับเวลาเดินเฉพาะตอนมีงาน หมดงานแล้วหยุด (ไม่ปลุก CPU ทิ้งไว้)
  2. เวลาอ้างจากนาฬิกาจริง ไม่ใช่นับเฟรม — เฟรมตกก็ยังจบตรงเวลา
  3. เคารพค่า "แสดงภาพเคลื่อนไหวใน Windows" ของผู้ใช้ ถ้าปิดไว้ก็ข้ามให้หมด
"""
from __future__ import annotations

import ctypes
import os
import time

FRAME_MS = 16                      # ~60 fps

_root = None
_tweens: list = []
_job = None
_hires = False
_enabled = True


# ─────────────────────────────────────────────────────────── ฟังก์ชันผ่อน
# ชื่อและสูตรตรงกับ anime.js / easings.net เพื่อให้เทียบกับดีไซน์ได้ตรงๆ

def linear(t):      return t
def out_quad(t):    return 1 - (1 - t) ** 2
def out_cubic(t):   return 1 - (1 - t) ** 3
def out_quart(t):   return 1 - (1 - t) ** 4
def out_quint(t):   return 1 - (1 - t) ** 5
def in_out_quad(t): return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
def in_out_cubic(t): return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def out_expo(t):
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def out_back(t, s=1.70158):
    """เลยเป้าไปนิดแล้วดีดกลับ — ใช้กับกล่องติ๊กให้รู้สึก 'ติดมือ'"""
    u = t - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def out_elastic(t, p=0.35):
    if t <= 0 or t >= 1:
        return float(t)
    import math
    return 2 ** (-10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1


# ─────────────────────────────────────────────────────── เปิด/ปิดทั้งระบบ

def motion_ok() -> bool:
    """ถามระบบว่าผู้ใช้เปิด 'แสดงภาพเคลื่อนไหวใน Windows' ไว้ไหม

    ตั้งค่าที่ Settings > Accessibility > Visual effects > Animation effects
    คนที่ปิดไว้มักปิดเพราะเวียนหัวหรือเครื่องช้า — ต้องเคารพ
    """
    if os.environ.get("SBTP_NO_ANIM"):
        return False
    try:
        v = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x1042, 0, ctypes.byref(v), 0)          # SPI_GETCLIENTAREAANIMATION
        return bool(v.value) if ok else True
    except Exception:
        return True


def setup(root, enabled=None):
    """ผูกกับหน้าต่างหลัก เรียกครั้งเดียวหลังสร้าง Tk()"""
    global _root, _enabled, _tweens, _job
    _root, _tweens, _job = root, [], None
    _enabled = motion_ok() if enabled is None else bool(enabled)
    return _enabled


def enabled() -> bool:
    return _enabled


# ────────────────────────────────────────────────────────────────── ทวีน

class Tween:
    __slots__ = ("dur", "apply", "ease", "delay", "done", "key", "t0")

    def __init__(self, dur, apply, ease, delay, done, key):
        self.dur, self.apply, self.ease = dur, apply, ease
        self.delay, self.done, self.key = delay, done, key
        self.t0 = time.perf_counter()

    def _step(self, now) -> bool:
        """คืน True เมื่อจบแล้ว"""
        e = now - self.t0 - self.delay
        if e < 0:
            return False
        p = 1.0 if self.dur <= 0 else min(1.0, e / self.dur)
        self.apply(self.ease(p))
        return p >= 1.0


def tween(dur, apply, ease=out_cubic, delay=0.0, done=None, key=None):
    """dur/delay หน่วยวินาที · apply(v) ถูกเรียกทุกเฟรมด้วยค่า 0→1 ที่ผ่อนแล้ว

    key: ทวีนที่ใช้ key เดียวกันจะแทนที่ตัวเก่า — กันไม่ให้อนิเมชันสองตัว
         แย่งกันเขียนค่าเดียวกัน (เช่นสีพื้นปุ่มตอนเมาส์เข้า-ออกเร็วๆ)
    """
    if key is not None:
        cancel(key)
    if not _enabled or _root is None:
        apply(1.0)
        if done:
            done()
        return None
    tw = Tween(dur, apply, ease, delay, done, key)
    if delay <= 0:
        _safe(apply, 0.0)
    _tweens.append(tw)
    _start()
    return tw


def cancel(key):
    """ทิ้งทวีนกลางคัน ไม่เรียก done"""
    for tw in [t for t in _tweens if t.key == key]:
        _tweens.remove(tw)


def finish(key):
    """กระโดดไปเฟรมสุดท้ายทันที แล้วเรียก done — ใช้ก่อนจะเขียนค่านั้นเอง"""
    for tw in [t for t in _tweens if t.key == key]:
        _tweens.remove(tw)
        _safe(tw.apply, 1.0)
        if tw.done:
            tw.done()


def running() -> int:
    return len(_tweens)


def stagger(items, each, gap=0.045, start=0.0):
    """ยิงทีละตัวห่างกัน gap วินาที — stagger ของ anime.js"""
    for i, it in enumerate(items):
        each(i, it, start + i * gap)


# ───────────────────────────────────────────────────────── ตัวจับเวลากลาง

def _safe(fn, v):
    """widget อาจถูก destroy ไปแล้วระหว่างทวีน — ปล่อยผ่าน ไม่ให้ล้มทั้งจอ"""
    try:
        fn(v)
    except Exception:
        pass


def _start():
    global _job, _hires
    if _job is not None or _root is None:
        return
    if not _hires:
        try:
            ctypes.windll.winmm.timeBeginPeriod(1)   # after() ปกติได้แค่ ~46fps
            _hires = True
        except Exception:
            pass
    _job = _root.after(FRAME_MS, _tick)


def _stop():
    """ยกเลิกนัดที่ค้างอยู่ด้วย ไม่ใช่แค่ลืมมันทิ้ง

    ถ้าแค่ตั้ง _job = None ทั้งที่ยังมีนัดค้างในคิวของ Tk พอมีทวีนตัวใหม่เข้ามา
    _start() จะเห็นว่าว่างแล้วนัดเพิ่มอีกสาย กลายเป็นตัวจับเวลาสองสายเดินขนาน
    (เทสจับได้ตอนวัดได้ 622 fps แทนที่จะเป็น 60)
    """
    global _job, _hires
    if _job is not None and _root is not None:
        try:
            _root.after_cancel(_job)
        except Exception:
            pass
    _job = None
    if _hires:
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
            _hires = False
        except Exception:
            pass


def _tick():
    global _job
    _job = None                      # นัดนี้ยิงไปแล้ว จะนัดใหม่ตอนท้ายถ้ายังมีงาน
    now = time.perf_counter()
    for tw in list(_tweens):
        if tw not in _tweens:                       # done ของตัวก่อนหน้ายกเลิกมันไปแล้ว
            continue
        try:
            over = tw._step(now)
        except Exception:
            over = True                             # widget หายไปแล้ว
        if over:
            if tw in _tweens:
                _tweens.remove(tw)
            if tw.done:
                _safe(lambda _v, f=tw.done: f(), None)
    if _tweens and _root is not None:
        _start()
    else:
        _stop()


def flush():
    """จบทวีนทุกตัวทันที — ไว้ให้เทสตรวจ "สถานะปลายทาง" โดยไม่ต้องรอเวลาจริง

    วนซ้ำเพราะ done ของทวีนหนึ่งอาจจุดทวีนตัวถัดไป (เช่นสไลด์จบแล้วค่อยเฟด)
    """
    for _ in range(24):
        if not _tweens:
            break
        for tw in list(_tweens):
            if tw in _tweens:
                _tweens.remove(tw)
            _safe(tw.apply, 1.0)
            if tw.done:
                _safe(lambda _v, f=tw.done: f(), None)
    _stop()
