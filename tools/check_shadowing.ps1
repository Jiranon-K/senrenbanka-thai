<#
  check_shadowing.ps1 - บอกว่า "บทพูดแต่ละบทเกมจะอ่านจาก archive ไหน"
  ใช้ตรวจว่าแพตช์ไทย (ที่เขียนลง patch.xp3) ถูก archive อื่นทับอยู่หรือเปล่า

  ลำดับโหลด (ต่ำ -> สูง):  scn.xp3 < patch_extra.xp3 < patch.xp3 < adult.xp3
  อ่านชื่อไฟล์จริงจาก sen: -> hnfn blob (ตาราง adler32 -> ชื่อไฟล์ ของ Yuzusoft)

  exit 0 = PASS (ไทยขึ้นครบ) / exit 1 = FAIL (โดนทับ)

  ตัวอย่าง:
    # สถานะเกมตอนนี้
    powershell -File tools\check_shadowing.ps1 -GameDir "E:\SteamLibrary\steamapps\common\SenrenBanka"

    # จำลอง "ลง R18 แล้ว" โดยไม่ต้องก๊อป archive 2.5 GB
    powershell -File tools\check_shadowing.ps1 -GameDir "...\SenrenBanka" -ExtraDir "...\senrenbanka_r18patch"

    # จำลอง "ยังไม่ลง adult.xp3"
    powershell -File tools\check_shadowing.ps1 -GameDir "...\SenrenBanka" -Ignore adult.xp3
#>
param(
    [Parameter(Mandatory=$true)][string]$GameDir,
    [string]$ExtraDir = "",
    [string[]]$Ignore = @()
)
$ErrorActionPreference = "Stop"

function Inflate([byte[]]$raw) {
    $ms = New-Object System.IO.MemoryStream -ArgumentList $raw, 2, ($raw.Length - 2)
    $ds = New-Object System.IO.Compression.DeflateStream($ms, [System.IO.Compression.CompressionMode]::Decompress)
    $o  = New-Object System.IO.MemoryStream
    $ds.CopyTo($o); $ds.Dispose()
    return $o.ToArray()
}

# -> List[string] of *.ks.scn real filenames in the archive
function Get-ScenarioNames([string]$path) {
    $fs = [System.IO.File]::Open($path, 'Open', 'Read', 'ReadWrite')
    $br = New-Object System.IO.BinaryReader($fs)
    try {
        $fs.Position = 11
        $ofs = $br.ReadInt64()
        if ($ofs -eq 0x17) { $fs.Position = 0x20; $real = $br.ReadInt64() } else { $real = $ofs }
        $fs.Position = $real
        $null = $br.ReadByte(); $comp = $br.ReadInt64(); $null = $br.ReadInt64()
        $idx = Inflate($br.ReadBytes([int]$comp))

        $out = New-Object 'System.Collections.Generic.List[string]'
        if (-not ($idx[0] -eq 0x73 -and $idx[1] -eq 0x65 -and $idx[2] -eq 0x6E -and $idx[3] -eq 0x3A)) { return $out }
        $senSize = [BitConverter]::ToInt64($idx, 4)
        $blobOff = [BitConverter]::ToUInt32($idx, 12)
        $blobLen = [BitConverter]::ToUInt32($idx, 24)
        $fs.Position = $blobOff
        $hn = Inflate($br.ReadBytes([int]$blobLen))

        $p = 0
        while ($p -lt $hn.Length - 12) {
            if (-not ($hn[$p] -eq 0x68 -and $hn[$p+1] -eq 0x6E -and $hn[$p+2] -eq 0x66 -and $hn[$p+3] -eq 0x6E)) { break }
            $sz = [BitConverter]::ToInt64($hn, $p + 4)
            $b  = $p + 12
            $nl = [BitConverter]::ToUInt16($hn, $b + 4)
            $nm = [System.Text.Encoding]::Unicode.GetString($hn, $b + 6, $nl * 2)
            if ($nm.EndsWith(".ks.scn")) { $out.Add($nm) }
            $p = $b + $sz
        }
        return $out
    } finally { $fs.Dispose() }
}

# lowest priority first
$order = @("scn.xp3", "patch_extra.xp3", "patch.xp3", "adult.xp3")
$layers = New-Object 'System.Collections.Generic.List[object]'
foreach ($n in $order) {
    if ($Ignore -contains $n) { Write-Host ("  [ignored] {0,-16} (simulating: not installed)" -f $n); continue }
    $dir = $GameDir
    if ($ExtraDir -ne "" -and (Test-Path (Join-Path $ExtraDir $n))) { $dir = $ExtraDir }
    $p = Join-Path $dir $n
    if (-not (Test-Path $p)) { Write-Host ("  [absent] {0,-16}" -f $n); continue }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $names = Get-ScenarioNames $p
    $sw.Stop()
    Write-Host ("  [read]   {0,-16} {1,3} scenario scripts   ({2:n1}s)  {3}" -f $n, $names.Count, $sw.Elapsed.TotalSeconds, $dir)
    $layers.Add([pscustomobject]@{ Name = $n; Names = $names })
}

$all = New-Object 'System.Collections.Generic.HashSet[string]'
foreach ($l in $layers) { foreach ($n in $l.Names) { $null = $all.Add($n) } }

$sets = @{}
foreach ($l in $layers) {
    $h = New-Object 'System.Collections.Generic.HashSet[string]'
    foreach ($n in $l.Names) { $null = $h.Add($n) }
    $sets[$l.Name] = $h
}

$counts = @{}
foreach ($n in $all) {
    $w = $null
    foreach ($l in $layers) { if ($sets[$l.Name].Contains($n)) { $w = $l.Name } }
    $counts[$w] = 1 + $counts[$w]
}

Write-Host ""
Write-Host "Which archive actually supplies each scenario script (later layer wins):"
foreach ($l in $layers) {
    $c = if ($counts.ContainsKey($l.Name)) { $counts[$l.Name] } else { 0 }
    Write-Host ("  {0,-16} {1,3} / {2}" -f $l.Name, $c, $all.Count)
}

$top = $layers[$layers.Count - 1].Name
Write-Host ""
Write-Host ("=> เกมจะอ่านบทพูดจาก '{0}' เป็นหลัก - ไทยต้องอยู่ใน archive ตัวนั้น" -f $top)
Write-Host "   สคริปต์นี้บอกแค่ 'ใครชนะลำดับโหลด' ไม่ได้เปิดดูว่ามีไทยข้างในจริงไหม"
Write-Host "   ตรวจของจริง (ข้อความ + ฟอนต์) ด้วย:  tools\check_thai.ps1 -GameDir <game dir>"
exit 0
