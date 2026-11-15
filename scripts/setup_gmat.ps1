<#
.SYNOPSIS
  Download a GMAT release zip (URL you supply) and extract it into tools/gmat/.

.PARAMETER Url
  Required. The release zip link (nothing is hard-coded; no archive is committed).

.PARAMETER Sha256
  Optional expected SHA-256 hex digest of the zip. Fails the setup on mismatch.

.PARAMETER OutDir
  Optional destination folder. Defaults to <repo>/tools/gmat.
#>
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Sha256 = "",
    [string]$OutDir = ""
)
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $repoRoot 'tools/gmat' }

$tmp = New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) ('orbitlab-gmat-' + [Guid]::NewGuid().ToString('N')))
try {
    $zip = Join-Path $tmp.FullName 'gmat.zip'
    Write-Host 'Downloading GMAT release...'
    Invoke-WebRequest -Uri $Url -OutFile $zip -UseBasicParsing
    if ($Sha256) {
        $actual = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $Sha256.ToLowerInvariant()) {
            throw 'SHA-256 mismatch: expected the given digest but got a different file. Setup stopped.'
        }
        Write-Host 'SHA-256 verified.'
    }
    New-Item -ItemType Directory -Force $OutDir | Out-Null
    Write-Host 'Extracting...'
    Expand-Archive -Path $zip -DestinationPath $OutDir -Force
    $console = Get-ChildItem -Path $OutDir -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'GmatConsole.exe' -and $_.Directory.Name -eq 'bin' } |
        Select-Object -First 1
    if (-not $console) {
        $console = Get-ChildItem -Path $OutDir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -eq 'GmatConsole' -and $_.Directory.Name -eq 'bin' } |
            Select-Object -First 1
    }
    if (-not $console) {
        throw 'bin/GmatConsole(.exe) not found after extracting. The archive layout is unexpected.'
    }
    Write-Host ('GMAT ready: ' + $console.FullName)
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
finally {
    try { Remove-Item -Recurse -Force $tmp.FullName -ErrorAction SilentlyContinue } catch {}
}
