# ภาษาไทย + แพตช์ R18 — สาเหตุ วิธีแก้ และสถานะปัจจุบัน

## อาการเดิม

ลงแพตช์ไทย → เล่นเป็นไทยได้ปกติ · ลงแพตช์ R18 ทับ → ข้อความกลับเป็นจีนทั้งเกม

## สาเหตุ

แพตช์ R18 ติดตั้ง `adult.xp3` ซึ่งเป็น **append pack** ของระบบ `sysscn/append_init.tjs`
ในไฟล์นี้ไม่ได้มีแค่ CG/เสียง แต่มี **สคริปต์บทพูด `*.ks.scn` ครบ 92 บท** ด้วย:

```
adult.xp3  (861 entries)
  ├─ 92 × *.ks.scn          <-- ชื่อไฟล์จริงชุดเดียวกับที่แพตช์ไทยเขียนทับใน patch.xp3
  ├─ append_setup_0.tjs · !scnlist_98.txt · !scnlist_99.txt
  ├─ cglist_0.csv · scenelist_0.csv
  └─ 297 ogg · 116 jpg · 36 tlg · 4 mp4 ...
```

ลำดับโหลด archive (ต่ำ → สูง):

```
scn.xp3  <  patch_extra.xp3  <  patch.xp3  <  adult.xp3
                                    ↑             ↑
                            แพตช์ไทยเขียนตรงนี้   append pack ทับหมด
```

`adult.xp3` อยู่บนสุด → บทพูดทุกบรรทัดถูกอ่านจากสำเนา R18 ซึ่ง CN slot ยังเป็นภาษาจีน
ไทยที่อยู่ใน `patch.xp3` จึงไม่เคยถูกอ่านเลย

### วัดจริงด้วย `tools/check_shadowing.ps1`

| สถานะ | patch.xp3 ส่งบทถึงเกม |
|---|---|
| ไม่มี `adult.xp3` (ก่อนลง R18) | 86 / 86 — ไทยขึ้นครบ |
| มี R18 `patch_extra.xp3` อย่างเดียว | 86 / 86 — ไทยยังขึ้น |
| มี `adult.xp3` | **0 / 86** — ไทยหายเกลี้ยง |

→ **`adult.xp3` คือตัวการเดียว** `patch_extra.xp3` อยู่ *ใต้* `patch.xp3` จึงไม่มีผล

### 🔑 สิ่งที่ไม่คาดคิด: สคริปต์ R18 มี 5 ภาษา ไม่ใช่ 4

```
all-ages (patch.xp3) : [JP, EN, CN, TW]
R18      (adult.xp3) : [JP, EN, CN, TW, KO]      <-- เกาหลีถูกเพิ่มเข้ามา
```

ตัวอย่างบล็อกเดียวกันในไฟล์ R18:

```json
[[null,"「……ぁ？」"], ["Masaomi","...Hm?"], ["将臣","「……呃？」"],
 ["將臣","「……呃？」"], ["마사오미","……응?"]]
```

**นี่คือสาเหตุหลักที่ไฟล์ R18 ใหญ่กว่า ~11.7% ไม่ใช่ฉาก H อย่างเดียว** และเป็นเหตุผลที่
`is_block()` เดิม (เช็ค `len(x) == 4`) มองไม่เห็นบล็อกบทพูดในไฟล์ R18 เลยแม้แต่บล็อกเดียว
`tools/port_r18.py` จึงรับทั้ง 4 และ 5 ช่อง (ตำแหน่ง CN ยังเป็น index 2 เหมือนเดิม)

---

## สิ่งที่ทำไปแล้ว (เสร็จเรียบร้อย)

| ขั้น | ผล |
|---|---|
| GARbro ถอด `patch.xp3` → `patch_extract/` | 86 สคริปต์ |
| GARbro ถอด `adult.xp3` → `adult_extract/` | 92 สคริปต์ |
| `pipeline_cn.py decompile/export` + `_merge.py` ทุก prefix | 45,182 บรรทัดไทยเข้า `strings_cn.csv` ครบ 100% |
| `port_r18.py decompile` (92 ไฟล์) | 87 วินาที |
| `port_r18.py align` (จับคู่ด้วยข้อความ JP + `difflib`) | **45,139 / 55,846 บรรทัด (80.8%)** |
| `port_r18.py import` | 45,120 บรรทัด + 19 ตัวเลือก เข้า CN slot |
| `port_r18.py recompile` | 92/92 ไฟล์ · ไม่มีไฟล์ไหนล้นขนาดเดิม |
| `port_r18.py pack adult.xp3` | 92/92 บท เข้ารหัสกลับด้วย keystream |
| `port_r18.py pack patch_extra.xp3` | 92/92 (กันเหนียว เผื่อลำดับโหลดต่างจากที่วิเคราะห์) |
| `install.bat` (xdelta patch.xp3 + data.xp3) | สำเร็จทั้งคู่ — ได้ฟอนต์ไทยมาด้วย |

**45,139 จาก 45,182 บรรทัดไทยเดิม (99.9%) ย้ายมาได้อัตโนมัติ**

### ผลตรวจ

```
tools/check_thai.ps1 -GameDir "E:\SteamLibrary\steamapps\common\SenrenBanka"

archive ที่ชนะลำดับโหลด: adult.xp3
92 ไฟล์ · สตริงไทยรวม 43,494 / 318,459 · ไฟล์ที่ไม่มีไทยเลย 6     (ก่อนแก้ = 0)
SourceHanSansSC-{Regular,Bold,Heavy}.otf  thai glyphs = 87        (ก่อนแก้ = 0)
VERDICT: PARTIAL — ฟอนต์พร้อม ไทยขึ้นได้ แต่ยังมีบทที่ไม่ได้แปล
```

asset อื่นไม่พัง: ถอดไฟล์เสียงทั้ง 297 ไฟล์จาก `adult.xp3` ที่แพตช์แล้ว เทียบกับต้นฉบับ
ตรงกันทุกไบต์

### ไฟล์สำรอง

| สำรองไว้ที่ | คือ |
|---|---|
| `adult.xp3.orig` | adult.xp3 ของ R18 ก่อนใส่ไทย |
| `patch_extra.xp3.orig` | patch_extra.xp3 ของ R18 ก่อนใส่ไทย |
| `patch_extra.xp3.steam.bak` (+`.sig`) | ของ Steam แท้ (53 MB) |
| `patch.xp3.bak` · `data.xp3.bak` | ของ Steam แท้ ก่อนลงแพตช์ไทย (`uninstall.bat` ใช้คู่นี้) |

---

## ⚠️ ข้อควรระวัง

1. **อย่ารันตัวติดตั้ง R18 (`SenrenBanka_Steam_R18DLC.exe`) ซ้ำ** — มันจะเขียนทับ `adult.xp3`
   ด้วยของเดิมที่ไม่มีไทย ถ้าเผลอรันไปแล้วให้ทำใหม่แค่:
   ```
   python tools/port_r18.py pack "<game>\adult.xp3" "<game>\adult_extract"
   ```
2. **Steam "Verify integrity" ไม่ลบ `adult.xp3` / `adult2.xp3`** เพราะไม่ใช่ไฟล์ของ Steam
   → เกมที่ "verify แล้ว" อาจยังโดน append pack ทับอยู่ ทั้งที่ดูเหมือนสะอาด
3. เข้าเกมแล้วต้องตั้ง **Language = Chinese (Simplified)** เหมือนเดิม

---

## งานแปลที่เหลือ

**10,707 บรรทัด ใน 36 ไฟล์** (อีก 50 ไฟล์แปลครบ 100%) แก้ที่คอลัมน์ `th` ว่างใน
`thai_work/strings_r18.csv` (คอลัมน์ `src` บอกที่มา: `NEW` = มีเฉพาะฝั่ง R18,
`UNTRANSLATED` = มีในฝั่ง all-ages แต่ยังไม่เคยแปล) แล้วรัน:

```powershell
python tools/port_r18.py report                    # ดูสถานะรายไฟล์
python tools/port_r18.py import
python tools/port_r18.py recompile
python tools/port_r18.py pack "<game>\adult.xp3" "<game>\adult_extract"
```

บรรทัดที่ยังไม่ได้แปลจะแสดงเป็นภาษาจีนเดิม — ไม่พัง ไม่ค้าง ทยอยแปลได้

6 บทที่ยังไม่มีไทยเลยสักบรรทัด:

```
115・芳乃－ａｆｔｅｒ · 211・茉子－ａｆｔｅｒ · 317・ムラサメちゃんおまけルート
429レナ・いらっしゃい · 513・サブ－小春（ａｆｔｅｒ） · 523・サブ－芦花（ａｆｔｅｒ）
```

ไฟล์ที่ต้องแปลเพิ่มมากสุด: `317` (774) · `115` (711) · `211` (608) · `210` (607) ·
`511` (606) · `110` (583) · `306` (570) · `112` (562) · `207` (509) · `523` (480)

### 📌 ช่องโหว่ที่มีอยู่เดิมในแพตช์ all-ages

ตอนสร้าง `strings_cn.csv` ใหม่พบว่า **1,140 บรรทัดไม่เคยถูกแปล** (จาก 46,322) —
เป็นของเดิมที่หลุดไป ไม่ใช่ผลจากงานครั้งนี้ เช่น `001・アーサー王` มี 814 บรรทัด
แต่ `th/001.tsv` มี 789 (idx 787–813 ว่าง) ไฟล์ที่หลุดเยอะสุด:
`109` (93) · `203` (85) · `522` (83) · `415` (70) · `310` (63) · `521` (59) · `101` (56)

แปลเพิ่มใน `th/*.tsv` แล้วรัน `_merge.py` → `port_r18.py align/import/recompile/pack`
จะได้ทั้งฝั่ง R18 ไปพร้อมกัน

---

## เครื่องมือใน `tools/`

| ไฟล์ | หน้าที่ |
|---|---|
| `port_r18.py` | decompile / align / report / import / recompile / pack ฝั่ง R18 |
| `garbro_extract.ps1` | ขับ `GameRes.dll` ของ GARbro ตรงๆ — แตก/ถอดรหัส XP3 โดยไม่ต้องเปิด GUI |
| `check_shadowing.ps1` | บอกว่า archive ไหนชนะลำดับโหลด (อ่านชื่อไฟล์จริงจาก `sen:`→`hnfn`) |
| `verify_thai.py` | นับสตริงไทยใน PSB (อ่าน string table ตรงๆ ไม่ต้อง decompile) |
| `check_thai.ps1` | คำสั่งเดียวจบ: หา archive ที่ชนะ → ถอด → นับไทย → เช็คฟอนต์ |

ของที่ต้องโหลดเอง (ไม่ commit): `tools/FreeMote/` v4.7.0 · `tools/GARbro/` v1.5.44 ·
`tools/xdelta/` · Python 3.13

## เกร็ดโครงสร้างไฟล์

* `SenrenBanka_Steam_R18DLC.exe` = **ตัวติดตั้ง NSIS** (section `.ndata`/`.exehead`)
  ไม่ใช่ตัวเกม — แค่ก๊อปไฟล์เข้าโฟลเดอร์เกม
* `sen:` ในดัชนี XP3 ชี้ไป blob `hnfn` (zlib) = **ตาราง adler32 → ชื่อไฟล์จริง**
  ใช้แปลงชื่อ md5 กลับเป็นชื่อญี่ปุ่นได้ (`check_shadowing.ps1` ใช้วิธีนี้)
* `adlr` ในดัชนี = **adler32 ของ plaintext** — ยืนยันแล้ว: `001・アーサー王` ใน
  `patch_extra.xp3` มี `adlr = 0f4e317b` และ adler32 ของไฟล์ที่ GARbro ถอดออกมาก็ `0f4e317b`
  ใช้เป็น oracle ตรวจว่าถอดรหัสถูกได้เลย
* `adlr` ของบทเดียวกันใน `adult.xp3` และ R18 `patch_extra.xp3` ตรงกัน
  (`001` = `812d4ee3` ทั้งคู่) → เนื้อในเหมือนกัน psb ชุดเดียว pack ได้ทั้งสอง
* `*.ks.scn` = PSB v3 เข้ารหัส XOR keystream ที่ผูกกับ `adlr` — **ไม่ใช่คีย์เดียวทั้งไฟล์**
  (ช่วง header คีย์ = `0x01`, ช่วง string table = `0x98`) จึงต้องใช้ GARbro ถอด
  แล้วใช้ keystream method (`ks = origEnc XOR origPlain`) ตอน pack กลับ
* pack ใช้ big-int XOR แทน loop ทีละไบต์ → `adult.xp3` 855 MB เสร็จใน **4 วินาที**
