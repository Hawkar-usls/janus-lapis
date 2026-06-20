$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"

Set-Location $PSScriptRoot

Clear-Host
Write-Host "==============================================================" -ForegroundColor DarkMagenta
Write-Host "              J A N U S - L A P I S   v0.1.4" -ForegroundColor Magenta
Write-Host "==============================================================" -ForegroundColor DarkMagenta
Write-Host "Canvas / Stagekeeper Edition: the stone prepares the scene." -ForegroundColor Green

python janus_lapis_selfrunner.py

Read-Host "Press Enter to close"
