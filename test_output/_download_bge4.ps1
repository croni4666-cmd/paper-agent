# Re-download BGE model.safetensors via clash proxy with redirect following
$dest = 'C:\Users\DengN\.paper-agent\models\bge-reranker-base'
$proxy = 'http://127.0.0.1:7897'

$model_out = Join-Path $dest 'model.safetensors'
if (Test-Path $model_out) { Remove-Item $model_out -Force }

# Try several URLs
$urls = @(
    "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/model.safetensors",
    "https://huggingface.co/BAAI/bge-reranker-base/resolve/main/model.safetensors"
)

foreach ($model_url in $urls) {
    Write-Host "Trying: $model_url"
    try {
        # Use Invoke-WebRequest with proxy, allow redirects
        [System.Net.WebRequest]::DefaultWebProxy = New-Object System.Net.WebProxy($proxy)
        $ProgressPreference = 'Continue'
        Invoke-WebRequest -Uri $model_url -OutFile $model_out -UseBasicParsing -TimeoutSec 1200 -MaximumRedirection 10
        $size = (Get-Item $model_out).Length
        Write-Host "  OK: $size bytes ($([math]::Round($size/1MB, 2)) MB)"
        if ($size -gt 100MB) {
            Write-Host "  Looks like a real download"
            break
        }
    } catch {
        Write-Host "  FAIL: $($_.Exception.Message)"
    }
}

Write-Host "`nFinal cache directory contents:"
Get-ChildItem $dest | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0,12:N0} bytes  {1}" -f $_.Length, $_.Name)
}
