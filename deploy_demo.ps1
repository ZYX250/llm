# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    传智杯「科研助手 Agent 系统 v2.0」一键部署演示脚本（含公网隧道）
.DESCRIPTION
    一条命令把项目拉起为"评委可公网访问的常驻演示"，满足比赛 2.4 在线演示要求：
      1) 端口预检（避免旧进程占用导致启动失败）
      2) 注入 REVIEWER_TOKEN（评审鉴权令牌，自动生成或外部传入）
      3) 后台启动后端(uvicorn:8000) + 前端(vite:5173，自带 /api 代理到后端)
      4) 等待端口就绪 + 冒烟测试（经 /api 代理访问 /reviewer/info）
      5) 局域网 / 公网隧道二选一，输出访问卡片 + 推荐演示流程
    关键点：前端 vite 已配置 /api -> 127.0.0.1:8000 的同源代理，因此公网只需
           暴露"前端 5173"一个端口，浏览器所有 API 与评审接口都经同一地址可达。

    用法：
      pwsh deploy_demo.ps1                      # 局域网模式（评委连同一 WiFi）
      pwsh deploy_demo.ps1 -Public              # 公网模式（自动选 cloudflared / ngrok 隧道前端）
      pwsh deploy_demo.ps1 -Public -TunnelTool ngrok   # 强制用 ngrok
      pwsh deploy_demo.ps1 -ReviewerToken abc123 # 指定固定令牌
      pwsh deploy_demo.ps1 -Follow              # 启动后尾随后端日志
      pwsh deploy_demo.ps1 -Stop                # 停止全部（含隧道进程）
#>
[CmdletBinding()]
param(
    [switch]$Public,

    [ValidateSet("auto", "ngrok", "cloudflared")]
    [string]$TunnelTool = "auto",

    [string]$ReviewerToken = "",

    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,

    [switch]$Stop,
    [switch]$Follow
)

$ErrorActionPreference = "Stop"

# 去除大小写重复的代理变量（如 HTTPS_PROXY 与 https_proxy 同时存在会导致
# Start-Process 继承环境时字典键冲突而报错）。只删大写形式，小写由 Python 正常识别。
Remove-Item -Path Env:HTTP_PROXY  -ErrorAction SilentlyContinue
Remove-Item -Path Env:HTTPS_PROXY -ErrorAction SilentlyContinue
Remove-Item -Path Env:NO_PROXY    -ErrorAction SilentlyContinue

$ROOT      = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND   = Join-Path $ROOT "backend"
$FRONTEND  = Join-Path $ROOT "frontend"
$PY        = Join-Path $BACKEND ".venv\Scripts\python.exe"
$ACCESSFILE = Join-Path $ROOT "reviewer_access.txt"
$BKLOG     = Join-Path $ROOT "backend.log"
$BKERR     = Join-Path $ROOT "backend.err.log"
$FNLOG     = Join-Path $ROOT "frontend.log"
$FNERR     = Join-Path $ROOT "frontend.err.log"
$CFLOG     = Join-Path $ROOT "cloudflared.log"
$CFERR     = Join-Path $ROOT "cloudflared.err.log"

function Get-PidOnPort($port) {
    $line = netstat -ano 2>$null | Select-String ":$port\s" | Select-String "LISTENING" | Select-Object -First 1
    if ($line) { return ($line.ToString() -split '\s+')[-1] }
    return $null
}

function Test-PortOpen($port) {
    return (Test-NetConnection -ComputerName 127.0.0.1 -Port $port -WarningAction SilentlyContinue -InformationLevel Quiet)
}

function Wait-Port($port, $timeout = 60) {
    $end = (Get-Date).AddSeconds($timeout)
    while ((Get-Date) -lt $end) {
        if (Test-PortOpen $port) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

# ─────────────────────────── 停止模式 ───────────────────────────
if ($Stop) {
    Write-Host "`n正在停止演示服务（含隧道进程）..." -ForegroundColor Yellow
    foreach ($p in @($BackendPort, $FrontendPort)) {
        $pidx = Get-PidOnPort $p
        if ($pidx) {
            Write-Host "  终止占用端口 $p 的进程树 (PID $pidx) ..."
            taskkill /PID $pidx /T /F 2>$null | Out-Null
        }
    }
    # 隧道进程（不绑定固定本地端口，直接按镜像名清理）
    taskkill /IM ngrok.exe /F 2>$null | Out-Null
    taskkill /IM cloudflared.exe /F 2>$null | Out-Null
    Remove-Item $ACCESSFILE -ErrorAction SilentlyContinue
    Write-Host "已停止。日志保留在 backend.log / frontend.log`n" -ForegroundColor Green
    exit 0
}

# ───────────────────── 1. 端口预检（防旧进程占用） ─────────────────────
Write-Host "`n[1/5] 端口预检 ..." -ForegroundColor Cyan
foreach ($p in @($BackendPort, $FrontendPort)) {
    if (Test-PortOpen $p) {
        $pidx = Get-PidOnPort $p
        Write-Host "  ⚠ 端口 $p 已被占用 (PID $pidx)。请先停止旧服务：`n      pwsh deploy_demo.ps1 -Stop" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  ✓ 端口 $BackendPort / $FrontendPort 均空闲" -ForegroundColor Green

# ───────────────────── 2. 准备 REVIEWER_TOKEN ─────────────────────
if (-not $ReviewerToken) {
    $chars = (48..57) + (65..90) + (97..122) | ForEach-Object { [char]$_ }
    $ReviewerToken = -join (1..20 | ForEach-Object { $chars[(Get-Random -Minimum 0 -Maximum $chars.Count)] })
}
$env:REVIEWER_TOKEN = $ReviewerToken

# CORS 白名单：浏览器走 vite 同源代理，本设置主要用于"直接访问后端 8000"的场景
$lanIP = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
          Where-Object { $_.IPAddress -ne "127.0.0.1" -and $_.InterfaceAlias -notmatch "Loopback" } |
          Select-Object -First 1).IPAddress
$origins = @("http://localhost:$FrontendPort", "http://127.0.0.1:$FrontendPort")
if ($lanIP) { $origins += "http://$lanIP`:$FrontendPort" }
$env:ALLOW_ORIGINS = $origins -join ","

# ───────────────────── 3. 启动后端 + 前端 ─────────────────────
if (-not (Test-Path $PY)) {
    Write-Host "  ✗ 未找到后端虚拟环境：$PY`n    请先在 backend 下创建 .venv 并安装 requirements.txt" -ForegroundColor Red
    exit 1
}

Write-Host "`n[2/5] 启动后端 (uvicorn:$BackendPort) ..." -ForegroundColor Cyan
Start-Process -FilePath $PY -ArgumentList "-m","uvicorn","main:app","--host","0.0.0.0","--port",$BackendPort `
    -WorkingDirectory $BACKEND -RedirectStandardOutput $BKLOG -RedirectStandardError $BKERR | Out-Null

Write-Host "[3/5] 启动前端 (vite:$FrontendPort，含 /api 代理到后端) ..." -ForegroundColor Cyan
Start-Process -FilePath "npm.cmd" -ArgumentList "run","dev","--","--port",$FrontendPort `
    -WorkingDirectory $FRONTEND -RedirectStandardOutput $FNLOG -RedirectStandardError $FNERR | Out-Null

# ───────────────────── 4. 等待就绪 + 冒烟测试 ─────────────────────
Write-Host "`n[4/5] 等待服务就绪 ..." -ForegroundColor Cyan
$okB = Wait-Port $BackendPort 60
$okF = Wait-Port $FrontendPort 60
if (-not ($okB -and $okF)) {
    Write-Host "  ✗ 服务未完全就绪（后端:$okB 前端:$okF）。查看 backend.log / frontend.log" -ForegroundColor Red
    exit 1
}

# 冒烟测试走 /api 代理（与评委实际访问路径一致）
$smoke = "评审端点未通过健康检查"
try {
    $info = Invoke-RestMethod -Uri "http://127.0.0.1:$FrontendPort/api/reviewer/info?token=$ReviewerToken" -TimeoutSec 10
    $nPapers = if ($info.papers) { $info.papers.Count } else { 0 }
    $smoke = "/api/reviewer/info 正常（已索引论文 $nPapers 篇）"
}
catch {
    $smoke = "⚠ 评审端点健康检查失败：$_ （请确认 REVIEWER_TOKEN 已生效、后端无报错）"
}
Write-Host "  ✓ $smoke" -ForegroundColor Green

# ───────────────────── 5. 公网隧道（可选，-Public 时启用） ─────────────────────
$publicURL = $null
if ($Public) {
    Write-Host "`n[5/5] 建立公网隧道（前端 $FrontendPort）..." -ForegroundColor Cyan
    $chosen = $null

    # 优先 cloudflared（免账号 quick tunnel）
    if (($TunnelTool -eq "auto" -or $TunnelTool -eq "cloudflared") -and -not $publicURL) {
        $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
        if ($cf) {
            $chosen = "cloudflared"
            Start-Process -FilePath $cf -ArgumentList "tunnel","--url","http://localhost:$FrontendPort" `
                -RedirectStandardOutput $CFLOG -RedirectStandardError $CFERR -WindowStyle Hidden | Out-Null
            for ($i = 0; $i -lt 20; $i++) {
                Start-Sleep -Seconds 1
                $m = Select-String -Path $CFLOG -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue |
                     Select-Object -First 1
                if ($m) { $publicURL = $m.Matches[0].Value.Trim(); break }
            }
        }
    }

    # 其次 ngrok（本机已配好 authtoken；注意 ngrok 经代理运行需付费，故启动前清空代理变量）
    if (($TunnelTool -eq "auto" -or $TunnelTool -eq "ngrok") -and -not $publicURL) {
        $ng = (Get-Command ngrok -ErrorAction SilentlyContinue).Source
        if (-not $ng) { $ng = Join-Path $ROOT "ngrok.exe" }
        if (Test-Path $ng) {
            $chosen = "ngrok"
            # 默认 5173 用 ngrok.yml 预定义 "web" 隧道（含 skip-browser-warning，评委无拦截面）
            $ngrokArgs = if ($FrontendPort -eq 5173) { "start web" } else { "http $FrontendPort" }
            # 写临时 bat：先清空代理变量再启动 ngrok（规避 ERR_NGROK_9009 代理付费限制）
            $ngrokBat = Join-Path $ROOT "ngrok_launch.bat"
            $batContent = "@echo off`r`nset http_proxy=`r`nset https_proxy=`r`nset HTTP_PROXY=`r`nset HTTPS_PROXY=`r`n`"$ng`" $ngrokArgs`r`n"
            Set-Content -Path $ngrokBat -Value $batContent -Encoding ascii
            Start-Process -FilePath $ngrokBat -WindowStyle Hidden | Out-Null
            # 轮询本地 API（用 cmd/curl 并清空代理，避免被本机代理拦截 127.0.0.1:4040）
            for ($i = 0; $i -lt 15; $i++) {
                Start-Sleep -Seconds 1
                $j = cmd /c "set http_proxy= & set https_proxy= & curl -s --max-time 3 http://127.0.0.1:4040/api/tunnels" 2>$null
                if ($j) {
                    $m = [regex]::Match($j, '"public_url"\s*:\s*"(https://[^"]+)"')
                    if ($m.Success) { $publicURL = $m.Groups[1].Value; break }
                }
            }
        }
    }

    if ($publicURL) {
        Write-Host "  ✓ 隧道已建立（$chosen）`n    公网地址：$publicURL" -ForegroundColor Green
    }
    else {
        Write-Host "  ⚠ 未能建立公网隧道。常见原因：① 本机设置了 http_proxy，ngrok 代理下运行需付费（脚本已尝试清空代理）；② 未配置 authtoken（需 ngrok config add-authtoken）。" -ForegroundColor Yellow
        Write-Host "    回退到局域网模式，评委需连同一 WiFi 访问。" -ForegroundColor Yellow
    }
}

# ───────────────────── 输出访问卡片 ─────────────────────
$localURL = "http://localhost:$FrontendPort"
$lanURL   = if ($lanIP) { "http://$lanIP`:$FrontendPort" } else { "(未检测到局域网 IP)" }
# 评审 API 走 /api 代理（与前端口同源，公网/局域网均可用）
$reviewerAPI = "http://<演示地址>:$FrontendPort/api/reviewer/qa?token=$ReviewerToken"
if ($publicURL) { $reviewerAPI = "$publicURL/api/reviewer/qa?token=$ReviewerToken" }

$demoFlow = @"
  推荐演示流程（评委第 6 条「带评审账号的常驻演示」）：
    1) 上传《Attention Is All You Need》v1 与 v7 两个版本
       → 触发「检测到同源/重复版本」去重提示
    2) 上传一篇引用它的论文（如引用 1706.03762 的后续工作）
       → 引用图谱出现「实体—引用」边（不再是孤立节点）
    3) 问一个论文里没有的数字（如「模型 BLEU 是多少？」且未检索到）
       → 触发「未通过引用校验」→ 程序判定拒答（抗幻觉演示）
    4) 问一个论文里有的数字（如「编码器有几层？」原文有 6 层）
       → 引用校验通过 + 数字回查通过
    5) 打开评审模式：/api/reviewer/qa?token=... 查看拒答明细 / RRF 排名 / 图谱边来源
"@

$card = @"

============================================================
   科研助手 Agent 系统 v2.0 —— 演示已就绪
============================================================
  前端（评委用，所有 API 经 /api 同源代理）：
    本机    : $localURL
    局域网  : $lanURL
$(if ($publicURL) { "    公网    : $publicURL   <- 提交给评委的演示地址" } else { "    公网    : 未启用（加 -Public 可建立公网隧道）" })

  评审账号（只读模式令牌）：
    REVIEWER_TOKEN = $ReviewerToken
    评审接口 : $reviewerAPI

  健康检查：
    $smoke

  评审期间保持可用提醒：
    - 保持本机不休眠 / 不关机；不要运行 -Stop 或关闭进程
    - 公网隧道进程已后台运行，重启电脑或断网会导致地址失效（需重跑本脚本）
    - 停止服务：pwsh deploy_demo.ps1 -Stop

$demoFlow
============================================================
"@

Write-Host $card
$card | Out-File -FilePath $ACCESSFILE -Encoding utf8
Write-Host "（以上访问信息已保存到 reviewer_access.txt，本地文件请勿提交）`n" -ForegroundColor DarkGray

if ($Follow) {
    Write-Host "尾随后端日志（Ctrl+C 退出查看，不影响服务）：" -ForegroundColor DarkGray
    Get-Content $BKLOG -Tail 0 -Wait
}





