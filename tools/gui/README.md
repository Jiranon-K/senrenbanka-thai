# ตัวติดตั้งแบบหน้าต่าง

โปรแกรม Windows จริงๆ — widget ของระบบล้วน มีปุ่มบน taskbar มี Alt-Tab
**ไม่มีเบราว์เซอร์ ไม่มี HTTP server ไม่เปิดพอร์ต ไม่ต้องพึ่ง WebView2**

ทำงานเหมือน `install.bat` ทุกประการ แต่หาโฟลเดอร์เกมให้เอง จึงแตกซิปไว้ที่ไหนก็ได้

ดีไซน์มาจาก Claude Design — โปรเจกต์ *Fan-translation mod installer*,
ไฟล์ `Mod Installer.dc.html` (ระบบดีไซน์ **Modernist**)

## Stack

| ชั้น | เลือกอะไร | ทำไม |
|---|---|---|
| หน้าต่าง | **tkinter** (มากับ Python) | เป็น Win32 window จริง ไม่มี dependency เพิ่ม และ `.exe` เล็กสุด |
| หน้าตา | Frame/Label/Canvas + สีจากโทเคนดีไซน์ | Modernist ใช้ `--radius: 0px` ไม่มี gradient ไม่มีเงาในตัว panel — ยกมาเป็น native widget ได้ครบโดยไม่เสียรายละเอียด |
| ตรรกะ | Python (`core.py`) | toolchain เดียวกับ pipeline แปล และเทสได้โดยไม่ต้องเปิดหน้าต่าง |
| แพ็ก | PyInstaller `--onefile --windowed` | ผู้เล่นได้ไฟล์เดียว ไม่ต้องลง Python |
| ฟอนต์ | Sarabun (OFL) bundle มาด้วย | โหลดเข้า process ด้วย `AddFontResourceExW` ไม่ต้องติดตั้งลงเครื่องผู้เล่น |

### ทำไมไม่ใช้ WebView2/pywebview

รอบแรกทำด้วย pywebview + WebView2 แล้ววัดได้ว่ามัน **ตั้ง HTTP server ที่
`127.0.0.1` แล้วโหลดหน้าเว็บผ่านพอร์ตนั้น** — เป็น web app ในกรอบหน้าต่างจริงๆ
ไม่ใช่โปรแกรมหน้าต่าง แถมยังเปิดพอร์ตทิ้งไว้ (มีสิทธิ์โดน firewall ถาม)
และพังทั้งใบถ้าเครื่องไม่มี WebView2 Runtime

Tk เรนเดอร์ไทยถูกด้วย: `test_app.py` วัดว่า `width("ที่") == width("ท")`
คือสระ/วรรณยุกต์ **ซ้อน** ไม่ใช่เรียงต่อกัน (เทสไว้ 3 คู่ กันไว้เผื่อ Tk
เปลี่ยน text engine ในอนาคต)

## ไฟล์

```
core.py       ตรรกะล้วน ไม่มี UI — หาเกม / แฮช / rename / xdelta / rollback
theme.py      โทเคนดีไซน์ (สี ฟอนต์ ระยะ) + DPI + โหลดฟอนต์ + สร้าง .ico
widgets.py    .btn / .tag / .input / progress / checkbox / badge เป็น Tk widget
app.py        หน้าต่าง + 5 หน้าจอ + เดินสถานะ + ดักคราช
build_gui.py  PyInstaller
test_core.py  เทสตรรกะ 6 เคสเดียวกับ tools/test_installer.sh + เคส rollback
test_app.py   เทสหน้าจอ 27 เคส (หน้าต่างถูก withdraw ไม่เด้งมากวน)
ui/fonts/     Sarabun 400/600/800 + OFL.txt
```

## รัน / build

```powershell
# ต้องมีชุดติดตั้งที่ build_release.py สร้างไว้ก่อน (manifest.json + *.xdelta + xdelta3.exe)
$env:SBTP_RES = "thai_work\dist\senrenbanka-thai-patch-v1.1"

python tools/gui/app.py                 # รันจาก source
python tools/gui/test_core.py           # เทสตรรกะ
python tools/gui/test_app.py            # เทสหน้าจอ
python tools/gui/build_gui.py --out thai_work\dist\senrenbanka-thai-patch-v1.1
```

หรือทำทั้งชุดรวด: `python tools/build_release.py --version 1.1 --gui`

`SBTP_RES` มีไว้ตอนพัฒนาเท่านั้น — ตัว `.exe` จริงอ่านไฟล์ที่วางอยู่ข้างๆ ตัวเอง

## ตัดสินใจอะไรไว้บ้าง

**ใช้กรอบหน้าต่างของ Windows เอง** — ดีไซน์วาดแถบหัวเองพร้อมปุ่มย่อ/ปิด
แต่โปรแกรมหน้าต่างจริงควรมี title bar ของระบบ (taskbar, Alt-Tab, Snap, เมนูระบบ)
จึงเก็บแถบหัวของดีไซน์ไว้เป็นแถบแบรนด์ (เครื่องหมาย + ชื่อ + เวอร์ชัน)
แล้วตัดปุ่มย่อ/ปิดที่ซ้ำกับของระบบออก

**ไม่ยัด `.xdelta` เข้าไปใน `.exe`** — ซิปมี `install.bat` ที่ใช้ไฟล์ชุดเดียวกันอยู่แล้ว
ยัดเข้าไปอีกชุดคือซิปโตขึ้น 26 MB แลกกับคำว่า "ไฟล์เดียว" ซึ่งไม่คุ้ม

**เพิ่มสองหน้าจากดีไซน์ต้นทาง** — mockup มี 4 ขั้น (locate / components / installing / done)
ของจริงเพิ่ม:
* ขั้น "ตรวจไฟล์" ใช้หน้าเดียวกับ installing (แถบเดียวกัน ต่างแค่ข้อความ) เพราะแฮช 2 GB
  กินเวลา 15-30 วิ ปล่อยจอนิ่งเฉยๆ ไม่ได้
* หน้า error — ล้มเหลวต้องบอกว่าล้มที่ไหน ไม่ใช่เงียบ

**ทุกรายการในหน้า "สิ่งที่จะติดตั้ง" ติ๊กไว้และแก้ไม่ได้** — ดีไซน์เป็น checkbox เลือกได้
แต่แพตช์นี้เลือกไม่ได้จริง: `adult.xp3` ทับบทพูดใน `patch.xp3` อยู่ (ดู `../R18_COMPAT.md`)
แปะไม่ครบ = เกมกลับไปขึ้นภาษาจีนโดยไม่แจ้งเตือน หน้านี้จึงเป็น "รายการที่จะทำ" ไม่ใช่ตัวเลือก

**ความคืบหน้าเป็นของจริง** — `xdelta3` ไม่มี progress ให้อ่าน จึงวัดจากขนาดไฟล์ปลายทาง
ที่โตขึ้นระหว่างทาง ไม่ใช่แถบวิ่งหลอกตา

## กับดักที่เจอมาแล้ว (อย่าเผลอทำซ้ำ)

* **ห้ามตั้ง `self._w` ใน subclass ของ widget** — tkinter เก็บ path ของ widget ไว้ในชื่อนั้น
  ทับแล้วทุกคำสั่ง Tcl จะยิงไปที่ command ผิด (`invalid command name "420"`)
* **`winfo_ismapped()` เป็น 0 เสมอตอน root ถูก withdraw** — เทสต้องใช้ `winfo_manager()`
  ไม่งั้นได้ PASS ปลอมทั้งสองทาง
* **Tk แตะได้จาก thread เดียว** — งานหนักส่งผลกลับผ่าน `queue.Queue` ที่ `after()` มาคอยดึง
* **`--windowed` ไม่มี console** ถ้าคราชตอน start ผู้เล่นเห็นแค่ "ไม่มีอะไรเกิดขึ้น"
  `app.py` จึงเขียน `installer-error.log` + เด้ง MessageBox บอกให้ไปใช้ `install.bat` แทน
* **ต้องเรียก `SetProcessDpiAwareness` ก่อนสร้าง `Tk()`** ไม่งั้นจอ 125/150% จะเบลอ
