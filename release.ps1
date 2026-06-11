# mochi一键发版 跑这个 输版本号和发布说明 后面全自动
$ErrorActionPreference = "Stop"

# gh是便携版不在PATH
$gh = "$env:LOCALAPPDATA\gh-cli\bin\gh.exe"
if (-not (Test-Path $gh)) { Write-Host "✗ 找不到 gh：$gh" -ForegroundColor Red; exit 1 }

# mochi开着会锁dist打包必失败
if (Get-Process Mochi -ErrorAction SilentlyContinue) { Write-Host "✗ Mochi.exe 正在运行 会锁住 dist 先退出它" -ForegroundColor Red; exit 1 }

# 工作区只允许脏着版本号文件 别的改动先自己处理
$dirty = git status --porcelain | Where-Object { $_ -notmatch 'desktop_pet/__init__\.py$' }
if ($dirty) {
    Write-Host "✗ 工作区有版本号之外的改动 先提交或暂存再发版：" -ForegroundColor Red
    $dirty | ForEach-Object { Write-Host "  $_" }
    exit 1
}

# 问版本号 回车默认用代码里现有的
$initPy = "desktop_pet\__init__.py"
$cur = (Select-String -Path $initPy -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$ver = Read-Host "新版本号（当前 $cur 直接回车沿用）"
if (-not $ver) { $ver = $cur }
if ($ver -notmatch '^\d+\.\d+\.\d+$') { Write-Host "✗ 版本号要长这样：0.2.3" -ForegroundColor Red; exit 1 }
$tag = "v$ver"
if (git tag --list $tag) { Write-Host "✗ tag $tag 已存在 换个号" -ForegroundColor Red; exit 1 }

# 写回代码里的版本号
if ($ver -ne $cur) {
    $content = [IO.File]::ReadAllText("$PWD\$initPy", [Text.Encoding]::UTF8)
    $content = $content -replace '__version__\s*=\s*"[^"]+"', "__version__ = `"$ver`""
    [IO.File]::WriteAllText("$PWD\$initPy", $content, (New-Object Text.UTF8Encoding $false))
    Write-Host "✓ __version__ 已改为 $ver" -ForegroundColor Green
}

# 问发布说明 可多行 空行结束 一行不写就用commit列表
Write-Host "发布说明（可多行 空行结束 直接回车=自动用上个tag以来的commit列表）" -ForegroundColor Cyan
$noteLines = @()
while ($true) {
    $line = Read-Host
    if ($line -eq "") { break }
    $noteLines += $line
}

Write-Host ""
Write-Host "开始发版 $tag ..." -ForegroundColor Cyan

# 提交版本号
if (git status --porcelain $initPy) {
    git add $initPy
    git commit -m $ver
    Write-Host "✓ 已提交版本号 $ver" -ForegroundColor Green
}

# 打包
& .\build.ps1
if (-not (Test-Path "dist\MochiSetup.exe")) { Write-Host "✗ 没产出 dist\MochiSetup.exe 发版中止" -ForegroundColor Red; exit 1 }
# 防止拿旧产物发新版
if ((Get-Item "dist\MochiSetup.exe").LastWriteTime -lt (Get-Date).AddMinutes(-30)) {
    Write-Host "✗ MochiSetup.exe 是30分钟前的旧文件 像是打包没真跑成 发版中止" -ForegroundColor Red; exit 1
}

# 推送加tag
git push
git tag $tag
git push origin $tag

# 发布说明 没手写就从上个tag以来的commit生成
if ($noteLines.Count -gt 0) {
    $notes = $noteLines -join "`n"
} else {
    $prev = git tag --list 'v*' --sort=-v:refname | Where-Object { $_ -ne $tag } | Select-Object -First 1
    if ($prev) {
        $range = "$prev..$tag"
        $header = "## 更新内容（$prev → $tag）"
    } else {
        $range = $tag
        $header = "## 更新内容"
    }
    $lines = git log $range --format='- %s' --no-merges | Where-Object { $_ -notmatch '^- \d+\.\d+\.\d+$' }
    $notes = "$header`n`n" + ($lines -join "`n")
}

& $gh release create $tag dist\MochiSetup.exe --title "Mochi $tag" --notes $notes
if ($LASTEXITCODE -ne 0) { Write-Host "✗ release 创建失败 tag已推上去 可手动重试：& `"$gh`" release create $tag dist\MochiSetup.exe" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "✓ 发版完成 → https://github.com/dulaiduwang003/MOCHI/releases/tag/$tag" -ForegroundColor Green
