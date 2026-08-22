# Senren Banka — Thai Translation
### 千恋＊万花 แปลไทย

**เกมครบ 100% แล้ว — 86/86 ไฟล์ · แปล + ตรวจสอบเสร็จทั้งหมด**
**v1.1 — รองรับเกมที่ลงแพตช์ R18 ไว้แล้วด้วย** ([รายละเอียด](tools/R18_COMPAT.md))

งานแปลแฟน (fan translation) ของวิชวลโนเวล *Senren Banka* (Yuzusoft) เป็นภาษาไทยเต็มเรื่อง ครอบคลุมทุกเส้นทาง — Common, Yoshino, Murasame, Mako, Lena และ Sub

> ⚠️ เพื่อการศึกษา/ใช้ส่วนตัวเท่านั้น ต้องเป็นเจ้าของเกมแท้ (Steam) จึงจะใช้ได้ — repo นี้ไม่มี asset เกมใดๆ (สคริปต์ต้นฉบับ, รูป, เสียง, ฟอนต์)

---

## ติดตั้งง่าย (แนะนำ — ไม่ต้องลงโปรแกรมอะไรเพิ่ม)

1. มีเกม Senren Banka แท้บน Steam (เวอร์ชันตรงกับ Release ที่ระบุ)
2. โหลด `senrenbanka-thai-patch-*.zip` จากหน้า [Releases](../../releases)
3. แตกไฟล์ zip ไว้ที่ไหนก็ได้ (ไม่ต้องแตกทับโฟลเดอร์เกม)
4. ดับเบิลคลิก `SenrenBanka-Thai-Patch.exe` — มันหาโฟลเดอร์เกมให้เอง
5. เปิดเกม → ตั้งค่า Language เป็น **Chinese (Simplified)** → ได้ไทยทันที

ถอดคืนได้ในตัวติดตั้งเอง (ปุ่ม "ถอดแพตช์") หรือใช้ `install.bat` / `uninstall.bat` แทนก็ได้ ผลลัพธ์เหมือนกัน — แต่แบบ `.bat` ต้องเอาไฟล์ไปวางในโฟลเดอร์เกมก่อน

ตัวติดตั้งเป็น binary diff (xdelta) — ไฟล์ zip ไม่มีเนื้อหาลิขสิทธิ์ของเกมอยู่เลย ใช้ได้เฉพาะกับคนที่มีเกมแท้อยู่แล้วเท่านั้น

## ถ้าลงแพตช์ R18 ไว้

ซิปเดียวใช้ได้ทั้งสองแบบ — `install.bat` เห็น `adult.xp3` ก็จะแปะไทยให้ฉาก R18 ให้เอง

เหตุผล: แพตช์ R18 ติดตั้ง `adult.xp3` ซึ่งเป็น *append pack* ที่มีสคริปต์บทพูดครบ 92 บท และอยู่ **เหนือ** `patch.xp3` ในลำดับโหลด (`scn < patch_extra < patch < adult`) คำแปลไทยที่เขียนไว้ใน `patch.xp3` จึงถูกทับทั้งหมด แพตช์ v1.1 เลยเขียนไทยลงในสคริปต์ฝั่ง R18 โดยตรง

- ลำดับติดตั้งที่ถูกต้อง: **เกม → แพตช์ R18 → แพตช์ไทย**
- ห้ามรันตัวติดตั้ง R18 ซ้ำหลังลงไทยแล้ว (มันเขียนทับ `adult.xp3` ไทยหายทั้งเกม)
- ฝั่ง R18 แปลแล้ว 45,139/55,846 บรรทัด (80.8%) — ดู [`thai_work/PROGRESS_R18.md`](thai_work/PROGRESS_R18.md)

## Build จากซอร์ส (สำหรับนักพัฒนา)

อยากดูเบื้องหลัง/แก้คำแปลเอง/build เอง — ดูขั้นตอนละเอียดที่ [`tools/THAI_TRANSLATION_GUIDE.md`](tools/THAI_TRANSLATION_GUIDE.md)

สรุปสั้น: `pipeline_cn.py decompile → export → import → recompile → pack` ใส่คำแปลจาก `thai_work/th/*.tsv` เข้าไปแทน "ช่องภาษาจีน" ที่มีอยู่แล้วในทุกบทพูด แล้วสลับฟอนต์จีนเป็นฟอนต์ไทย — ไม่ต้องแก้เอนจิ้นเกม

ฝั่ง R18 ใช้ `port_r18.py` (align ด้วยข้อความ JP ต้นฉบับ ไม่ใช่ index) — ดู [`tools/R18_COMPAT.md`](tools/R18_COMPAT.md)

ทำชุดติดตั้งเอง: `python tools/build_release.py --version 1.1` (สร้าง diff → ตรวจย้อนกลับ → เขียน installer → zip)

## โครงสร้าง

```
CONTEXT.md  ศัพท์ของโปรเจกต์ — CN slot, load order, keystream, target/plan/step
tools/      เครื่องมือแปล/แพ็กไฟล์ (Python) + xdelta (ทำตัวติดตั้ง)
tools/gui/  ตัวติดตั้งแบบหน้าต่าง (tkinter, native Win32) — ดีไซน์จาก Claude Design
thai_work/  คำแปลไทยทั้งหมด + progress tracker + glossary
```

**อ่าน [`CONTEXT.md`](CONTEXT.md) ก่อนแก้โค้ด** — คำว่า "CN" ในชื่อไฟล์ไม่ได้แปลว่า
ภาษาจีน และ "repo" กับ "โฟลเดอร์เกม" เป็นคนละโฟลเดอร์กัน

ดูสถานะแบบละเอียดรายไฟล์ได้ที่ [`thai_work/PROGRESS.md`](thai_work/PROGRESS.md)

---

## License

- โค้ดเครื่องมือ (`tools/*.py`) — MIT ([`LICENSE`](LICENSE))
- คำแปลไทย (`thai_work/th/`, `glossary.csv`) — งานแปลแฟน เพื่อการศึกษา/ใช้ส่วนตัว
- ฟอนต์ที่ build ใช้ชื่อ reserved "Source Han Sans SC" ตาม OFL — ห้าม redistribute, build เองเท่านั้น
- เกม/บทต้นฉบับ — ลิขสิทธิ์ Yuzusoft/NekoNyan ไม่รวมอยู่ใน repo นี้
