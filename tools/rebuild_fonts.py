#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rebuild data.xp3 from data.xp3.orig: replace SourceHanSansSC-{Regular,Bold,Heavy}
with the merged Sarabun variants (Thai + CJK punctuation glyphs).
Cipher = keystream (content-independent): newEnc = variant XOR (origEnc XOR origPlain),
keep native adlr. Preserves the Yuzu 'sen:' pre-index blob. v2 header + zlib index.
"""
import os, sys, struct, zlib, shutil
sys.stdout.reconfigure(encoding="utf-8")
GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAR  = os.path.join(GAME, "thai_work", "fonts", "variants")
SHS  = os.path.join(GAME, "dataxp3", "font")
# hash -> (variant path, original plaintext path) for the 3 cn message fonts
EDITS = {
    "5fe64cd667860a8436ceae6bbaf1f5ce": ("SourceHanSansSC-Regular.ttf", "SourceHanSansSC-Regular.otf"),
    "eb936bac69df4fe4dbdc6dd191044be0": ("SourceHanSansSC-Bold.ttf",    "SourceHanSansSC-Bold.otf"),
    "ec5a25946224844562dd5e43b255f916": ("SourceHanSansSC-Heavy.ttf",   "SourceHanSansSC-Heavy.otf"),
}

def main():
    src = os.path.join(GAME, "data.xp3"); orig = src + ".orig"
    assert os.path.exists(orig), "data.xp3.orig missing"
    d = open(orig, "rb").read()
    hp = struct.unpack("<Q", d[11:19])[0]; assert d[hp] == 0x80
    real = struct.unpack("<Q", d[hp+9:hp+17])[0]
    comp = struct.unpack("<Q", d[real+1:real+9])[0]
    idx = zlib.decompress(d[real+17:real+17+comp])
    sp = idx.find(b"sen:"); sen = idx[sp+12:sp+12+struct.unpack("<Q", idx[sp+4:sp+12])[0]]
    bo = struct.unpack("<I", sen[0:4])[0]; bc = struct.unpack("<I", sen[12:16])[0]
    blob = d[bo:bo+bc]
    first = idx.find(b"File"); prefix = bytearray(idx[:first])
    # parse entries
    p = first; ents = []
    while p < len(idx) and idx[p:p+4] == b"File":
        p += 4; cs = struct.unpack("<Q", idx[p:p+8])[0]; p += 8
        chunk = idx[p:p+cs]; p += cs
        q = 0; subs = []; nm = off = size = None
        while q < len(chunk):
            tag = chunk[q:q+4]; q += 4; ss = struct.unpack("<Q", chunk[q:q+8])[0]; q += 8
            sd = bytearray(chunk[q:q+ss]); q += ss; subs.append([tag, sd])
            if tag == b"info":
                nl = struct.unpack("<H", sd[20:22])[0]; nm = sd[22:22+nl*2].decode("utf-16-le", "replace")
            if tag == b"segm":
                off = struct.unpack("<Q", sd[4:12])[0]; size = struct.unpack("<Q", sd[12:20])[0]
        ents.append({"subs": subs, "name": nm, "off": off, "size": size})
    # keystream-encrypt the 3 variants
    enc_map = {}
    for e in ents:
        if e["name"] in EDITS:
            vfile, pfile = EDITS[e["name"]]
            variant = open(os.path.join(VAR, vfile), "rb").read()
            origP = open(os.path.join(SHS, pfile), "rb").read()
            origE = d[e["off"]:e["off"]+e["size"]]
            assert len(variant) <= e["size"], f"{vfile} too big"
            variant = variant + b"\x00" * (e["size"] - len(variant))
            ks = bytes(origE[i] ^ origP[i] for i in range(e["size"]))
            enc_map[e["name"]] = bytes(variant[i] ^ ks[i] for i in range(e["size"]))
    assert len(enc_map) == 3, f"matched {len(enc_map)}/3 SC fonts"
    # assemble: v2 header(40) + data + sen blob + zlib index
    buf = bytearray(d[0:40])
    for e in ents:
        payload = enc_map.get(e["name"], d[e["off"]:e["off"]+e["size"]])
        e["newoff"] = len(buf); e["newsize"] = len(payload); buf += payload
    nbo = len(buf); buf += blob; iofs = len(buf)
    struct.pack_into("<I", prefix, prefix.find(b"sen:")+12, nbo)   # sen field0 = new blob offset
    nidx = bytearray(prefix)
    for e in ents:
        for tag, sd in e["subs"]:
            if tag == b"segm": sd[4:12] = struct.pack("<Q", e["newoff"])   # size unchanged (padded to orig); keep adlr
        chunk = bytearray()
        for tag, sd in e["subs"]: chunk += tag + struct.pack("<Q", len(sd)) + sd
        nidx += b"File" + struct.pack("<Q", len(chunk)) + chunk
    cidx = zlib.compress(bytes(nidx), 6)
    buf += b"\x01" + struct.pack("<Q", len(cidx)) + struct.pack("<Q", len(nidx)) + cidx
    buf[32:40] = struct.pack("<Q", iofs)
    open(src, "wb").write(buf)
    print(f"data.xp3 rebuilt: 3 SC fonts -> merged Sarabun, size={len(buf)}")

main()
