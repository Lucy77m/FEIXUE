
# ★ FEIXUE

**An AI companion living on your Windows desktop — emotional, memorable, and capable of controlling your PC**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![UI](https://img.shields.io/badge/UI-PySide6%20·%20Qt-41CD52?logo=qt&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-blueviolet)

[简体中文](README.md) · **English** · [日本語](README.ja.md)

🔗 [github.com/Lucy77m/FEIXUE](https://github.com/Lucy77m/FEIXUE)

---

## What is it

FEIXUE is two things in one:

- 🐾 **A desktop pet** — Xiaofeixue sprite animation is the default, with the classic Blob appearance still available. She idles, waves, performs, shelters from rain, reacts to machine state, entertains herself when left alone, and occasionally revisits memories you created together.
- 🧠 **A local AI agent** — Connects to any OpenAI-compatible LLM. It can see your screen, move the mouse and keyboard, run commands, write code, read/write files, and search the web. Supports scheduled screen-watching, background tasks, parallel sub-agents, and reminders — turning "chat with AI" into "let AI do it for you."

It has persistent **emotion and rapport** that evolve over time, developing a **self-portrait** through your interactions. It's the same companion every session, not a reset-able chat box.

> Alive in your computer — with a body and real capabilities.

---

## Feature overview

### 🧠 Gets work done

| Capability | Details |
|------------|---------|
| Commands & code | PowerShell / Python persistent sessions, background long-running tasks |
| File operations | Read/write/edit, PDF/image OCR, regex code search, glob by name |
| Screen awareness | Screenshot, OCR, accessibility-tree precise clicking, mouse & keyboard control |
| Web access | Search engines, page scraping, HTTP requests, pip install |
| Long-term memory | Experience/preference/environment memory + knowledge base RAG + journal, auto-reflection |
| Memory panel | Browse, search, and deliberately forget core memories, recent experiences, preferences, and environment facts |
| Orchestration | MCP connectors, sub-agent fanout/pipeline, background task management |
| Safety guardrails | Confirmation dialog before irreversible ops, hard block on catastrophic commands |

### 🐾 Warm companion

| Experience | Details |
|------------|---------|
| Emotion system | Mood shifts with interaction; the closer you are, the more expressive it gets |
| Personality evolution | Slowly rewrites its "self-portrait" through reflection — shaped by your relationship |
| Machine mimicry | Fans itself on hot CPU, squished by low memory, blanket at night, snuggles warm hardware in winter |
| Weather mimicry | Umbrella in rain, huddles in snow, melts in heat |
| Screen reactions | OCR snapshots + keyword rules — celebrates green tests, frowns at errors, worries when you code late |
| Rituals | Daily mood forecast, anniversary cake, bedtime farewell, pomodoro focus timer |
| Feed & interact | Drop files: junk → recycle bin, docs → knowledge base, images → glance |
| Footprints & play | Happy footprints (flowers/snow on holidays), ball catching, tickle giggles, grudge when tossed |
| Desk-side world | Documents become physical books in the workshop; FEIXUE may revisit an old book and bring back a new thought |
| Memory fishing & performances | A three-round memory-fishing game plus dedicated dance, fishing, and other sprite performances |

v0.4 adds Memory Weather, expanded workshop shelf objects, richer dream fragments, and a quieter local project-awareness signal. Project awareness is used only for local ambience and does not persist full foreground window titles.

### ⌨️ Convenient

- **Global hotkeys**: `Ctrl+Alt+S` summon input, `Ctrl+Alt+A` ask about selection, `Ctrl+Shift+Q` quick-rewrite selection
- **Control panel**: API config, capability toggles, proactive frequency, multilingual (CN/EN/JP)
- **Speech output**: optional interruptible Edge TTS, disabled by default

---

## Quick start

```bash
git clone https://github.com/Lucy77m/FEIXUE.git
cd FEIXUE
uv sync
uv run python main.py
```

On first launch the control panel opens — fill in your API Key and model name on the Connect page.

Detailed install, packaging, and troubleshooting → [GUIDE.en.md](GUIDE.en.md)

---

## Tech stack

Python 3.11+ · PySide6 (Qt) · OpenAI-compatible API · sherpa-onnx (local speech input) · Edge TTS (optional output) · RapidOCR · SQLite + vector embeddings · MCP protocol · Win32 API

---

## License

[MIT](LICENSE)
