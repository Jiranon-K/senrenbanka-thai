<#
  check_thai.ps1 - คำสั่งเดียวจบ: "เกมจะแสดงภาษาไทยได้จริงไหม"

  1. หาว่า archive ไหนชนะลำดับโหลดสำหรับสคริปต์บทพูด (check_shadowing.ps1)
  2. ถอด archive นั้นด้วย GARbro
  3. นับสตริงไทยในสคริปต์จริง (verify_thai.py)
  4. ตรวจว่าฟอนต์ใน data.xp3 มี glyph ไทยหรือยัง

  exit 0 = PASS · 1 = FAIL · 2 = PARTIAL (ไทยขึ้น แต่บางบทยังไม่ได้แปล)

    powershell -File tools\check_thai.ps1 -GameDir "E:\SteamLibrary\steamapps\common\SenrenBanka"
#>
param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [string]$Python = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
)
$ErrorActionPreference = "Stop"
$tools = $PSScriptRoot
$tmp = Join-Path $env:TEMP "senren_thai_check"

# ลำดับโหลดจากต่ำไปสูง - archive ท้ายสุดที่มีไฟล์นั้นคือตัวที่เกมใช้จริง
$order = @("scn.xp3", "patch_extra.xp3", "patch.xp3", "adult.xp3")
$winner = $null
foreach ($n in $order) { if (Test-Path (Join-Path $GameDir $n)) { $winner = $n } }
if (-not $winner) { Write-Host "ไม่พบ archive ของเกมใน $GameDir" -ForegroundColor Red; exit 1 }

Write-Host "archive ที่ชนะลำดับโหลด: $winner"
Write-Host "กำลังถอดสคริปต์ออกมาตรวจ..."
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
& (Join-Path $tools "garbro_extract.ps1") -Archive (Join-Path $GameDir $winner) -OutDir $tmp -Filter "*.ks.scn" | Out-Null

$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
& $Python (Join-Path $tools "verify_thai.py") $tmp | Select-Object -Last 3
$textCode = $LASTEXITCODE

Write-Host ""
Write-Host "--- ฟอนต์ใน data.xp3 ---"
$fontDir = Join-Path $tmp "_font"
& (Join-Path $tools "garbro_extract.ps1") -Archive (Join-Path $GameDir "data.xp3") -OutDir $fontDir -Filter "*SourceHanSansSC*" | Out-Null
$fontOk = $true
foreach ($f in (Get-ChildItem $fontDir -Filter *.otf -File)) {
    $n = & $Python -c @"
import sys
from fontTools.ttLib import TTFont
f = TTFont(sys.argv[1], lazy=True)
print(sum(1 for c in f.getBestCmap() if 0x0E00 <= c <= 0x0E7F))
"@ $f.FullName
    Write-Host ("  {0,-34} thai glyphs = {1}" -f $f.Name, $n)
    if ([int]$n -eq 0) { $fontOk = $false }
}
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue

Write-Host ""
if (-not $fontOk) {
    Write-Host "VERDICT: FAIL - ฟอนต์ยังไม่มี glyph ไทย (ยังไม่ได้ลง data.xp3 ของแพตช์ไทย) ข้อความจะขึ้นเป็นกล่องเปล่า" -ForegroundColor Red
    exit 1
}
switch ($textCode) {
    0 { Write-Host "VERDICT: PASS - ทั้งข้อความและฟอนต์พร้อม" -ForegroundColor Green; exit 0 }
    2 { Write-Host "VERDICT: PARTIAL - ฟอนต์พร้อม ไทยขึ้นได้ แต่ยังมีบทที่ไม่ได้แปล (จะเห็นเป็นภาษาจีน)" -ForegroundColor Yellow; exit 2 }
    default { Write-Host "VERDICT: FAIL - ไม่มีข้อความไทยใน $winner" -ForegroundColor Red; exit 1 }
}
