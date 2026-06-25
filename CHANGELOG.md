# Changelog

## 0.4.0 - 2026-06-26

### 中文

- 记忆天气系统：根据情绪/环境信号合成天气状态（rain/fog/stars/warm/static/gentle），在宠物附近画轻量粒子效果
- 天气行为联动：天气变化时宠物自动做出对应反应（叹气/发呆/观星/挥手），空闲时持续响应天气氛围
- 天气呼吸态：记忆天气影响宠物身体动画（下沉/仰头/摇晃/深呼吸），表演时自动压制
- 粒子渐变过渡：天气切换时旧粒子自然淡出、新粒子同步淡入，不再瞬间替换
- 小屋视觉扩展：书架新增信物(keepsake)、梦境碎片(dream)、里程碑纪念品(memento)三种物件
- 梦境丰富化：12 种梦境意象（月牙/灯笼/纸船/镜子/雨滴等），每个梦有独特颜色和形状
- 梦境聚集成群：所有梦境在书架上连续排列，形成视觉群落
- 梦境/纪念品回访：点击梦境碎片或纪念品，宠物朗读完整内容
- 项目感知：跟踪前台窗口识别当前项目，注入 LLM 上下文和 journal
- 书架扩容：15 格 → 20 格（4 行 × 5 列），溢出物件自动回捞
- 工坊氛围增强：窗户叠加天气微缩视觉 + 全屏色温变化
- 全部 i18n：新增 25 个三语 key（中/英/日）

### English

- Memory Weather: synthesizes weather states from emotion/environment signals, renders ambient particles
- Weather behavior: pet reacts to weather changes (sigh/stargaze/ponder), continuously responds during idle
- Weather breathing: memory weather affects pet body animation (sink/tilt/sway), suppressed during performances
- Particle cross-fade: smooth transitions between weather states, old particles fade out naturally
- Workshop expansion: new shelf objects — keepsakes, dream fragments, milestone mementos
- Dream enrichment: 12 dream motifs (moon/lantern/boat/mirror/rain etc.), unique colors and glyphs per dream
- Dream clustering: dreams group together on the shelf, forming a visual constellation
- Dream/memento revisit: click a dream or memento to hear the full content read aloud
- Project awareness: tracks foreground window to identify current project, feeds LLM context and journal
- Bookshelf expansion: 15 → 20 slots (4 rows × 5 columns), archived objects auto-resurface
- Workshop ambiance: window weather overlay + full-scene color tint
- Full i18n: 25 new keys across zh/en/ja

## 0.3.0 - 2026-06-23

### 中文

- 完成 FEIXUE / 绯雪品牌重塑与 Windows 打包链整理。
- 默认启用小绯雪 sprite，并加入专属表演、自然动作与大小缩放。
- 新增桌边工坊、实体书架、世界物件持久化和低频旧书回访。
- 新增羁绊反馈、文件投喂入口和三回合记忆钓鱼。
- 新增屏幕情境反应、每日工作回忆、对话历史与长期记忆面板。
- 新增可选 Edge TTS 语音输出，并加强设置、线程、日志和安全边界。

> Windows 安装包尚未代码签名。SmartScreen 可能显示“未知发布者”，请从官方 GitHub Release 下载并核对 SHA256。

### English

- Rebranded the project as FEIXUE and completed the Windows packaging flow.
- Added the Xiaofeixue sprite as the default skin, with dedicated performances, natural motion, and scaling.
- Added the desk workshop, physical bookshelf, persistent world objects, and low-frequency book revisits.
- Added bond feedback, file feeding, and the three-round memory-fishing game.
- Added screen-context reactions, daily work memories, conversation history, and a long-term memory panel.
- Added optional Edge TTS output and hardened settings, threading, logging, and safety boundaries.

> Windows binaries are currently unsigned. SmartScreen may report an unknown publisher; download only from the official GitHub Release and verify SHA256 checksums.
