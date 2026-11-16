# pack.ps1 —— 生成比赛提交用 ZIP
#
# 显式排除：真实密钥 .env、虚拟环境 .venv、node_modules、各类缓存、用户上传的论文、
#           向量库、构建产物、遗留 _old 文件、ngrok.exe。
# 打包完成后会重新读回 ZIP 条目做一次“泄漏检查”，一旦发现 .env / .venv 等立即报错退出。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File .\pack.ps1
#   powershell -ExecutionPolicy Bypass -File .\pack.ps1 -Output D:\llm_competition.zip
#   powershell -ExecutionPolicy Bypass -File .\pack.ps1 -IncludeNotes   # 附带评委反馈文档

param(
    [string]$Output = "",
    [switch]$IncludeNotes
)

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
if (-not $Output) { $Output = Join-Path $root "llm_competition.zip" }

# 目录级排除（按路径段精确匹配，不误伤同名文件）
$excludeDirNames = @(
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".cache", "chroma_db", "papers", "dist", ".vscode"
)

# 文件级排除（-like 通配）
# 技术文档（docx/pdf）走大赛官网单独提交，不进代码包：否则包体里多出一份
# 与仓库不同步的文档副本，评委也分不清哪份是准的。
$excludeFilePatterns = @(".env", "*.old", "*.pyc", "*.log", "ngrok.exe", "*.zip",
                         "科研助手Agent应用系统*技术文档*")

# 额外的单个文件（默认不进包）
$alwaysExcludeFileNames = @("reviewer_access.txt", "ngrok_launch.bat")   # 含真实令牌 / 与提交无关
$excludeFileNames = @("修改建议_评委反馈.md")
if ($IncludeNotes) { $excludeFileNames = @() }

$stage = Join-Path ([IO.Path]::GetTempPath()) ("llmpack_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage -Force | Out-Null

$kept = New-Object System.Collections.Generic.List[string]
$skipped = New-Object System.Collections.Generic.List[string]

try {
    $all = Get-ChildItem -LiteralPath $root -Recurse -File -Force

    foreach ($f in $all) {
        $rel = $f.FullName.Substring($root.Length).TrimStart('\')
        $segs = $rel -split '\\'

        # 判断所在目录是否命中排除名单
        $inExcludedDir = $false
        if ($segs.Count -gt 1) {
            foreach ($s in $segs[0..($segs.Count - 2)]) {
                if ($excludeDirNames -contains $s) { $inExcludedDir = $true; break }
            }
        }

        # 判断文件名是否命中排除名单
        $isExcludedFile = ($excludeFileNames -contains $f.Name) -or ($alwaysExcludeFileNames -contains $f.Name)
        if (-not $isExcludedFile) {
            foreach ($pat in $excludeFilePatterns) {
                if ($f.Name -like $pat) { $isExcludedFile = $true; break }
            }
        }

        if ($inExcludedDir -or $isExcludedFile) {
            $skipped.Add($rel) | Out-Null
            continue
        }

        $dest = Join-Path $stage $rel
        $destDir = Split-Path -Path $dest -Parent
        if (-not (Test-Path -LiteralPath $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $f.FullName -Destination $dest -Force
        $kept.Add($rel) | Out-Null
    }

    if ($kept.Count -eq 0) { throw "没有可打包的文件，请检查 -Output 与脚本所在目录。" }

    if (Test-Path -LiteralPath $Output) { Remove-Item -LiteralPath $Output -Force }
    $outDir = Split-Path -Path $Output -Parent
    if ($outDir -and -not (Test-Path -LiteralPath $outDir)) {
        New-Item -ItemType Directory -Path $outDir -Force | Out-Null
    }
    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $Output -CompressionLevel Optimal

    # ---- 泄漏检查：重新打开 ZIP，按条目名找敏感文件 ----
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($Output)
    try {
        $bad = @()
        foreach ($e in $zip.Entries) {
            $name = ($e.FullName -split '/')[-1]
            $full = $e.FullName
            if ($name -eq ".env" -or $name -eq "ngrok.exe" -or $name -like "*.old") { $bad += $full }
            if ($name -eq "reviewer_access.txt" -or $name -like "*.log" -or $name -eq "ngrok_launch.bat") { $bad += $full }
            if ($full -match "(^|/)(\.venv|node_modules|\.git|\.cache|chroma_db)/") { $bad += $full }
        }
        $entryCount = $zip.Entries.Count
        $zipSize = (Get-Item -LiteralPath $Output).Length
    } finally {
        $zip.Dispose()
    }

    if ($bad.Count -gt 0) {
        Remove-Item -LiteralPath $Output -Force -ErrorAction SilentlyContinue
        throw ("泄漏检查未通过，已删除产物。以下文件不应进包：`n" + ($bad -join "`n"))
    }

    Write-Host "打包完成"
    Write-Host ("  ZIP     : " + $Output)
    Write-Host ("  大小    : " + [math]::Round($zipSize / 1KB, 1) + " KB")
    Write-Host ("  条目数  : " + $entryCount)
    Write-Host ("  已排除  : " + $skipped.Count + " 个文件（.env/.venv/node_modules/.cache/chroma_db/papers/dist/_old 等）")
    Write-Host "  泄漏检查: 通过（不含 .env、reviewer_access.txt、.venv、node_modules、日志、_old）"
}
finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}
