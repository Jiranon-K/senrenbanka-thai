#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shape.py — สี่เหลี่ยมมุมโค้งแบบขอบเนียน (anti-aliased) สำหรับ Tk

Canvas ของ Tk บน Windows วาดรูปทรงแบบไม่มี anti-aliasing — มุมโค้ง 6-8 px
จะเป็นขั้นบันไดชัดเจน ซึ่งทำลายลุค shadcn ทั้งหมด
ทางออก: วาดเป็น PhotoImage เองโดยรู้สีพื้นข้างใต้อยู่แล้ว (ทุกจอพื้นทึบ)
จึงผสมสีขอบกับพื้นตรงๆ ได้ ไม่ต้องใช้ alpha และไม่ต้องพึ่ง PIL

  * ส่วนกลางกับเส้นขอบตรง เทสีทีเดียวด้วย put(color, to=box) — เร็วมาก
  * คำนวณทีละพิกเซลเฉพาะสี่มุม (สุ่ม 4x4 จุดย่อยต่อพิกเซล) — มุมละ r² พิกเซล
  * เก็บผลไว้ใน cache แบบจำกัดขนาด: ทวีนสีปุ่มสร้างสีใหม่ทุกเฟรม ห้ามโตไม่สิ้นสุด
"""
from __future__ import annotations

from collections import OrderedDict

import tkinter as tk

import theme as T

_SS = 4                                   # จุดย่อยต่อแกนต่อพิกเซล
_SUB = [(i + 0.5) / _SS for i in range(_SS)]
_CACHE: "OrderedDict[tuple, tk.PhotoImage]" = OrderedDict()
_CACHE_MAX = 400


def _cover(x: int, y: int, x0: float, y0: float, x1: float, y1: float, r: float) -> float:
    """สัดส่วนของพิกเซล (x, y) ที่อยู่ในสี่เหลี่ยมมุมโค้ง (x0,y0)-(x1,y1) รัศมี r"""
    if r <= 0:
        return 1.0 if x0 <= x + 0.5 < x1 and y0 <= y + 0.5 < y1 else 0.0
    hit = 0
    for sy in _SUB:
        py = y + sy
        if not y0 <= py < y1:
            continue
        for sx in _SUB:
            px = x + sx
            if not x0 <= px < x1:
                continue
            # ระยะเกินเข้าไปในโซนมุม (0 ถ้าอยู่ในช่วงตรง)
            dx = (x0 + r - px) if px < x0 + r else (px - (x1 - r)) if px > x1 - r else 0.0
            dy = (y0 + r - py) if py < y0 + r else (py - (y1 - r)) if py > y1 - r else 0.0
            if dx * dx + dy * dy <= r * r:
                hit += 1
    return hit / (_SS * _SS)


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def _mask(w: int, h: int, r: float, b: int) -> list:
    """พิกเซลมุมที่ต้องผสมสีเอง: [(y, [(x_start, [(outer, inner), ...]), ...]), ...]

    ขึ้นกับรูปทรงอย่างเดียว ไม่ขึ้นกับสี — ทวีนสีปุ่มจึงคำนวณส่วนนี้ครั้งเดียว
    """
    key = (w, h, r, b)
    got = _MASKS.get(key)
    if got is not None:
        return got
    ri = max(0.0, r - b)
    n = int(r) + 1 + b                    # ขนาดโซนมุมที่ต้องคำนวณทีละพิกเซล
    spans = [range(0, min(n, w))]
    if w - n > n:
        spans.append(range(w - n, w))
    else:
        spans = [range(0, w)]
    ys = sorted(set(list(range(0, min(n, h))) + list(range(max(0, h - n), h))))
    rows = []
    for y in ys:
        segs = []
        for sp in spans:
            cov = []
            for x in sp:
                o = _cover(x, y, 0, 0, w, h, r)
                i = _cover(x, y, b, b, w - b, h - b, ri) if b else o
                cov.append((o, i))
            segs.append((sp.start, cov))
        rows.append((y, segs))
    _MASKS[key] = rows
    return rows


_MASKS: dict = {}


def rrect(master, w: int, h: int, r: float, fill: str, bg: str,
          border: str | None = None, bw: int = 1) -> tk.PhotoImage:
    """PhotoImage ขนาด w x h: สี่เหลี่ยมมุมโค้ง fill (+ เส้นขอบ border) บนพื้น bg

    ผู้เรียกต้องเก็บ reference ของรูปที่ได้ไว้เองตราบที่ยังแสดงอยู่ —
    cache ทิ้งของเก่าได้ทุกเมื่อ และ PhotoImage ที่ไม่มีใครถือจะหายจากจอ
    """
    w, h = max(1, int(w)), max(1, int(h))
    r = max(0.0, min(float(r), w / 2.0, h / 2.0))
    key = (w, h, r, fill, bg, border, bw)
    img = _CACHE.get(key)
    if img is not None:
        _CACHE.move_to_end(key)
        return img

    img = tk.PhotoImage(master=master, width=w, height=h)
    edge = border or fill
    b = bw if border else 0
    img.put(fill, to=(0, 0, w, h))
    if b:
        img.put(edge, to=(0, 0, w, b))
        img.put(edge, to=(0, h - b, w, h))
        img.put(edge, to=(0, 0, b, h))
        img.put(edge, to=(w - b, 0, w, h))

    cb, ce, cf = T.rgb(bg), T.rgb(edge), T.rgb(fill)
    memo = {}
    for y, segs in _mask(w, h, r, b):
        for x0, cov in segs:
            row = []
            for oi in cov:
                c = memo.get(oi)
                if c is None:
                    o, i = oi
                    c = memo[oi] = _hex([cb[k] * (1 - o) + ce[k] * (o - i) + cf[k] * i
                                         for k in range(3)])
                row.append(c)
            img.put("{" + " ".join(row) + "}", to=(x0, y))

    _CACHE[key] = img
    if len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return img


def _seg_dist(px: float, py: float, a, b) -> float:
    (x1, y1), (x2, y2) = a, b
    dx, dy = x2 - x1, y2 - y1
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L))
    ex, ey = x1 + t * dx - px, y1 + t * dy - py
    return (ex * ex + ey * ey) ** 0.5


def marked(master, w: int, h: int, r: float, fill: str, bg: str, lines: list,
           sw: float, color: str, border: str | None = None) -> tk.PhotoImage:
    """รูปทรงมุมโค้ง + เส้น (เครื่องหมายถูก/กากบาท) ที่ขอบเนียน ปลายมน

    เส้นของ Canvas ไม่มี anti-aliasing เหมือนกัน เส้นทแยง 2-3 px จึงหยักชัด
    ที่นี่คิด coverage จากระยะถึงเส้นตรงๆ (คำนวณครั้งเดียวต่อพิกเซล ไม่ต้องสุ่ม)
    เส้นต้องอยู่ในเนื้อของรูปทรง — ใต้เส้นถือว่าเป็นสี fill เสมอ
    ได้รูปใหม่ทุกครั้ง (ไม่ cache) เพราะเรียกระหว่างอนิเมชันที่เส้นยาวขึ้นทุกเฟรม
    """
    base = rrect(master, w, h, r, fill, bg, border)
    img = tk.PhotoImage(master=master, width=w, height=h)
    img.tk.call(img, "copy", base)
    segs = [(p, q) for pl in lines for p, q in zip(pl, pl[1:])]
    if not segs:
        return img
    half = sw / 2.0
    xs = [c[0] for s in segs for c in s]
    ys = [c[1] for s in segs for c in s]
    x0, x1 = max(0, int(min(xs) - half - 1)), min(w, int(max(xs) + half + 2))
    y0, y1 = max(0, int(min(ys) - half - 1)), min(h, int(max(ys) + half + 2))
    cf, cs = T.rgb(fill), T.rgb(color)
    for y in range(y0, y1):
        row = []
        for x in range(x0, x1):
            d = min(_seg_dist(x + 0.5, y + 0.5, a, b) for a, b in segs)
            a = max(0.0, min(1.0, half + 0.5 - d))
            row.append(_hex([cf[k] + (cs[k] - cf[k]) * a for k in range(3)]))
        img.put("{" + " ".join(row) + "}", to=(x0, y))
    return img
