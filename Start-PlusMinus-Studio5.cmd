@echo off
setlocal EnableExtensions
title PlusMinus Studio 5 - Tauri
cd /d "%~dp0"
if errorlevel 1 (
  echo [Studio 5] Cannot open the project directory.
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\bootstrap-studio5.ps1" %*
set "status=%errorlevel%"
if not "%status%"=="0" (
  echo [Studio 5] Bootstrap failed with exit code %status%.
  echo [Studio 5] Run this CMD from PowerShell to inspect its full diagnostics.
)
exit /b %status%
