; ============================================================================
;  墨池 Mochi —— Windows 安装程序脚本 (Inno Setup 6)
;  作用：把 PyInstaller 产物 dist\Mochi\ 打成一个专业的安装包 dist\MochiSetup.exe
;        (双击安装、装进用户目录免 UAC、开始菜单/桌面快捷方式、可选开机自启、可卸载)
;
;  前提：先跑 build.ps1 生成 dist\Mochi\(含 Mochi.exe 与 pyruntime\)
;  手动编译：iscc installer.iss   →   产出 dist\MochiSetup.exe
;  (build.ps1 末尾会在检测到 Inno Setup 时自动调用本脚本)
;
;  没装 Inno Setup？一行装上：  winget install JRSoftware.InnoSetup
; ============================================================================

#define MyAppName "墨池 Mochi"
; 版本号真源是 desktop_pet\__init__.py 的 __version__；build.ps1 打包时用 /DMyAppVersion 传进来。
; 下面这行只是手动 iscc 编译时的兜底默认值。
#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "bdth"
#define MyAppExeName "Mochi.exe"

[Setup]
; AppId 是这个软件的唯一身份(升级/卸载靠它识别)——固定不要改
AppId={{8F3A1C5E-9B2D-4E7A-A1F6-2C9D4B8E7A30}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; 默认装到用户目录(localappdata\Programs\Mochi)，不需要管理员、不弹 UAC
DefaultDirName={autopf}\Mochi
DefaultGroupName=Mochi
DisableDirPage=no
DisableProgramGroupPage=yes
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=MochiSetup
SetupIconFile=mochi.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64

[Languages]
; 默认英文向导(一定能编译)。想要简体中文向导：把 ChineseSimplified.isl 放进
; Inno Setup 的 Languages\ 目录，再取消下面那行注释即可。
Name: "en"; MessagesFile: "compiler:Default.isl"
; Name: "chs"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "Start Mochi automatically when I sign in (开机自启)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; 整个 PyInstaller 目录(含 pyruntime\、RapidOCR 模型等)一起装进去
Source: "dist\Mochi\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

; 卸载时只删程序本身；用户数据(API Key/记忆/日志)在 %APPDATA%\Mochi，刻意保留——
; 重装能接着用。要彻底清掉就手动删 %APPDATA%\Mochi。
