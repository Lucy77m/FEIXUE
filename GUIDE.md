<div align="center">

# Mochi · 使用与部署指南

[← 返回主 README](README.md)

**简体中文** · [English](GUIDE.en.md) · [日本語](GUIDE.ja.md)

</div>

---

## 1. 安装与运行

**环境**：Windows 10 / 11 · Python ≥ 3.11 · [uv](https://github.com/astral-sh/uv)

```powershell
# 安装依赖
uv sync

# 运行
uv run python main.py
```

首次启动会弹出控制面板，填入你的大模型配置即可：

- **API Key** / **接口地址（base_url）** —— 任何 **OpenAI 兼容**服务（通义千问 / DeepSeek / OpenAI / 本地 vLLM、Ollama……）
- **对话模型** —— 主回合用的 chat 模型
- **嵌入模型** —— 用于知识库与记忆的语义检索（没有嵌入端点会自动降级成子串检索，可不填）
- **回复语言 / 能力开关 / 主动频率 / 发散度与最大长度 / 是否展示思维链** —— 均在面板内调整，每回合实时生效

配置好后，Mochi 会从屏幕角落"入场"。点它（或按 `Ctrl + Alt + S`）打字聊天；托盘图标可随时重开面板。

> 配置只存在本地 `data/settings.json`，不上传任何地方。数据目录可用环境变量 `STAR_DATA_DIR` 覆盖。

---

## 2. 打包分发（Windows · PyInstaller）

把 Mochi 打成一个不依赖 Python 环境、双击即用的 Windows 程序。

### 2.1 一键打包

```powershell
.\build.ps1
```

等价于手动：

```powershell
uv sync                                   # 装依赖（含 dev 组的 pyinstaller）
uv run pyinstaller mochi.spec --noconfirm
```

产物：**`dist\Mochi\Mochi.exe`** —— 分发时把**整个 `dist\Mochi\` 目录**一起拷给别人（exe 旁边那一堆是它的依赖）。

### 2.2 关键设计

| 点 | 选择 | 原因 |
| --- | --- | --- |
| 形态 | **onedir**（目录版） | 启动快；RapidOCR 模型较大，单文件每次解压会很慢 |
| 控制台 | **无**（`console=False`） | 双击不弹黑框 |
| 数据目录 | **`%APPDATA%\Mochi`** | 打包后 exe 旁是只读 / 无写权限的；配置、记忆、日志都写这里 |

开发期（`uv run python main.py`）仍用项目内 `data\`，打包版用 `%APPDATA%\Mochi`，两者都可被 `STAR_DATA_DIR` 覆盖。

### 2.3 内置独立 Python（让 run_python 可用）

打包后 `sys.executable` 是 `Mochi.exe` 而非 Python，直接拿它跑 `run_python` 会起 Mochi 自己。所以 `build.ps1` 额外下载**官方 embeddable Python + pip**，放到 `dist\Mochi\pyruntime\`；`run_python` / `install_package` 在打包版（仅 `frozen` 时）自动改用它，开发期不受影响。

- pyruntime 是**干净的**（只有标准库 + pip）。要用第三方库（requests / numpy 等）得先 `install_package` 现装到 pyruntime —— 开发版预装好，打包版按需装，属正常差异。
- `build.ps1` 末尾会打印 `pip OK / 缺失`。缺失就重跑 `build.ps1`，或手动补：把 embeddable Python 解压到 `dist\Mochi\pyruntime\`、改 `._pth` 启用 `import site`、跑一次 `get-pip.py`。

### 2.4 首次打包常见调整（重依赖应用通病）

打完先**双击跑一遍、把每个功能点一下**，按报错补 `mochi.spec`：

- **OCR 一用就崩 / 找不到模型** → RapidOCR 模型没收全；spec 已 `collect_data_files("rapidocr_onnxruntime")`，若仍缺按报错路径用 `datas` 补 `.onnx`。
- **`ModuleNotFoundError`** → 把模块名加进 spec 的 `hiddenimports`。
- **窗口起不来 / Qt 插件缺失** → spec 顶部 `collect_all("PySide6")` 兜底，或命令行 `--collect-all PySide6`。
- **`uiautomation` / `comtypes` 报错**（看屏幕 / 点控件）→ spec 已带 `comtypes*`，若仍报加 `--collect-all comtypes`。
- 加图标：把 `.ico` 路径填进 `mochi.spec` 的 `icon=`。
- 杀毒软件可能误报 PyInstaller 打的 exe（通病，加信任即可）；`build\`、`dist\` 已在 `.gitignore`。

---

## 3. 测试与排错

无自动化 UI 测试，靠一份**人工走查清单**逐项验证（操作 → 预期）。跑之前确保 Mochi 已启动、控制面板已配好 API。三个观察渠道：

1. 宠物身边的**气泡 / 黑板 / 拍立得 / 确认面板**；
2. **控制面板**（接口 / 对话 / 权限 / 关于四页）；
3. **审计日志** `data/logs/audit-YYYYMMDD.jsonl`（用 `Get-Content` 看最新几行）。

走查覆盖面：基础对话与表情、命令动作（perform / 小品）、空闲行为、打断、主动消息、记忆与情景日志、全局热键（含顺手改写）、剪贴板与窗口、控制面板、提醒与定时（含重复 / 系统通知）、朗读音色与逐句同步、定时看屏、任务清单浮窗、子代理编排、远程触发、思考动画、黑板与图片、反思门控。

**常见排错**：

- **回复语言不对** → 控制面板「对话」页的"回复语言"框（清空 = 跟随你说的语言）。
- **某些能力"做不到"** → 「权限」页关了对应能力组（联网 / 操控 / 命令），工具被从模型工具表里隐藏，属预期。
- **主动消息不出现** → 它克制：要在场 + 不忙 + rapport 达标 + 冷却已过；想快验证把主动频率调"话痨"，但仍非秒触发。
- **启动提示"热键没抢到"** → `Ctrl+Alt+S` 被别的软件占用，点宠物仍可聊。
- **纯闲聊后不应有反思模型调用**（短闲聊跳过反思）；用到工具的实质任务才反思并可能更新记忆 / 日志 / 自我画像。

---

## 4. 能力与安全

Mochi **能在你的机器上执行任意命令和代码、操控鼠标键盘、读写文件** —— 这是它强大的根源，也意味着风险：

- 它本质上拥有**和你本人同等的电脑操作权限**。
- 控制面板里可**按组关闭**能力（联网 / 操控 / 命令执行），给不放心的场景降权。
- **不可逆 / 高风险操作走 `confirm` 面板**，弹"执行 / 不执行"等你点头才动手。
- **安全护栏**（`executor/safety.py`）只硬拦**极小、高精度的灾难性不可逆**操作（格式化磁盘、`diskpart` / `remove-partition`、`reg delete HKLM /f`、对裸驱动根 / 系统目录的递归强删等），刻意不做沙箱、不拦普通删文件 —— 它是个"全权"伙伴，不是被关进笼子的助手。
- **远程触发默认关**：文件收件箱（`remote.py`）默认关闭，且**只读本地文件、不监听任何网络端口**；开启后丢进 `inbox/` 的 `task` 会以完整权限后台执行，所以只在你信任的设备 / 网盘上开。
- API Key 等配置、记忆 / 知识库 / 日志全部**本地存储**；"清空记忆"按钮可一键抹掉（含自我画像，回到出厂底色）。

---

## 5. 本地数据

全部在 `data/`（开发期项目内，打包后移到 `%APPDATA%\Mochi`；可用 `STAR_DATA_DIR` 覆盖）：

| 文件 | 内容 |
| --- | --- |
| `settings.json` | 接口 / 模型 / 语言 / 能力开关 / 主动频率 / 朗读音色与语速 / 远程触发开关 |
| `emotion.json` | valence / arousal / rapport + 时间戳 |
| `persona.json` | 自我画像（人格演化层） |
| `proactive.json` | 主动消息的冷却 / 计数状态 |
| `reminders.json` | 待触发的提醒 / 定时任务（含重复规则） |
| `journal.json` | 情景日志（最近若干条） |
| `memory/memory.db` | 长期记忆（SQLite） |
| `docs.db` | 知识库 chunk + 嵌入 |
| `skills/` | 自建技能代码 + 注册表 |
| `inbox/` | 远程触发收件箱（默认关；处理后归档到 `inbox/done/`） |
| `logs/audit-*.jsonl` · `logs/crash.log` | 审计日志（按天）+ 崩溃栈转储 |
| `mcp.json` | MCP 连接器配置（可选） |
