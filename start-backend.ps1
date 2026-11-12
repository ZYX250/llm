# 一键启动后端：自动切到 backend 目录并用虚拟环境里的 python 跑 uvicorn
# 用法：
#   .\start-backend.ps1               启动并开启热重载（开发用）
#   .\start-backend.ps1 -NoReload     不开启热重载（答辩/演示用，启动更快更稳）
param([switch]$NoReload)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
if (-not $root) { $root = Split-Path -Parent $MyInvocation.MyCommand.Path }
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "[错误] 找不到虚拟环境：$python" -ForegroundColor Red
    Write-Host "请先执行：" -ForegroundColor Yellow
    Write-Host "  cd backend" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

$busy = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($busy) {
    # 注意不能只查 -State Listen：uvicorn 是先 bind 再 import app，
    # 若 import 失败进程会留下 Bound 状态占着端口，只查 Listen 会漏判
    $pidNum = ($busy | Select-Object -First 1).OwningProcess
    $state = ($busy | Select-Object -First 1).State
    Write-Host "[提示] 端口 8000 已被进程 $pidNum 占用（状态 $state）。" -ForegroundColor Yellow
    Write-Host "       若该进程是上次加载失败的残留，先结束它：Stop-Process -Id $pidNum" -ForegroundColor Yellow
    exit 1
}

Set-Location -LiteralPath $backend
$uvArgs = @("-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000")
if (-not $NoReload) { $uvArgs += "--reload" }

Write-Host "工作目录：$backend" -ForegroundColor Cyan
Write-Host "命令：python $($uvArgs -join ' ')" -ForegroundColor DarkGray
Write-Host "启动完成后访问：http://127.0.0.1:8000/docs" -ForegroundColor Cyan
Write-Host ""

& $python @uvArgs
