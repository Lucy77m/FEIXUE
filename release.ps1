# mochi一键发版 改好__init__.py版本号后跑这个 打包+推送+tag+github release
$ErrorActionPreference = "Stop"

# gh是便携版不在PATH
$gh = "$env:LOCALAPPDATA\gh-cli\bin\gh.exe"
if (-not (Test-Path $gh)) { Write-Host "✗ 找不到 gh：$gh" -ForegroundColor Red; exit 1 }

# 版本号从__init__.py读
$ver = (Select-String -Path "desktop_pet\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if (-not $ver) { Write-Host "✗ 读不到 __version__" -ForegroundColor Red; exit 1 }
$tag = "v$ver"
Write-Host "发版：$tag" -ForegroundColor Cyan

# tag重复说明忘了改版本号
if (git tag --list $tag) { Write-Host "✗ tag $tag 已存在 先改 __init__.py 里的版本号" -ForegroundColor Red; exit 1 }

# mochi开着会锁dist打包必失败
if (Get-Process Mochi -ErrorAction SilentlyContinue) { Write-Host "✗ Mochi.exe 正在运行 会锁住 dist 先退出它" -ForegroundColor Red; exit 1 }

# 工作区只脏着版本号就顺手提交 脏着别的先自己处理
$dirty = git status --porcelain
if ($dirty) {
    $onlyVer = -not ($dirty | Where-Object { $_ -notmatch 'desktop_pet/__init__\.py$' })
    if ($onlyVer) {
        git add desktop_pet/__init__.py
        git commit -m $ver
        Write-Host "✓ 已提交版本号 $ver" -ForegroundColor Green
    } else {
        Write-Host "✗ 工作区有版本号之外的改动 先提交或暂存再发版：" -ForegroundColor Red
        $dirty | ForEach-Object { Write-Host "  $_" }
        exit 1
    }
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

# 发布说明从上个tag以来的commit生成
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

& $gh release create $tag dist\MochiSetup.exe --title "Mochi $tag" --notes $notes
if ($LASTEXITCODE -ne 0) { Write-Host "✗ release 创建失败 tag已推上去 可手动重试：& `"$gh`" release create $tag dist\MochiSetup.exe" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "✓ 发版完成 → https://github.com/dulaiduwang003/MOCHI/releases/tag/$tag" -ForegroundColor Green
