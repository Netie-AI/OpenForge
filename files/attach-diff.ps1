# .cursor/hooks/attach-diff.ps1
# Cursor "stop" hook: capture git evidence on every agent stop.
#
# Intended behavior:
# - Append a markdown evidence block under .cursor/hooks/session-evidence/
# - Record status + unstaged diff + staged diff
# - Fail open (log what happened, do not block stop event)

$raw = [Console]::In.ReadToEnd()
$convId = "unknown-session"

try {
    $payload = $raw | ConvertFrom-Json
    if ($payload.conversation_id) {
        $convId = "$($payload.conversation_id)"
    }
} catch {
    # Keep default unknown-session and continue.
}

function Invoke-GitCapture {
    param([string[]]$GitArgs)
    try {
        $result = & git @GitArgs 2>&1 | Out-String
        if ([string]::IsNullOrWhiteSpace($result)) {
            return "<empty>"
        }
        return $result.TrimEnd()
    } catch {
        $joined = $GitArgs -join " "
        return "<error running: git $joined>`n$($_.Exception.Message)"
    }
}

$logDir = ".cursor/hooks/session-evidence"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$logFile = Join-Path $logDir "$convId.md"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$repoCheck = Invoke-GitCapture @("rev-parse", "--is-inside-work-tree")

if ($repoCheck -notmatch "true") {
    $entry = @"
## Session evidence - $timestamp

### Hook status
~~~text
attach-diff: git repository not detected
conversation_id: $convId
rev-parse output:
$repoCheck
~~~
"@
    Add-Content -Path $logFile -Value $entry
    Write-Output $entry
    exit 0
}

$status = Invoke-GitCapture @("status", "--short")
$diffStat = Invoke-GitCapture @("diff", "--stat")
$unstaged = Invoke-GitCapture @("diff")
$stagedStat = Invoke-GitCapture @("diff", "--cached", "--stat")
$staged = Invoke-GitCapture @("diff", "--cached")

$entry = @"
## Session evidence - $timestamp

### git status --short
~~~text
$status
~~~

### git diff --stat (unstaged)
~~~text
$diffStat
~~~

### git diff (unstaged)
~~~diff
$unstaged
~~~

### git diff --cached --stat (staged)
~~~text
$stagedStat
~~~

### git diff --cached (staged)
~~~diff
$staged
~~~
"@

Add-Content -Path $logFile -Value $entry
Write-Output $entry
