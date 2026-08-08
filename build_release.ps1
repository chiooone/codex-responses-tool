$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -m unittest discover -s tests -v
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --noupx `
    --name CodexResponsesTool `
    --add-data "assets/codex_model_catalog.json;assets" `
    --version-file version_info.txt `
    app.py

$executable = Join-Path $PSScriptRoot "dist\CodexResponsesTool.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Build completed without producing $executable"
}

$hash = Get-FileHash -LiteralPath $executable -Algorithm SHA256
$checksumPath = Join-Path $PSScriptRoot "dist\CodexResponsesTool.exe.sha256"
"$($hash.Hash.ToLowerInvariant())  CodexResponsesTool.exe" | Set-Content -LiteralPath $checksumPath -Encoding ascii

Write-Output "Built: $executable"
Write-Output "SHA256: $($hash.Hash.ToLowerInvariant())"
