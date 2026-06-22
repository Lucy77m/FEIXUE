
# ★ 绯雪 (FEIXUE)

**住在你 Windows 桌面上的 AI 伴侣 —— 有情绪、有记忆、能帮你操控电脑的本地小家伙**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![UI](https://img.shields.io/badge/UI-PySide6%20·%20Qt-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blueviolet)

**简体中文** · [English](README.en.md) · [日本語](README.ja.md)

🔗 [github.com/Lucy77m/FEIXUE](https://github.com/Lucy77m/FEIXUE)

---

## 它是什么

绯雪是两样东西合为一体：

- 🐾 **桌宠** —— 纯代码绘制的角色（没有贴图素材），会眨眼、跟着鼠标看、发呆哼歌、下雨撑伞、机器发烫扇风、垃圾多了抓虫。你不理它它自己找乐子，你离开它打瞌睡，偶尔主动找你说句话。
- 🧠 **本地 AI Agent** —— 接你自己的大模型（任意 OpenAI 兼容接口），能看屏幕、动鼠标键盘、跑命令、写代码、读写文件、上网搜索。支持定时盯屏、后台长任务、并行子代理、提醒闹钟——把"对话"变成"让它替你动手"。

它有持久的**情绪和亲密度**，会随相处慢慢长出**自我画像**。是"同一只"，不是每次重置的聊天框。

> 活在你电脑里，有身体也有能力。

---

## 功能一览

### 🧠 能干活

| 能力 | 说明 |
|------|------|
| 命令与代码 | PowerShell / Python 持久环境，支持后台长任务 |
| 文件操作 | 读写编辑、PDF/图片识别、正则搜代码、按名找文件 |
| 屏幕感知 | 截图、OCR 认字、无障碍树精准点击、鼠标键盘控制 |
| 联网 | 搜索引擎、网页抓取、HTTP 请求、装 pip 包 |
| 长期记忆 | 经验/偏好/环境记忆 + 知识库 RAG + 情景日志，自动反思沉淀 |
| 编排扩展 | MCP 连接器、子代理并行扇出/流水线、后台任务管理 |
| 安全护栏 | 不可逆操作前弹确认面板，灾难命令硬拦截 |

### 🐾 有温度

| 体验 | 说明 |
|------|------|
| 情绪系统 | 心情随互动变化，越熟越放得开；夸它开心、骂它低落 |
| 人格演化 | 每轮反思缓慢重写"自我画像"，是你养出来的"它" |
| 机器拟态 | CPU 热了扇风、内存满被压扁、低电量提醒、深夜盖被、冬天蹭暖 |
| 天气拟态 | 下雨撑伞、落雪缩团、酷暑融化 |
| 屏幕感知 | OCR 快照 + 关键词规则——看到测试全绿庆祝、看到报错皱眉、深夜写代码关心你 |
| 仪式感 | 每天心情预报、纪念日蛋糕、退出道晚安、番茄钟专注 |
| 投喂互动 | 拖文件给它：垃圾进回收站、文档进知识库、图片看一眼 |
| 脚印与玩耍 | 心情好走过留脚印（节日变花瓣/雪花）、丢球接球、挠它咯咯笑、摔它记仇 |

### ⌨️ 顺手

- **全局热键**：`Ctrl+Alt+S` 唤出输入框，`Ctrl+Alt+A` 问选中文字，`Ctrl+Shift+Q` 选中文字一键改写
- **控制面板**：接口配置、能力开关、主动频率、多语言（中/英/日）

---

## 快速开始

```bash
git clone https://github.com/Lucy77m/FEIXUE.git
cd FEIXUE
uv sync
python main.py
```

首次启动会打开控制面板，在「接口」页填入你的 API Key 和模型名即可。

详细安装、打包、排错指南 → [GUIDE.md](GUIDE.md)

---

## 技术栈

Python 3.11+ · PySide6 (Qt) · OpenAI 兼容 API · sherpa-onnx (本地语音) · RapidOCR · SQLite + 向量嵌入 · MCP 协议 · Win32 API (UIA / SendInput / 注册表)

---

## 许可

[MIT](LICENSE)
