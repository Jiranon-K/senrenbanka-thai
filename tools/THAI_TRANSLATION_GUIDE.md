# Senren Banka — Thai Translation Guide (WORKING METHOD ✅)

แปล Senren Banka (Yuzusoft, KiriKiri Z) เป็นไทย. **พิสูจน์แล้วว่าไทย render ในเกมจริง.**

## กลยุทธ์ที่ใช้งานได้ (สรุป)

1. **แปลใส่ CN slot** — แต่ละบทพูดเก็บ 4 ภาษา `[JP, EN, CN, TW]`. แปลไทยทับ **CN (index 2)**.
   ในเกมเลือกภาษา **Chinese (Simplified)** → ได้ไทย.
   *(ทำไม CN ไม่ใช่ EN: jp/en ใช้ font "スキップ"=.tft prerendered ไม่มี glyph ไทย แก้ยาก.
   cn/tw ใช้ vector font SourceHanSansSC → สลับเป็น Thai font ได้ง่าย.)*

2. **Font** — แทน `SourceHanSansSC-{Regular,Bold,Heavy}.otf` ใน data.xp3 ด้วย **Sarabun**
   ที่ copy name table + OS/2 weight ของ original (ให้ Windows GDI หา face เจอ).
   → cn message render ด้วย Sarabun (มีไทย). ทำแล้วด้วย keystream method.

3. **Cipher = keystream method** (content-independent, ไม่ต้องรู้ key):
   ```
   keystream[i] = origEnc[i] XOR origPlain[i]      # origPlain จาก GARbro extract
   newEnc[i]    = myData[i]  XOR keystream[i]       # keep native adlr!
   ```
   game สร้าง keystream เดิมจาก adlr ที่ไม่เปลี่ยน → decrypt = myData. เงื่อนไข: myData ≤ original size (pad ด้วย 0).

4. **Rebuild archive** — preserve `sen:` pre-index blob (hnfn zlib). Layout:
   `[40B v2 header][file data][sen: blob verbatim][zlib index]`. update sen: field0 = blob offset ใหม่.

## Scenario coverage
- **87/90 บทอยู่ใน patch.xp3** (priority สูงสุด, ชนะ scn+patch_extra) → แก้ patch.xp3
- **3 บทอยู่ scn.xp3 อย่างเดียว** → แก้ scn.xp3
- patch_extra.xp3 = ไม่ต้องแตะ (patch.xp3 ชนะ)

## Toolchain (`tools/`)
- **FreeMote** v4.5 — decompile/recompile PSB
- **GARbro** — extract xp3 (decrypt) → ได้ plaintext (origPlain) + translation source
- **fonttools** (pip) — rename font name table
- `tools/pipeline_cn.py` — pipeline หลัก (CN slot + keystream pack)
- `tools/rebuild_data_font.py` — font swap (ทำแล้ว)

## Workflow เต็มเกม

```powershell
# 0. GARbro: extract patch.xp3 -> D:\...\SenrenBanka\patch_extract\  (real names, decrypted)
#    (scn.xp3 -> scnxp3\ ทำแล้ว สำหรับ 3 บท scn-only)

cd D:\SteamLibrary\steamapps\common\SenrenBanka
python tools/pipeline_cn.py decompile patch_extract   # 1. *.ks.scn -> json_cn\
python tools/pipeline_cn.py export                    # 2. -> thai_work/strings_cn.csv

#  3. แปล: เติมคอลัมน์ "th" ใน strings_cn.csv  (jp=ต้นฉบับ, en=NekoNyan ref)

python tools/pipeline_cn.py import                    # 4. th -> CN slot(2) + choices
python tools/qc.py <ชื่อไฟล์/all>                      # 4.5 QC (gate): untranslated/glyph/tag/overflow/glossary
python tools/pipeline_cn.py recompile                 # 5. json -> psb_cn\
python tools/pipeline_cn.py pack patch.xp3 patch_extract   # 6a. keystream-rebuild patch.xp3
python tools/pipeline_cn.py pack scn.xp3   scnxp3          # 6b. 3 scn-only บท
python tools/track.py scan && python tools/track.py report # 7. อัปเดต progress
python tools/track.py set <ไฟล์.scn> packed                # หลัง pack
python tools/track.py set <ไฟล์.scn> verified              # หลังเทสในเกม ok
```
แล้วเล่นเกม → Language = **Chinese (Simplified)** → ไทย.

## Harness (track + QC + glossary)
- **`thai_work/PROGRESS.md`** = dashboard (รัน `track.py report`) — สถานะต่อไฟล์/route
- **`thai_work/glossary.csv`** = ชื่อ/ศัพท์ (ความสม่ำเสมอ) — อ้างตอนแปล, qc ตรวจ
- **`qc.py`** gate ก่อน pack: hard = untranslated/missing-glyph (exit 1); soft = tag/overflow/glossary
- ลำดับแปล: Common → Yoshino → Murasame → Mako → Lena → Sub; ข้าม is_h (🔞 ใน PROGRESS.md) ทำทีหลัง

## Font (ทำครั้งเดียว, เสร็จแล้ว)
```
python tools/build_thai_font.py   # merge CJK punct (【】「」『』、。・〜♪！？（）) เข้า Sarabun -> Sarabun-merged.ttf + 3 SC variants
python tools/rebuild_fonts.py     # แทน SourceHanSansSC-{Reg,Bold,Heavy} ใน data.xp3 ด้วย merged variant (keystream)
```
- ชื่อตัวละคร cn ห่อด้วย `【】` (U+3010/3011 ตาม `dataxp3/main/syslangtext_cn.ini`) → ต้องมี glyph นี้
- pipeline จับ **choice** (`language[2]` dict) + **ruby narration** (is_block `len>=2`) อัตโนมัติแล้ว

## Backup / restore
ทุก archive มี `.orig`. restore: `copy xxx.xp3.orig xxx.xp3`.

## Polish ที่เหลือ
- ✅ ชื่อ 【】 + ♪ + ruby + choice = แก้แล้ว (font glyph merge + pipeline)
- Word-wrap ไทย (ไม่มี space คั่นคำ) — KiriKiri wrap แบบ CJK ใช้ได้; ปรับด้วย ZWSP ถ้าต้องการ
- ตรวจ render ยาวๆ (สระซ้อน/วรรณยุกต์) — ทดสอบจริงต่อ
- ภาษา tw ยังไม่ทำ font (ถ้าจะใช้ ทำ SourceHanSansTC แบบเดียวกับ build_thai_font.py)

## ❌ ทิ้งได้
`extract_text.py`/`senren_banka_translation*.csv` (strings บน PSB = garbage).
`patch_thai.xp3`/`KrkrPatch*`/`KrkrExtract*` (ทางที่ลองแล้วไม่ใช้ — KrkrPatch ติด SteamStub DRM).
