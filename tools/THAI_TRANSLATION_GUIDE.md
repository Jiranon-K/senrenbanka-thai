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

## ตัวติดตั้งสำหรับผู้เล่นทั่วไป (xdelta patch)

ไม่แจก `patch.xp3`/`data.xp3` ตรงๆ (มีข้อมูลเกมลิขสิทธิ์เต็ม) — แจกเป็น **binary diff** แทน (มาตรฐาน fan-patch/ROM hack) ใช้ได้เฉพาะคนมีเกมแท้ + `.orig` เดิม

**เครื่องมือ**: `tools/xdelta/xdelta3.exe` (ไม่ commit เข้า repo — โหลดแยกจาก [jmacd/xdelta releases](https://github.com/jmacd/xdelta/releases), official Windows binary)

**สร้าง diff ใหม่** (ทำทุกครั้งที่แปลเพิ่ม/เกมอัปเดตเวอร์ชัน — ต้องมี `.orig` ที่ตรงกับเวอร์ชันเกมปัจจุบัน):
```powershell
tools/xdelta/xdelta3.exe -e -f -9 -B 1073741824 -s patch.xp3.orig patch.xp3 thai_work/dist/thai-patch.xdelta
tools/xdelta/xdelta3.exe -e -f -9 -B 1073741824 -s data.xp3.orig  data.xp3  thai_work/dist/thai-data.xdelta
```
`-B 1GB` = source window เต็มไฟล์ (จำเป็น เพราะ rebuild ทำให้ offset ข้อมูลเดิมเลื่อน) `-s` = source ฐาน (`.orig`). ตรวจผลด้วยการ decode กลับมาเทียบ byte-ต่อ-byte ก่อนแจกทุกครั้ง (`xdelta3.exe -d -s <.orig> <.xdelta> <out>` แล้ว `cmp`).

**แพ็กเป็น zip แจก**: `install.bat` + `uninstall.bat` + `xdelta3.exe` + `thai-patch.xdelta` + `thai-data.xdelta` + `README.txt` (source อยู่ใน `thai_work/dist/` ระหว่างสร้าง — ไม่ commit โฟลเดอร์นี้ อัปโหลดเป็น GitHub Release asset แทน)

**ทดสอบก่อนแจกทุกครั้ง**: จำลอง fresh install (copy `.orig` ทั้งคู่ตั้งเป็น `patch.xp3`/`data.xp3` ใน folder ทดสอบ, ใส่ `SenrenBanka.exe` เปล่าไว้ด้วยเพื่อผ่านเช็ค) → รัน `install.bat` → เทียบ SHA256 กับไฟล์แปลไทยจริง → รัน `uninstall.bat` → เทียบ SHA256 กับ `.orig` เดิม

⚠️ ข้อควรระวังตอนเขียน `.bat`:
- **ต้องเซฟเป็น CRLF + UTF-8 BOM** (ไม่ใช่ LF) — cmd.exe parse ผิดเพี้ยนกับ LF-only โดยเฉพาะไฟล์ที่มี `chcp 65001` + ข้อความไทย (token แตกกลางบรรทัด)
- **ห้ามเรียกโปรแกรมด้วยชื่อเปล่า** (เช่น `xdelta3.exe`) — ต้องใช้ `"%~dp0xdelta3.exe"` เสมอ เพราะเครื่องที่ปิด `NoDefaultCurrentDirectoryInExePath` (ค่าตั้งความปลอดภัยที่พบได้จริง โดยเฉพาะเครื่ององค์กร/hardened) จะหา exe ใน current directory ไม่เจอ แม้ `cd` เข้าไปถูกโฟลเดอร์แล้วก็ตาม — ใช้ full path จาก `%~dp0` ปลอดภัยเสมอไม่ว่า policy จะเป็นแบบไหน
- ใส่ `cd /d "%~dp0"` ต้นสคริปต์เสมอ กัน user รันจาก shortcut/cwd ผิดที่

## ❌ ทิ้งได้
`extract_text.py`/`senren_banka_translation*.csv` (strings บน PSB = garbage).
`patch_thai.xp3`/`KrkrPatch*`/`KrkrExtract*` (ทางที่ลองแล้วไม่ใช้ — KrkrPatch ติด SteamStub DRM).
