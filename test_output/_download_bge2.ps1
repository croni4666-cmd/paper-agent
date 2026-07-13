# Download BGE-reranker-base (v2) — proper file list
$dest = 'C:\Users\DengN\.paper-agent\models\bge-reranker-base'
New-Item -ItemType Directory -Path $dest -Force | Out-Null

# Correct file list (no vocab.txt — that doesn't exist; vocab is in sentencepiece.bpe.model)
$small_files = @('config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'sentencepiece.bpe.model')
$model_file = 'model.safetensors'

foreach ($f in $small_files) {
    $url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/$f"
    $out = Join-Path $dest $f
    if (Test-Path $out) {
        Write-Host "  exists: $f"
        continue
    }
    Write-Host "Downloading $f..."
    try {
        Invoke-WebRequest -Uri $url -OutFile $out -UseBasicParsing -TimeoutSec 120
        $size = (Get-Item $out).Length
        Write-Host "  OK: $size bytes"
    } catch {
        Write-Host "  FAIL: $_"
    }
}

# Now download the large model file (~278MB safetensors)
$model_url = "https://hf-mirror.com/BAAI/bge-reranker-base/resolve/main/$model_file"
$model_out = Join-Path $dest $model_file
if (Test-Path $model_out) {
    Write-Host "  exists: $model_file"
} else {
    Write-Host "Downloading $model_file (~278 MB, may take a few minutes)..."
    try {
        $ProgressPreference = 'Continue'
        Invoke-WebRequest -Uri $model_url -OutFile $model_out -UseBasicParsing -TimeoutSec 1200
        $size = (Get-Item $model_out).Length
        Write-Host "  OK: $size bytes ($([math]::Round($size/1MB, 2)) MB)"
    } catch {
        Write-Host "  FAIL: $_"
    }
}

# List final contents
Write-Host "`nFinal cache directory contents:"
Get-ChildItem $dest | Sort-Object Name | ForEach-Object {
    Write-Host ("  {0,12:N0} bytes  {1}" -f $_.Length, $_.Name)
}
