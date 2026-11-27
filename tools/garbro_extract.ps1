param(
    [Parameter(Mandatory=$true)][string]$Archive,
    [Parameter(Mandatory=$true)][string]$OutDir,
    [string]$Filter = "*",
    [switch]$ListOnly,
    [switch]$ListAll,
    [switch]$KeepPaths
)
$ErrorActionPreference = "Stop"

$GarDir = Join-Path $PSScriptRoot "GARbro"
if (-not (Test-Path (Join-Path $GarDir "GameRes.dll"))) { throw "GARbro not found under $GarDir" }

foreach ($dll in (Get-ChildItem $GarDir -Filter *.dll -File)) {
    try { $null = [Reflection.Assembly]::LoadFrom($dll.FullName) } catch { }
}

$cat = [GameRes.FormatCatalog]::Instance
Write-Host ("GARbro catalog: {0} archive formats" -f @($cat.ArcFormats).Count)

$schemeFile = Join-Path $GarDir "GameData\Formats.dat"
if (Test-Path $schemeFile) {
    $fs = [IO.File]::OpenRead($schemeFile)
    try { $cat.DeserializeScheme($fs); Write-Host "loaded scheme db" } finally { $fs.Dispose() }
}

$arc = $null
try { $arc = [GameRes.ArcFile]::TryOpen($Archive) }
catch { throw ("GARbro could not open {0}: {1}" -f $Archive, $_.Exception.Message) }
if ($null -eq $arc) { throw "GARbro returned null for $Archive (format not recognised)" }

try {
    $entries = @($arc.Dir)
    Write-Host ("opened {0}: {1} entries via {2}" -f (Split-Path $Archive -Leaf), $entries.Count, $arc.Interface.Tag)

    $want = @($entries | Where-Object { $_.Name -like $Filter })
    Write-Host ("matching '{0}': {1} entries" -f $Filter, $want.Count)
    $shown = if ($ListAll) { $want } else { $want | Select-Object -First 5 }
    $shown | ForEach-Object { Write-Host ("  {0}   ({1:n0} bytes)" -f $_.Name, $_.Size) }
    if ($ListOnly) { return }

    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $i = 0
    foreach ($e in $want) {
        $rel = if ($KeepPaths) { $e.Name } else { [IO.Path]::GetFileName($e.Name) }
        $dest = Join-Path $OutDir $rel
        if ($KeepPaths) { New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null }
        $inp = $arc.OpenEntry($e)
        try {
            $out = [IO.File]::Create($dest)
            try { $inp.CopyTo($out) } finally { $out.Dispose() }
        } finally { $inp.Dispose() }
        $i++
        if ($i % 20 -eq 0) { Write-Host ("  ...{0}/{1}" -f $i, $want.Count) }
    }
    Write-Host ("extracted {0} files -> {1}" -f $i, $OutDir)
} finally { $arc.Dispose() }
