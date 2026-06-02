# Mochi 一键打包（Windows）。产物：dist\Mochi\Mochi.exe
# 用法： .\build.ps1
$ErrorActionPreference = "Stop"

Write-Host "[1/3] 确保依赖（含 pyinstaller）..." -ForegroundColor Cyan
uv sync

Write-Host "[2/3] 清理旧产物..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

Write-Host "[3/3] 打包中（PyInstaller，首次较慢）..." -ForegroundColor Cyan
uv run pyinstaller mochi.spec --noconfirm
$built = ($LASTEXITCODE -eq 0)

if ($built) {
    Write-Host "[4/4] 为 run_python 配独立 Python(embeddable + pip)..." -ForegroundColor Cyan
    $pyVer = "3.11.9"
    $rt = "dist\Mochi\pyruntime"
    $zip = Join-Path $env:TEMP "mochi-py-embed.zip"
    Invoke-WebRequest "https://www.python.org/ftp/python/$pyVer/python-$pyVer-embed-amd64.zip" -OutFile $zip
    Expand-Archive $zip -DestinationPath $rt -Force
    # embeddable 默认禁用 site-packages，pip 装的库才 import 得到——打开它
    $pth = Get-ChildItem "$rt\python*._pth" | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '#\s*import site', 'import site' | Set-Content $pth.FullName
    Add-Content $pth.FullName "Lib\site-packages"
    # 引导 pip
    $getpip = Join-Path $env:TEMP "get-pip.py"
    Invoke-WebRequest "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
    & "$rt\python.exe" $getpip --no-warn-script-location 2>&1 | Out-Null
    $pipOk = (Test-Path "$rt\Scripts\pip.exe") -or (Test-Path "$rt\Lib\site-packages\pip")
    Write-Host ("  pyruntime: python " + $(if (Test-Path "$rt\python.exe") {'OK'} else {'缺失!'}) + " / pip " + $(if ($pipOk) {'OK'} else {'缺失!'})) -ForegroundColor $(if ($pipOk) {'Green'} else {'Yellow'})
}

if ($built -and (Test-Path "dist\Mochi\Mochi.exe")) {
    Write-Host "`n✓ 完成 → dist\Mochi\Mochi.exe（整个 dist\Mochi\ 目录一起分发）" -ForegroundColor Green
} else {
    Write-Host "`n✗ 打包失败。最常见原因：正在运行的 Mochi.exe 锁住了 dist\ —— 先彻底关掉它再打。其余按 docs\打包说明.md 补 datas/hiddenimports" -ForegroundColor Red
}
