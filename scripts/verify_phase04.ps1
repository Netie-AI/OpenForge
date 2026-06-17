# Hardened Phase 0.4 launcher (Windows PowerShell)
# Usage: .\scripts\verify_phase04.ps1

param([int]$Port = 8080)

$ErrorActionPreference = "Continue"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$ports = 8080, 8081, 8082, 8083
Write-Host "=== Killing listeners on ports $($ports -join ', ') ===" -ForegroundColor Cyan
foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "  Stop $($proc.ProcessName) (PID $($proc.Id)) on :$p"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
Start-Sleep -Seconds 2

$env:OPENFORGE_WSL_DISTRO = "Ubuntu"
if (Test-Path ".\.venv_wsl\Scripts\python.exe") {
    $python = (Resolve-Path ".\.venv_wsl\Scripts\python.exe").Path
} elseif (Test-Path ".\.venv\Scripts\python.exe") {
    $python = (Resolve-Path ".\.venv\Scripts\python.exe").Path
} else {
    $python = (Get-Command python -ErrorAction Stop).Source
}

Write-Host "=== Starting server on :$Port using $python ===" -ForegroundColor Cyan
$job = Start-Job -ScriptBlock {
    param($py, $root, $port)
    Set-Location $root
    $env:OPENFORGE_WSL_DISTRO = "Ubuntu"
    & $py -m openanalog serve --host 127.0.0.1 --port $port 2>&1
} -ArgumentList $python, $Root, $Port

Start-Sleep -Seconds 5
for ($i = 1; $i -le 15; $i++) {
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$Port/api/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
        Write-Host "Server ready."
        break
    } catch {
        Start-Sleep -Seconds 2
    }
}

& $python scripts/verify_phase04.py $Port
$code = $LASTEXITCODE

Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}

exit $code
