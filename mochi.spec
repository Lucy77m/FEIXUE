# -*- mode: python ; coding: utf-8 -*-
# Mochi · PyInstaller 打包配置
#   构建： uv run pyinstaller mochi.spec --noconfirm    （或 .\build.ps1）
#   产物： dist\Mochi\Mochi.exe   —— 整个 dist\Mochi\ 目录一起分发
#   形态： onedir（目录版，启动快；OCR 模型较大，不宜单文件）+ 无控制台窗口
#
# 这是一个合理的起点，不保证一次成功——重依赖应用首次打包常要按运行时报错补
# datas / hiddenimports（详见 docs/打包说明.md）。

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

datas = []
binaries = []
hiddenimports = []

# RapidOCR：识别/检测模型 + 配置（不收集 → 运行时 OCR 找不到模型而崩，这是最常见的坑）
datas += collect_data_files("rapidocr_onnxruntime")
hiddenimports += collect_submodules("rapidocr_onnxruntime")
# onnxruntime 的原生 DLL
binaries += collect_dynamic_libs("onnxruntime")
# uiautomation 的加速 DLL 在 uiautomation/bin/ 子目录（看屏幕点控件的 C++ 加速；漏了会退回更慢的 comtypes）
# —— glob 必须带 bin/，写成 "*.dll" 只匹配包根、收不到子目录
binaries += collect_dynamic_libs("uiautomation")
datas += collect_data_files("uiautomation", includes=["bin/*.dll"])
# trafilatura 自带配置文件
datas += collect_data_files("trafilatura")

# 易被漏掉的隐藏依赖：pywin32 时区、uiautomation 依赖的 comtypes
hiddenimports += ["win32timezone", "comtypes", "comtypes.client", "comtypes.stream"]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Mochi",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI：不弹控制台黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 暂无 .ico；要 exe 图标就把 .ico 路径填这里
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Mochi",
)
