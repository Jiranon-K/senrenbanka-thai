# Internals

Background notes moved out of the module headers. Rules the code depends on are in [RULES.md](RULES.md).

## `tools/build_release.py`

```text
build_release.py — สร้างชุดติดตั้งสำหรับผู้เล่นทั่วไป (xdelta) แบบครบวงจร

ทำอะไร
------
1. หาโฟลเดอร์เกม (ไต่ขึ้นไปหา SenrenBanka.exe)
2. สร้าง binary diff ของทุก archive ที่แพตช์ไทยแตะ:
       patch.xp3.bak  -> patch.xp3    (บทพูด all-ages)
       data.xp3.bak   -> data.xp3     (ฟอนต์ Sarabun)
       adult.xp3.orig -> adult.xp3    (บทพูดฝั่ง R18)  <-- ใหม่ใน v1.1
3. **ตรวจย้อนกลับทุกไฟล์**: decode diff แล้วเทียบ SHA256 กับของจริง
   (ไม่ผ่าน = ไม่ปล่อย ไม่มีข้อยกเว้น)
4. เขียน install.bat / uninstall.bat / README.txt / checksums.txt
   โดยฝัง SHA256 ที่คำนวณได้จริงลงไปในตัวสคริปต์
5. zip ออกมาเป็น senrenbanka-thai-patch-v<version>.zip

ทำไม installer ถึงหน้าตาแบบนี้
------------------------------
* **ซิปเดียวจบ ตรวจโหมดเอง** — มี adult.xp3 อยู่ = ผู้เล่นลงแพตช์ R18 แล้ว
  ก็แปะ thai-adult.xdelta ให้ด้วย; ไม่มีก็ข้าม. แยกสองซิปแล้วคนโหลดผิดตัว
  จะได้ไทยครึ่งๆ กลางๆ ซึ่งเป็นบั๊กที่ debug ยากที่สุด
* **สำรองด้วยการ "เปลี่ยนชื่อ" ไม่ใช่ "ก็อปปี้"** — v1.0 ก็อปปี้ patch+data
  ก่อนแปะ = เขียนดิสก์เกินไป 1.3 GB; v1.1 มี adult.xp3 อีก 855 MB
  move บน volume เดียวกันเป็น O(1) → ใช้พื้นที่แค่เท่าไฟล์ผลลัพธ์ และเร็วกว่ามาก
* **เช็ค SHA256 ก่อนแตะไฟล์** — xdelta จะ error เองถ้าเวอร์ชันไม่ตรง แต่สาย
  เกินไปและข้อความอ่านไม่รู้เรื่อง เช็คก่อนทำให้แยกได้ว่า
  "ลงไปแล้ว" / "Steam อัปเดตเกม" / "แพตช์ R18 คนละ build"
* **ถ้าแปะ adult.xp3 ไม่ได้ = ล้มทั้งชุด** ไม่ยอมแปะครึ่งเดียว เพราะ adult.xp3
  ทับ patch.xp3 อยู่ (ดู R18_COMPAT.md) → แปะครึ่งเดียวเกมจะขึ้นภาษาจีนเงียบๆ

หมายเหตุเรื่อง encoding ของ .bat
--------------------------------
`.bat` ที่มีข้อความไทยต้องเป็น **UTF-8 ไม่มี BOM + CRLF** และมี `chcp 65001` บนสุด

BOM ทำให้บรรทัดแรกกลายเป็น `<BOM>@echo off` ซึ่ง cmd.exe อ่านไม่ออก → ขึ้น
`'@echo' is not recognized` แล้ว echo ก็ไม่ถูกปิด ผู้เล่นเห็นทุกคำสั่งวิ่งผ่านจอ
(v1.0 เป็นแบบนี้) วัดจริงด้วยเมทริกซ์ codepage เริ่มต้น x BOM:

    CP เริ่มต้น   ไม่มี BOM                 มี BOM
    437           ok / ไทยขึ้น / echo off    parse error + echo ไม่ปิด
    874 (ไทย)     ok / ไทยขึ้น / echo off    parse error + echo ไม่ปิด
    1252          ok / ไทยขึ้น / echo off    parse error + echo ไม่ปิด
    65001         ok / ไทยขึ้น / echo off    ok (บังเอิญรอด)

cmd.exe อ่าน batch ทีละบรรทัดโดย decode ด้วย codepage *ปัจจุบัน* → `chcp 65001`
บรรทัดที่ 3 ทำให้บรรทัดหลังจากนั้นถูกอ่านเป็น UTF-8 อยู่แล้ว ไม่ต้องพึ่ง BOM
(บรรทัดก่อน chcp ต้องเป็น ASCII ล้วน — ซึ่งเป็นแบบนั้นอยู่แล้ว)

`README.txt` / `checksums.txt` **คง BOM ไว้** เพราะเปิดด้วย Notepad

วิธีใช้
-------
    python tools/build_release.py --version 1.1
    python tools/build_release.py --version 1.1 --reuse      # ไม่ encode ใหม่
```

## `tools/build_thai_font.py`

```text
Build the Thai message font:
  1. Merge CJK punctuation glyphs (「」『』、。・〜♪！？) from SourceHanSansSC (CFF)
     into Sarabun (glyf) via cu2qu (UPM 1000 == 1000, no scaling). -> Sarabun-merged.ttf
  2. Make 3 SC variants carrying each SourceHanSansSC-{Regular,Bold,Heavy} name table
     + weight so Windows GDI face-matching works. -> thai_work/fonts/variants/
```

## `tools/corpus.py`

```text
corpus.py — decompile / import / recompile / pack ที่ทั้งสองสายใช้ร่วมกัน

เดิมสี่คำสั่งนี้ถูกก็อปไว้ใน `pipeline_cn.py` กับ `port_r18.py` ต่างกันแค่ที่อยู่
กับ layout ตอนนี้ต่างกันแค่ค่า `Corpus` ที่ส่งเข้ามา:

    ALL_AGES_CORPUS  -> scenario.ALL_AGES (pipeline_cn.py)
    R18_CORPUS       -> scenario.R18      (port_r18.py)

**สองค่านี้ห้ามสลับกัน** — ระบบเลข idx ต่างกัน (อ่านหัวไฟล์ tools/scenario.py)
```

## `tools/freemote.py`

```text
freemote.py — PSB <-> json ผ่าน FreeMote (PsbDecompile.exe / PsBuild.exe)

เดิม `subprocess.run(..., capture_output=True)` ถูกเขียนไว้ 5 ที่ แล้ว**ทิ้ง output**
ทุกที่ จากนั้นเดาเอาว่า FreeMote เขียนไฟล์ชื่ออะไร (`.pure.scn` หรือ `.psb`)
ถ้า build ไม่ผ่าน บทนั้นก็แค่หายไปจาก pack เงียบๆ — ไม่มี error สักบรรทัด

ตอนนี้ทุกที่เรียกผ่านตัวนี้ ซึ่ง raise `FreeMoteError` (พร้อม stdout/stderr)
เมื่อ exit code ไม่ใช่ 0 หรือหาไฟล์ผลลัพธ์ไม่เจอ

    fm = freemote.default()
    js  = fm.decompile("001.ks.scn", out_dir)     # -> out_dir/001.ks.json
    scn = fm.build(js, psb_dir)                   # -> psb_dir/001.ks.scn

พฤติกรรมของ FreeMote ที่ต้องรู้ (ซ่อนไว้ในนี้ทั้งหมด)
  * PsbDecompile เขียน `<stem>.json` (+ `<stem>.resx.json`) **ข้างไฟล์ต้นทาง**
  * PsBuild เขียนลง **CWD** เป็น `<stem>.pure.scn` หรือ `<stem>.psb`

`run` รับเข้ามาได้ เทสจึงใส่ตัวปลอมแทน exe จริงได้ (ดู test_pipeline.py)
```

## `tools/gui/anim.py`

```text
anim.py — เครื่องยนต์ทวีนแบบ anime.js ขนาดพอดีมือ สำหรับ tkinter

แนวคิดเดียวกับ anime.js: บอก "ระยะเวลา + ฟังก์ชันผ่อน (easing) + สิ่งที่จะทำ
ในแต่ละเฟรม" แล้วปล่อยให้ตัวจับเวลากลางเดินให้

ทำไมต้องเขียนเอง ไม่ใช้ไลบรารี:
  * Tk ไม่มีระบบ animation ในตัว
  * ห้ามมี dependency เพิ่ม (`.exe` ต้องเล็กและ build ผ่านทุกเครื่อง)
  * ที่สำคัญคือต้องมี **ตัวจับเวลาตัวเดียว** สำหรับทวีนทุกตัว
    ถ้าปล่อยให้แต่ละอนิเมชันเรียก after() ของตัวเอง งานจะซ้อนกันจน Tk
    ประมวลผลไม่ทัน — เป็นสาเหตุเดียวกับที่ทำให้หน้าต่างลากแล้วกระตุก

กติกาสามข้อที่ยึดไว้:
  1. ตัวจับเวลาเดินเฉพาะตอนมีงาน หมดงานแล้วหยุด (ไม่ปลุก CPU ทิ้งไว้)
  2. เวลาอ้างจากนาฬิกาจริง ไม่ใช่นับเฟรม — เฟรมตกก็ยังจบตรงเวลา
  3. เคารพค่า "แสดงภาพเคลื่อนไหวใน Windows" ของผู้ใช้ ถ้าปิดไว้ก็ข้ามให้หมด
```

## `tools/gui/app.py`

```text
app.py — หน้าต่างติดตั้งแพตช์แปลไทย (Windows native, tkinter)

    python tools/gui/app.py
    python tools/gui/build/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

เป็นโปรแกรมหน้าต่างจริงๆ: widget ของ Windows ล้วน มีปุ่มบน taskbar
ไม่มีเบราว์เซอร์ ไม่มี HTTP server ไม่เปิดพอร์ต ไม่ต้องพึ่ง WebView2

หน้าตาแบบ shadcn/ui (zinc + มุมโค้ง) — โครงหน้าจอเดิมมาจาก Claude Design
โปรเจกต์ "Fan-translation mod installer"
(โทเคนอยู่ใน theme.py, คอมโพเนนต์อยู่ใน widgets.py, รูปทรงโค้งอยู่ใน shape.py,
เปลือกหน้าต่างอยู่ใน window.py)

ตรรกะทั้งหมดอยู่ใน core.py — ไฟล์นี้เป็นแค่หน้าจอกับการเดินสถานะ
```

## `tools/gui/assets.py`

```text
assets.py — หาไฟล์ใน ui/ (ฟอนต์ · โลโก้ · ไอคอน · ภาพพื้นหลัง)

แยกออกจาก theme.py เพราะเป็นคนละเรื่อง: theme บอกว่า "สีอะไร ตัวหนังสือเท่าไร"
ส่วนไฟล์นี้บอกว่า "ไฟล์อยู่ที่ไหน" — และเปลี่ยนด้วยเหตุผลคนละอย่าง
(theme เปลี่ยนตามดีไซน์ ไฟล์นี้เปลี่ยนตามวิธี build)

ไฟล์ใน ui/ สร้างตอน build ด้วย tools/gui/build/make_logo.py และ make_bg.py
ถ้าไม่มีสักไฟล์ แอปยังรันได้ปกติ แค่ถอยไปใช้ดีไซน์เปล่าๆ
```

## `tools/gui/build/build_gui.py`

```text
build_gui.py — build tools/gui/ เป็น .exe เดี่ยวด้วย PyInstaller

    python tools/gui/build/build_gui.py --out <โฟลเดอร์ชุดติดตั้ง>

สิ่งที่ **อยู่ใน** .exe: Python runtime, tkinter, ฟอนต์ Sarabun
สิ่งที่ **ไม่อยู่ใน** .exe: manifest.json, *.xdelta, xdelta3.exe และทุกอย่าง
ในโฟลเดอร์ build/ นี้ (เครื่องมือทำ asset — ทำงานตอน build เท่านั้น)

ทำไมไม่ยัด .xdelta เข้าไปด้วย: ชุดติดตั้งมี install.bat ที่ใช้ไฟล์ชุดเดียวกันอยู่แล้ว
ยัดเข้าไปอีกชุด = ซิปโตขึ้น 26 MB โดยได้อะไรกลับมาแค่ "ไฟล์เดียว"
ตัว GUI หาโฟลเดอร์เกมเองได้อยู่แล้ว ผู้เล่นจึงแตกซิปไว้ที่ไหนก็ได้ ไม่ต้องแตกทับเกม
```

## `tools/gui/build/imgtool.py`

```text
imgtool.py — งานภาพที่ทำ **ตอน build เท่านั้น** (ตัวแอปไม่ได้ import ไฟล์นี้)

ถอดรหัส/ย่อขยายภาพด้วย GDI+ ผ่าน ctypes — มีอยู่ในทุกเครื่อง Windows ไม่ต้องลง
อะไรเพิ่ม และคุณภาพการย่อขยายดีกว่าเขียน bicubic เองใน Python มาก (เร็วกว่าด้วย)

ทำไมไม่ใช้ Pillow: `.exe` จะโตขึ้นหลาย MB เพื่องานที่ทำครั้งเดียวตอน build
ส่วนตัวแอปเองอ่าน PNG ด้วย Tk ได้อยู่แล้ว

ใช้โดย make_bg.py (แผงพื้นหลัง) และ make_logo.py (โลโก้ + ไอคอน)
```

## `tools/gui/build/make_bg.py`

```text
make_bg.py — แปลงภาพต้นฉบับเป็นแผงพื้นหลังแบบกระจกฝ้าของตัวติดตั้ง

    python tools/gui/build/make_bg.py "...\ภาพ.jpg"

ทำงาน **ตอน build เท่านั้น** ผลลัพธ์คือ `ui/bg.png` (RGBA) ที่ฝังการไล่จางไว้
ในช่อง alpha เรียบร้อยแล้ว ตัวแอปจึงแค่วางภาพลง canvas ไม่ต้องคำนวณอะไรเลย

ทำไมต้องแปลงก่อน ไม่โหลด .jpg ตรงๆ:
  * Tk อ่านได้แค่ PNG / GIF / PPM — ไม่มี JPEG
  * ห้ามลาก Pillow เข้ามาเพื่องานนี้งานเดียว (`.exe` จะโตขึ้นหลาย MB)
  * การไล่จาง/เบลอ/ลดความอิ่มสี ถ้าทำตอนรันคือเสียเวลาเปิดโปรแกรมฟรีๆ
    ทั้งที่ผลลัพธ์เหมือนเดิมทุกครั้ง

หมายเหตุเรื่องลิขสิทธิ์: ภาพ CG เป็นของผู้พัฒนาเกม สคริปต์นี้จึงรับ path
จากภายนอก ไม่เก็บไฟล์ต้นฉบับไว้ในที่เก็บโค้ด
```

## `tools/gui/build/make_logo.py`

```text
make_logo.py — ทำโลโก้มุมบนซ้าย + ไอคอนหน้าต่าง/taskbar จากภาพต้นฉบับ

    python tools/gui/build/make_logo.py "...\ภาพ.jpg"

ทำงาน **ตอน build เท่านั้น** ได้ออกมาสองอย่าง:

    ui/logo@20.png .. logo@40.png   เครื่องหมายมุมบนซ้ายของหน้าต่าง
    ui/icon.ico                     ไอคอนหน้าต่าง / taskbar / ตัว .exe

ทำไมต้องมีหลายขนาด: Tk ย่อภาพได้แค่หารด้วยจำนวนเต็มแบบ nearest-neighbour
ซึ่งขอบจะแตกทันทีที่ย่อ จอ 125%/150%/200% จึงต้องมีไฟล์ของตัวเอง สร้างไว้
ล่วงหน้าด้วย bicubic ของ GDI+ แล้วให้แอปหยิบขนาดที่ใกล้ที่สุดไปใช้ตรงๆ

ไอคอนเก็บเป็น PNG ข้างใน .ico (รูปแบบที่ Windows อ่านได้ตั้งแต่ Vista)
จึงไม่ต้องเขียน BMP + AND mask เอง

หมายเหตุเรื่องลิขสิทธิ์: ภาพเป็นของผู้พัฒนาเกม สคริปต์นี้จึงรับ path จากภายนอก
ไม่เก็บไฟล์ต้นฉบับไว้ในที่เก็บโค้ด
```

## `tools/gui/core.py`

```text
core.py — ตรรกะการติดตั้งทั้งหมด ไม่มีส่วน UI เลย

แยกออกมาจาก app.py เพื่อให้เทสได้โดยไม่ต้องเปิดหน้าต่าง และเพื่อให้เห็นชัดว่า
GUI กับ install.bat ทำ "สิ่งเดียวกัน" — ลำดับขั้นตอนตรงกับ install.bat ที่
tools/test_installer.sh เทสไว้แล้ว 6 เคส:

  1. ต้องไม่มี .bak ค้างอยู่          (มี = ติดตั้งไปแล้ว)
  2. เช็ค SHA256 ก่อนแตะไฟล์ใดๆ
       - ตรงกับ hash ของไฟล์ที่แปะไทยแล้ว -> ติดตั้งแล้ว
       - ไม่ตรงกับ hash ต้นฉบับ           -> เวอร์ชันไม่รองรับ ยกเลิกทั้งชุด
  3. สำรองด้วยการ "เปลี่ยนชื่อ" ไม่ใช่ก็อปปี้ (adult.xp3 = 855 MB)
  4. xdelta3 -d ทีละไฟล์
  5. ล้มกลางคัน -> คืนทุกไฟล์ที่ rename ไปแล้ว

เจตนาสำคัญ: **ไม่แปะครึ่งเดียว** ถ้า adult.xp3 มีอยู่แต่แปะไม่ได้ ต้องล้มทั้งชุด
เพราะ adult.xp3 ทับบทพูดใน patch.xp3 อยู่ (ดู tools/R18_COMPAT.md)
แปะครึ่งเดียว = เกมขึ้นภาษาจีนเงียบๆ ซึ่งหาสาเหตุยากที่สุด
```

## `tools/gui/shape.py`

```text
shape.py — สี่เหลี่ยมมุมโค้งแบบขอบเนียน (anti-aliased) สำหรับ Tk

Canvas ของ Tk บน Windows วาดรูปทรงแบบไม่มี anti-aliasing — มุมโค้ง 6-8 px
จะเป็นขั้นบันไดชัดเจน ซึ่งทำลายลุค shadcn ทั้งหมด
ทางออก: วาดเป็น PhotoImage เองโดยรู้สีพื้นข้างใต้อยู่แล้ว (ทุกจอพื้นทึบ)
จึงผสมสีขอบกับพื้นตรงๆ ได้ ไม่ต้องใช้ alpha และไม่ต้องพึ่ง PIL

  * ส่วนกลางกับเส้นขอบตรง เทสีทีเดียวด้วย put(color, to=box) — เร็วมาก
  * คำนวณทีละพิกเซลเฉพาะสี่มุม (สุ่ม 4x4 จุดย่อยต่อพิกเซล) — มุมละ r² พิกเซล
  * เก็บผลไว้ใน cache แบบจำกัดขนาด: ทวีนสีปุ่มสร้างสีใหม่ทุกเฟรม ห้ามโตไม่สิ้นสุด
```

## `tools/gui/test_app.py`

```text
test_app.py — เทสหน้าจอ (tkinter) โดยไม่ต้องมองจอ

    set SBTP_RES=...\thai_work\dist\senrenbanka-thai-patch-v1.1
    python tools/gui/test_app.py
    python tools/gui/test_app.py --no-input     # ข้ามเคสที่ขยับเมาส์จริง

หน้าต่างถูก withdraw ไว้ตลอด ไม่เด้งขึ้นมากวน — ตรวจจาก widget tree ตรงๆ
ยกเว้นเคสลากหน้าต่างด้วยเมาส์จริง ซึ่งต้องโชว์หน้าต่างจริงๆ ราว 1 วินาที

สิ่งที่เทสนี้กันไว้:
  * ฟอนต์ไทยที่ bundle มาต้องลงทะเบียนได้ และ Tk ต้องซ้อนสระ/วรรณยุกต์ถูก
    (ถ้าวันหนึ่ง Tk เปลี่ยน text engine แล้วไทยแตก เทสนี้จะจับได้ทันที)
  * โปรแกรมต้อง **ไม่เปิดพอร์ต TCP** — เวอร์ชันก่อนหน้าใช้ pywebview
    ซึ่งแอบตั้ง HTTP server ที่ 127.0.0.1 แล้วโหลดหน้าเว็บผ่านมัน
  * แถบหัวของ Windows ต้องถูกถอดออกจริง แต่หน้าต่างยังเป็น top-level ปกติ
  * **ลากหน้าต่างต้องเร็ว** — เดิมใช้ root.geometry() ซึ่งกิน 30 ms ต่อเฟรม
    (เพดาน 33 fps) หน้าต่างเลยตามเมาส์ไม่ทัน เห็นเป็นเงาแล้วกระโดดตาม
  * ตัวเลือก all-ages / R18 ต้องเปลี่ยนสิ่งที่จะทำกับไฟล์จริงๆ
  * สถานะปุ่ม/ขั้นตอน/หน้าจอ เดินถูกตามตาราง

หมายเหตุเรื่องอนิเมชัน: ค่าบนจอระหว่างทวีนยังไม่ใช่ค่าปลายทาง เทสจึงเรียก
A.flush() (จบทุกทวีนทันที) ก่อนตรวจ "สถานะที่ควรจะเป็น" เสมอ ส่วนตัวอนิเมชัน
เองมีหัวข้อเทสของมันแยกต่างหาก
```

## `tools/gui/test_core.py`

```text
test_core.py — เทส core.py ด้วยเคสชุดเดียวกับ tools/test_installer.sh

    set SBTP_RES=...\thai_work\dist\senrenbanka-thai-patch-v1.1
    python tools/gui/test_core.py

GUI กับ install.bat ต้องทำสิ่งเดียวกันเป๊ะ ถ้าเทสสองชุดนี้ให้ผลต่างกัน
แปลว่ามีตัวใดตัวหนึ่งผิด — จึงจงใจให้เคสตรงกัน

โฟลเดอร์ทดสอบใช้ **hard link** ไปยัง archive ต้นฉบับจริง: ไม่ต้องก็อป 2 GB
และ os.replace() ที่ core ใช้ก็แค่เปลี่ยนชื่อ link ไม่แตะไฟล์จริง
(เคสสุดท้ายยืนยันซ้ำว่าต้นฉบับไม่เปลี่ยน)
```

## `tools/gui/theme.py`

```text
theme.py — โทเคนสีและขนาดของตัวติดตั้ง หน้าตาแบบ shadcn/ui แปลงเป็น Tk

ที่มา: ค่าสีกลางคือชุด **zinc** ของ Tailwind (ตัวเดียวกับธีมตั้งต้นของ shadcn/ui)
ส่วนสีส้มเก็บไว้ใช้เฉพาะ action หลัก ขั้นปัจจุบัน และของที่ "ถูกเลือก"
— ตรงกับหลักของ shadcn ที่ให้สีหลักโผล่น้อยที่สุด

เดิมใช้ระบบ "Modernist" จาก Claude Design (มุมฉาก ไม่มีขอบโค้ง) ชื่อโทเคนยังคง
ชื่อเดิมไว้ (TEXT_55, HOVER_SOFT, ...) เพื่อไม่ต้องไล่แก้ทุกที่ที่ใช้ ค่าข้างในเปลี่ยน

shadcn ใช้ alpha หลายจุด (`bg-primary/20` ฯลฯ) — Tk ไม่มี alpha บนพื้นทึบ จึงคำนวณ
ล่วงหน้าเป็น hex โดยผสมกับพื้นขาว ได้ผลตาเดียวกัน

**ไฟล์นี้มีแต่โทเคน ไม่มีอย่างอื่น**
  * ปลั๊กเข้าระบบปฏิบัติการ -> winui.py
  * หาไฟล์ใน ui/           -> assets.py
  * วาดรูปทรงมุมโค้ง        -> shape.py
  * เขียน PNG/ICO           -> build/imgtool.py (ทำตอน build เท่านั้น)
```

## `tools/gui/widgets.py`

```text
widgets.py — คอมโพเนนต์หน้าตาแบบ shadcn/ui ทำเป็น Tk widget

ทุกตัวเป็น widget ของ Windows จริง ไม่มี HTML/เบราว์เซอร์เข้ามาเกี่ยว
ของที่มีมุมโค้ง (ปุ่ม ป้าย ช่องกรอก การ์ด กล่องติ๊ก แถบคืบหน้า) เป็น Canvas
ที่แปะรูปจาก shape.py — Canvas ของ Tk วาดโค้งแบบขอบหยัก จึงไม่ใช้รูปทรงของมันเอง

ตัวที่มีข้อความ (Button, Tag) ตอบ config/cget เหมือน Label: `text`,
`foreground` และ `background` — โดย background หมายถึง **สีของรูปทรง**
(พื้นของ canvas จริงๆ คือสีของ parent) จึงใช้ _tint ไล่สีได้เหมือนเดิมทุกอย่าง

การเคลื่อนไหวทุกตัวเดินผ่าน anim.py (ตัวจับเวลากลางตัวเดียว) และผูก key ไว้กับ
id ของ widget เสมอ เพื่อให้ทวีนตัวใหม่ล้มตัวเก่าทิ้ง — ไม่งั้นเมาส์กวาดเข้า-ออก
เร็วๆ จะมีทวีนสองตัวแย่งกันเขียนสีเดียวกัน แล้วสีค้างผิด
```

## `tools/gui/window.py`

```text
window.py — เปลือกหน้าต่างแบบไม่มีแถบหัวของระบบ

แยกออกมาจาก app.py ซึ่งเป็นคลาสเดียว 800 บรรทัดที่ทำสี่เรื่องไม่เกี่ยวกัน
(เปลือกหน้าต่าง · ประกอบหน้าจอ · เดินสถานะ · เธรดกับงานจริง) เรื่องแรก
ไม่เกี่ยวกับ "การติดตั้งแพตช์" เลยสักนิด — มันจะเหมือนกันหมดไม่ว่าหน้าต่างนี้
จะเอาไปทำอะไร

ที่อยู่หลัง interface นี้: การสร้าง Tk, ตัวคูณ DPI, การถอดแถบหัวด้วย Win32,
การจัดกลางจอ, การหักขนาดกรอบที่ Tk จำไว้, ไล่ความทึบเข้า/ออก, ลากหน้าต่างเอง
ด้วย SetWindowPos, สั่นตอนล้มเหลว, โลโก้ที่เลือกไฟล์ตาม DPI และแผงภาพพื้นหลัง

ผู้เรียกเห็นแค่:

    win = Window("ชื่อ", (880, 600), on_close=...)
    win.root                      Tk root ตัวจริง
    win.appear() / win.close()
    win.shake()
    win.drag_from(widget, ...)
    win.mark(parent)              เครื่องหมายมุมบนซ้าย
    win.backdrop(parent, box)     แผงภาพด้านขวา
    win.slide_backdrop(dx, dur)
```

## `tools/gui/winui.py`

```text
winui.py — สิ่งที่ต้องคุยกับ Windows ตรงๆ ผ่าน ctypes

แยกออกจาก theme.py เพราะคนละเรื่องกันโดยสิ้นเชิง: theme คือโทเคนดีไซน์
(สี ฟอนต์ ระยะ) ส่วนไฟล์นี้คือปลั๊กเข้าระบบปฏิบัติการ ก่อนหน้านี้อยู่ปนกัน
ในไฟล์ชื่อ "theme.py" ซึ่งคนเปิดเข้ามาหาสีจะเจอ ctypes ของ Win32 แทน

ผลพลอยได้ที่สำคัญ: `import theme` ตอนนี้ไม่ลาก ctypes ตามมา เทส widgets
จึงรันได้โดยไม่ต้องมี Windows

ตั้งชื่อ winui ไม่ใช่ win32 เพราะ pywin32 จองชื่อ `win32` ไว้แล้ว
```

## `tools/mt.py`

```text
mt.py — machine-translate scenario lines JP/EN -> Thai with Claude, one line per idx.

The released patch has 1,744 lines whose Thai belongs to a different JP line
(docs/audit-2026-10.md). This tool cannot produce that defect: every request
asks for a JSON list keyed by `idx`, and a chunk is rejected unless it returns
exactly the idx set it was given, with the same opening quote bracket as the JP.

    python tools/mt.py sync   --csv cn --file 001 [--all]   # direct calls (pilot)
    python tools/mt.py submit --csv cn --file 001 [--all]   # Message Batches, 50% price
    python tools/mt.py collect <batch_id>                   # fetch batch results
    python tools/mt.py wait <batch_id>...                   # block until batches end
    python tools/mt.py merge 001 003 ...                    # mt/cn -> th/<prefix>.tsv
    python tools/mt.py cost                                 # spend so far

--csv cn|r18 picks strings_cn.csv (all-ages) or strings_r18.csv.
Without --all only lines whose `th` is empty are sent; --all retranslates every line.
H scenarios (scenarios.json is_h) are never sent.

Output: thai_work/mt/<csv>/<prefix>.json  {idx: thai}. Nothing in th/ or the
CSVs is touched — review first, then merge.

The key is read from REPO/.env (ANTHROPIC_API_KEY=...), never from the process
environment, so Claude Code keeps using the subscription. Plain urllib on purpose:
the SDK's native dependency (jiter) is blocked by Windows Application Control here.
```

## `tools/paths.py`

```text
paths.py — ที่อยู่ของทุกอย่างในโปรเจกต์ ประกาศไว้ที่เดียว

เดิมทุกสคริปต์ใน tools/ ประกาศเองว่า

    GAME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ซึ่งพังไปแล้วสองชั้น:

1. **ชื่อโกหก** — ค่านั้นคือ *โฟลเดอร์ repo* ไม่ใช่โฟลเดอร์เกม เห็นได้จาก
   `os.path.join(GAME, "tools", "FreeMote", ...)` ส่วนคำว่า "game" ที่
   tools/gui/core.py ใช้ หมายถึงโฟลเดอร์ที่ผู้เล่นลงเกมไว้จริงๆ — คนละอย่าง
   กันคนละฝั่ง repo แต่ชื่อเดียวกัน

2. **สมมติฐานหมดอายุ** — หัว .gitignore เขียนไว้ว่า "This repo lives inside
   the GAME directory" ซึ่งเคยจริง ตอนนี้ repo ย้ายลงมาลึกอีกสองชั้นแล้ว
   (…/SenrenBanka/senrenbanka-thai-patch-v1.0/senrenbanka-thai/) ทำให้
   `join(GAME, "data.xp3")` ชี้ไปที่ที่ไม่มีไฟล์ — pipeline_cn.py pack,
   port_r18.py pack และ rebuild_fonts.py จึงหาไฟล์ไม่เจอทั้งหมด

ตกลงกันใหม่ ใช้สองคำนี้เท่านั้น (ดู CONTEXT.md):

    REPO         โฟลเดอร์ repo — ที่อยู่ของ tools/ กับ thai_work/
    game_dir()   โฟลเดอร์ที่ผู้เล่นลงเกมไว้ — ที่อยู่ของ *.xp3 กับ SenrenBanka.exe

หมายเหตุ: **tools/gui/ ไม่ import ไฟล์นี้** ตัวติดตั้งถูก build เป็น .exe
เดี่ยวๆ ไปอยู่บนเครื่องผู้เล่นที่ไม่มี repo อยู่เลย มันจึงต้องหาโฟลเดอร์เกม
ด้วยวิธีของมันเอง (core.find_game_dirs — อ่าน Steam library เพิ่มด้วย)
```

## `tools/qc.py`

```text
QC for translated scenarios. Run after `import`, before `pack`.
  qc.py <substr|all> [all-ages|r18]        (default: all-ages)
Checks (on the post-import json + strings CSV of the chosen corpus):
  1 untranslated  : CN slot still has Han/kana  (=> □ or original Chinese on screen)
  2 missing glyph : char in CN slot not in Sarabun-merged.ttf cmap  (=> □)
  3 tag preserve  : control codes (%NN; [..] \n ${..} 【】) count en vs th mismatch
  4 overflow      : len(th)/len(en) > 1.7  (may overflow textbox)
  5 glossary      : en has glossary key but th missing its value
Exit 1 if any untranslated or missing-glyph (hard errors).

เดิมไฟล์นี้มีตัวเดินบล็อกเป็นของตัวเอง ซึ่งรับแค่ 4 ช่องภาษา แปลว่าตอนเอามา
ตรวจฝั่ง R18 (ที่มี 5 ช่อง) มันข้ามบทพูดทั้งหมดไปเงียบๆ แล้วรายงานว่าผ่าน
ทั้งที่ยังไม่ได้ตรวจอะไรเลย — ตอนนี้ใช้ layout ตัวเดียวกับ pipeline โดยเลือก
ตามคลังที่กำลังตรวจ (ดู tools/scenario.py)
```

## `tools/rebuild_fonts.py`

```text
Rebuild data.xp3 from data.xp3.orig: replace SourceHanSansSC-{Regular,Bold,Heavy}
with the merged Sarabun variants (Thai + CJK punctuation glyphs).

Uses the same keystream trick as the scenario packers — see tools/xp3.py.
Fonts are the one case where the archive's own entry name IS the real filename,
so these are matched by name instead of by size.
```

## `tools/scenario.py`

```text
scenario.py — เดินสคริปต์บทพูดที่ decompile ออกมาเป็น json

บทพูดหนึ่งบรรทัดเก็บเป็น "ช่องภาษาเรียงกัน":

    [[ชื่อผู้พูด|null, ข้อความ, ...], ...]   ← JP, EN, CN, TW  (+ KO ฝั่ง R18)

แพตช์นี้เอาคำแปลไทยไปทับ **ช่อง CN** (index 2) ดู CONTEXT.md

═══════════════════════════════════════════════════════════════════════
  ทำไมมี Layout สองตัว และทำไมห้ามรวมเป็นตัวเดียว
═══════════════════════════════════════════════════════════════════════
สายงานสองสายนับ "อะไรคือบล็อกบทพูด" ไม่เหมือนกัน:

    ALL_AGES   4 ช่อง · ยอมให้สมาชิกในช่องเป็นอย่างอื่นนอกจากข้อความได้
    R18        4 หรือ 5 ช่อง · ทุกสมาชิกต้องเป็นข้อความหรือ null เท่านั้น

วัดกับสคริปต์จริง 86 บท: **นับได้ไม่เท่ากัน 70 บท** (46,303 vs 45,208 บล็อก)

นั่นไม่ใช่ "ฉบับหนึ่งถูก อีกฉบับผิด" แต่แปลว่า **เลข idx คนละระบบ**
และ `thai_work/th/*.tsv` กับ `strings_cn.csv` (คำแปล 45,182 บรรทัด) ถูก
เก็บเป็น `idx<TAB>คำแปล` โดยนับด้วย ALL_AGES ไว้แล้ว

ถ้าเผลอเอา R18 ไปใช้กับสาย all-ages: เลขเลื่อนทั้งเกม คำแปลไปโผล่ผิดคน
ทั้ง 45,182 บรรทัด และ**ไม่มีอะไรพัง ไม่มี error** — เห็นตอนเล่นอย่างเดียว

ตัวที่ ALL_AGES รับแต่ R18 ไม่รับ คือ node อย่าง
    [["bgm","bgm",{...}], ["lse","loopse",{...}], ...]
ซึ่งบังเอิญมี 4 ช่องเหมือนบทพูด — เป็น false positive จริง แต่มันถูกนับไป
แล้วตอนสร้าง CSV จะแก้ได้ก็ต่อเมื่อ export ใหม่ทั้งชุดพร้อมย้ายคำแปลตาม
(ไม่ใช่งานของการจัดระเบียบโค้ด)

จึงตั้งชื่อตาม **คลังคำแปลที่มันนับไว้** ไม่ใช่ตามความถูกต้อง — ที่จุดเรียก
จะได้อ่านออกทันทีว่ากำลังนับด้วยระบบไหน
```

## `tools/targets.py`

```text
targets.py — ตารางไฟล์ที่แพตช์แตะ **ที่เดียวในโปรเจกต์**

เดิมตารางนี้อยู่ 5 ที่ และเพิ่ม archive สักไฟล์ต้องแก้ครบทุกที่ ใน 2 ภาษา:

    1. TARGETS (tuple 5 ช่อง) ใน build_release.py
    2. บล็อก set ที่ hardcode ชื่อตัวแปร ORIG_/THAI_ x PATCH/DATA/ADULT
    3. รายชื่อไฟล์ใน INSTALL_BODY (for %%F in (...)) + บล็อก rollback
    4. UNINSTALL_BODY
    5. core.Plan.R18_FILES — ซึ่งมี adult2.xp3 ที่ไม่มีในข้อ 1 เลย

ลืมที่ใดที่หนึ่ง = `.bat` กับ GUI ทำคนละอย่างกัน ซึ่งเป็นบั๊กประเภทที่ผู้เล่น
เจอแต่คนพัฒนาไม่เจอ (คนพัฒนารัน GUI ผู้เล่นดับเบิลคลิก .bat)

ตอนนี้ทุกอย่างงอกออกจากตารางนี้: manifest.json ที่ตัวติดตั้ง GUI อ่าน และ
ชิ้นส่วนของ install.bat/uninstall.bat ที่เป็นรายการซ้ำๆ ต่อไฟล์

**ส่วนที่ยังไม่ได้ generate**: ลำดับขั้นตอนใน .bat (เช็ค -> สำรอง -> แปะ)
ยังเขียนไว้ตรงๆ เพราะมีเงื่อนไขเฉพาะของ R18 ที่ไม่เหมือนไฟล์อื่น และมี
tools/test_installer.sh คุมอยู่แล้ว 6 เคส — แต่ build_release.py จะ assert
ว่า .bat พูดถึงทุกไฟล์ในตารางนี้ครบ ถ้าเพิ่ม target แล้วลืมแก้ .bat จะ
**build ไม่ผ่าน** แทนที่จะปล่อยแพตช์ครึ่งเดียวออกไป
```

## `tools/test_pipeline.py`

```text
test_pipeline.py — เทสเครื่องมือฝั่ง tools/ ที่ไม่ใช่ GUI

    python tools/test_pipeline.py

ครอบ xp3.py (รูปแบบ archive), scenario.py (ตัวเดินบทพูด) และ targets.py
(ตารางไฟล์ที่แพตช์แตะ)

**ไม่ต้องมีเกม ไม่ต้องมีไฟล์ .xp3** — สร้าง archive จิ๋วขึ้นมาในหน่วยความจำเอง
นี่คือเหตุผลที่แยกโมดูลพวกนี้ออกมา: ตอนที่โค้ดยังฝังอยู่ใน cmd_pack()
ที่อ่าน sys.argv เองและเขียนทับ archive 855 MB เอง มันเทสไม่ได้เลยสักบรรทัด

ถ้ามี archive จริง / ชุดติดตั้งที่ build ไว้อยู่ในเครื่อง จะเทสเพิ่มอีกชุด
(ข้ามเองถ้าไม่มี)
```

## `tools/verify_thai.py`

```text
verify_thai.py - นับ "สตริงภาษาไทย" ในไฟล์ .ks.scn ที่ถอดรหัสแล้ว

ใช้เป็นตัวตัดสิน PASS/FAIL แบบตรงอาการ: เกมจะแสดงไทยได้ก็ต่อเมื่อ
สคริปต์ใน archive ที่ชนะลำดับโหลด (adult.xp3) มีข้อความไทยอยู่จริง

วิธีใช้
  # ถอด archive ที่จะตรวจออกมาก่อน
  powershell -File tools\garbro_extract.ps1 -Archive "...\adult.xp3" -OutDir "...\check_extract" -Filter "*.ks.scn"
  python tools/verify_thai.py "...\check_extract"

อ่าน string table ของ PSB v3 ตรงๆ (OffsetStringsData .. OffsetChunkOffsets)
ไม่ต้อง decompile ด้วย FreeMote จึงเร็วมาก
```

## `tools/xp3.py`

```text
xp3.py — อ่าน/เขียน archive .xp3 ของ KiriKiri (แบบที่ Yuzusoft ใช้)

เดิมโค้ดชุดนี้ถูกก็อปไว้ **สามที่** — `pipeline_cn.cmd_pack`, `port_r18.cmd_pack`
และ `rebuild_fonts.main` — แล้วสามฉบับก็ห่างกันไปเรื่อยๆ ฉบับหนึ่งมี assert กัน
header ผิดรุ่น อีกฉบับมี XOR แบบ big-int ที่เร็วกว่าเป็นร้อยเท่า อีกฉบับไม่มี
ทั้งคู่ ใครแก้ฝั่งไหนอีกสองฝั่งไม่ได้ตาม

ทั้งสามทำเรื่องเดียวกันเป๊ะ: "เอาไฟล์ใหม่ยัดกลับเข้า archive โดยไม่ต้องรู้คีย์"

    ar = xp3.Archive.read(game_file("adult.xp3"))
    for e in ar.entries:
        ar.replace(e, ไบต์ใหม่, ไบต์เดิมที่ถอดรหัสแล้ว)
    ar.save(game_file("adult.xp3"))

รูปแบบไฟล์ (เท่าที่ต้องรู้)
--------------------------
    [0:40]      header v2  (ไบต์ที่ 32-40 = offset ของ index)
    ...         เนื้อไฟล์แต่ละตัว เรียงต่อกัน (เข้ารหัสไว้)
    ...         'sen:' blob — ก้อนพิเศษของ Yuzu ที่ต้องขนไปด้วย ไม่งั้นเกมไม่โหลด
    [iofs:]     index บีบด้วย zlib — ต่อกันเป็นชุด 'File' + ความยาว + chunk
                chunk ข้างในเป็นชุด tag ('info' = ชื่อ, 'segm' = offset+size,
                'adlr' = id ที่ห้ามแตะ) + ความยาว + ข้อมูล

keystream (ไม่ต้องรู้คีย์)
--------------------------
    keystream = ไบต์ที่เข้ารหัสอยู่ XOR ไบต์จริงตัวเดิม
    ไบต์ที่จะเขียน = ไฟล์ใหม่ (pad ให้ยาวเท่าเดิม) XOR keystream

เกมสร้าง keystream เดิมขึ้นมาใหม่จาก `adlr` ที่เราไม่แตะ จึงถอดออกมาได้เป็น
ไฟล์ใหม่ ข้อจำกัดเดียว: **ไฟล์ใหม่ต้องไม่ใหญ่กว่าช่องเดิม**

สองเรื่องที่โค้ดชุดเดิมพลาด (เพิ่งเห็นตอนเอามาเทสได้)
------------------------------------------------------
1. `segm` ยาว 28 ไบต์เก็บ **สองขนาด**: หลังคลายบีบอัด กับที่เก็บจริง โค้ดเดิม
   อ่านแต่ตัวแรกมาใช้เป็นจำนวนไบต์ที่จะก็อป — data.xp3 มี 318 จาก 1,278 entry
   ที่บีบอัดไว้ ทุกครั้งที่ประกอบใหม่จึงลากเนื้อของ entry ข้างเคียงติดมาด้วย
2. entry หลายตัวชี้ไปที่ **ช่วงเดียวกัน** ได้ (data.xp3 มี 13 ช่วง = 26 MB)
   โค้ดเดิมก็อปแยกให้ทุกตัว ไฟล์จึงโตขึ้นฟรี

ผลรวมของสองข้อ: `data.xp3` ที่แพตช์แล้วโตกว่าต้นฉบับ 35 MB โดยไม่มีเหตุผล
ตอนนี้ประกอบกลับได้ขนาดเท่าเดิม (±ไม่กี่สิบไบต์จากการบีบ index) และเนื้อทุก
ไฟล์ตรงกันไบต์ต่อไบต์ — มีเทสคุมไว้ใน tools/test_pipeline.py

ดู CONTEXT.md หัวข้อ keystream packing
```
