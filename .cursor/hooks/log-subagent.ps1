# .cursor/hooks/log-subagent.ps1
# Cursor "subagentStop" hook (beta API). Subagent intermediate output is
# isolated to its own context by design - the parent only sees a final
# summary. This hook at least logs *that* a subagent ran and when, so
# there's an audit trail independent of the summary's honesty.

$stdin = [Console]::In.ReadToEnd()
try {
    $payload = $stdin | ConvertFrom-Json
    $convId = $payload.conversation_id
} catch {
    $convId = "unknown-session"
}

$logFile = ".cursor/hooks/subagent-log.md"
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $logFile -Value "- $timestamp :: subagent stopped :: conversation $convId"
