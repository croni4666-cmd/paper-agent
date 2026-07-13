# Re-download BGE model.safetensors via local clash proxy (port 7897)
$dest = 'C:\Users\DengN\.paper-agent\models\bge-reranker-base'
$proxy = 'http://127.0.0.1:7897'

# Delete corrupted file
$model_out = Join-Path $dest 'model.safetensors'
if (Test-Path $model_out) {
    Write-Host "Deleting corrupted model.safetensors ($((Get-Item $model_out).Length) bytes)..."
    Remove-Item $model_out -Force
}

# Re-download via proxy
$model_url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/model.safetensors"
Write-Host "Downloading model.safetensors via $proxy ..."
Write-Host "URL: $model_url"

# Use curl via PowerShell with proxy
try {
    $ProgressPreference = 'Continue'
    $wc = New-Object System.Net.WebClient
    $wc.Proxy = New-Object System.Net.WebProxy($proxy)
    $wc.DownloadFile($model_url, $model_out)
    $size = (Get-Item $model_out).Length
    Write-Host "  OK: $size bytes ($([math]::Round($size/1MB, 2)) MB)"
} catch {
    Write-Host "  FAIL: $_"
}

# List final contents
Write-Host "`nFinal cache directory contents:"
Get-ChildItem $dest | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0,12:N0} bytes  {1}" -f $_.Length, $_.Name)
}

# Verify the safetensors file size is reasonable
Write-Host "`nExpected size for model.safetensors: ~278 MB (278,044,931 params * ~4 bytes/float)"
