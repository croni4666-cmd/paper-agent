# Export-CNKICookies.ps1
# Export xueshu789.com cookies to ~/.paper-agent/cookies/cnki.json
# Usage: Right-click → "Run with PowerShell"
#        OR from PowerShell: .\Export-CNKICookies.ps1 -OpenBrowser
#
# What it does:
#   1. Tells you to open Edge/Chrome and visit https://www.xueshu789.com/dbItem/1
#   2. Wait 3 seconds for the JS redirect to fire
#   3. Open browser DevTools (F12) → Application → Cookies → https://www.xueshu789.com
#   4. Copy cookies → paste into this script's terminal
#   5. Saves to $env:USERPROFILE\.paper-agent\cookies\cnki.json
#
# Why manual: xueshu789.com has anti-bot (possibly CAPTCHA on first visit).
# Automated cookie export would need CAPTCHA solver — outside hobbyist scope.

[CmdletBinding()]
param(
    [switch]$OpenBrowser,
    [string]$OutputDir = "$env:USERPROFILE\.paper-agent\cookies"
)

$ErrorActionPreference = "Stop"

# === Step 1: Create output dir ===
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "✓ Created $OutputDir" -ForegroundColor Green
}

$OutputFile = Join-Path $OutputDir "cnki.json"
Write-Host ""
Write-Host "=== Export CNKI Cookies (for paper-agent v3.9.8.x) ===" -ForegroundColor Cyan
Write-Host "Output file: $OutputFile"
Write-Host ""

# === Step 2: Open browser to xueshu789 entry ===
if ($OpenBrowser -or -not $env:PA_BROWSER_OPENED) {
    Write-Host "Step 1/3: Opening Edge to xueshu789.com/dbItem/1 (1.5s JS redirect)..." -ForegroundColor Yellow
    $url = "https://www.xueshu789.com/dbItem/1"
    Start-Process "msedge.exe" $url
    Start-Sleep -Seconds 1
    Write-Host "  ✓ Edge opened to: $url" -ForegroundColor Green
    Write-Host "  ⚠ IMPORTANT: Wait 3-5 seconds for the JS redirect to fire (lands on CNKI proxy IP)" -ForegroundColor Yellow
    Write-Host ""
}

# === Step 3: Walk user through cookie extraction ===
Write-Host "Step 2/3: Extract cookies from browser" -ForegroundColor Yellow
Write-Host "  1. In the opened Edge window, press F12 (open DevTools)" -ForegroundColor White
Write-Host "  2. Go to: Application tab → Storage → Cookies → https://www.xueshu789.com" -ForegroundColor White
Write-Host "  3. You should see 4 cookies: PHPSESSID, user, entrys, expires" -ForegroundColor White
Write-Host "     (If you see 0 cookies, the JS redirect didn't fire — refresh the page)" -ForegroundColor DarkGray
Write-Host "  4. For each of the 4 cookies, copy the value and paste below" -ForegroundColor White
Write-Host ""

$cookies = [ordered]@{
    "PHPSESSID" = ""
    "user"      = ""
    "entrys"    = ""
    "expires"   = ""
}

$idx = 0
foreach ($name in @("PHPSESSID", "user", "entrys", "expires")) {
    $idx++
    Write-Host "  Cookie ${idx}/4 — $name" -ForegroundColor Cyan -NoNewline
    $val = Read-Host " :"
    $cookies[$name] = $val.Trim()
}

# === Step 4: Validate and write JSON ===
$missing = $cookies.Values | Where-Object { $_ -eq "" }
if ($missing) {
    Write-Host ""
    Write-Host "✗ Some cookies are empty. Aborting." -ForegroundColor Red
    exit 1
}

# Playwright-compatible JSON format
$json = @($cookies.Keys | ForEach-Object {
    @{
        name     = $_
        value    = $cookies[$_]
        domain   = "www.xueshu789.com"
        path     = "/"
        expires  = -1
        httpOnly = $false
        secure   = $false
        sameSite = "Lax"
    }
}) | ConvertTo-Json -Depth 5

$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($OutputFile, $json, $utf8NoBom)
Write-Host ""
Write-Host "Step 3/3: Wrote $OutputFile" -ForegroundColor Green
Write-Host ""
Write-Host "=== Cookie summary ===" -ForegroundColor Cyan
foreach ($k in $cookies.Keys) {
    $v = $cookies[$k]
    $masked = if ($v.Length -gt 8) { $v.Substring(0, 4) + "***" + $v.Substring($v.Length - 4) } else { $v }
    Write-Host "  ${k}: $masked (length=$($v.Length))"
}
Write-Host ""
Write-Host "✓ Done. Test with:" -ForegroundColor Green
Write-Host "    python -c `"import sys; sys.path.insert(0, r'G:\minimax - workspace\Paper agent'); from pa_cli.cnki_channel import cookies_exist, cookie_age_hours; print('exists:', cookies_exist(), 'age:', cookie_age_hours())`"" -ForegroundColor White
Write-Host ""
Write-Host "Then try:" -ForegroundColor Green
Write-Host "    pa fetch --doi 10.3969/j.issn.1003-9031.2022.04.008 --out test.pdf" -ForegroundColor White
Write-Host ""
Write-Host "⚠ Cookies expire after ~4 hours. Re-run this script when fetch fails with 'cookie_expired'." -ForegroundColor Yellow
