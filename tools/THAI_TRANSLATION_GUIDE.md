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
- **87/90 บทอยู่ใน patch.xp3** (ชนะ scn+patch_extra) → แก้ patch.xp3
- **3 บทอยู่ scn.xp3 อย่างเดียว** → แก้ scn.xp3
- patch_extra.xp3 = ไม่ต้องแตะ (patch.xp3 ชนะ)

⚠️ **patch.xp3 ไม่ใช่ priority สูงสุดเสมอไป** — ถ้าผู้เล่นลงแพตช์ R18 จะมี `adult.xp3`
(append pack ของ `sysscn/append_init.tjs`) เข้ามาอยู่ *เหนือ* patch.xp3 และในนั้นมี
`*.ks.scn` ครบ 92 บท → ไทยใน patch.xp3 ถูกทับหมด

ลำดับจริง: `scn.xp3 < patch_extra.xp3 < patch.xp3 < adult.xp3`

รายละเอียด + วิธีพอร์ตไทยไปฝั่ง R18: [`R18_COMPAT.md`](R18_COMPAT.md) · เครื่องมือ:
`port_r18.py`, `check_thai.ps1`

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
python tools/pipeline_cn.py pack scn.xp3 thai_work/scnxp3  # 6b. 3 scn-only บท
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

**สร้างชุดติดตั้งทั้งชุด = คำสั่งเดียว** (`tools/build_release.py`):
```powershell
python tools/build_release.py --version 1.1
```
ทำให้ครบตั้งแต่ต้นจนจบ: หาโฟลเดอร์เกม → encode diff ทั้ง 3 ตัว → **decode กลับมาเทียบ SHA256 ทุกไฟล์** (ไม่ตรง = หยุด ไม่ปล่อย) → เขียน `install.bat`/`uninstall.bat`/`README.txt`/`checksums.txt` โดยฝัง SHA256 จริงลงไป → zip
ผลลัพธ์อยู่ใน `thai_work/dist/` (gitignore ไว้ — อัปโหลดเป็น GitHub Release asset แทน)

| diff | source | target | หมายเหตุ |
|---|---|---|---|
| `thai-patch.xdelta` | `patch.xp3.bak` | `patch.xp3` | บทพูด all-ages |
| `thai-data.xdelta` | `data.xp3.bak` | `data.xp3` | ฟอนต์ Sarabun |
| `thai-adult.xdelta` | `adult.xp3.orig` | `adult.xp3` | บทพูดฝั่ง R18 (ข้ามอัตโนมัติถ้าไม่มี `.orig`) |

`-B 1GB` = source window เต็มไฟล์ (จำเป็นตอน **encode** เพราะ rebuild ทำให้ offset ข้อมูลเดิมเลื่อน; ตอน decode ไม่ต้องใส่ — ทดสอบแล้วกับ adult.xp3 855 MB ใช้เวลา 2.2 วิ)

**สิ่งที่ installer ทำต่างจาก v1.0 และทำไม**
- **ซิปเดียวรองรับทั้ง all-ages และ R18** — เห็น `adult.xp3` = แปะ `thai-adult.xdelta` ด้วย. แยกสองซิปเสี่ยงคนโหลดผิดตัวแล้วได้ไทยครึ่งๆ
- **สำรองด้วย `move` ไม่ใช่ `copy`** — v1.0 ก็อปปี้ 1.3 GB ก่อนแปะ, v1.1 มี `adult.xp3` อีก 855 MB. rename บน volume เดียวกันเป็น O(1) → ใช้พื้นที่แค่เท่าไฟล์ผลลัพธ์
- **เช็ค SHA256 ก่อนแตะไฟล์** — `certutil -hashfile` แยกได้ว่า "ลงไปแล้ว" / "Steam อัปเดตเกม" / "แพตช์ R18 คนละ build" แทนที่จะปล่อยให้ xdelta error ตอนท้ายด้วยข้อความที่ผู้เล่นอ่านไม่รู้เรื่อง
- **ถ้าแปะ `adult.xp3` ไม่ได้ = ล้มทั้งชุด** ไม่ยอมแปะครึ่งเดียว เพราะ `adult.xp3` ทับ `patch.xp3` อยู่ → แปะครึ่งเดียวเกมขึ้นภาษาจีนเงียบๆ (คือบั๊กที่ v1.1 เกิดมาเพื่อแก้)
- **`:rollback`** คืนไฟล์ทุกตัวที่ rename ไปแล้วถ้าล้มกลางคัน

**ตัวติดตั้งแบบหน้าต่าง** (`--gui`): `python tools/build_release.py --version 1.1 --gui`
จะ build `tools/gui/` (tkinter — Win32 window จริง, ดีไซน์จาก Claude Design) ใส่เข้าไปในซิปด้วย
หาโฟลเดอร์เกมเองจาก `libraryfolders.vdf` ผู้เล่นจึงแตกซิปไว้ที่ไหนก็ได้
และอ่าน `manifest.json` ตัวเดียวกับที่ฝัง hash ลง `install.bat` จึงไม่มีทางหลุด sync กัน

เคยลองทำด้วย pywebview + WebView2 ก่อน แล้ววัดได้ว่ามันตั้ง **HTTP server ที่ 127.0.0.1**
แล้วโหลดหน้าเว็บผ่านพอร์ตนั้น (เป็น web app ในกรอบหน้าต่าง ไม่ใช่โปรแกรมหน้าต่าง)
จึงเปลี่ยนมาเป็น tkinter — ไม่มี dependency เพิ่ม ไม่เปิดพอร์ต และไม่ต้องพึ่ง WebView2 Runtime
รายละเอียด/กับดักที่เจอมาแล้ว: [`gui/README.md`](gui/README.md)

**ทดสอบก่อนแจกทุกครั้ง** — อัตโนมัติแล้ว 3 ชุด:
```bash
bash   tools/test_installer.sh thai_work/dist/senrenbanka-thai-patch-v1.1   # install.bat, 6 เคส
python tools/gui/test_core.py                                              # ตรรกะ GUI, 6 เคสเดียวกัน
python tools/gui/test_app.py                                               # หน้าจอ tkinter, 27 เคส
```
สองชุดแรกจำลอง fresh install: R18 / all-ages / adult.xp3 คนละ build / แตกซิปไม่ครบ / รันผิดโฟลเดอร์ /
ต้นฉบับต้องไม่ถูกแตะ — เทียบ SHA256 ทุกไฟล์ทั้งหลังติดตั้งและหลังถอด
(ฝั่ง GUI มีเคสเพิ่ม: xdelta ล้มกลางคันแล้วต้อง rollback ครบ)
**เคสต้องตรงกันทั้งสองชุด** — ถ้าให้ผลต่างกัน แปลว่ามีตัวใดตัวหนึ่งผิด

ไฟล์ต้นทางในโฟลเดอร์ทดสอบเป็น **hard link** ไปยัง archive จริง → ไม่ต้องก็อป 2 GB และ `move` ใน installer แค่เปลี่ยนชื่อ link (เทสเคสที่ 6 ยืนยันซ้ำว่าต้นฉบับไม่เปลี่ยน) ค่า SHA256 ที่คาดหวังอ่านจาก `install.bat` ที่ build มา ไม่ต้อง sync มือ

⚠️ ข้อควรระวังตอนเขียน `.bat`:
- **CRLF เสมอ** (ไม่ใช่ LF) — cmd.exe parse ผิดเพี้ยนกับ LF-only โดยเฉพาะไฟล์ที่มี `chcp 65001` + ข้อความไทย (token แตกกลางบรรทัด)
- **ห้ามใส่ UTF-8 BOM ใน `.bat`** (แก้จากที่เคยเขียนไว้ — v1.0 ใส่ BOM แล้วพลาด) BOM ทำให้บรรทัดแรกเป็น `<BOM>@echo off` ซึ่ง cmd อ่านไม่ออก → ขึ้น `'@echo' is not recognized` และ echo ไม่ถูกปิด ผู้เล่นเห็นทุกคำสั่งวิ่งผ่านจอ. ไม่ต้องพึ่ง BOM เพราะ cmd decode ทีละบรรทัดด้วย codepage ปัจจุบัน — `chcp 65001` บรรทัดที่ 3 ทำให้บรรทัดถัดไปอ่านเป็น UTF-8 เอง. วัดจริงทั้ง CP 437 / 874 / 1252 / 65001 (ไม่มี BOM ผ่านหมด, มี BOM พังทุกตัวยกเว้น 65001) — ตารางอยู่ใน `build_release.py`
- `README.txt` ยังคง BOM ไว้ (เปิดด้วย Notepad)
- **ห้ามเรียกโปรแกรมด้วยชื่อเปล่า** (เช่น `xdelta3.exe`) — ต้องใช้ `"%~dp0xdelta3.exe"` เสมอ เพราะเครื่องที่ปิด `NoDefaultCurrentDirectoryInExePath` (ค่าตั้งความปลอดภัยที่พบได้จริง โดยเฉพาะเครื่ององค์กร/hardened) จะหา exe ใน current directory ไม่เจอ แม้ `cd` เข้าไปถูกโฟลเดอร์แล้วก็ตาม — ใช้ full path จาก `%~dp0` ปลอดภัยเสมอไม่ว่า policy จะเป็นแบบไหน
- ใส่ `cd /d "%~dp0"` ต้นสคริปต์เสมอ กัน user รันจาก shortcut/cwd ผิดที่

## ❌ ทิ้งได้
`extract_text.py`/`senren_banka_translation*.csv` (strings บน PSB = garbage).
`patch_thai.xp3`/`KrkrPatch*`/`KrkrExtract*` (ทางที่ลองแล้วไม่ใช้ — KrkrPatch ติด SteamStub DRM).
