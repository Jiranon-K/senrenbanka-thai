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
        $manifest += ("{0}`t{1}`t{2}" -f $i, $name, $e.Offset)
        $i++
    }
    [IO.File]::WriteAllLines((Join-Path $OutDir "manifest.tsv"), [string[]]$manifest)
    Write-Host ("wrote {0} keystreams -> {1}" -f $i, $OutDir)
} finally { $arc.Dispose() }
