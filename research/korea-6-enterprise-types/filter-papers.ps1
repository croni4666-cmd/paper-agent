$ErrorActionPreference = 'Stop'
Set-Location "G:\minimax - workspace\Paper agent\research\korea-6-enterprise-types"

# Step 1: Load all bib files (they're JSON) and concatenate
$allPapers = New-Object System.Collections.ArrayList
Get-ChildItem -Name q*.bib | Sort-Object | ForEach-Object {
    try {
        $content = Get-Content $_ -Raw -Encoding UTF8
        if ($content -match '^\s*\{') {
            $j = $content | ConvertFrom-Json
            foreach ($r in $j.results) {
                $allPapers.Add($r) | Out-Null
            }
        }
    } catch {
        Write-Host "PARSE_FAIL: $_" -ForegroundColor Yellow
    }
}

Write-Host "Total loaded: $($allPapers.Count)"

# Step 2: Korea-related filter
$koreaKw = '(korea|korean|chaebol|재벌|파견|도급|위장|사내|하청|기간제|비정규직|용역|외주|용역|도급|하도급|위탁|사내하청|파견업체|파견사업|dispatch|subcontract|tier.?[12]|saenae|samcheop|hyundai|samsung|LG|SK|lotte|hanjin|daewoo|hyosung)'
$laborKw = '(labor|labour|employ|work|wage|union|工人|劳动|労使|雇用|고용|임금|노조|파견|도급|dispatch|subcontract|non.?regular|fixed.?term|precarious|atypical|temporary|agency|platform|gig|freelanc)'

$koreaRel = @()
foreach ($p in $allPapers) {
    $text = "$($p.title) $($p.abstract) $($p.venue)"
    if ($text -match $koreaKw -and $text -match $laborKw) {
        $koreaRel += $p
    }
}

Write-Host "Korea + labor related: $($koreaRel.Count)"

# Step 3: Dedup by DOI
$seen = @{}
$dedup = @()
foreach ($p in $koreaRel) {
    $key = if ($p.doi) { $p.doi } else { $p.title }
    if (-not $seen.ContainsKey($key)) {
        $seen[$key] = $true
        $dedup += $p
    }
}

Write-Host "After dedup: $($dedup.Count)"

# Step 4: Sort by cited_by_count desc
$dedup = $dedup | Where-Object { $null -ne $_.cited_by_count } | Sort-Object -Property @{Expression="cited_by_count"; Descending=$true}

# Step 5: Output
$dedup | Select-Object -First 60 | ForEach-Object {
    $cite = $_.cited_by_count
    $year = $_.year
    $venue = $_.venue
    $title = $_.title
    if ($title.Length -gt 100) { $title = $title.Substring(0, 97) + '...' }
    $authors = ($_.authors | Where-Object { $_ } | Select-Object -First 3) -join ', '
    if ($authors.Length -gt 50) { $authors = $authors.Substring(0, 47) + '...' }
    "{0,-6} | {1,-4} | {2,-30} | {3} | {4}" -f $cite, $year, $venue, $title, $authors
} | Out-File -Encoding UTF8 "filtered-top60.txt"

Write-Host "Top 60 saved to filtered-top60.txt"
