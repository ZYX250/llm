@echo off
rem 用绝对路径调用系统自带 Windows PowerShell，避免 PATH 中找不到 powershell
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-backend.ps1" %*
pause
