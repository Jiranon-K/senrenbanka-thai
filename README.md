# Senren Banka — Thai Translation (千恋＊万花 แปลไทย)

ชุดเครื่องมือ + ข้อมูลคำแปลสำหรับแปลวิชวลโนเวล **Senren Banka** (Yuzusoft, เอนจิน KiriKiri Z) เป็น **ภาษาไทย** — พิสูจน์แล้วว่าเรนเดอร์ไทยในเกมจริงได้ครบ (บทพูด, บรรยาย, ruby, ชื่อตัวละคร 【】, choice).

> ⚠️ **Disclaimer:** โปรเจกต์นี้เป็นงานแปลแฟน (fan translation) เพื่อการศึกษา/ใช้ส่วนตัว.
> repo นี้เก็บ **เฉพาะโค้ดเครื่องมือ + คำแปลภาษาไทย** เท่านั้น —
> **ไม่มี** asset เกม (`*.xp3`, ต้นฉบับ JP/EN, รูป, เสียง) ใดๆ ทั้งสิ้น.
> ต้องเป็นเจ้าของเกมแท้ (Steam) จึงจะ build แพตช์มาใช้ได้.

---

## วิธีการ (Method) — สรุปสั้น

กลยุทธ์ที่พิสูจน์แล้วว่าใช้งานได้บนเกมจริง:

1. **CN-slot strategy** — แต่ละบทพูดเก็บ 4 ภาษา `[JP, EN, CN, TW]`. แปลไทยทับ **CN slot (index 2)**; ในเกมเลือกภาษา **Chinese (Simplified)** → ได้ไทย. (เลี่ยง JP/EN ที่ใช้ฟอนต์ `.tft` prerendered ซึ่งไม่มี glyph ไทย; CN/TW ใช้ vector font สลับได้)
2. **KEYSTREAM cipher** (content-independent, ไม่ต้องรู้คีย์) — `newEnc = myData XOR (origEnc XOR origPlain)`, คง native adler. เลี่ยงการ reverse Yuzu cxdec VM ทั้งหมด.
3. **Rebuild .xp3** — รักษา `sen:` pre-index blob (hnfn zlib) ของ Yuzu; layout `[40B v2 header][data][sen: blob][zlib index]`.
4. **Font** — merge เครื่องหมาย CJK (「」『』【】、。…―— ♪ ฯลฯ) เข้าฟอนต์ไทย (Noto Sans Thai) → แทน `SourceHanSansSC-{Regular,Bold,Heavy}` ใน `data.xp3` (copy name table + OS/2 weight ให้ GDI face-match).

### 🎯 KiriKiri Z Thai rendering — บทเรียนสำคัญ

KiriKiri Z (krkrz) เรนเดอร์ข้อความ **glyph-by-glyph ไม่มี OpenType shaping** (ไม่อ่าน GSUB/GPOS) และเลื่อน pen ด้วย `GetTextExtentPoint32(char, 1)`.

- combining mark ภาษาไทย (สระบน/ล่าง, วรรณยุกต์) ต้องมี **advanceWidth = 0 + LSB ติดลบ** (overlay) baked ในตัว glyph
- **ตัวการ "สระห่าง":** ถ้าฟอนต์มี glyph **U+25CC (dotted circle)** → Uniscribe แทรก dotted circle หน้า mark โดดเดี่ยว → `GetTextExtentPoint32` คืน advance บวก → เกิดช่องว่างหลังทุกสระ. **แก้โดยลบ U+25CC ออกจาก cmap** (อยู่ใน `build_thai_font.py` แล้ว) — ยืนยันด้วย Win32 GDI API จริง

คู่มือเต็ม: [`tools/THAI_TRANSLATION_GUIDE.md`](tools/THAI_TRANSLATION_GUIDE.md)

---

## โครงสร้าง repo

```
tools/
  pipeline_cn.py        แกนหลัก: decompile / export / import / recompile / pack (keystream)
  track.py              progress tracker -> manifest.json + progress.json + PROGRESS.md
  qc.py                 QC gate: untranslated / missing-glyph / tag / overflow / glossary
  build_thai_font.py    merge CJK punct เข้าฟอนต์ไทย + ลบ U+25CC (krkrz fix)
  rebuild_fonts.py      แทนฟอนต์ SC ใน data.xp3 (keystream)
  THAI_TRANSLATION_GUIDE.md
thai_work/
  th/<file>.tsv         คำแปลไทยต่อไฟล์ (idx -> th)  ← งานแปลหลัก
  glossary.csv          ชื่อตัวละคร/ศัพท์ (ความสม่ำเสมอทั้งเกม)
  PROGRESS.md           dashboard ความคืบหน้า
  manifest.json / progress.json
```

**ไม่อยู่ใน repo** (ต้องมีจากเกมแท้ของคุณเอง): `*.xp3`, `thai_work/{strings_cn.csv,fonts,json_cn,psb_cn,pe_extract}/`, `tools/FreeMote/` (ดาวน์โหลดแยก).

---

## Requirements

- เกม Senren Banka แท้ (Steam) — เวอร์ชันตรงกับที่พัฒนา
- [GARbro](https://github.com/morkt/GARbro) — แตก/ถอดรหัส `.xp3`
- [FreeMote](https://github.com/UlyssesWu/FreeMote) v4.5 — `PsbDecompile` / `PsBuild` (วางใน `tools/FreeMote/`)
- Python 3 + `fonttools` (+ `Pillow` สำหรับ proxy render)
- ฟอนต์ base: Noto Sans Thai (OFL) — [google/fonts](https://github.com/google/fonts/tree/main/ofl/notosansthai)

---

## Build (ย่อ)

```powershell
# 0. GARbro: extract patch.xp3 -> thai_work\pe_extract\   (ครั้งเดียว)
python tools/pipeline_cn.py decompile thai_work/pe_extract   # *.ks.scn -> json
python tools/pipeline_cn.py export                           # -> strings_cn.csv (jp/en | th)
#    เติมคำแปลในคอลัมน์ th  (หรือ merge จาก thai_work/th/<file>.tsv)
python tools/pipeline_cn.py import                           # th -> CN slot
python tools/qc.py <file|all>                                # QC gate
python tools/pipeline_cn.py recompile <file>                 # json -> psb
python tools/pipeline_cn.py pack patch.xp3 thai_work/pe_extract
# ฟอนต์ (ครั้งเดียว):
python tools/build_thai_font.py    # merge punct + ลบ U+25CC
python tools/rebuild_fonts.py      # แทนฟอนต์ใน data.xp3
```
เล่นเกม → Language = **Chinese (Simplified)** → ได้ไทย.

---

## Progress

<!-- snapshot — สร้างใหม่ด้วย: python tools/track.py report  (ดูไฟล์เต็ม thai_work/PROGRESS.md) -->

**16/86 packed · 16 verified**

| Route | Packed | ไฟล์ |
|---|--:|--:|
| Common | 13 | 13 |
| Yoshino | 0 | 15 |
| Murasame | 0 | 16 |
| Mako | 3 | 11 |
| Lena | 0 | 17 |
| Sub | 0 | 14 |

### Common (13/13 verified ✅)

| file | lines | choices | H | status |
|---|--:|--:|:-:|---|
| 001・アーサー王 | 812 | 2 |  | ✅ verified |
| 002・祟り神 | 555 | 0 |  | ✅ verified |
| 003・巫女の秘密 | 961 | 0 |  | ✅ verified |
| 004・学院初日 | 490 | 0 |  | ✅ verified |
| 005・鍛錬 | 313 | 0 |  | ✅ verified |
| 008・仕切り直し | 193 | 0 |  | ✅ verified |
| 009・謎の欠片 | 781 | 0 |  | ✅ verified |
| 010・リフレッシュ | 1212 | 9 |  | ✅ verified |
| 011・襲来 | 439 | 0 |  | ✅ verified |
| 012・病床 | 787 | 2 |  | ✅ verified |
| 013・欠片集め | 512 | 0 |  | ✅ verified |
| 014・合体編 | 651 | 2 |  | ✅ verified |
| 015・ノーマルend | 298 | 0 |  | ✅ verified |

> เส้นทางอื่น (Yoshino / Murasame / Mako / Lena / Sub) ยัง `🔧 decompiled` — ดูรายไฟล์ใน [`thai_work/PROGRESS.md`](thai_work/PROGRESS.md). 🔞 = H-scene (ทำทีหลัง)

สถานะ: ⬜ pending · 🔧 decompiled · ✏️ partial · 📝 translated · ✅ verified · ✅ verified

---

## License

- **โค้ดเครื่องมือ** (`tools/*.py`): MIT — ดู [`LICENSE`](LICENSE)
- **คำแปลภาษาไทย** (`thai_work/th/`, `glossary.csv`): งานแปลแฟน เพื่อการศึกษา/ใช้ส่วนตัว
- **ฟอนต์**: Noto Sans Thai / Sarabun / Source Han Sans = SIL Open Font License (OFL) — ไม่ได้ฝากไว้ใน repo, build เอง. ⚠️ ฟอนต์ variant ที่ build ใช้ชื่อ reserved `Source Han Sans SC` (จำเป็นต่อ GDI matching ในเกม) — **ห้าม redistribute** ตาม OFL, ให้ build local เท่านั้น
- **เกมและบทต้นฉบับ**: ลิขสิทธิ์ Yuzusoft / NekoNyan — ไม่รวมอยู่ใน repo นี้
