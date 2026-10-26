#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
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
"""
import os, sys, argparse, hashlib, json, shutil, subprocess, zipfile

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paths as P                                             # noqa: E402
import targets as T                                           # noqa: E402


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def find_xdelta():
    for p in (P.XDELTA, os.path.join(os.path.dirname(P.REPO), "xdelta3.exe")):
        if os.path.isfile(p):
            return p
    sys.exit("ไม่พบ xdelta3.exe — วางไว้ที่ tools/xdelta/xdelta3.exe "
             "(โหลดจาก https://github.com/jmacd/xdelta/releases)")


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        sys.exit("คำสั่งล้มเหลว: %s\n%s" % (" ".join(cmd),
                                            r.stderr.decode("utf-8", "replace")))


# ------------------------------------------------------------------ templates

BAT_HEAD = """@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Senren Banka - Thai Patch %s v%s
cd /d "%%~dp0"
"""

INSTALL_BODY = r"""
echo ============================================
echo   Senren Banka - แพตช์แปลไทย v__VER__
echo ============================================
echo.

if not exist "SenrenBanka.exe" (
    echo [ERROR] ไม่พบ SenrenBanka.exe ในโฟลเดอร์นี้
    echo.
    echo ต้องเอาไฟล์ในซิปนี้ทั้งหมดไปวางใน "โฟลเดอร์เกม" ก่อน แล้วค่อยรัน install.bat
    echo ตัวอย่าง: E:\SteamLibrary\steamapps\common\SenrenBanka\
    echo วิธีหาโฟลเดอร์เกม: Steam ^> คลิกขวาที่เกม ^> Manage ^> Browse local files
    goto :fail
)
for %%F in (__DELTAS__) do (
    if not exist "%%F" (
        echo [ERROR] ไม่พบไฟล์ %%F - แตกซิปไม่ครบ
        echo แตกไฟล์ zip ให้ครบทุกไฟล์ก่อน อย่าลากมาแค่ install.bat
        goto :fail
    )
)
if not exist "patch.xp3" goto :broken
if not exist "data.xp3"  goto :broken

if exist "patch.xp3.bak" (
    echo [SKIP] ติดตั้งแพตช์นี้ไปแล้ว ^(พบ patch.xp3.bak^)
    echo ถ้าต้องการติดตั้งใหม่ ให้รัน uninstall.bat ก่อน แล้วค่อยรัน install.bat อีกครั้ง
    goto :end
)

set "MODE=all-ages"
if exist "adult.xp3" set "MODE=R18"
echo โหมดที่ตรวจพบ: %MODE%
if "%MODE%"=="R18"      echo   ^(พบ adult.xp3 = ลงแพตช์ R18 ไว้ - จะแปะไทยให้ฉาก R18 ด้วย^)
if "%MODE%"=="all-ages" echo   ^(ไม่พบ adult.xp3 = เกม Steam ล้วน^)
echo.

echo [1/4] ตรวจไฟล์เกม ^(SHA256^) - ใช้เวลาสักครู่...
call :sha256 "patch.xp3" H_PATCH
call :sha256 "data.xp3"  H_DATA
if "%MODE%"=="R18" call :sha256 "adult.xp3" H_ADULT
if "%MODE%"=="R18" if exist "patch_extra.xp3" call :sha256 "patch_extra.xp3" H_PEXTRA

if defined H_PATCH if /i "!H_PATCH!"=="%THAI_PATCH%"     goto :already
if defined H_ADULT if /i "!H_ADULT!"=="%THAI_ADULT%"     goto :already
if defined H_PATCH if /i not "!H_PATCH!"=="%ORIG_PATCH%" goto :ver_game
if defined H_DATA  if /i not "!H_DATA!"=="%ORIG_DATA%"   goto :ver_game
if defined H_ADULT if /i not "!H_ADULT!"=="%ORIG_ADULT%" goto :ver_adult
if defined H_PEXTRA if /i not "!H_PEXTRA!"=="%ORIG_PEXTRA%" goto :ver_pextra
echo       ผ่าน
echo.

echo [2/4] สำรองไฟล์ต้นฉบับ ^(เปลี่ยนชื่อเป็น .bak - ไม่ก็อปปี้ จึงไม่กินพื้นที่^)...
move /y "patch.xp3" "patch.xp3.bak" >nul
if errorlevel 1 goto :fail_move
move /y "data.xp3" "data.xp3.bak" >nul
if errorlevel 1 goto :rollback
if "%MODE%"=="R18" (
    move /y "adult.xp3" "adult.xp3.bak" >nul
    if errorlevel 1 goto :rollback
)
if defined H_PEXTRA (
    move /y "patch_extra.xp3" "patch_extra.xp3.bak" >nul
    if errorlevel 1 goto :rollback
)
echo.

echo [3/4] แปะแพตช์...
echo       - patch.xp3  ^(บทพูด^)
"%~dp0xdelta3.exe" -d -f -s "patch.xp3.bak" "thai-patch.xdelta" "patch.xp3"
if errorlevel 1 goto :rollback
echo       - data.xp3   ^(ฟอนต์ไทย^)
"%~dp0xdelta3.exe" -d -f -s "data.xp3.bak" "thai-data.xdelta" "data.xp3"
if errorlevel 1 goto :rollback
if "%MODE%"=="R18" (
    echo       - adult.xp3  ^(บทพูดฉาก R18^)
    "%~dp0xdelta3.exe" -d -f -s "adult.xp3.bak" "thai-adult.xdelta" "adult.xp3"
    if errorlevel 1 goto :rollback
)
if defined H_PEXTRA (
    echo       - patch_extra.xp3  ^(บทพูดฉาก R18 ชุดสำรอง^)
    "%~dp0xdelta3.exe" -d -f -s "patch_extra.xp3.bak" "thai-patchextra.xdelta" "patch_extra.xp3"
    if errorlevel 1 goto :rollback
)
echo.

echo [4/4] เสร็จสิ้น
echo.
echo ============================================
echo   ติดตั้งสำเร็จ! ^(โหมด %MODE%^)
echo ============================================
echo.
echo เปิดเกม -^> Options -^> Language -^> เลือก "Chinese (Simplified)"
echo จะได้ข้อความเป็นภาษาไทย
echo.
if "%MODE%"=="R18" echo หมายเหตุ: อย่ารันตัวติดตั้งแพตช์ R18 ซ้ำอีก มันจะเขียนทับ adult.xp3
if "%MODE%"=="R18" echo           ทำให้ไทยหาย ถ้าเผลอรันไปแล้วให้รัน uninstall.bat แล้ว install.bat ใหม่
echo.
echo ถอดแพตช์: รัน uninstall.bat
goto :end

:already
echo.
echo [SKIP] ไฟล์เกมมีคำแปลไทยอยู่แล้ว - ไม่ต้องติดตั้งซ้ำ
echo ถ้าอยากติดตั้งใหม่จริงๆ ให้รัน uninstall.bat ก่อน
echo ^(ถ้า uninstall.bat บอกว่าไม่พบไฟล์สำรอง = ไฟล์ .bak หายไป
echo   ต้องให้ Steam ดึงไฟล์แท้กลับมาก่อน: คลิกขวาเกม ^> Properties ^> Installed Files ^> Verify^)
goto :end

:ver_game
echo.
echo [ERROR] patch.xp3 / data.xp3 ไม่ตรงกับเวอร์ชันที่แพตช์นี้รองรับ
echo สาเหตุที่พบบ่อยที่สุดคือ Steam อัปเดตเกมมาใหม่ ต้องรอแพตช์เวอร์ชันถัดไป
echo.
echo ไฟล์เกมยังไม่ถูกแก้ไขเลย ปลอดภัย
goto :fail

:ver_adult
echo.
echo [ERROR] adult.xp3 ไม่ตรงกับ build ของแพตช์ R18 ที่รองรับ
echo แพตช์ไทยชุดนี้ทำจาก adult.xp3 ที่ SHA256 ขึ้นต้นด้วย %ORIG_ADULT:~0,16%
echo แต่ของเครื่องนี้ขึ้นต้นด้วย !H_ADULT:~0,16!
echo.
echo แปลว่าใช้แพตช์ R18 คนละ build กัน - ยังติดตั้งไม่ได้
echo ^(ไม่แปะให้ครึ่งเดียว เพราะ adult.xp3 ทับบทพูดใน patch.xp3 อยู่
echo   ถ้าแปะแค่ patch.xp3 เกมจะขึ้นภาษาจีนเงียบๆ หาสาเหตุยาก^)
echo.
echo ไฟล์เกมยังไม่ถูกแก้ไขเลย ปลอดภัย
goto :fail

:ver_pextra
echo.
echo [ERROR] patch_extra.xp3 ไม่ตรงกับ build ของแพตช์ R18 ที่รองรับ
echo แพตช์ไทยชุดนี้ทำจาก patch_extra.xp3 ที่ SHA256 ขึ้นต้นด้วย %ORIG_PEXTRA:~0,16%
echo แต่ของเครื่องนี้ขึ้นต้นด้วย !H_PEXTRA:~0,16!
echo.
echo แพตช์ R18 วางสคริปต์บทพูดไว้ในไฟล์นี้ด้วย ถ้าไม่แปะ เกมจะยังขึ้นบทเก่า - ยังติดตั้งไม่ได้
echo.
echo ไฟล์เกมยังไม่ถูกแก้ไขเลย ปลอดภัย
goto :fail

:broken
echo.
echo [ERROR] ไม่พบ patch.xp3 หรือ data.xp3 - ไฟล์เกมไม่สมบูรณ์
echo Steam ^> คลิกขวาเกม ^> Properties ^> Installed Files ^> Verify integrity of game files
goto :fail

:fail_move
echo.
echo [ERROR] สำรองไฟล์ไม่สำเร็จ
echo ปิดเกมก่อนถ้ากำลังเปิดอยู่ หรือลองคลิกขวา install.bat ^> Run as administrator
goto :fail

:rollback
echo.
echo [ERROR] แปะแพตช์ไม่สำเร็จ - กำลังคืนไฟล์ต้นฉบับ...
__ROLLBACK__
echo คืนไฟล์ต้นฉบับเรียบร้อย เกมยังเล่นได้ปกติ
echo.
echo สาเหตุที่เป็นไปได้: พื้นที่ดิสก์ไม่พอ ^(ต้องว่างอย่างน้อย 3 GB^) หรือไฟล์แพตช์เสีย
goto :fail

:sha256
set "_h="
for /f "skip=1 tokens=*" %%A in ('certutil -hashfile "%~1" SHA256 2^>nul') do if not defined _h set "_h=%%A"
if not defined _h goto :eof
set "_h=%_h: =%"
set "%~2=%_h%"
goto :eof

:fail
echo.
pause
exit /b 1

:end
echo.
pause
exit /b 0
"""

UNINSTALL_BODY = r"""
echo ============================================
echo   Senren Banka - ถอดแพตช์แปลไทย v__VER__
echo ============================================
echo.

set "FOUND=0"
__UNINSTALL_FOUND__

if "%FOUND%"=="0" (
    echo [SKIP] ไม่พบไฟล์สำรอง .bak - ยังไม่เคยติดตั้ง หรือถอดไปแล้ว
    goto :end
)

echo กำลังคืนไฟล์ต้นฉบับ...
__UNINSTALL_RESTORE__

echo.
echo ============================================
echo   ถอดแพตช์สำเร็จ - เกมกลับเป็นต้นฉบับแล้ว
echo ============================================

:end
echo.
pause
exit /b 0
"""

README = """\
======================================================
  Senren Banka - แพตช์แปลไทย v__VER__
======================================================

รองรับทั้งเกม Steam ล้วน และเกมที่ลงแพตช์ R18 ไว้แล้ว
ตัวติดตั้งจะตรวจเองว่าเครื่องคุณเป็นแบบไหน

วิธีติดตั้ง (แบบง่าย — แนะนำ)
-----------
1. ต้องมีเกม Senren Banka แท้บน Steam ติดตั้งไว้ก่อน
2. แตกไฟล์ zip นี้ให้ครบทุกไฟล์ ไว้ที่ไหนก็ได้ (ไม่ต้องแตกทับโฟลเดอร์เกม)
3. ดับเบิลคลิก SenrenBanka-Thai-Patch.exe
   ตัวติดตั้งจะหาโฟลเดอร์เกมให้เอง กด "ถัดไป" แล้ว "ติดตั้ง"
   ถ้าเครื่องมีแพตช์ R18 อยู่ จะมีช่อง "ฉาก R18" ให้เลือกในหน้ารายการ
     ติ๊กไว้  = ลงเวอร์ชัน R18 (ฉาก R18 เป็นไทยด้วย)
     ติ๊กออก = ลงเวอร์ชัน all-ages (ปิด adult.xp3/adult2.xp3 ไว้ กดถอดแพตช์แล้วได้คืน)
4. เปิดเกม > Options > Language > เลือก "Chinese (Simplified)"
5. เล่นได้เลย ข้อความจะเป็นภาษาไทย

ถอดคืน: เปิดตัวติดตั้งอีกครั้ง แล้วกด "ถอดแพตช์"

วิธีติดตั้ง (แบบ command line)
-----------
ถ้าตัวหน้าต่างเปิดไม่ขึ้น (เครื่องที่ไม่มี Edge WebView2 Runtime) ใช้ install.bat แทนได้
ผลลัพธ์เหมือนกันทุกอย่าง แต่ต้องเอาไฟล์ทั้งหมด "ไปวางในโฟลเดอร์เกม" ก่อน
   วิธีหาโฟลเดอร์เกม: Steam > คลิกขวาที่เกม > Manage > Browse local files
   ตัวอย่าง: ...\\SteamLibrary\\steamapps\\common\\SenrenBanka\\
แล้วดับเบิลคลิก install.bat (ถอดคืนด้วย uninstall.bat)

  ทำไมต้องเลือกจีน: ช่องภาษาจีนใช้ฟอนต์แบบ vector สลับเป็นฟอนต์ไทยได้
  ส่วนช่อง JP/EN ใช้ภาพตัวอักษรที่ render มาแล้ว ใส่ไทยไม่ได้
  แพตช์นี้เลยเขียนคำแปลไทยลงในช่องจีน

ถ้าลงแพตช์ R18 ไว้
-----------
ติดตั้งได้เหมือนกัน และเลือกได้ว่าจะเอาเวอร์ชันไหน:

  เวอร์ชัน R18       ฉาก R18 เป็นภาษาไทยด้วย (ค่าเริ่มต้น)
  เวอร์ชัน all-ages  ปิด adult.xp3 + adult2.xp3 ไว้ เกมกลับเป็นฉบับ all-ages
                     (แค่เปลี่ยนชื่อเป็น .off ไม่ได้ลบ กด "ถอดแพตช์" แล้วได้คืนครบ)

install.bat ทำได้เฉพาะเวอร์ชัน R18 อัตโนมัติ ถ้าอยากเลือกให้ใช้ตัวติดตั้งแบบหน้าต่าง

** ห้ามรันตัวติดตั้งแพตช์ R18 ซ้ำหลังลงแพตช์ไทยแล้ว **
มันจะเขียนทับ adult.xp3 ทำให้ไทยหายทั้งเกม (ไม่ใช่แค่ฉาก R18)
ถ้าเผลอไปแล้ว: รัน uninstall.bat -> ลงแพตช์ R18 -> รัน install.bat ใหม่

ลำดับที่ถูกต้องคือ: ลงเกม -> ลงแพตช์ R18 -> ลงแพตช์ไทย

วิธีถอดแพตช์
-----------
ในตัวติดตั้ง: กดปุ่ม "ถอดแพตช์"
หรือดับเบิลคลิก uninstall.bat  (คืนไฟล์ต้นฉบับทั้ง patch.xp3 / data.xp3 / adult.xp3 / patch_extra.xp3)

ปัญหาที่พบบ่อย
-----------
- "ไม่ตรงกับเวอร์ชันที่แพตช์นี้รองรับ"
  Steam อัปเดตเกมมาใหม่ ต้องรอแพตช์เวอร์ชันถัดไป
  ไฟล์เกมยังไม่ถูกแก้ไข ปลอดภัย

- "adult.xp3 ไม่ตรงกับ build ของแพตช์ R18 ที่รองรับ"
  แพตช์ R18 มีหลาย build แพตช์ไทยชุดนี้ทำจาก build ที่ระบุใน checksums.txt

- ลงไปแล้วยังเป็นภาษาจีน/อังกฤษอยู่
  ตรวจว่าเลือก Language = Chinese (Simplified) แล้วหรือยัง
  ถ้าเลือกแล้วยังเป็นจีน = adult.xp3 ทับอยู่ ให้รัน uninstall.bat แล้ว install.bat ใหม่

- เกมพัง / อยากกลับไปเป็นเกมแท้
  Steam > คลิกขวาเกม > Properties > Installed Files > Verify integrity of game files
  (หมายเหตุ: Verify จะ **ไม่** ลบ adult.xp3 / adult2.xp3 ของแพตช์ R18)

- อยาก build เองจากซอร์ส / อยากรู้เบื้องหลัง
  https://github.com/Jiranon-K/senrenbanka-thai

สถานะงานแปล
-----------
__COVERAGE__

หมายเหตุ
-----------
แพตช์นี้เป็น binary diff (xdelta) ใช้ได้เฉพาะคนที่มีไฟล์เกมอยู่แล้วเท่านั้น
ในไฟล์แพตช์ไม่มีเนื้อหาลิขสิทธิ์ของเกมอยู่เลย

งานแปลแฟน เพื่อการศึกษา/ใช้ส่วนตัว ไม่เกี่ยวข้องกับ Yuzusoft / NekoNyan
"""


def write_text(path, text, crlf=True, bom=True):
    """.bat ต้อง **ไม่มี** BOM (ดูหมายเหตุ encoding ด้านบน) แต่ต้องเป็น CRLF เสมอ"""
    data = text.replace("\r\n", "\n")
    if crlf:
        data = data.replace("\n", "\r\n")
    with open(path, "wb") as f:
        if bom:
            f.write(b"\xef\xbb\xbf")
        f.write(data.encode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="1.1")
    ap.add_argument("--game-dir", default=None)
    ap.add_argument("--reuse", action="store_true",
                    help="ใช้ .xdelta เดิมถ้ามีอยู่แล้ว (ยังตรวจย้อนกลับเหมือนเดิม)")
    ap.add_argument("--coverage",
                    default="แปลครบทั้งเกมฝั่ง all-ages; ฝั่ง R18 แปลแล้วบางส่วน")
    ap.add_argument("--gui", action="store_true",
                    help="build ตัวติดตั้งแบบ GUI ใส่เข้าไปในซิปด้วย (ต้องมี PyInstaller)")
    a = ap.parse_args()

    game = os.path.abspath(a.game_dir) if a.game_dir else P.game_dir()
    xd = find_xdelta()
    out = os.path.join(P.DIST, "senrenbanka-thai-patch-v%s" % a.version)
    os.makedirs(out, exist_ok=True)
    print("game dir : %s" % game)
    print("xdelta3  : %s" % xd)
    print("output   : %s\n" % out)

    hashes, present = {}, []
    for t in T.TARGETS:
        po, pt = os.path.join(game, t.orig), os.path.join(game, t.file)
        if not (os.path.isfile(po) and os.path.isfile(pt)):
            if t.required:
                sys.exit("ไม่พบ %s หรือ %s ในโฟลเดอร์เกม" % (t.orig, t.file))
            print("[skip]   %-20s ไม่มี %s -> ข้าม" % (t.delta, t.orig))
            continue

        # ไฟล์ที่แพตช์แล้วต้องไม่โตกว่าต้นฉบับ — ของใหม่ถูก pad ให้เท่าช่องเดิม
        # เสมอ ผังจึงยาวเท่ากัน (ต่างกันได้ไม่กี่ร้อยไบต์จากช่องว่างที่ Yuzu
        # เผื่อไว้ กับขนาด index หลัง zlib) โตขึ้นเป็น MB = แพ็กด้วยโค้ดรุ่นที่
        # ยังอ่าน segm ผิดช่องและก็อป payload ที่ใช้ร่วมกันแยกทุกตัว —
        # ปล่อยออกไปคือส่ง 33 MB ที่ไม่มีประโยชน์ไปลงเครื่องผู้เล่นทุกคน
        grew = os.path.getsize(pt) - os.path.getsize(po)
        if grew > (1 << 20):
            sys.exit("%s โตกว่า %s อยู่ %.1f MB — แพ็กใหม่ก่อนปล่อย"
                     % (t.file, t.orig, grew / 2 ** 20))

        delta = os.path.join(out, t.delta)
        if not (a.reuse and os.path.isfile(delta)):
            print("[encode] %-20s %s" % (t.delta, t.label))
            run(xd, "-e", "-f", "-9", "-B", "1073741824", "-s", po, pt, delta)

        # ตรวจย้อนกลับ: decode แล้วต้องได้ไฟล์เดิมเป๊ะ ไม่ผ่าน = ไม่ปล่อย
        tmp = delta + ".roundtrip"
        run(xd, "-d", "-f", "-s", po, delta, tmp)
        h_orig, h_thai, h_rt = sha256(po), sha256(pt), sha256(tmp)
        os.remove(tmp)
        if h_rt != h_thai:
            sys.exit("ตรวจย้อนกลับไม่ผ่าน: %s (decode แล้วได้ไฟล์ไม่ตรง)" % t.delta)
        print("         %-20s %8.1f MB  roundtrip ตรง"
              % (t.delta, os.path.getsize(delta) / 2 ** 20))

        hashes[t.file] = (h_orig, h_thai)
        present.append(t)

    shutil.copy2(xd, os.path.join(out, "xdelta3.exe"))

    # manifest.json — ตาราง target + แฮชจริง ที่ตัวติดตั้ง GUI อ่าน
    # ทั้งไฟล์นี้และ .bat งอกจาก tools/targets.py ตัวเดียวกัน
    manifest = {
        "version": a.version,
        "product": "Senren Banka — แพตช์แปลไทย",
        "repo": "https://github.com/Jiranon-K/senrenbanka-thai",
        "coverage": a.coverage,
        # ไฟล์ R18 ที่ต้อง "ปิด" เมื่อผู้เล่นเลือก all-ages — เดิม core.py
        # hardcode ไว้เอง ทำให้ไม่มีใครยืนยันได้ว่าตรงกับตารางนี้ไหม
        "disable_on_all_ages": T.DISABLE_ON_ALL_AGES,
        "targets": [
            {
                "file": t.file,
                "delta": t.delta,
                "label": t.label,
                "required": t.required,
                "r18": t.r18,
                "sha_orig": hashes[t.file][0],
                "sha_thai": hashes[t.file][1],
                "delta_size": os.path.getsize(os.path.join(out, t.delta)),
            }
            for t in present
        ],
    }
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    def fill(body):
        return (body.replace("__VER__", a.version)
                    .replace("__DELTAS__", T.bat_required_files())
                    .replace("__ROLLBACK__", T.bat_rollback())
                    .replace("__UNINSTALL_FOUND__", T.bat_uninstall_found())
                    .replace("__UNINSTALL_RESTORE__", T.bat_uninstall_restore()))

    # เพิ่ม target แล้วลืมแก้ .bat = build ไม่ผ่าน ดีกว่าปล่อยแพตช์ครึ่งเดียว
    # ต้องตรวจ **ข้อความที่เติมค่าแล้ว** — ชื่อไฟล์ทั้งหมดงอกมาจาก targets.py
    # ตอน fill() ในตัว template มีแต่ placeholder ตรวจตัว template จึงตกเสมอ
    install_bat = (BAT_HEAD % ("Installer", a.version)) + "\n" \
        + T.bat_hash_vars(hashes) + "\n" + fill(INSTALL_BODY)
    uninstall_bat = (BAT_HEAD % ("Uninstaller", a.version)) + fill(UNINSTALL_BODY)
    T.check_bat_mentions_every_target(install_bat, "install.bat")
    T.check_bat_mentions_every_target(uninstall_bat, "uninstall.bat")

    # bom=False สำคัญมาก — ดู "หมายเหตุเรื่อง encoding ของ .bat" ด้านบน
    write_text(os.path.join(out, "install.bat"), install_bat, bom=False)
    write_text(os.path.join(out, "uninstall.bat"), uninstall_bat, bom=False)
    write_text(os.path.join(out, "README.txt"),
               README.replace("__VER__", a.version).replace("__COVERAGE__", a.coverage))

    # GUI สร้างทีหลังสุด เพราะต้องให้ manifest.json มีอยู่ก่อน แล้วค่อยนับ checksum
    if a.gui:
        print("\n[gui] build ตัวติดตั้งแบบ GUI")
        run(sys.executable, os.path.join(P.REPO, "tools", "gui", "build", "build_gui.py"),
            "--out", out)

    lines = ["Senren Banka Thai patch v%s - SHA256" % a.version, "",
             "ไฟล์เกมที่รองรับ (ก่อนแปะแพตช์):"]
    for t in present:
        lines.append("  %-14s %s" % (t.file, hashes[t.file][0]))
    lines += ["", "ไฟล์เกมหลังแปะแพตช์:"]
    for t in present:
        lines.append("  %-14s %s" % (t.file, hashes[t.file][1]))
    lines += ["", "ไฟล์ในชุดติดตั้ง:"]
    for f in sorted(os.listdir(out)):
        p = os.path.join(out, f)
        if os.path.isfile(p) and f != "checksums.txt":
            lines.append("  %-22s %s" % (f, sha256(p)))
    write_text(os.path.join(out, "checksums.txt"), "\n".join(lines) + "\n")

    zip_path = out + ".zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(os.listdir(out)):
            z.write(os.path.join(out, f), f)
    print("\nzip      : %s  (%.1f MB)" % (zip_path, os.path.getsize(zip_path) / 2 ** 20))
    print("sha256   : %s" % sha256(zip_path))


if __name__ == "__main__":
    main()
