# Builds plugin\dist\exhibit-<version>.zip for import into WorkSwarm.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$package = Join-Path $PSScriptRoot 'exhibit'
$manifest = Get-Content -LiteralPath (Join-Path $package 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$dist = Join-Path $PSScriptRoot 'dist'
$zipPath = Join-Path $dist "$($manifest.id)-$($manifest.version).zip"

New-Item -ItemType Directory -Force $dist | Out-Null
if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }

$zip = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
try {
    Get-ChildItem -LiteralPath $package -Recurse -File -Force |
        Where-Object { $_.FullName -notmatch '[\\/](__pycache__|\.pytest_cache|\.ruff_cache)[\\/]' -and $_.Extension -ne '.pyc' } |
        ForEach-Object {
            # Zip entries need forward slashes.
            $relative = $_.FullName.Substring($package.Length + 1).Replace('\', '/')
            $entry = "$($manifest.id)/$relative"
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $entry) | Out-Null
            Write-Output $entry
        }
} finally {
    $zip.Dispose()
}
Write-Output "Built $zipPath"
