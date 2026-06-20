@echo off
chcp 65001 >nul
cd /d "%~dp0"
title JANUS-LAPIS v0.1.5 Birth-Gate Edition
where wt >nul 2>nul
if errorlevel 1 (
    powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0RUN_JANUS_LAPIS.ps1"
    exit /b 0
)
wt -w 0 powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0RUN_JANUS_LAPIS.ps1"
exit /b 0
