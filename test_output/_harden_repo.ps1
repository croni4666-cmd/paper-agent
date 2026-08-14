$ErrorActionPreference = 'Stop'
$env:GH_TOKEN = (Get-Content (Join-Path $env:USERPROFILE '.gh_token') -Raw).Trim()
$env:HTTPS_PROXY = 'http://127.0.0.1:10808'
$h = @{
    'Authorization' = "token $env:GH_TOKEN"
    'Accept'        = 'application/vnd.github+json'
    'User-Agent'    = 'paper-agent-audit'
}
$repo = 'croni4666-cmd/paper-agent'

Write-Host '=== 3.1 enable vulnerability alerts ==='
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/vulnerability-alerts" -Method Put -Headers $h -TimeoutSec 30
    Write-Host "  vulnerability_alerts: ENABLED"
} catch { Write-Host "  ERR: $($_.Exception.Message)" }

Write-Host '=== 3.2 enable automated security fixes (Dependabot) ==='
try {
    Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/automated-security-fixes" -Method Put -Headers $h -TimeoutSec 30
    Write-Host "  automated_security_fixes: ENABLED"
} catch { Write-Host "  ERR: $($_.Exception.Message)" }

Write-Host '=== 3.3 enable branch protection on main (linear history only) ==='
$bpBody = @{
    required_status_checks            = $null
    enforce_admins                    = $false
    required_pull_request_reviews     = $null
    restrictions                      = $null
    required_linear_history           = $true
    allow_force_pushes                = $false
    allow_deletions                   = $false
    block_creations                   = $false
    required_conversation_resolution  = $true
    lock_branch                       = $false
    allow_fork_syncing                = $false
} | ConvertTo-Json -Depth 5 -Compress
try {
    $r = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/branches/main/protection" -Method Put -Headers $h -Body $bpBody -TimeoutSec 30
    Write-Host "  branch_protection: ENABLED"
    Write-Host "    required_linear_history: $($r.required_linear_history.enabled)"
    Write-Host "    allow_force_pushes:    $($r.allow_force_pushes.enabled)"
    Write-Host "    allow_deletions:       $($r.allow_deletions.enabled)"
} catch { Write-Host "  ERR: $($_.Exception.Message)" }

Write-Host '=== 3.4 verify settings ==='
try {
    $a = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/vulnerability-alerts" -Method Get -Headers $h -TimeoutSec 30
    Write-Host "  vulnerability_alerts: $(if ($a.enabled) { 'ENABLED' } else { 'disabled' })"
} catch { Write-Host "  vulnerability_alerts: 404 (free-plan or not enabled)" }
try {
    $b = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/automated-security-fixes" -Method Get -Headers $h -TimeoutSec 30
    Write-Host "  dependabot_alerts: enabled=$($b.dependabot_alerts.enabled)  dependabot_security_updates.enabled=$($b.dependabot_security_updates.enabled)"
} catch { Write-Host "  dependabot_alerts: 404 (free-plan or not enabled)" }
try {
    $p = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/branches/main/protection" -Method Get -Headers $h -TimeoutSec 30
    Write-Host "  branch_protection: ENABLED (linear_history: $($p.required_linear_history.enabled))"
} catch { Write-Host "  branch_protection: NOT ENABLED" }
