# 绯雪一键打包 产出目录版和安装程序
$ErrorActionPreference = "Stop"

# 版本号从__init__.py读
$ver = (Select-String -Path "desktop_pet\__init__.py" -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
if (-not $ver) { Write-Host "✗ 读不到 __version__（desktop_pet\__init__.py）" -ForegroundColor Red; exit 1 }
Write-Host "打包版本：v$ver" -ForegroundColor Cyan

Write-Host "[1/6] 确保依赖（含 pyinstaller）..." -ForegroundColor Cyan
uv sync

Write-Host "[2/6] 清理旧产物..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item build -Recurse -Force }
if (Test-Path dist) { Remove-Item dist -Recurse -Force }

Write-Host "[3/6] 生成应用图标 feixue.ico（FEIXUE 自己的脸）..." -ForegroundColor Cyan
$env:QT_QPA_PLATFORM = "offscreen"
uv run python -c "from PySide6.QtWidgets import QApplication; QApplication([]); from desktop_pet.pet.icon import save_ico; save_ico('feixue.ico')"
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue  # 别把offscreen泄漏给后续命令

Write-Host "[4/6] 打包中（PyInstaller，首次较慢）..." -ForegroundColor Cyan
uv run pyinstaller feixue.spec --noconfirm
$built = ($LASTEXITCODE -eq 0)

if ($built) {
    Write-Host "[5/6] 为 run_python 配独立 Python(embeddable + pip)..." -ForegroundColor Cyan
    $pyVer = "3.11.9"
    $rt = "dist\FEIXUE\pyruntime"
    $zip = Join-Path $env:TEMP "feixue-py-embed.zip"
    curl.exe -L --ssl-no-revoke -o $zip "https://www.python.org/ftp/python/$pyVer/python-$pyVer-embed-amd64.zip"
    Expand-Archive $zip -DestinationPath $rt -Force
    # 打开site-packages
    $pth = Get-ChildItem "$rt\python*._pth" | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '#\s*import site', 'import site' | Set-Content $pth.FullName
    Add-Content $pth.FullName "Lib\site-packages"
    # 引导pip
    $getpip = Join-Path $env:TEMP "get-pip.py"
    curl.exe -L --ssl-no-revoke -o $getpip "https://bootstrap.pypa.io/get-pip.py"
    & "$rt\python.exe" $getpip --no-warn-script-location 2>&1 | Out-Null
    $pipOk = (Test-Path "$rt\Scripts\pip.exe") -or (Test-Path "$rt\Lib\site-packages\pip")
    Write-Host ("  pyruntime: python " + $(if (Test-Path "$rt\python.exe") {'OK'} else {'缺失!'}) + " / pip " + $(if ($pipOk) {'OK'} else {'缺失!'})) -ForegroundColor $(if ($pipOk) {'Green'} else {'Yellow'})
}

$setupMade = $false
if ($built -and (Test-Path "dist\FEIXUE\FEIXUE.exe")) {
    # 找ISCC.exe
    $iscc = $null
    foreach ($p in @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe")) {
        if (Test-Path $p) { $iscc = $p; break }
    }
    if (-not $iscc) {
        $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }
    if ($iscc) {
        Write-Host "[6/6] 制作安装程序（Inno Setup）..." -ForegroundColor Cyan
        & $iscc /Q "/DMyAppVersion=$ver" installer.iss
        $setupMade = (Test-Path "dist\FEIXUESetup.exe")
    } else {
        Write-Host "[6/6] 跳过安装程序：未检测到 Inno Setup。" -ForegroundColor Yellow
        Write-Host "      想要 setup 安装包，装一次再重跑本脚本：  winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
    }
}

Write-Host ""
if ($built -and (Test-Path "dist\FEIXUE\FEIXUE.exe")) {
    Write-Host "✓ 目录版    → dist\FEIXUE\FEIXUE.exe（整个 dist\FEIXUE\ 目录一起分发）" -ForegroundColor Green
    if ($setupMade) {
        Write-Host "✓ 安装程序  → dist\FEIXUESetup.exe（单文件，发这个给别人双击安装）" -ForegroundColor Green
    }
} else {
    Write-Host "✗ 打包失败。最常见原因：正在运行的 FEIXUE.exe 锁住了 dist\ —— 先彻底关掉它再打。其余按 docs\打包说明.md 补 datas/hiddenimports" -ForegroundColor Red
}
