# Senren Banka — Thai Translation
### 千恋＊万花 แปลไทย

**เกมครบ 100% แล้ว — 86/86 ไฟล์ · แปล + ตรวจสอบเสร็จทั้งหมด**

งานแปลแฟน (fan translation) ของวิชวลโนเวล *Senren Banka* (Yuzusoft) เป็นภาษาไทยเต็มเรื่อง ครอบคลุมทุกเส้นทาง — Common, Yoshino, Murasame, Mako, Lena และ Sub

> ⚠️ เพื่อการศึกษา/ใช้ส่วนตัวเท่านั้น ต้องเป็นเจ้าของเกมแท้ (Steam) จึงจะใช้ได้ — repo นี้ไม่มี asset เกมใดๆ (สคริปต์ต้นฉบับ, รูป, เสียง, ฟอนต์)

---

## ติดตั้งง่าย (แนะนำ — ไม่ต้องลงโปรแกรมอะไรเพิ่ม)

1. มีเกม Senren Banka แท้บน Steam (เวอร์ชันตรงกับ Release ที่ระบุ)
2. โหลด `senrenbanka-thai-patch-*.zip` จากหน้า [Releases](../../releases)
3. แตกไฟล์ zip ใส่ในโฟลเดอร์เกม (ที่มี `SenrenBanka.exe`)
4. ดับเบิลคลิก `install.bat`
5. เปิดเกม → ตั้งค่า Language เป็น **Chinese (Simplified)** → ได้ไทยทันที

ถอดแพตช์คืนได้ด้วย `uninstall.bat`. ตัวติดตั้งเป็น binary diff (xdelta) — ไฟล์ zip ไม่มีเนื้อหาลิขสิทธิ์ของเกมอยู่เลย ใช้ได้เฉพาะกับคนที่มีเกมแท้อยู่แล้วเท่านั้น

## Build จากซอร์ส (สำหรับนักพัฒนา)

อยากดูเบื้องหลัง/แก้คำแปลเอง/build เอง — ดูขั้นตอนละเอียดที่ [`tools/THAI_TRANSLATION_GUIDE.md`](tools/THAI_TRANSLATION_GUIDE.md)

สรุปสั้น: `pipeline_cn.py decompile → export → import → recompile → pack` ใส่คำแปลจาก `thai_work/th/*.tsv` เข้าไปแทน "ช่องภาษาจีน" ที่มีอยู่แล้วในทุกบทพูด แล้วสลับฟอนต์จีนเป็นฟอนต์ไทย — ไม่ต้องแก้เอนจิ้นเกม

## โครงสร้าง

```
tools/     เครื่องมือแปล/แพ็กไฟล์ (Python) + xdelta (ทำตัวติดตั้ง)
thai_work/ คำแปลไทยทั้งหมด + progress tracker + glossary
```

ดูสถานะแบบละเอียดรายไฟล์ได้ที่ [`thai_work/PROGRESS.md`](thai_work/PROGRESS.md)

---

## License

- โค้ดเครื่องมือ (`tools/*.py`) — MIT ([`LICENSE`](LICENSE))
- คำแปลไทย (`thai_work/th/`, `glossary.csv`) — งานแปลแฟน เพื่อการศึกษา/ใช้ส่วนตัว
- ฟอนต์ที่ build ใช้ชื่อ reserved "Source Han Sans SC" ตาม OFL — ห้าม redistribute, build เองเท่านั้น
- เกม/บทต้นฉบับ — ลิขสิทธิ์ Yuzusoft/NekoNyan ไม่รวมอยู่ใน repo นี้
