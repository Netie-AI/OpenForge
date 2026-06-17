# OpenForge training launcher — run from repo root in PowerShell
# Usage: .\scripts\train.ps1 check | dryrun | finetune | dag

param(
    [Parameter(Position = 0)]
    [ValidateSet("check", "dryrun", "finetune", "dag", "preflight", "harness", "benchmark", "forge", "download", "download-status")]
    [string]$Mode = "check",
    [int]$Hours = 48,
    [int]$MaxSteps = 0,
    [string]$Lora = "",
    [switch]$Smoke,
    [switch]$Full,
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

# Load HF_TOKEN from env.local if not already in session
$envFile = Join-Path (Get-Location) "env.local"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*HF_TOKEN\s*=\s*(.+)\s*$') {
            if (-not $env:HF_TOKEN) { $env:HF_TOKEN = $Matches[1].Trim() }
        }
    }
}

$python = Join-Path (Get-Location) ".venv_train\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Missing .venv_train - run: python -m venv .venv_train; pip install -e '.[train]' mlflow"
}

function Invoke-TrainPython {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $python @Args 2>&1 | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $msg = if ($_.Exception.Message) { $_.Exception.Message } else { "$_" }
                Write-Host $msg
            } else {
                Write-Host $_
            }
        }
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    } finally {
        $ErrorActionPreference = $prev
    }
}

Write-Host "=== OpenForge train.ps1: $Mode ===" -ForegroundColor Cyan

switch ($Mode) {
    "check" {
        Invoke-TrainPython @("scripts/check_train_env.py")
    }
    "preflight" {
        Invoke-TrainPython @("scripts/validate_finetune_jsonl.py")
        Invoke-TrainPython @("scripts/preflight_corpus.py")
        Invoke-TrainPython @("scripts/check_chat_format.py")
        Invoke-TrainPython @("scripts/check_netlist_parse.py")
        Invoke-TrainPython @("scripts/check_lora_targets.py")
    }
    "dryrun" {
        Remove-Item Env:OPENFORGE_FORCE_SMOKE -ErrorAction SilentlyContinue
        $args = @("-u", "scripts/dryrun_finetune.py")
        if ($Smoke) { $args += "--smoke" }
        elseif ($Full) { $args += "--full" }
        if ($Model) { $args += @("--model", $Model) }
        Invoke-TrainPython $args
    }
    "finetune" {
        Remove-Item Env:OPENFORGE_FORCE_SMOKE -ErrorAction SilentlyContinue
        $finetuneArgs = @("-u", "scripts/finetune_lora.py")
        if ($Smoke) { $finetuneArgs += "--smoke" }
        elseif ($Full) { $finetuneArgs += "--full" }
        if ($Model) { $finetuneArgs += @("--model", $Model) }
        if ($MaxSteps -gt 0) { $finetuneArgs += @("--max-steps", $MaxSteps) }
        Invoke-TrainPython $finetuneArgs
    }
    "dag" {
        $dagArgs = @("scripts/run_train_dag.py", "--hours", "$Hours")
        if ($MaxSteps -gt 0) { $dagArgs += @("--max-steps", "$MaxSteps") }
        Invoke-TrainPython $dagArgs
    }
    "harness" {
        Invoke-TrainPython @("scripts/harness_gate_report.py")
    }
    "benchmark" {
        $benchArgs = @("scripts/benchmark_models.py", "--samples", "10")
        if ($Lora) { $benchArgs += @("--lora", $Lora) }
        Invoke-TrainPython $benchArgs
    }
    "forge" {
        Invoke-TrainPython @("-m", "openanalog", "forge", "--n", "200", "--workers", "4")
    }
    "download" {
        $env:HF_HUB_DISABLE_XET = "1"
        Invoke-TrainPython @("-u", "scripts/download_model.py")
    }
    "download-status" {
        Invoke-TrainPython @("scripts/download_status.py")
    }
}
