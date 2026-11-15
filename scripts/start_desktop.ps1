<#
.SYNOPSIS
  Launch OrbitLab in its own desktop window (no browser).

.DESCRIPTION
  Sets PYTHONPATH, picks up GMAT_PATH from the bundled tools/gmat copy only
  when GMAT_PATH is not already set, then runs scripts/desktop_app.py.

.PARAMETER Demo
  Pass the launcher --demo (sets ORBITLAB_DEMO_MODE=true before starting).

.PARAMETER Port
  Optional fixed local port (default 0 = the launcher picks a free one).
#>
param(
    [switch]$Demo,
    [int]$Port = 0
)
$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $repoRoot 'phase4_backend'

if (-not $env:GMAT_PATH) {
    $console = Get-ChildItem -Path (Join-Path $repoRoot 'tools/gmat') -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { ($_.Name -eq 'GmatConsole.exe' -or $_.Name -eq 'GmatConsole') -and $_.Directory.Name -eq 'bin' } |
        Select-Object -First 1
    if ($console) { $env:GMAT_PATH = $console.FullName }
}

$launcherArgs = @((Join-Path $repoRoot 'scripts/desktop_app.py'))
if ($Demo) { $launcherArgs += '--demo' }
if ($Port) { $launcherArgs += @('--port', "$Port") }
& python @launcherArgs
