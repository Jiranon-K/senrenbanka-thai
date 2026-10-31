#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import ctypes
import os
import time

FRAME_MS = 16

_root = None
_tweens: list = []
_job = None
_hires = False
_enabled = True


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
    u = t - 1
    return 1 + (s + 1) * u ** 3 + s * u ** 2


def out_elastic(t, p=0.35):
    if t <= 0 or t >= 1:
        return float(t)
    import math
    return 2 ** (-10 * t) * math.sin((t - p / 4) * (2 * math.pi) / p) + 1


def motion_ok() -> bool:
    if os.environ.get("SBTP_NO_ANIM"):
        return False
    try:
        v = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x1042, 0, ctypes.byref(v), 0)
        return bool(v.value) if ok else True
    except Exception:
        return True


def setup(root, enabled=None):
    global _root, _enabled, _tweens, _job
    _root, _tweens, _job = root, [], None
    _enabled = motion_ok() if enabled is None else bool(enabled)
    return _enabled


def enabled() -> bool:
    return _enabled


class Tween:
    __slots__ = ("dur", "apply", "ease", "delay", "done", "key", "t0")

    def __init__(self, dur, apply, ease, delay, done, key):
        self.dur, self.apply, self.ease = dur, apply, ease
        self.delay, self.done, self.key = delay, done, key
        self.t0 = time.perf_counter()

    def _step(self, now) -> bool:
        e = now - self.t0 - self.delay
        if e < 0:
            return False
        p = 1.0 if self.dur <= 0 else min(1.0, e / self.dur)
        self.apply(self.ease(p))
        return p >= 1.0


def tween(dur, apply, ease=out_cubic, delay=0.0, done=None, key=None):
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
    for tw in [t for t in _tweens if t.key == key]:
        _tweens.remove(tw)


def finish(key):
    for tw in [t for t in _tweens if t.key == key]:
        _tweens.remove(tw)
        _safe(tw.apply, 1.0)
        if tw.done:
            tw.done()


def running() -> int:
    return len(_tweens)


def stagger(items, each, gap=0.045, start=0.0):
    for i, it in enumerate(items):
        each(i, it, start + i * gap)


def _safe(fn, v):
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
            ctypes.windll.winmm.timeBeginPeriod(1)
            _hires = True
        except Exception:
            pass
    _job = _root.after(FRAME_MS, _tick)


def _stop():
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
    _job = None
    now = time.perf_counter()
    for tw in list(_tweens):
        if tw not in _tweens:
            continue
        try:
            over = tw._step(now)
        except Exception:
            over = True
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
