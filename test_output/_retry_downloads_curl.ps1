# Try to download the 10 manual PDFs via curl.exe (which we know works with proxy)
$proxy = 'http://127.0.0.1:7897'
$dest = 'C:\Users\DengN\.paper-agent\deep_rerank\manual_retry'
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# 10 DOIs from v3.9.5 manual downloads list
$dois = @(
    @{qid='q001'; doi='10.1186/s41239-021-00292-9'},
    @{qid='q001'; doi='10.1001/jamanetworkopen.2021.49008'},
    @{qid='q001'; doi='10.3390/su151612451'},
    @{qid='q002'; doi='10.1093/oxrep/graa051'},
    @{qid='q002'; doi='10.1016/j.jebo.2020.07.014'},
    @{qid='q002'; doi='10.1111/j.1467-9914.2007.00378.x'},
    @{qid='q002'; doi='10.5089/9781498303743.001'},
    @{qid='q002'; doi='10.1037/e686432011-001'},
    @{qid='q003'; doi='10.1145/3488560.3498443'},
    @{qid='q003'; doi='10.1109/icdar.2013.114'}
)

# Build a list of mirror URLs to try
# Strategy: for each DOI, try (in order):
#   1. doi.org direct (works for some open access)
#   2. sci-hub mirror (multiple known)
#   3. arXiv (if applicable)
#   4. semanticscholar.org
#   5. europepmc.org

$urlPatterns = @(
    'https://doi.org/{doi}',
    'https://sci-hub.se/{doi}',
    'https://sci-hub.st/{doi}',
    'https://sci-hub.ru/{doi}',
    'https://www.semanticscholar.org/doi/{doi}',
    'https://europepmc.org/article/MED/{doi}'
)

$results = @()
foreach ($d in $dois) {
    $qid = $d.qid
    $doi = $d.doi
    Write-Host "Processing $qid | $doi"

    $dir = Join-Path $dest $qid
    New-Item -ItemType Directory -Path $dir -Force | Out-Null

    $downloaded = $false
    foreach ($pattern in $urlPatterns) {
        $url = $pattern -replace '\{doi\}', $doi
        $doiSlug = $doi -replace '/', '_' -replace '\.', '_'
        $out = Join-Path $dir ($doiSlug + '.pdf')

        Write-Host "  Trying: $url" -NoNewline
        try {
            # HEAD first to check Content-Type
            $ProgressPreference = 'SilentlyContinue'
            $response = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 10
            $ct = $response.Headers['Content-Type']
            $len = $response.Headers['Content-Length']
            Write-Host "  [$ct, $len bytes]" -NoNewline

            if ($ct -like '*pdf*') {
                # Download with curl
                & curl.exe -L --proxy $proxy -o $out --connect-timeout 15 --max-time 90 $url 2>$null
                if (Test-Path $out) {
                    $size = (Get-Item $out).Length
                    if ($size -gt 10000) {
                        Write-Host "  OK: $size bytes"
                        $results += [PSCustomObject]@{
                            qid = $qid
                            doi = $doi
                            url = $url
                            saved_as = $out
                            size_bytes = $size
                            status = 'ok'
                        }
                        $downloaded = $true
                        break
                    } else {
                        Write-Host "  Too small: $size bytes, skipping"
                        Remove-Item $out -ErrorAction SilentlyContinue
                    }
                }
            } else {
                Write-Host "  [not PDF]"
            }
        } catch {
            $msg = $_.Exception.Message
            Write-Host "  [err: $($msg.Substring(0, [Math]::Min(60, $msg.Length)))]"
        }
    }
    if (-not $downloaded) {
        Write-Host "  No source worked"
        $results += [PSCustomObject]@{
            qid = $qid
            doi = $doi
            url = $null
            saved_as = $null
            size_bytes = 0
            status = 'no_source_worked'
        }
    }
}

$summary = $results | Group-Object -Property status
Write-Host "`nSummary:"
foreach ($g in $summary) {
    Write-Host "  $($g.Name): $($g.Count)"
}

$json = $results | ConvertTo-Json -Depth 3
$outPath = Join-Path $dest ('manual_retry_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
$json | Out-File $outPath -Encoding UTF8
Write-Host "`nOutput: $outPath"
