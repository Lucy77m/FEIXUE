# -*- mode: python ; coding: utf-8 -*-
# pyinstaller打包配置 构建走build.ps1

import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

datas = []
binaries = []
hiddenimports = []

# 桌宠 sprite、表演图集和桌边工坊场景
_assets = os.path.join("desktop_pet", "assets")
if os.path.isdir(_assets):
    datas += [(_assets, os.path.join("desktop_pet", "assets"))]

# rapidocr模型和配置
datas += collect_data_files("rapidocr_onnxruntime")
hiddenimports += collect_submodules("rapidocr_onnxruntime")
# onnxruntime原生dll
binaries += collect_dynamic_libs("onnxruntime")
# uiautomation加速dll在bin子目录
binaries += collect_dynamic_libs("uiautomation")
datas += collect_data_files("uiautomation", includes=["bin/*.dll"])
# trafilatura配置文件
datas += collect_data_files("trafilatura")
# justext的stoplists数据
datas += collect_data_files("justext")
hiddenimports += collect_submodules("justext")
# certifi证书
datas += collect_data_files("certifi")
# 听觉链 sherpa-onnx原生库 sounddevice带的portaudio
binaries += collect_dynamic_libs("sherpa_onnx")
datas += collect_data_files("sherpa_onnx")
datas += collect_data_files("sounddevice")
hiddenimports += ["sherpa_onnx", "sounddevice"]
# edge-tts is imported lazily only when speech starts, so Analysis cannot discover it.
hiddenimports += collect_submodules("edge_tts")
datas += collect_data_files("edge_tts")

# 易漏的隐藏依赖
hiddenimports += ["win32timezone", "comtypes", "comtypes.client", "comtypes.stream"]

# ui检测模型 放eyes/models下就打进包 没有就跳过
_ui_model = os.path.join("desktop_pet", "eyes", "models", "ui_detect.onnx")
if os.path.exists(_ui_model):
    datas += [(_ui_model, os.path.join("desktop_pet", "eyes", "models"))]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],  # 没用tk 不带整套tcl数据
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FEIXUE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # 不弹控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="feixue.ico",  # 图标由build.ps1生成
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FEIXUE",
)
