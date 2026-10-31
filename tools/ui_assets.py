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
import freemote

UI = os.path.join(P.WORK, "ui")
ORIG = os.path.join(UI, "orig")
DECOMP = os.path.join(UI, "pimg")
TODO = os.path.join(UI, "todo")
MANIFEST = os.path.join(UI, "ui_manifest.csv")

FIELDS = ["kind", "source", "layer_id", "name", "width", "height", "left", "top",
          "todo", "en_ref"]


def decompile(pimg: str) -> str:
    os.makedirs(DECOMP, exist_ok=True)
    stem = os.path.splitext(os.path.basename(pimg))[0]
    js = os.path.join(DECOMP, stem + ".json")
    if not os.path.exists(js):
        dst = os.path.join(DECOMP, os.path.basename(pimg))
        shutil.copyfile(pimg, dst)
        freemote.default().decompile(dst)
    return js


def layers(js: str) -> list[dict]:
    meta = json.load(open(js, encoding="utf-8"))
    base = os.path.splitext(js)[0]
    out = []
    for L in meta.get("layers", []):
        png = os.path.join(base, "%d.png" % L["layer_id"])
        if os.path.exists(png):
            out.append(dict(L, png=png))
    return out


def differs(png_a: str, png_b: str, threshold: int = 64) -> bool:
    from PIL import Image, ImageChops

    def premul(im):
        r, g, b, a = im.convert("RGBA").split()
        return [ImageChops.multiply(c, a) for c in (r, g, b)] + [a]

    with Image.open(png_a) as a, Image.open(png_b) as b:
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

    for cn in sorted(glob.glob(os.path.join(ORIG, "uipsd", "cn", "*_cn.pimg"))):
        stem = os.path.basename(cn)[:-len("_cn.pimg")]
        jp = os.path.join(ORIG, "uipsd", "jp", stem + "_jp.pimg")
        en = os.path.join(ORIG, "uipsd", "en", stem + "_en.pimg")
        cn_layers = layers(decompile(cn))
        twin_sheet = jp if os.path.exists(jp) else en
        jp_by = {L["name"]: L
                 for L in (layers(decompile(twin_sheet)) if os.path.exists(twin_sheet) else [])}
        en_by = {L["name"]: L for L in (layers(decompile(en)) if os.path.exists(en) else [])}
        for L in cn_layers:
            key = L["name"]
            twin = jp_by.get(key)
            if twin is not None and not differs(twin["png"], L["png"]):
                continue
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


TEXT = os.path.join(UI, "text")
KS = os.path.join(UI, "ks")


def garbro_extract(archive: str, name: str, out_dir: str) -> str:
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    os.path.join(P.TOOLS, "garbro_extract.ps1"), "-Archive", archive,
                    "-OutDir", out_dir, "-Filter", name, "-KeepPaths"], capture_output=True)
    return os.path.join(out_dir, name.replace("/", os.sep))


def text_files() -> list[str]:
    return sorted(os.path.relpath(f, TEXT).replace(os.sep, "/")
                  for f in glob.glob(os.path.join(TEXT, "**", "*"), recursive=True) if os.path.isfile(f))


SHADOWED = {"patch.xp3": {"help_sys_cn.txt": "main/help_sys_cn.txt"}}


def _apply_text(ar, base: str, files: dict[str, str]) -> dict:
    plain = {}
    for n, src in files.items():
        with open(os.path.join(TEXT, src), "rb") as f:
            plain[n] = f.read()
    return _apply_plain(ar, base, plain)


def _apply_plain(ar, base: str, plain: dict[str, bytes]) -> dict:
    os.makedirs(KS, exist_ok=True)
    req = os.path.join(KS, "req.tsv")
    with open(req, "w", encoding="utf-8") as fh:
        for n in plain:
            fh.write("%s\t%d\n" % (n, len(plain[n])))
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        os.path.join(P.TOOLS, "xp3_keystream.ps1"), "-Archive", base,
                        "-List", req, "-OutDir", KS], capture_output=True, text=True)
    if r.returncode:
        sys.exit(r.stdout + r.stderr)
    with open(os.path.join(KS, "manifest.tsv"), encoding="utf-8-sig") as f:
        manifest = [l.rstrip("\r\n").split("\t") for l in f if l.strip()]

    by_offset = {e.offset: e for e in ar.entries}
    for i, name, offset in manifest:
        e = by_offset[int(offset)]
        with open(os.path.join(KS, i + ".ks"), "rb") as f:
            ks = f.read()
        old = e.stored
        new = ar.replace_sized(e, plain[name], ks)
        print("  %-32s %7d -> %7d bytes stored%s" % (name, old, new, " (zlib)" if e.compressed else ""))
    return plain


TH = os.path.join(UI, "th")
SHEET_ENTRY = "uipsd/cn/%s_cn.pimg"


def image_sheets() -> list[str]:
    return sorted(d for d in os.listdir(TH) if os.path.isdir(os.path.join(TH, d))
                  and not d.startswith("_")) if os.path.isdir(TH) else []


WIDEN_MAX = 120


def thai_layers(sheet: str) -> dict[str, str]:
    from PIL import Image
    out, bad = {}, []
    for png in sorted(glob.glob(os.path.join(TH, sheet, "*.png"))):
        name = os.path.basename(png)
        ref = os.path.join(TODO, sheet, name)
        if not os.path.exists(ref):
            bad.append("%s: no CN original in todo/%s" % (name, sheet))
            continue
        with Image.open(png) as a, Image.open(ref) as b:
            widened = a.height == b.height and b.width < a.width <= b.width + WIDEN_MAX
            if (a.size != b.size and not widened) or a.mode != "RGBA":
                bad.append("%s: %s %s, want %s RGBA" % (name, a.size, a.mode, b.size))
                continue
        out[name.split("_", 1)[0]] = png
    if bad:
        sys.exit("%s: bad Thai layers\n  " % sheet + "\n  ".join(bad))
    return out


IMAGES = "_images"


def thai_images() -> dict[str, str]:
    from PIL import Image
    root = os.path.join(TH, IMAGES)
    out, bad = {}, []
    for png in sorted(glob.glob(os.path.join(root, "**", "*.png"), recursive=True)):
        rel = os.path.relpath(png, root).replace(os.sep, "/")
        ref = os.path.join(TODO, IMAGES, rel)
        if not os.path.exists(ref):
            bad.append("%s: no CN original in todo/%s" % (rel, IMAGES))
            continue
        with Image.open(png) as a, Image.open(ref) as b:
            if a.size != b.size:
                bad.append("%s: %s, want %s" % (rel, a.size, b.size))
                continue
        out[rel] = png
    if bad:
        sys.exit("%s: bad Thai images\n  " % IMAGES + "\n  ".join(bad))
    return out


def build_sheet(base: str, sheet: str) -> bytes:
    entry = SHEET_ENTRY % sheet
    work = os.path.join(UI, "build", sheet)
    shutil.rmtree(work, ignore_errors=True)
    src = garbro_extract(base, entry, os.path.join(work, "src"))
    if not os.path.exists(src):
        sys.exit("could not extract %s from %s" % (entry, base))
    pimg = os.path.join(work, os.path.basename(src))
    shutil.copyfile(src, pimg)
    js = freemote.default().decompile(pimg, raw=True)
    resx = os.path.splitext(js)[0] + ".resx.json"
    meta = json.load(open(resx, encoding="utf-8"))
    res = meta["Resources"]
    slots = list(res)
    index = {}
    for k, v in json.load(open(js, encoding="utf-8")).items():
        if k.endswith(".tlg") and isinstance(v, str) and v.startswith("#resource#"):
            index[k[:-4]] = int(v[len("#resource#"):])
    layers_ = thai_layers(sheet)
    missing = [lid for lid in layers_ if lid not in index or index[lid] >= len(slots)]
    if missing:
        sys.exit("%s: layer ids not in sheet: %s" % (sheet, ", ".join(missing)))
    for lid, png in layers_.items():
        slot = slots[index[lid]]
        rel = os.path.splitext(res[slot])[0] + ".png"
        shutil.copyfile(png, os.path.join(work, rel))
        res[slot] = rel
    with open(resx, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    from PIL import Image
    widths = {}
    for lid, png in layers_.items():
        with Image.open(png) as im:
            widths[int(lid)] = im.width
    sheet_meta = json.load(open(js, encoding="utf-8"))
    for L in sheet_meta["layers"]:
        if L.get("layer_id") in widths and L.get("width") != widths[L["layer_id"]]:
            L["width"] = widths[L["layer_id"]]
    with open(js, "w", encoding="utf-8") as fh:
        json.dump(sheet_meta, fh, ensure_ascii=False, indent=2)
    built = freemote.default().build(js, os.path.join(work, "out"), ext=".pimg")
    print("  %-32s %d Thai layers" % (entry, len(layers_)))
    with open(built, "rb") as f:
        return f.read()


def build_data(out: str | None = None, verify: bool = True):
    import xp3
    import targets as T
    import rebuild_fonts
    t = T.by_file("data.xp3")
    base = P.game_file(t.orig)
    if not os.path.exists(base):
        sys.exit("missing pristine %s" % t.orig)
    target = out or P.game_file(t.file)

    ar = xp3.Archive.read(base)
    rebuild_fonts.apply_fonts(ar)
    files = text_files()
    sheets = image_sheets()
    plain = {}
    for n in files:
        with open(os.path.join(TEXT, n), "rb") as f:
            plain[n] = f.read()
    for sheet in sheets:
        plain[SHEET_ENTRY % sheet] = build_sheet(base, sheet)
    images = thai_images()
    for rel, png in images.items():
        with open(png, "rb") as f:
            plain[rel] = f.read()
    if plain:
        _apply_plain(ar, base, plain)
    ar.save(target)
    print("wrote %s from %s (3 fonts + %d text files + %d image sheets + %d images)"
          % (target, t.orig, len(files), len(sheets), len(images)))

    if verify and plain:
        verify_text(target, plain)


def apply_shadowed(ar, base: str, name: str) -> dict:
    files = SHADOWED.get(name, {})
    missing = [src for src in files.values() if not os.path.exists(os.path.join(TEXT, src))]
    if missing:
        sys.exit("missing Thai text for %s: %s" % (name, ", ".join(missing)))
    return _apply_text(ar, base, files) if files else {}


def verify_text(archive: str, plain: dict):
    chk = os.path.join(UI, "verify")
    shutil.rmtree(chk, ignore_errors=True)
    bad = []
    for n in plain:
        with open(garbro_extract(archive, n, chk), "rb") as f:
            if f.read() != plain[n]:
                bad.append(n)
    print("verify: %d/%d files read back byte-identical" % (len(plain) - len(bad), len(plain)))
    if bad:
        sys.exit("MISMATCH: " + ", ".join(bad))


def cmd_pack_text(out: str | None = None, verify: bool = True):
    if not text_files():
        sys.exit("nothing under " + TEXT)
    build_data(out, verify)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "inventory":
        cmd_inventory()
    elif cmd == "pack-text":
        cmd_pack_text(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print(__doc__)
        sys.exit(2)
