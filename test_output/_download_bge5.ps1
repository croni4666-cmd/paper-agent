# Use curl.exe for robust download with redirect following + resume
$dest = 'C:\Users\DengN\.paper-agent\models\bge-reranker-base'
$proxy = 'http://127.0.0.1:7897'

$model_out = Join-Path $dest 'model.safetensors'
if (Test-Path $model_out) { Remove-Item $model_out -Force }

$model_url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/model.safetensors"
Write-Host "Downloading via curl.exe with proxy $proxy"
Write-Host "URL: $model_url"

# curl.exe with: -L (follow redirects), -C - (resume), --proxy, --output
& curl.exe -L -C - --proxy "$proxy" -o "$model_out" --connect-timeout 30 --max-time 1200 "$model_url"
$rc = $LASTEXITCODE

if (Test-Path $model_out) {
    $size = (Get-Item $model_out).Length
    Write-Host "Download complete. Size: $size bytes ($([math]::Round($size/1MB, 2)) MB)"
    Write-Host "curl exit code: $rc"
} else {
    Write-Host "Download failed. curl exit code: $rc"
}

Write-Host "`nFinal cache directory contents:"
Get-ChildItem $dest | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0,12:N0} bytes  {1}" -f $_.Length, $_.Name)
}
