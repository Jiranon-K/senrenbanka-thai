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
import glob
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

STYLE = {
    "title":   dict(font=SERIF, wght=800, scale=0.95, align="left", pad=6, fx=()),
    "heading": dict(font=SERIF, wght=700, scale=1.0, align="left", pad=3, fx=("grad",)),
    "tab":     dict(font=SANS, wght=None, scale=1.05, align="left", pad=2, fx=()),
    "button":  dict(font=SANS, wght=None, scale=1.05, align="center", pad=3, fx=()),
    "gold":    dict(font=SERIF, wght=800, scale=0.95, align="left", pad=4,
                    fx=("grad", "outline", "shadow")),
}
FLAGS = {"grad", "outline", "shadow", "flat", "center", "left", "smooth", "interp", "whole",
         "clearall", "jponly", "widen", "bottom"}
WIDEN = 80


def parse_kind(kind: str) -> tuple[str, dict, set]:
    base, *flags = kind.split("+")
    if base not in STYLE or not set(flags) <= FLAGS:
        raise RenderError("unknown kind %r" % kind)
    st = dict(STYLE[base])
    fx = set(st["fx"]) | set(flags)
    if "flat" in fx:
        fx -= {"grad", "flat"}
    for a in ("center", "left"):
        if a in fx:
            st["align"] = a
            fx.discard(a)
    return base, st, fx


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


def placed(twin: dict, ref: dict, cn: Image.Image, reach: int = 2) -> Image.Image:
    with Image.open(twin["png"]) as im:
        src = im.convert("RGBA")
    best = None
    for dy in range(-2, 3):
        for dx in range(-reach, reach + 1):
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


def clear_shadow(img: Image.Image, box) -> Image.Image:
    out = img.copy()
    px = out.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            p = px[x, y]
            if p[3] < 140 or lum(p) < 70:
                px[x, y] = (0, 0, 0, 0)
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
    rows = [mask.crop((0, y, w, y + 1)).histogram()[255] > w * 0.5 for y in range(h)]
    cols = [mask.crop((x, 0, x + 1, h)).histogram()[255] > h * 0.6 for x in range(w)]
    for flags, line in ((rows, lambda i: (0, i, w, i + 1)), (cols, lambda i: (i, 0, i + 1, h))):
        for a, b in spans([1 if f else 0 for f in flags], 0):
            if b - a <= 2:
                for i in range(a, b):
                    out.paste(0, line(i))
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


def lum(p) -> float:
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def ink_pixels(cn: Image.Image, clean: Image.Image, box, fx: set) -> list[tuple]:
    a, b = cn.crop(box), clean.crop(box)
    w = a.width
    data = list(a.getdata())
    dd = list(diff(a, b).getdata())
    keep = [(i % w, i // w, p) for i, (p, k) in enumerate(zip(data, dd)) if p[3] > 0 and k > 0]
    if "outline" in fx:
        keep = [k for k in keep if lum(k[2]) < 215] or keep
    if not keep:
        return []
    top = max(dd[y * w + x] for x, y, _ in keep) or 1
    return [k for k in keep if dd[k[1] * w + k[0]] >= top * 0.6]


def ink(cn: Image.Image, clean: Image.Image, box, fx: set = frozenset()) -> dict:
    px = ink_pixels(cn, clean, box, fx)
    if not px:
        return dict(flat=(80, 40, 20, 255), grad=None, axis=None)
    n = len(px)
    flat = tuple(int(sum(p[i] for _, _, p in px) / n) for i in range(3)) + (max(p[3] for _, _, p in px),)
    w, h = box[2] - box[0], box[3] - box[1]
    best = None
    for axis, span in (("x", w), ("y", h)):
        bins = [[] for _ in range(6)]
        for x, y, p in px:
            t = (x if axis == "x" else y) / max(1, span)
            bins[min(5, int(t * 6))].append(p)
        means = [tuple(sum(q[i] for q in b) / len(b) for i in range(3)) if b else None for b in bins]
        filled = [m for m in means if m]
        if len(filled) < 3:
            continue
        spread = max(sum(abs(u[i] - v[i]) for i in range(3)) for u in filled for v in filled)
        for i, m in enumerate(means):
            if m is None:
                means[i] = next(x for x in means[i:] + means[::-1] if x)
        if best is None or spread > best[0]:
            best = (spread, axis, means)
    if best and best[0] > 60:
        return dict(flat=flat, grad=[tuple(int(c) for c in m) for m in best[2]], axis=best[1])
    return dict(flat=flat, grad=None, axis=None)


def outline_colour(cn: Image.Image, mask: Image.Image, box) -> tuple:
    a, m = cn.crop(box), mask.crop(box)
    px = sorted((p for p, k in zip(a.getdata(), m.getdata()) if k and p[3] > 128), key=lum)
    if not px:
        return (255, 255, 250, 255)
    top = px[-max(1, len(px) // 10):]
    return tuple(int(sum(p[i] for p in top) / len(top)) for i in range(3)) + (255,)


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
        if not text:
            return Image.new("L", (1, self.size), 0), 0
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


def render_lines(face: Face, text: str, pitch: float | None = None) -> tuple[Image.Image, int]:
    lines = text.split("\\n")
    if len(lines) == 1:
        return face.render(text)
    imgs = []
    for ln in lines:
        img, _ = face.render(ln)
        bb = img.getbbox()
        imgs.append(img.crop((bb[0], 0, bb[2], img.height)) if bb else img)
    step = round(max(face.size * 1.05, pitch or 0))
    W = max(i.width for i in imgs)
    out = Image.new("L", (W, imgs[0].height + step * (len(imgs) - 1)), 0)
    for n, i in enumerate(imgs):
        x = (W - i.width) // 2
        out.paste(ImageChops.lighter(out.crop((x, n * step, x + i.width, n * step + i.height)), i),
                  (x, n * step))
    return out, 0


def fit(face: Face, text: str, target_h: int, max_w: int, max_h: int, condense: bool,
        pitch: float | None = None):
    size = 40
    face.set(size)
    ch = consonant_height(face)
    size = max(8, round(size * target_h / ch))
    widths = [None, 87.5, 75.0, 62.5] if condense else [None]
    while size >= 8:
        for wdth in widths:
            face.set(size, wdth)
            img, base = render_lines(face, text, pitch)
            bb = img.getbbox()
            if bb and bb[2] - bb[0] <= max_w and bb[3] - bb[1] <= max_h:
                return img.crop(bb), base - bb[1], size, wdth
        size -= 1
    raise RenderError("%r does not fit in %dx%d" % (text, max_w, max_h))


def draw_label(clean: Image.Image, box, paint_info: dict, text: str, kind: str, faces: dict,
               area: tuple[int, int, int, int], outline: tuple | None = None,
               line_h: int | None = None):
    base, st, fx = parse_kind(kind)
    face = faces[(st["font"], st["wght"])]
    x0, y0, x1, y1 = box
    h_cn = y1 - y0
    ax0, ay0, ax1, ay1 = area
    lines = text.count("\\n") + 1
    glyph_h = line_h or h_cn / lines
    target = max(6, round(glyph_h * st["scale"] * 0.62))
    rim = max(1, round(glyph_h * 0.07)) if "outline" in fx else 0
    pitch = h_cn / lines if lines > 1 and line_h else None
    condense = "wdth" in face.tags
    max_w = (ax1 - ax0 if st["align"] == "center" else ax1 - x0) - 2 * rim
    glyphs, _, size, wdth = fit(face, text, target, max_w, ay1 - ay0 - 2 * rim, condense, pitch)
    if rim:
        pad = Image.new("L", (glyphs.width + 2 * rim, glyphs.height + 2 * rim), 0)
        pad.paste(glyphs, (rim, rim))
        glyphs = pad
    w, h = glyphs.size
    cy = (y0 + y1) / 2
    if st["align"] == "center":
        left = min(max(round((x0 + x1) / 2 - w / 2), ax0), ax1 - w)
    else:
        left = max(ax0, x0 - rim)
    top = min(max(round(cy - h / 2), ay0), ay1 - h)
    layer = Image.new("RGBA", glyphs.size, (0, 0, 0, 0))
    if "shadow" in fx:
        src = glyphs.filter(ImageFilter.MaxFilter(2 * rim + 1)) if rim else glyphs
        moved = Image.new("L", src.size, 0)
        moved.paste(src, (1, 2))
        sh = moved.filter(ImageFilter.GaussianBlur(1)).point(lambda v: v * 150 // 255)
        layer.alpha_composite(Image.merge("RGBA", (Image.new("L", glyphs.size, 40),
                                                    Image.new("L", glyphs.size, 22),
                                                    Image.new("L", glyphs.size, 8), sh)))
    if rim:
        oc = outline or (255, 255, 250, 255)
        o = Image.new("RGBA", glyphs.size, oc[:3] + (0,))
        o.putalpha(glyphs.filter(ImageFilter.MaxFilter(2 * rim + 1)))
        layer.alpha_composite(o)
    r, g, b, a = paint_info["flat"]
    fill_img = Image.new("RGBA", glyphs.size, (r, g, b, 255))
    if "grad" in fx and paint_info.get("grad"):
        stops, axis = paint_info["grad"], paint_info["axis"]
        bb = glyphs.getbbox() or (0, 0, w, h)
        lo, hi = (bb[0], bb[2]) if axis == "x" else (bb[1], bb[3])
        d = ImageDraw.Draw(fill_img)
        for k in range(w if axis == "x" else h):
            t = min(0.9999, max(0.0, (k - lo) / max(1, hi - lo))) * (len(stops) - 1)
            i0 = int(t)
            u = t - i0
            i1 = min(i0 + 1, len(stops) - 1)
            c = tuple(int(stops[i0][q] * (1 - u) + stops[i1][q] * u) for q in range(3))
            d.line(((k, 0), (k, h)) if axis == "x" else ((0, k), (w, k)), fill=c + (255,))
    fill_img.putalpha(glyphs.point(lambda v: v * a // 255))
    layer.alpha_composite(fill_img)
    out = clean.copy()
    out.alpha_composite(layer, (left, top))
    return out, (left, top, left + w, top + h), size, wdth


def layer_area(kind: str, size, box, pad: int, right: int | None = None):
    base = kind.split("+")[0]
    w, h = size
    x0, y0, x1, y1 = box
    hh = y1 - y0
    if base == "button":
        return (max(0, x0 - hh), max(0, y0 - pad), min(w, x1 + hh), min(h, y1 + pad))
    if base == "tab":
        return (x0, max(0, y0 - pad - 2), w - 1, min(h, y1 + pad))
    lim = min(w, right if right is not None else w)
    if base == "heading":
        return (x0, max(0, y0 - round(hh * 0.3)), min(lim, x0 + 760), min(h, y1 + round(hh * 0.3)))
    return (x0, max(0, y0 - pad), min(lim, x0 + 520), min(h, y1 + pad))


def block_numbers(label_key: str) -> list[int]:
    out = []
    for part in label_key.split("#")[1].split(","):
        lo, _, hi = part.partition("-")
        out.extend(range(int(lo), int(hi or lo) + 1))
    return out


def twin_maps(sheet: str) -> dict:
    twins = {}
    for lang in ("jp", "en"):
        if not os.path.exists(os.path.join(PIMG, "%s_%s.json" % (sheet, lang))):
            continue
        ls = sheet_layers(sheet, lang)
        k = label_keys(ls)
        twins[lang] = {(k[L["layer_id"]], L["name"]): L for L in ls}
    return twins


def blocks(L: dict, key: str, cn: Image.Image, twins: dict,
           langs: tuple = ("jp", "en")) -> tuple[list, Image.Image]:
    reach = 32 if langs == ("jp",) else 2
    others = [placed(twins[g][(key, L["name"])], L, cn, reach) for g in langs
              if g in twins and (key, L["name"]) in twins[g]]
    own = grow(binary(diff(cn, cn.filter(ImageFilter.MedianFilter(9)))), 1)
    mask = own
    for o in others:
        mask = AND(mask, binary(diff(cn, o)))
    return reading_order(text_boxes(mask), cn.width), mask


def sheet_todo(sheet: str) -> dict[int, str]:
    return {int(f.split("_", 1)[0]): f for f in os.listdir(os.path.join(TODO, sheet)) if f.endswith(".png")}


IMAGES = "_images"


def image_units() -> tuple[list, dict, dict, dict]:
    root = os.path.join(TODO, IMAGES)
    rels = sorted(os.path.relpath(f, root).replace(os.sep, "/")
                  for f in glob.glob(os.path.join(root, "image", "**", "*_cn.png"), recursive=True))
    layers, keys, todo = [], {}, {}
    twins = {"jp": {}, "en": {}}
    for n, rel in enumerate(rels, 1):
        key = os.path.basename(rel)[:-len("_cn.png")]
        with Image.open(os.path.join(root, rel)) as im:
            w, h = im.size
        L = dict(layer_id=n, name=key, left=0, top=0, width=w, height=h, png=os.path.join(root, rel))
        layers.append(L)
        keys[n] = key
        todo[n] = rel
        for lang, suffix in (("jp", ".png"), ("en", "_en.png")):
            twin = os.path.join(UI, "orig", rel[:-len("_cn.png")] + suffix)
            if os.path.exists(twin):
                twins[lang][(key, key)] = dict(L, png=twin)
    return layers, keys, twins, todo


def units(sheet: str) -> tuple[list, dict, dict, dict]:
    if sheet == IMAGES:
        return image_units()
    layers = sheet_layers(sheet, "cn")
    return layers, label_keys(layers), twin_maps(sheet), sheet_todo(sheet)


def survey(sheet: str, path: str):
    cn_layers, keys, twins, todo = units(sheet)
    seen, tiles = set(), []
    order = sorted((L for L in cn_layers if L["layer_id"] in todo),
                   key=lambda L: (keys[L["layer_id"]], ":defo" not in L["name"]))
    for L in order:
        key = keys[L["layer_id"]]
        if key in seen:
            continue
        seen.add(key)
        with Image.open(L["png"]) as im:
            cn = im.convert("RGBA")
        try:
            bxs, _ = blocks(L, key, cn, twins)
        except RenderError as e:
            print("  %-28s %s" % (key, e))
            continue
        en_t = twins.get("en", {}).get((key, L["name"]))
        en = placed(en_t, L, cn) if en_t else None
        for n, b in enumerate(bxs, 1):
            pad = (max(0, b[0] - 4), max(0, b[1] - 4), min(cn.width, b[2] + 4), min(cn.height, b[3] + 4))
            a = cn.crop(pad)
            e = en.crop((max(0, b[0] - 40), pad[1], min(cn.width, b[2] + 80), pad[3])) if en else None
            print("  %-28s #%d %dx%d at %s" % (key, n, b[2] - b[0], b[3] - b[1], b[:2]))
            tiles.append(("%s#%d" % (key, n), a, e))
    if not tiles:
        return
    k = lambda im: 2 if im.height < 40 else 1
    W = 1400
    H = sum(max(t[1].height * k(t[1]), (t[2].height * k(t[2])) if t[2] else 0) + 22 for t in tiles) + 10
    img = Image.new("RGBA", (W, H), (120, 116, 110, 255))
    d = ImageDraw.Draw(img)
    y = 5
    for name, a, e in tiles:
        d.text((6, y + 4), name, fill=(255, 255, 255, 255))
        s = k(a)
        a2 = a.resize((a.width * s, a.height * s))
        img.alpha_composite(a2.crop((0, 0, min(a2.width, 640), a2.height)), (230, y))
        h = a2.height
        if e is not None:
            e2 = e.resize((e.width * s, e.height * s))
            img.alpha_composite(e2.crop((0, 0, min(e2.width, 520), e2.height)), (880, y))
            h = max(h, e2.height)
        y += h + 22
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)


def render_sheet(sheet: str) -> list[dict]:
    labels = load_labels(sheet)
    cn_layers, keys, twins, todo = units(sheet)
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
        targets = [k for k in targets if labels[k]["thai"] != "-"]
        if not targets:
            report.append(dict(layer=todo[L["layer_id"]], status="no label"))
            continue
        try:
            report.extend(render_layer(L, key, targets, labels, twins, todo, faces, out_dir))
        except RenderError as e:
            report.append(dict(layer=todo[L["layer_id"]], status="ERROR", label=str(e)))
    return report


def render_layer(L, key, targets, labels, twins, todo, faces, out_dir) -> list[dict]:
    report = []
    with Image.open(L["png"]) as im:
        cn = im.convert("RGBA")
    fxs = set().union(*(parse_kind(labels[k]["kind"])[2] for k in targets))
    bxs, mask = blocks(L, key, cn, twins, ("jp",) if "jponly" in fxs else ("jp", "en"))
    if "widen" in fxs:
        wide = Image.new("RGBA", (cn.width + WIDEN, cn.height), (0, 0, 0, 0))
        wide.paste(cn, (0, 0))
        cn = wide
        m = Image.new("L", cn.size, 0)
        m.paste(mask, (0, 0))
        mask = m
    if "bottom" in fxs:
        bxs = [b for b in bxs if b[1] >= cn.height * 0.65] or bxs
    if "clearall" in fxs:
        bb = cn.getbbox()
        if not bb:
            return [dict(layer=todo[L["layer_id"]], status="no text found")]
        bxs = [bb]
        targets = [key]
        labels = {key: labels[[k for k in labels if k == key or k.split("#")[0] == key][0]]}
    if not bxs:
        return [dict(layer=todo[L["layer_id"]], status="no text found")]
    line_h, parts = {}, {}
    if targets == [key]:
        ink_px = lambda b: mask.crop(b).histogram()[255]
        top = max(bxs, key=ink_px)
        sel = [b for b in bxs if ink_px(b) >= ink_px(top) * 0.1 and b[0] < top[2] and b[2] > top[0]]
        parts[key] = sel
        pairs = [(labels[key], (min(b[0] for b in sel), min(b[1] for b in sel),
                                max(b[2] for b in sel), max(b[3] for b in sel)))]
    else:
        pairs = []
        for k in sorted(targets, key=lambda k: block_numbers(k)[0]):
            nums = block_numbers(k)
            if max(nums) > len(bxs):
                raise RenderError("%s: label %s but only %d text blocks"
                                  % (todo[L["layer_id"]], k, len(bxs)))
            sel = [bxs[n - 1] for n in nums]
            if "whole" not in parse_kind(labels[k]["kind"])[2]:
                line_h[k] = sorted(b[3] - b[1] for b in sel)[len(sel) // 2]
            parts[k] = sel
            pairs.append((labels[k], (min(b[0] for b in sel), min(b[1] for b in sel),
                                      max(b[2] for b in sel), max(b[3] for b in sel))))
    cols = []
    for x in sorted({b[0] for _, b in pairs}):
        if cols and x - cols[-1][-1] < 60:
            cols[-1].append(x)
        else:
            cols.append([x])
    col_of = {x: c for c in cols for x in c}

    def column(b):
        c = col_of[b[0]]
        nxt = [d[0] for d in cols if d[0] > c[-1]]
        return c[0], (nxt[0] - 30 if nxt else None)
    img = Image.new("RGBA", cn.size, (0, 0, 0, 0)) if "clearall" in fxs else cn
    for lab, box in pairs:
        fx = parse_kind(lab["kind"])[2]
        if "clearall" in fx:
            continue
        if "smooth" in fx:
            img = smooth_erase(img, box)
            continue
        for b in ([box] if "whole" in fx else parts.get(lab["layer"], [box])):
            g = (max(0, b[0] - 3), max(0, b[1] - 3), min(cn.width, b[2] + 3), min(cn.height, b[3] + 3))
            if cn.width - g[2] <= 6:
                g = g[:2] + (cn.width, g[3])
            if "interp" in fx:
                img = interpolate(img, g)
            elif parse_kind(lab["kind"])[0] == "gold" and "smooth" not in fx:
                img = clear(img, (max(0, g[0] - 3), max(0, g[1] - 3), min(cn.width, g[2] + 3), min(cn.height, g[3] + 3)))
                img = clear_shadow(img, (max(0, g[0] - 14), max(0, g[1] - 14),
                                         min(cn.width, g[2] + 14), min(cn.height, g[3] + 6)))
            else:
                img = erase_box(img, g)
    clean = img
    for lab, box in pairs:
        kind = lab["kind"]
        base, st, fx = parse_kind(kind)
        right = None
        if base in ("heading", "title", "gold"):
            x_col, right = column(box)
            if base == "heading":
                box = (x_col,) + box[1:]
        info = ink(cn, clean, box, fx)
        oc = outline_colour(cn, mask, box) if "outline" in fx else None
        area = layer_area(kind, cn.size, box, st["pad"], right)
        img, drawn, size, wdth = draw_label(img, box, info, lab["thai"], kind, faces, area, oc,
                                            line_h.get(lab["layer"]))
        inside = (drawn[0] >= area[0] and drawn[1] >= area[1]
                  and drawn[2] <= area[2] and drawn[3] <= area[3])
        report.append(dict(layer=todo[L["layer_id"]], label=lab["thai"], cn_box=box,
                           drawn=drawn, area=area, size=size, wdth=wdth,
                           colour=info["flat"], status="ok" if inside else "OVERFLOW"))
    dst = os.path.join(out_dir, todo[L["layer_id"]])
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst)
    return report


def donor_end(img: Image.Image, y0: int, y1: int, x: int, step: int, limit: int) -> int:
    if not 0 <= x < img.width:
        return x
    ref = img.crop((x, y0, x + 1, y1))
    end = x
    for n in range(limit):
        c = x + step * n
        if not 1 <= c < img.width - 1:
            break
        hist = diff(ref, img.crop((c, y0, c + 1, y1))).histogram()
        mean = sum(v * k for v, k in enumerate(hist)) / max(1, sum(hist))
        if mean > 28:
            break
        end = c
    end -= step * 3
    return end + 1 if step > 0 else end


def erase_box(img: Image.Image, g) -> Image.Image:
    x0, y0, x1, y1 = g
    ring = [img.getpixel((x, y)) for x in range(x0, x1) for y in (y0, y1 - 1)
            if 0 <= y < img.height] +            [img.getpixel((x, y)) for y in range(y0, y1) for x in (x0, x1 - 1) if 0 <= x < img.width]
    if sum(1 for p in ring if p[3] < 24) > len(ring) * 0.6:
        return clear(img, g)
    w = x1 - x0
    limit = max(40, min(240, w))
    right = (x1 + 2, donor_end(img, y0, y1, x1 + 2, +1, limit))
    left = donor_end(img, y0, y1, x0 - 3, -1, limit), x0 - 2
    left = (left[0] + 1, left[1])
    for donor in sorted((right, left), key=lambda d: d[0] - d[1]):
        if donor[1] - donor[0] >= 12:
            try:
                return fill(img, g, donor)
            except RenderError:
                pass
    return interpolate(img, g)


def smooth_erase(img: Image.Image, box, steps: int = 40) -> Image.Image:
    x0, y0, x1, y1 = (max(0, box[0] - 12), max(0, box[1] - 12),
                      min(img.width, box[2] + 12), min(img.height, box[3] + 12))
    crop = img.crop((x0, y0, x1, y1))
    ink_m = grow(binary(diff(crop, crop.filter(ImageFilter.MedianFilter(9)))), 3)
    small_m = ink_m.resize((crop.width // 2, crop.height // 2), Image.BOX).point(lambda v: 255 if v else 0)
    work = crop.resize(small_m.size, Image.BOX)
    keep = work.copy()
    for n in range(steps):
        work = Image.composite(work.filter(ImageFilter.GaussianBlur(2 + n // 10)), keep, small_m)
    base = work.resize(crop.size, Image.BICUBIC)
    out = img.copy()
    out.paste(Image.composite(base, crop, ink_m.filter(ImageFilter.GaussianBlur(1))), (x0, y0))
    return out


def interpolate(img: Image.Image, g) -> Image.Image:
    x0, y0, x1, y1 = g
    lx, rx = max(0, x0 - 1), min(img.width - 1, x1)
    out = img.copy()
    px = out.load()
    for y in range(y0, y1):
        a, b = img.getpixel((lx, y)), img.getpixel((rx, y))
        for x in range(x0, x1):
            t = (x - lx) / max(1, rx - lx)
            px[x, y] = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(4))
    return out


def contact_sheet(sheet: str, path: str, scale_big: float = 0.5):
    root = os.path.join(TH, sheet)
    names = sorted(os.path.relpath(f, root) for f in glob.glob(os.path.join(root, "**", "*.png"), recursive=True))
    if not names:
        return
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
    if sys.argv[1:2] == ["survey"]:
        for sheet in sys.argv[2:]:
            print(sheet)
            survey(sheet, os.path.join(REVIEW, "survey_%s.png" % sheet))
        sys.exit(0)
    bad = 0
    for sheet in sys.argv[1:]:
        rep = render_sheet(sheet)
        for r in rep:
            if r["status"] not in ("ok", "no label"):
                bad += 1
            print("  %-8s %-34s %s" % (r["status"], r["layer"], r.get("label", "")))
        contact_sheet(sheet, os.path.join(REVIEW, sheet + ".png"))
        print("%s: %d rows, review -> %s" % (sheet, len(rep), os.path.join(REVIEW, sheet + ".png")))
    sys.exit(1 if bad else 0)
