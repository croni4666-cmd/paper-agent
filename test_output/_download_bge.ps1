# Download BGE-reranker-base files via PowerShell (urllib fails from Python on this network)
$dest = 'C:\Users\DengN\.paper-agent\models\bge-reranker-base'
New-Item -ItemType Directory -Path $dest -Force | Out-Null

$files = @('config.json', 'tokenizer.json', 'tokenizer_config.json', 'vocab.txt', 'special_tokens_map.json')
$model_file = 'model.safetensors'

foreach ($f in $files) {
    $url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/$f"
    $out = Join-Path $dest $f
    if (Test-Path $out) {
        Write-Host "  exists: $f"
        continue
    }
    Write-Host "Downloading $f..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -TimeoutSec 60
        $size = (Get-Item $out).Length
        Write-Host "  OK: $size bytes"
    } catch {
        Write-Host "  FAIL: $_"
    }
}

# Now download the large model file (~278MB)
$model_url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/$model_file"
$model_out = Join-Path $dest $model_file
if (Test-Path $model_out) {
    Write-Host "  exists: $model_file"
} else {
    Write-Host "Downloading $model_file (this may take a few minutes)..."
    try {
        Invoke-WebRequest -Uri $model_url -OutFile $model_out -UseBasicParsing -TimeoutSec 600
        $size = (Get-Item $model_out).Length
        Write-Host "  OK: $size bytes"
    } catch {
        Write-Host "  FAIL: $_"
    }
}

# List final contents
Write-Host "`nFinal cache directory contents:"
Get-ChildItem $dest | ForEach-Object { Write-Host ("  {0,12:N0} bytes  {1}" -f $_.Length, $_.Name) }
