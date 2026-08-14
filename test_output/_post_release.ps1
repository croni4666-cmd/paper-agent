$ErrorActionPreference = 'Stop'
Set-Location 'G:\minimax - workspace\Paper agent'
$token = Get-Content (Join-Path $env:USERPROFILE '.gh_token') -Raw
$token = $token.Trim()
$headers = @{
    'Authorization' = "token $token"
    'User-Agent'    = 'paper-agent-releaser'
    'Accept'        = 'application/vnd.github+json'
}
$body = Get-Content test_output/_release_notes_v3_9_12_0.md -Raw -Encoding UTF8
$payload = @{
    tag_name         = 'v3.9.12.0'
    target_commitish = 'main'
    name             = 'v3.9.12.0 — ClinicalTrials.gov engine & 7 prior commits'
    body             = $body
    draft            = $false
    prerelease       = $false
} | ConvertTo-Json -Depth 10 -Compress
$proxy = [System.Net.WebProxy]::new('http://127.0.0.1:10808')
try {
    $resp = Invoke-RestMethod -Uri 'https://api.github.com/repos/croni4666-cmd/paper-agent/releases' -Method Post -Headers $headers -Body $payload -ContentType 'application/json' -TimeoutSec 300 -Proxy $proxy
    Write-Host "OK: $($resp.html_url)"
    Write-Host "name: $($resp.name)"
    Write-Host "tag:  $($resp.tag_name)"
    Write-Host "draft: $($resp.draft) prerelease: $($resp.prerelease)"
} catch {
    Write-Host "ERR: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        Write-Host "body: $($reader.ReadToEnd())"
    }
}
