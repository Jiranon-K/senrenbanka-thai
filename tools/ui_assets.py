#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_assets.py — find every UI image that carries localized text, and hand it out
for translation.

The patch overwrites the game's CN slot (see CONTEXT.md), so the UI images to
translate are exactly the CN-slot ones in data.xp3:

    uipsd/cn/*_cn.pimg      layered UI sheets (title, system, save/load, backlog...)
    **/*_cn.png|PNG         single images (title_bg, attention, about dialog...)

A pimg holds dozens of layers and most are artwork shared by every language.
A layer is "text" when the CN layer differs clearly (beyond compression noise)
from the JP layer with the same name and size — the language versions only
diverge where words were drawn. That turns ~1,000 layers into a short list a person can work on.

    python tools/ui_assets.py inventory     # decompile + classify + export todo/

Inputs : thai_work/ui/orig/   (GARbro extract of data.xp3, -KeepPaths)
Outputs: thai_work/ui/pimg/   (FreeMote decompile, cn + jp)
         thai_work/ui/todo/   (images to redraw in Thai, plus EN references)
         thai_work/ui/ui_manifest.csv
"""
import os, sys, csv, json, glob, shutil, subprocess, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

UI = os.path.join(P.WORK, "ui")
ORIG = os.path.join(UI, "orig")
DECOMP = os.path.join(UI, "pimg")
TODO = os.path.join(UI, "todo")
MANIFEST = os.path.join(UI, "ui_manifest.csv")

FIELDS = ["kind", "source", "layer_id", "name", "width", "height", "left", "top",
          "todo", "en_ref"]


def decompile(pimg: str) -> str:
    """Decompile one pimg into DECOMP/<stem>/ and return the json path."""
    os.makedirs(DECOMP, exist_ok=True)
    stem = os.path.splitext(os.path.basename(pimg))[0]
    js = os.path.join(DECOMP, stem + ".json")
    if not os.path.exists(js):
        dst = os.path.join(DECOMP, os.path.basename(pimg))
        shutil.copyfile(pimg, dst)
        subprocess.run([P.PSB_DECOMPILE, os.path.abspath(dst)], capture_output=True)
    if not os.path.exists(js):
        raise RuntimeError("FreeMote could not decompile " + pimg)
    return js


def layers(js: str) -> list[dict]:
    """Image layers of a decompiled pimg, each with its png path attached."""
    meta = json.load(open(js, encoding="utf-8"))
    base = os.path.splitext(js)[0]
    out = []
    for L in meta.get("layers", []):
        png = os.path.join(base, "%d.png" % L["layer_id"])
        if os.path.exists(png):
            out.append(dict(L, png=png))
    return out


def differs(png_a: str, png_b: str, threshold: int = 64) -> bool:
    """True when the two layers differ by more than compression noise.

    Every language's sheet was encoded separately, so even pure artwork (the
    title background) differs by a few levels here and there. Drawn text moves
    pixels by far more, so count only channel differences above `threshold`,
    after premultiplying by alpha so changes in invisible pixels don't count.
    """
    from PIL import Image, ImageChops

    def premul(im):
        r, g, b, a = im.convert("RGBA").split()
        return [ImageChops.multiply(c, a) for c in (r, g, b)] + [a]

    with Image.open(png_a) as a, Image.open(png_b) as b:
        # A text layer is cropped to its words, so its size changes with the
        # language. Artwork may be re-cropped by a pixel or two; compare the overlap.
        if abs(a.width - b.width) > 4 or abs(a.height - b.height) > 4:
            return True
        box = (0, 0, min(a.width, b.width), min(a.height, b.height))
        a, b = a.crop(box), b.crop(box)
        diff = None
        for x, y in zip(premul(a), premul(b)):
            d = ImageChops.difference(x, y)
            diff = d if diff is None else ImageChops.lighter(diff, d)
    return diff.point(lambda v: 255 if v > threshold else 0).getbbox() is not None


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|%@\s]+', "_", name).strip("_") or "layer"


def cmd_inventory():
    rows = []

    # 1) layered sheets: keep CN layers that differ from their JP twin
    for cn in sorted(glob.glob(os.path.join(ORIG, "uipsd", "cn", "*_cn.pimg"))):
        stem = os.path.basename(cn)[:-len("_cn.pimg")]
        jp = os.path.join(ORIG, "uipsd", "jp", stem + "_jp.pimg")
        en = os.path.join(ORIG, "uipsd", "en", stem + "_en.pimg")
        cn_layers = layers(decompile(cn))
        twin_sheet = jp if os.path.exists(jp) else en       # touchvolume has no JP sheet
        jp_by = {L["name"]: L
                 for L in (layers(decompile(twin_sheet)) if os.path.exists(twin_sheet) else [])}
        en_by = {L["name"]: L for L in (layers(decompile(en)) if os.path.exists(en) else [])}
        for L in cn_layers:
            key = L["name"]
            twin = jp_by.get(key)
            if twin is not None and not differs(twin["png"], L["png"]):
                continue                                   # shared artwork
            out_dir = os.path.join(TODO, stem)
            os.makedirs(out_dir, exist_ok=True)
            fname = "%d_%s.png" % (L["layer_id"], safe(L["name"]))
            shutil.copyfile(L["png"], os.path.join(out_dir, fname))
            ref = ""
            if key in en_by:
                ref = os.path.join(out_dir, "_en", fname)
                os.makedirs(os.path.dirname(ref), exist_ok=True)
                shutil.copyfile(en_by[key]["png"], ref)
            rows.append(dict(kind="pimg-layer", source="uipsd/cn/%s_cn.pimg" % stem,
                             layer_id=L["layer_id"], name=L["name"],
                             width=L["width"], height=L["height"],
                             left=L.get("left", ""), top=L.get("top", ""),
                             todo=os.path.relpath(os.path.join(out_dir, fname), UI),
                             en_ref=os.path.relpath(ref, UI) if ref else "",
                             ) | ({} if twin else {"name": L["name"] + "  [no JP twin]"}))

    # 2) single images whose file name carries the CN tag
    from PIL import Image
    for f in sorted(glob.glob(os.path.join(ORIG, "**", "*_cn.*"), recursive=True)):
        if not f.lower().endswith(".png"):
            continue
        rel = os.path.relpath(f, ORIG).replace(os.sep, "/")
        dst = os.path.join(TODO, "_images", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(f, dst)
        en = re.sub(r"_cn(\.png)$", r"_en\1", f, flags=re.I)
        ref = ""
        if os.path.exists(en):
            ref = os.path.join(TODO, "_images", "_en", os.path.relpath(en, ORIG))
            os.makedirs(os.path.dirname(ref), exist_ok=True)
            shutil.copyfile(en, ref)
        with Image.open(f) as im:
            w, h = im.size
        rows.append(dict(kind="png", source=rel, layer_id="", name=os.path.basename(f),
                         width=w, height=h, left="", top="",
                         todo=os.path.relpath(dst, UI),
                         en_ref=os.path.relpath(ref, UI) if ref else ""))

    with open(MANIFEST, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        w.writeheader()
        w.writerows(rows)

    by = {}
    for r in rows:
        by[r["source"]] = by.get(r["source"], 0) + 1
    for k, n in sorted(by.items()):
        print("%4d  %s" % (n, k))
    print("total %d images -> %s" % (len(rows), os.path.relpath(TODO, P.REPO)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd =sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "inventory":
        cmd_inventory()
    else:
        print(__doc__)
        sys.exit(2)
