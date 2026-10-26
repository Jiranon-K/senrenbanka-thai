<#
  xp3_keystream.ps1 - write the cx keystream of named XP3 entries to files.

  The game's cipher (SenrenCxCrypt in GARbro) is a pure XOR: Decrypt(x) = x ^ Decrypt(0),
  checked on 4,096 random bytes with 0 violations. So decrypting a buffer of zeros yields
  the keystream for that entry at any length, and the new file can be any size — unlike
  the "origEnc XOR origPlain" method, which only covers the original length.

  Input: a TSV of  <entry name> TAB <length>  per line.
  Output: <OutDir>\<index>.ks  (index = line number, 0-based) — raw keystream bytes,
          <OutDir>\manifest.tsv  index TAB name TAB archive offset.

    powershell -File tools\xp3_keystream.ps1 -Archive "...\data.xp3.orig" -List req.tsv -OutDir ks
#>
param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$List,
    [Parameter(Mandatory=$true)][string]$OutDir
)
$ErrorActionPreference = "Stop"
$GarDir = Join-Path $PSScriptRoot "GARbro"
foreach ($dll in (Get-ChildItem $GarDir -Filter *.dll -File)) {
    try { $null = [Reflection.Assembly]::LoadFrom($dll.FullName) } catch { }
}
$cat = [GameRes.FormatCatalog]::Instance
$fs = [IO.File]::OpenRead((Join-Path $GarDir "GameData\Formats.dat"))
try { $cat.DeserializeScheme($fs) } finally { $fs.Dispose() }

$arc = [GameRes.ArcFile]::TryOpen($Archive)
if ($null -eq $arc) { throw "GARbro could not open $Archive" }
try {
    $byName = @{}
    foreach ($e in $arc.Dir) { $byName[$e.Name] = $e }
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $i = 0
    $manifest = @()
    foreach ($line in [IO.File]::ReadAllLines($List)) {
        if (-not $line.Trim()) { continue }
        $name, $len = $line.Split("`t")
        $e = $byName[$name]
        if ($null -eq $e) { throw "entry not found: $name" }
        $buf = New-Object byte[] ([int]$len)
        if ($e.IsEncrypted) { $e.Cipher.Decrypt($e, 0, $buf, 0, $buf.Length) }
        [IO.File]::WriteAllBytes((Join-Path $OutDir ("{0}.ks" -f $i)), $buf)
        # the archive index stores hashed names; the offset is how xp3.py finds the entry
        $manifest += ("{0}`t{1}`t{2}" -f $i, $name, $e.Offset)
        $i++
    }
    [IO.File]::WriteAllLines((Join-Path $OutDir "manifest.tsv"), [string[]]$manifest)
    Write-Host ("wrote {0} keystreams -> {1}" -f $i, $OutDir)
} finally { $arc.Dispose() }
