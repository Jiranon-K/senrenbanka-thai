#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_render.py — draw Thai over the CN-slot UI layers listed in tools/ui_labels.tsv.

For each layer the CN text is found by comparing the CN layer with its JP and EN
twins (same name, placed by their own left/top): a pixel is CN text when it differs
from both. Those pixels are refilled from a twin that has no text there. Then the
Thai label is shaped with harfbuzz, rasterized with FreeType, and drawn in the CN
text colour, inside the area the CN text occupied.

    python tools/ui_render.py sys_page0 sys_base   # -> thai_work/ui/th/<sheet>/
                                                   #    thai_work/ui/review/<sheet>.png

Inputs : thai_work/ui/pimg/<sheet>_{cn,jp,en}.json + layer PNGs (ui_assets inventory)
         thai_work/fonts/ui/NotoSerifThai.ttf, tools/gui/ui/fonts/Sarabun-*.ttf
"""
from __future__ import annotations

import csv
import json
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

UI = os.path.join(P.WORK, "ui")
PIMG = os.path.join(UI, "pimg")
TODO = os.path.join(UI, "todo")
TH = os.path.join(UI, "th")
REVIEW = os.path.join(UI, "review")
LABELS = os.path.join(P.TOOLS, "ui_labels.tsv")

SERIF = os.path.join(P.WORK, "fonts", "ui", "NotoSerifThai.ttf")
SANS = os.path.join(P.TOOLS, "gui", "ui", "fonts", "Sarabun-SemiBold.ttf")

THRESH = 48
GROW = 2
DONOR = {"heading": (240, 60), "title": (110, 0), "button": (40, 22)}

STYLE = {
    "title":   dict(font=SERIF, wght=800, scale=0.95, align="left", pad=6),
    "heading": dict(font=SERIF, wght=700, scale=1.0, align="left", pad=3),
    "tab":     dict(font=SANS, wght=None, scale=0.92, align="left", pad=2),
    "button":  dict(font=SANS, wght=None, scale=0.92, align="center", pad=3),
}


class RenderError(RuntimeError):
    pass


def load_labels(sheet: str) -> dict[str, dict]:
    with open(LABELS, encoding="utf-8") as f:
        return {r["layer"]: r for r in csv.DictReader(f, delimiter="\t") if r["sheet"] == sheet}


def sheet_layers(sheet: str, lang: str) -> list[dict]:
    js = os.path.join(PIMG, "%s_%s.json" % (sheet, lang))
    meta = json.load(open(js, encoding="utf-8"))
    base = os.path.splitext(js)[0]
    out = []
    for L in meta["layers"]:
        png = os.path.join(base, "%d.png" % L["layer_id"])
        if os.path.exists(png):
            out.append(dict(L, png=png))
    return out


def label_keys(layers: list[dict]) -> dict[int, str]:
    by_name: dict[str, set] = {}
    for L in layers:
        by_name.setdefault(L["name"].split(":")[0].lstrip("@"), set()).add(L.get("group_layer_id"))
    keys = {}
    for L in layers:
        base = L["name"].split(":")[0].lstrip("@")
        groups = by_name[base]
        if len(groups) > 1:
            order = sorted(groups, key=lambda g: min(x["left"] for x in layers
                                                     if x.get("group_layer_id") == g
                                                     and x["name"].split(":")[0].lstrip("@") == base))
            base = "%s~%d" % (base, order.index(L.get("group_layer_id")) + 1)
        keys[L["layer_id"]] = base
    return keys


def premul(im: Image.Image) -> list[Image.Image]:
    r, g, b, a = im.split()
    return [ImageChops.multiply(c, a) for c in (r, g, b)] + [a]


def diff(a: Image.Image, b: Image.Image) -> Image.Image:
    out = None
    for x, y in zip(premul(a), premul(b)):
        d = ImageChops.difference(x, y)
        out = d if out is None else ImageChops.lighter(out, d)
    return out


def placed(twin: dict, ref: dict, cn: Image.Image) -> Image.Image:
    with Image.open(twin["png"]) as im:
        src = im.convert("RGBA")
    best = None
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            canvas = Image.new("RGBA", cn.size, (0, 0, 0, 0))
            canvas.paste(src, (twin["left"] - ref["left"] + dx, twin["top"] - ref["top"] + dy))
            hist = binary(diff(cn, canvas)).histogram()
            score = hist[255]
            if best is None or score < best[0]:
                best = (score, canvas)
    return best[1]


def binary(d: Image.Image) -> Image.Image:
    return d.point(lambda v: 255 if v > THRESH else 0)


def grow(m: Image.Image, px: int = GROW) -> Image.Image:
    return m.filter(ImageFilter.MaxFilter(2 * px + 1)) if px else m


def AND(a, b):
    return ImageChops.multiply(a, b)


def NOT(a):
    return ImageChops.invert(a)


def text_mask(cn: Image.Image, jp: Image.Image, en: Image.Image) -> Image.Image:
    own = grow(binary(diff(cn, cn.filter(ImageFilter.MedianFilter(9)))), 1)
    return AND(own, AND(binary(diff(cn, jp)), binary(diff(cn, en))))


def period(strip: Image.Image, lo: int = 4, hi: int = 80) -> int:
    w = strip.width
    best = []
    for p in range(lo, min(hi, w // 2) + 1):
        a, b = strip.crop((0, 0, w - p, strip.height)), strip.crop((p, 0, w, strip.height))
        hist = diff(a, b).histogram()
        n = sum(hist) or 1
        best.append((sum(v * c for v, c in enumerate(hist)) / n, p))
    if not best:
        return 1
    floor = min(v for v, _ in best)
    return next(p for v, p in best if v <= floor * 1.15 + 0.5)


def fill(img: Image.Image, box, donor: tuple[int, int]) -> Image.Image:
    x0, y0, x1, y1 = box
    d0, d1 = donor
    if d1 - d0 < 4:
        raise RenderError("no clean donor strip beside %s" % (box,))
    p = period(img.crop((d0, y0, d1, y1)))
    span = (d1 - d0) // p * p or p
    out = img.copy()
    for x in range(x0, x1):
        sx = d0 + (x - d0) % span if x >= d0 else d0 + (span - (d0 - x) % span) % span
        out.paste(img.crop((sx, y0, sx + 1, y1)), (x, y0))
    return out


def clear(img: Image.Image, box) -> Image.Image:
    out = img.copy()
    out.paste((0, 0, 0, 0), box)
    return out


def spans(profile: list[int], gap: int) -> list[tuple[int, int]]:
    out, start, last = [], None, None
    for i, v in enumerate(profile):
        if v:
            if start is None:
                start = i
            elif i - last > gap:
                out.append((start, last + 1))
                start = i
            last = i
    if start is not None:
        out.append((start, last + 1))
    return out


def strip_lines(mask: Image.Image) -> Image.Image:
    w, h = mask.size
    out = mask.copy()
    for y in range(h):
        if mask.crop((0, y, w, y + 1)).histogram()[255] > w * 0.5:
            out.paste(0, (0, y, w, y + 1))
    for x in range(w):
        if mask.crop((x, 0, x + 1, h)).histogram()[255] > h * 0.6:
            out.paste(0, (x, 0, x + 1, h))
    return out


def text_boxes(mask: Image.Image, min_area: int = 12) -> list[tuple[int, int, int, int]]:
    mask = strip_lines(mask)
    w, h = mask.size
    rows = [1 if mask.crop((0, y, w, y + 1)).getbbox() else 0 for y in range(h)]
    boxes = []
    for y0, y1 in spans(rows, 6):
        band = mask.crop((0, y0, w, y1))
        cols = [1 if band.crop((x, 0, x + 1, y1 - y0)).getbbox() else 0 for x in range(w)]
        for x0, x1 in spans(cols, 16):
            bb = mask.crop((x0, y0, x1, y1)).getbbox()
            if bb and (bb[2] - bb[0]) * (bb[3] - bb[1]) >= min_area:
                boxes.append((x0 + bb[0], y0 + bb[1], x0 + bb[2], y0 + bb[3]))
    return boxes


def reading_order(boxes, width):
    mid = width / 2
    return sorted(boxes, key=lambda b: (b[0] >= mid, b[1], b[0]))


def ink(cn: Image.Image, clean: Image.Image, box) -> tuple:
    a, b = cn.crop(box), clean.crop(box)
    d = diff(a, b)
    top = max(d.getdata()) or 1
    px = [p for p, k in zip(a.getdata(), d.getdata()) if k >= top * 0.75 and p[3] > 0]
    n = len(px) or 1
    return tuple(int(sum(p[i] for p in px) / n) for i in range(3)) + (max(p[3] for p in px) if px else 255,)


class Face:
    def __init__(self, path: str, wght: int | None):
        import freetype
        import uharfbuzz as hb
        self.path = path
        self.ft = freetype.Face(path)
        blob = hb.Blob.from_file_path(path)
        self.hb = hb.Font(hb.Face(blob))
        self.tags = ([a.tag for a in self.ft.get_variation_info().axes]
                     if self.ft.has_multiple_masters else [])
        self.axes = {}
        if wght is not None:
            self.axes["wght"] = wght

    def set(self, size_px: int, wdth: float | None = None):
        axes = dict(self.axes)
        if wdth is not None:
            axes["wdth"] = wdth
        self.size = size_px
        self.ft.set_pixel_sizes(0, size_px)
        if axes:
            self.ft.set_var_design_coords([axes.get(a.tag, a.default)
                                           for a in self.ft.get_variation_info().axes])
            self.hb.set_variations(axes)
        self.hb.scale = (size_px * 64, size_px * 64)

    def render(self, text: str) -> tuple[Image.Image, int]:
        import freetype
        import uharfbuzz as hb
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        asc = self.ft.size.ascender // 64
        desc = -self.ft.size.descender // 64
        pad = self.size
        width = sum(p.x_advance for p in buf.glyph_positions) // 64 + 2 * pad
        img = Image.new("L", (max(width, 1), asc + desc + 2 * pad), 0)
        x = pad * 64
        base = pad + asc
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            self.ft.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER | freetype.FT_LOAD_NO_HINTING)
            g = self.ft.glyph
            bm = g.bitmap
            if bm.width and bm.rows:
                glyph = Image.frombytes("L", (bm.width, bm.rows), bytes(bm.buffer), "raw", "L", bm.pitch)
                gx = (x + pos.x_offset) // 64 + g.bitmap_left
                gy = base - pos.y_offset // 64 - g.bitmap_top
                img.paste(ImageChops.lighter(img.crop((gx, gy, gx + bm.width, gy + bm.rows)), glyph),
                          (gx, gy))
            x += pos.x_advance
        return img, base


def consonant_height(face: Face) -> int:
    img, _ = face.render("กนม")
    bb = img.getbbox()
    return bb[3] - bb[1]


def fit(face: Face, text: str, target_h: int, max_w: int, max_h: int, condense: bool):
    size = 40
    face.set(size)
    ch = consonant_height(face)
    size = max(8, round(size * target_h / ch))
    widths = [None, 87.5, 75.0, 62.5] if condense else [None]
    while size >= 8:
        for wdth in widths:
            face.set(size, wdth)
            img, base = face.render(text)
            bb = img.getbbox()
            if bb and bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
                return img.crop(bb), base - bb[1], size, wdth
        size -= 1
    raise RenderError("%r does not fit in %dx%d" % (text, max_w, max_h))


def draw_label(clean: Image.Image, box, colour, text: str, kind: str, faces: dict,
               area: tuple[int, int, int, int]):
    st = STYLE[kind]
    face = faces[(st["font"], st["wght"])]
    x0, y0, x1, y1 = box
    h_cn = y1 - y0
    ax0, ay0, ax1, ay1 = area
    target = max(6, round(h_cn * st["scale"] * 0.62))
    condense = "wdth" in face.tags
    if st["align"] == "center":
        max_w = ax1 - ax0
    else:
        max_w = ax1 - x0
    glyphs, base, size, wdth = fit(face, text, target, max_w, ay1 - ay0, condense)
    w, h = glyphs.size
    cy = (y0 + y1) / 2
    if st["align"] == "center":
        left = min(max(round((x0 + x1) / 2 - w / 2), ax0), ax1 - w)
    else:
        left = x0
    top = round(cy - h / 2)
    top = min(max(top, ay0), ay1 - h)
    r, g, b, a = colour
    paint = Image.new("RGBA", glyphs.size, (r, g, b, 0))
    paint.putalpha(glyphs.point(lambda v: v * a // 255))
    out = clean.copy()
    out.alpha_composite(paint, (left, top))
    return out, (left, top, left + w, top + h), size, wdth


def layer_area(kind: str, size, box, pad: int):
    w, h = size
    x0, y0, x1, y1 = box
    hh = y1 - y0
    if kind == "button":
        return (max(0, x0 - hh), max(0, y0 - pad), min(w, x1 + hh), min(h, y1 + pad))
    if kind == "tab":
        return (x0, max(0, y0 - pad - 2), w - 1, min(h, y1 + pad))
    if kind == "heading":
        return (x0, max(0, y0 - round(hh * 0.3)), min(w, x0 + 760), min(h, y1 + round(hh * 0.3)))
    return (x0, max(0, y0 - pad), min(w, x0 + 520), min(h, y1 + pad))


def render_sheet(sheet: str) -> list[dict]:
    labels = load_labels(sheet)
    cn_layers = sheet_layers(sheet, "cn")
    keys = label_keys(cn_layers)
    twins = {}
    for lang in ("jp", "en"):
        ls = sheet_layers(sheet, lang)
        k = label_keys(ls)
        twins[lang] = {(k[L["layer_id"]], L["name"]): L for L in ls}
    todo = {int(f.split("_", 1)[0]): f for f in os.listdir(os.path.join(TODO, sheet)) if f.endswith(".png")}
    faces = {}
    for st in STYLE.values():
        faces.setdefault((st["font"], st["wght"]), Face(st["font"], st["wght"]))
    out_dir = os.path.join(TH, sheet)
    os.makedirs(out_dir, exist_ok=True)
    report = []
    for L in cn_layers:
        if L["layer_id"] not in todo:
            continue
        key = keys[L["layer_id"]]
        targets = [k for k in labels if k == key or k.split("#")[0] == key]
        if not targets:
            report.append(dict(layer=todo[L["layer_id"]], status="no label"))
            continue
        jp, en = twins["jp"].get((key, L["name"])), twins["en"].get((key, L["name"]))
        if not jp or not en:
            report.append(dict(layer=todo[L["layer_id"]], status="no JP/EN twin"))
            continue
        with Image.open(L["png"]) as im:
            cn = im.convert("RGBA")
        mask = text_mask(cn, placed(jp, L, cn), placed(en, L, cn))
        if targets == [key]:
            boxes = text_boxes(mask)
            ink_px = lambda b: mask.crop(b).histogram()[255]
            pairs = [(labels[key], max(boxes, key=ink_px))] if boxes else []
        else:
            boxes = reading_order(text_boxes(mask), cn.width)
            want = sorted(targets, key=lambda k: int(k.split("#")[1]))
            if len(boxes) != len(want):
                raise RenderError("%s: found %d text blocks, labels list %d: %s"
                                  % (todo[L["layer_id"]], len(boxes), len(want), boxes))
            pairs = [(labels[k], b) for k, b in zip(want, boxes)]
            cols = {}
            for _, b in pairs:
                c = b[0] >= cn.width / 2
                cols[c] = min(cols.get(c, b[0]), b[0])
            pairs = [(lab, (cols[b[0] >= cn.width / 2],) + b[1:]) for lab, b in pairs]
        img = cn
        for lab, box in pairs:
            kind = lab["kind"]
            g = (max(0, box[0] - 3), max(0, box[1] - 3), min(cn.width, box[2] + 3), min(cn.height, box[3] + 3))
            if kind == "tab":
                img = clear(img, g)
            else:
                room = DONOR[kind]
                img = fill(img, g, (g[2] + 2, min(cn.width - room[1], g[2] + 2 + room[0])))
        clean = img
        for lab, box in pairs:
            kind = lab["kind"]
            colour = ink(cn, clean, box)
            area = layer_area(kind, cn.size, box, STYLE[kind]["pad"])
            img, drawn, size, wdth = draw_label(img, box, colour, lab["thai"], kind, faces, area)
            inside = (drawn[0] >= area[0] and drawn[1] >= area[1]
                      and drawn[2] <= area[2] and drawn[3] <= area[3])
            report.append(dict(layer=todo[L["layer_id"]], label=lab["thai"], cn_box=box,
                               drawn=drawn, area=area, size=size, wdth=wdth,
                               colour=colour, status="ok" if inside else "OVERFLOW"))
        img.save(os.path.join(out_dir, todo[L["layer_id"]]))
    return report


def contact_sheet(sheet: str, path: str, scale_big: float = 0.5):
    names = sorted(f for f in os.listdir(os.path.join(TH, sheet)) if f.endswith(".png"))
    tiles = []
    for n in names:
        a = Image.open(os.path.join(TODO, sheet, n)).convert("RGBA")
        b = Image.open(os.path.join(TH, sheet, n)).convert("RGBA")
        if a.width > 600:
            a = a.resize((int(a.width * scale_big), int(a.height * scale_big)), Image.LANCZOS)
            b = b.resize(a.size, Image.LANCZOS)
        tiles.append((n, a, b))
    W = max(2 * a.width for _, a, _ in tiles) + 30
    H = sum(a.height + 26 for _, a, _ in tiles) + 10
    sheet_img = Image.new("RGBA", (W, H), (74, 70, 70, 255))
    d = ImageDraw.Draw(sheet_img)
    y = 5
    for n, a, b in tiles:
        d.text((8, y), n, fill=(230, 230, 230, 255))
        sheet_img.alpha_composite(a, (10, y + 14))
        sheet_img.alpha_composite(b, (20 + a.width, y + 14))
        y += a.height + 26
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet_img.save(path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    bad = 0
    for sheet in sys.argv[1:]:
        rep = render_sheet(sheet)
        for r in rep:
            if r["status"] != "ok":
                bad += 1
            print("  %-8s %-34s %s" % (r["status"], r["layer"], r.get("label", "")))
        contact_sheet(sheet, os.path.join(REVIEW, sheet + ".png"))
        print("%s: %d rows, review -> %s" % (sheet, len(rep), os.path.join(REVIEW, sheet + ".png")))
    sys.exit(1 if bad else 0)
