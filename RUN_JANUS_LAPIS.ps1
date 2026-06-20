$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Set-Location $PSScriptRoot

Clear-Host
Write-Host "==============================================================" -ForegroundColor DarkMagenta
Write-Host "              J A N U S - L A P I S   v0.1.3" -ForegroundColor Magenta
Write-Host "==============================================================" -ForegroundColor DarkMagenta
Write-Host "Demiurge Edition: the stone is also the engine." -ForegroundColor Green

python janus_lapis_selfrunner.py

Read-Host "Press Enter to close"
