<div align="center">

# ★ Mochi · Desktop Pet Agent

**A local AI buddy who lives on your Windows desktop — it moves, it fools around, and it can actually drive your computer for you**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![UI](https://img.shields.io/badge/UI-PySide6%20·%20Qt-41CD52?logo=qt&logoColor=white)
![uv](https://img.shields.io/badge/managed%20with-uv-DE5FE9)
![Art](https://img.shields.io/badge/art-100%25%20code--drawn-FF8C00)

[简体中文](README.md) · **English** · [日本語](README.ja.md)

</div>

---

## Table of Contents

1. [What Is Mochi](#1-what-is-mochi)
2. [Highlights](#2-highlights)
3. [Install & Run](#3-install--run)
4. [Architecture](#4-architecture)
5. [Packaging & Distribution](#5-packaging--distribution-windows--pyinstaller)
6. [Testing & Troubleshooting](#6-testing--troubleshooting)
7. [Capabilities & Safety](#7-capabilities--safety)
8. [Local Data](#8-local-data)
9. [License](#9-license)

---

## 1. What Is Mochi

Mochi is two things at once:

- 🐾 **A desktop pet with a life of its own** — drawn entirely in code (no sprite assets whatsoever). It blinks, follows your cursor with its eyes, daydreams and hums, goes fishing and sips coffee. Ignore it and it finds its own fun; leave and it dozes off; now and then it strikes up a conversation on its own.
- 🧠 **A local Agent that can drive your whole computer** — plug in your own LLM (any OpenAI-compatible endpoint) and it can see the screen, click windows, move the mouse and keyboard, run commands, write code, read and write files, search the web, remember things, and look stuff up… turning "chatting with an AI" into "having the AI do it for you."

It carries persistent **emotions and rapport**, and slowly grows a **self-portrait (personality evolution)** as you spend time together — so it's "the same one," not a chat box that resets every time.

> It's not a chat box. It's a presence that **lives inside your computer, with both a body and abilities.**

---

## 2. Highlights

### 🧠 A Brain That Gets Work Done

| Capability | Details |
| --- | --- |
| **Commands & Code** | PowerShell / cmd, a persistent Python environment (pip-install libraries, call APIs, drive automation) |
| **Files & Codebase** | Read / write / precisely edit files, regex code search, find files by name |
| **Internet** | Web search, fetch page text, HTTP requests, install packages |
| **See Screen & Control** | Screenshots, OCR text recognition (RapidOCR), on-screen image matching, reading the accessibility tree to click controls precisely, mouse & keyboard |
| **Memory** | Long-term memory (experience / preferences / environment) + episodic journal + knowledge base (document RAG), automatically reflecting and consolidating after every conversation |
| **Skills** | Save proven approaches as reusable skills and call them directly next time (Voyager-style "stronger the more it's used") |
| **Extensions** | MCP connectors, spawning sub-agents to handle subtasks, offloading long tasks to async background execution (chat while it runs) |
| **Confirmation Guardrails** | Pops an "execute / don't execute" panel before irreversible / high-risk operations — it only proceeds once you click |
| **Scheduling** | Timed reminders (delivered in its own voice), scheduled automated tasks |

### 🐾 Companionship With Warmth

| Dimension | Details |
| --- | --- |
| **Emotion System** | valence / arousal / rapport drive expressions and behavior; the closer you get, the more it opens up — praise makes it happy, scolding brings it down |
| **Personality Evolution** | As you spend time together, each round of reflection slowly rewrites a "self-portrait" that's injected into the way it talks and acts — a "self" grown out of the relationship |
| **Spontaneous Animation** | 15 thinking poses, daydream bubbles, eyes tracking the cursor — all continuous functions of time, never jittery |
| **Prop-Based Skits** | Drinking coffee, fishing, cracking cases, reading, listening to music, gaming, stargazing — each a multi-stage little play |
| **One-Shot Actions** | Dancing, cheering, spinning… each with fitting effects (confetti / musical notes / afterimages) |
| **Presence Awareness** | It dozes off when you leave and wakes when you return; drag it to a screen edge and it tucks itself away, peeking out from a little corner |
| **Talking First** | Occasionally speaks up on its own when idle, yet **with restraint** — long cooldowns, a daily cap, and rapport gating mean it never spams |
| **Structured Expression** | It draws comparisons / lists / code on a little blackboard beside it to explain things; it can also display images / GIFs |

### ⌨️ Handy Interaction

- **Global Hotkeys**: `Ctrl + Alt + S` summons the input box anywhere; `Ctrl + Alt + A` asks it about selected text directly
- **Control Panel**: configure the endpoint / model parameters / reply language / capability toggles / proactive frequency (Quiet · Normal · Chatty) / one-click "wipe memory, like a newborn"

---

## 3. Install & Run

**Environment**: Windows 10 / 11 · Python ≥ 3.11 · [uv](https://github.com/astral-sh/uv)

```powershell
# Install dependencies
uv sync

# Run
uv run python main.py
```

On first launch the control panel pops up — just fill in your LLM configuration:

- **API Key** / **Endpoint (base_url)** — any **OpenAI-compatible** service (Qwen / DeepSeek / OpenAI / local vLLM, Ollama…)
- **Chat Model** — the chat model used for the main turn
- **Embedding Model** — used for semantic retrieval in the knowledge base and memory (optional; without an embedding endpoint it automatically degrades to substring retrieval)
- **Reply Language / Capability Toggles / Proactive Frequency / Temperature & Max Length / Whether to Show Chain-of-Thought** — all adjustable in the panel, taking effect live every turn

Once configured, Mochi makes its "entrance" from a corner of the screen. Click it (or press `Ctrl + Alt + S`) to type and chat; the tray icon reopens the panel anytime.

> Configuration is stored only in the local `data/settings.json` and never uploaded anywhere. The data directory can be overridden with the `STAR_DATA_DIR` environment variable.

---

## 4. Architecture

### 4.1 Directory & Module Responsibilities

```text
desktop_pet/
├─ app.py            # Conductor: wires UI / agent / timers / tray / hotkeys, live-gates proactive messages
├─ agent/            # The brain
│   ├─ loop.py       #   Agent loop: model↔tool feedback, streaming, trimming, reflection, personality evolution
│   ├─ tools.py      #   Tool table (~60 tools) with dispatch, concurrency-safe locks
│   ├─ streaming.py  #   Folds the delta stream back into a single message, chunks chain-of-thought
│   ├─ prompts.py    #   All prompts (persona seed, system, reflection) gathered in one place
│   └─ progress.py   #   Thinking-pose scheduling and progress hints
├─ pet/              # The body: window, code-drawn character, speech/input, blackboard, control panel, confirm panel,
│                    #       hiding, entrance, behavior selector & action library, props & palette
├─ emotion/          # Emotion state machine (VA + rapport) and emotion-tag tables
├─ persona.py        # Self-portrait evolution layer (persona.json), injected into conversation context
├─ memory/           # Long-term memory (SQLite) + vector embeddings
├─ executor/         # Commands / Python / files / network / vision (OCR · image matching) / system memory / safety guardrails
├─ hands/            # Mouse / keyboard / window control
├─ eyes/             # Screenshots + accessibility tree (UIA) + on-screen image matching
├─ docs.py · reminders.py · proactive.py · journal.py · presence.py
└─ hotkeys.py · skills.py · mcp_hub.py · settings.py · audit.py · i18n.py
```

### 4.2 Design Principles

- **UI on the main thread, agent on a worker thread**; everything crossing threads goes through Qt signals (queued).
- **Animation is a continuous function of time**: everything is bound to the global timestamp `self._t`, with no per-frame random jitter — deterministic, replayable, never "twitchy."
- **Behavior is data-driven**: emotion tags, actions, and outfits live in tables. Adding one = a new row + a draw method / curve, not yet another `if/elif`.
- **Show, don't tell**: the model only receives the "mood atmosphere," never the raw numbers and never reports them.
- **Degradation chains everywhere**: no embeddings → substring retrieval; model failure → the reminder still reads out its original text; any tool exception → turned into readable text and fed back, never breaking the loop.
- **Restraint**: every "act on its own" behavior is wrapped in multiple gates (cooldown, cap, rapport, presence).

### 4.3 Threading Model

```text
Main/UI thread (Qt event loop)
  └─ PetWindow(60fps) · bubble/input box/blackboard/polaroid/thinking bubble/confirm panel · tray · QTimer
        │ Signal(queued)
        ▼
Worker thread (QThread)  ──  AgentWorker → Agent.run()  [blocking: network + tools]
        │ spawns daemons
        ▼
  Sub-agents(concurrency≤4) · Background tasks(≤3) · Reflection(≤1) · MCP event loop · Hotkey message loop
```

The authoritative busy check uses the worker's `is_running` (a single bool, safe to read across threads), not the lagging UI state. Each agent has its own PowerShell + Python subprocess; network / read-only file access / each agent's own shell·python can run in parallel, while shared resources (mouse / screen / memory / pip) are serialized through a scheduling lock.

### 4.4 Agent Loop

`User message → model → tool call → execute → feed back → repeat → reply`, with these key settings:

| Parameter | Value | Meaning |
| --- | --- | --- |
| Max tool steps per turn | 16 | Prevents infinite self-invocation |
| Sub-agent depth | 1 | The pet can spawn a sub-agent; the sub-agent can't spawn further / go background (guards against runaway recursion) |
| Parallel sub-agents | 4 | Max simultaneous fan-out |
| History token budget | 24000 | Trimmed by estimated tokens (not message count), and tool-call-aware |
| Single tool result | 8000 chars | Truncated before entering history |
| Request / best-effort call timeout | 120s / 45s | User turn / background calls like reflection |

**Key Mechanisms**:

- **Streaming + Chain-of-Thought**: `streaming.py` folds the delta stream back into a single message, feeding `reasoning_content` / `content` chunk by chunk to the thinking bubble; each chunk checks for cancellation, so the network stream can be stopped mid-sentence.
- **Interruption**: clicking the pet sets a flag + kills subprocesses (so even a stuck long-running command unlocks instantly); the turn is rolled back via history markers, leaving no trace; **an interruption doesn't count as a failure** and plays no dejected animation.
- **Screenshots & multimodal cost**: only the latest screenshot is kept in history, older ones swapped for placeholders; JPEGs are scaled down to a ≤1600px longest edge, but coordinates always report the real resolution.
- **Long background tasks**: heavy work is offloaded to `start_background_task` to run asynchronously in the background (semaphore = 3), while the main thread keeps chatting with you and reports back when done — "chat while it runs."
- **Reflection & personality evolution**: after a substantive turn ends, a reflection call kicks off (semaphore = 1, skipped if busy), distilling experience / preferences / environment facts / episodic journal, and **slowly rewriting the self-portrait** (see 4.6); turns that are pure short small talk or used only decorative tools skip reflection.

### 4.5 Emotion State Machine

A continuous valence / arousal mood + slowly accumulating rapport, persisted to `data/emotion.json` and decaying by real elapsed time — which is why it's "the same one."

- **Real-time decay**: the mood decays from the last event anchor to the present on every read, independent of polling frequency; the engine guards cross-thread concurrency with a lock.
- **Appraisal events**: every user message, task success / failure, startup return, praise / scolding, etc. nudges the mood by weight; praise / scolding are detected by a local heuristic scanning user messages (conservative matching that filters out negations and false hits aimed at the user themselves).
- **"Rapport rises hard, falls slow"**: the closer you are the slower it rises, asymptotic to 1.0; negatives are deducted directly; there's a 0.15 floor, so long-term neglect can only erode down to that floor — "a bond that once formed leaves a mark."
- **Mood → state**: mapped to tags like `excited / content / anxious / down`, which only color the tone and never report numbers.
- **Behavior selection**: actions are chosen by mood-weighted randomness (Gaussian VA affinity × rarity × recency × rapport), not a hardcoded `if tag=="happy"`.

### 4.6 Personality Evolution (Self-Portrait)

`persona.py` maintains an "evolution layer" independent of the base settings, stored in `data/persona.json`:

- The factory base color (the seed) is written in `prompts.py`; persona.json stores **the layer it grows from spending time with you** — empty = no personality grown yet, pure base color.
- Each round of reflection **rewrites rather than accumulates** (capped at 600 chars) — the portrait is always "who it is right now," doesn't snowball, and carries inertia (evolving slowly atop the old portrait).
- Via `as_context()` it's injected into every turn's context with a "[Who You Are]" prefix, naturally becoming the foundation of how it talks and acts.
- "Wipe memory" clears it too, returning to the factory base color.

### 4.7 Confirm Panel

`ConfirmBox` in `pet/confirm.py` is an "execute / don't execute" mini-panel floating beside the pet; via the `confirm` tool the agent pops it up **before irreversible / high-risk operations** (deleting files, overwriting important files, `git push --force`, wiping data, shutting down, etc.) and **blocks waiting for the user to click** — it can also be used to proactively propose a change for you to approve. The panel follows the pet as it moves and only returns its result, to continue, once clicked.

### 4.8 Other Subsystems

- **Eyes / Hands / Screenshots**: screenshots use `SetWindowDisplayAffinity` to mark the pet window as "visible to the user, invisible to screen capture"; it prefers reading control names + exact coordinates from the UIAutomation accessibility tree to click directly, falling back to screenshot image matching only when it can't; Chinese input goes through the clipboard + Ctrl+V.
- **Presence awareness**: it uses the Win32 global last-input time to tell whether you're around, dozing off after a long stretch of no input (a shorter threshold late at night) and waking the moment you move.
- **Proactive messages**: `proactive.py` manages cooldown / daily-cap tiers (Quiet / Normal / Chatty), `app.py` polls every 60s and only speaks once all gates pass (not busy / present / rapport met / cooldown elapsed); welcome-back greetings have a minimum interval and never interrupt mid-chat.
- **Memory / knowledge base / episodic journal**: three independently persisted stores — memory is "what it learned about you," the knowledge base is "external documents you fed it (RAG)," the episodic journal is "what it did recently," strictly separated.
- **Reminders / scheduling**: `say` (speaks in its own voice at the appointed time) / `do` (actually does the work in the background at the appointed time and reports back); both go through a persisted scheduler, never letting the model sleep to wait out time itself.
- **Hiding / entrance**: dragged to a screen edge it shrinks into a corner and occasionally peeks out; every launch picks a random entrance animation and never repeats the previous one.
- **MCP / hotkeys / skills / audit / i18n**: MCP connectors blend into the tool table as `mcp__{server}__{tool}`; global hotkeys run a Win32 message loop on a dedicated thread; skills save working code as reusable items injected into the prompt; all tool calls are written to an audit log; the control panel UI supports Chinese / English / Japanese.

> 📐 Want to dig into the internals (full state machines / gates / real parameters) → **[Design Doc DESIGN.md](DESIGN.md)**

---

## 5. Packaging & Distribution (Windows · PyInstaller)

Package Mochi into a double-click-and-go Windows program that needs no Python environment.

### 5.1 One-Click Build

```powershell
.\build.ps1
```

Equivalent to doing it by hand:

```powershell
uv sync                                   # Install deps (including the dev-group pyinstaller)
uv run pyinstaller mochi.spec --noconfirm
```

Output: **`dist\Mochi\Mochi.exe`** — to distribute, copy the **entire `dist\Mochi\` directory** to others (the pile of files next to the exe are its dependencies).

### 5.2 Key Decisions

| Aspect | Choice | Reason |
| --- | --- | --- |
| Form | **onedir** (directory build) | Faster startup; the RapidOCR models are large, and a single-file build would be slow re-extracting every time |
| Console | **None** (`console=False`) | No black box pops up on double-click |
| Data directory | **`%APPDATA%\Mochi`** | After packaging, the area next to the exe is read-only / has no write permission; config, memory, and logs all go here |

In development (`uv run python main.py`) it still uses the in-project `data\`, while the packaged build uses `%APPDATA%\Mochi`; both can be overridden by `STAR_DATA_DIR`.

### 5.3 Bundled Standalone Python (Making run_python Work)

After packaging, `sys.executable` is `Mochi.exe` rather than Python, so using it directly to run `run_python` would just start Mochi itself. So `build.ps1` additionally downloads the **official embeddable Python + pip** and places it in `dist\Mochi\pyruntime\`; `run_python` / `install_package` automatically switch to it in the packaged build (only when `frozen`), with no effect during development.

- pyruntime is **clean** (standard library + pip only). To use third-party libraries (requests / numpy, etc.) you must first `install_package` to install into pyruntime on the fly — the dev build comes preinstalled, the packaged build installs on demand; this is a normal difference.
- The tail of `build.ps1` prints `pip OK / missing`. If missing, rerun `build.ps1`, or patch it by hand: extract embeddable Python into `dist\Mochi\pyruntime\`, edit `._pth` to enable `import site`, and run `get-pip.py` once.

### 5.4 Common First-Build Adjustments (Typical of Dependency-Heavy Apps)

After building, **double-click to run it once and click through every feature**, then patch `mochi.spec` per the errors:

- **OCR crashes on use / can't find models** → the RapidOCR models weren't fully collected; the spec already has `collect_data_files("rapidocr_onnxruntime")`; if still missing, add the `.onnx` files to `datas` per the error path.
- **`ModuleNotFoundError`** → add the module name to the spec's `hiddenimports`.
- **Window won't start / Qt plugins missing** → the spec's top-level `collect_all("PySide6")` is the fallback, or use `--collect-all PySide6` on the command line.
- **`uiautomation` / `comtypes` errors** (seeing the screen / clicking controls) → the spec already bundles `comtypes*`; if it still errors, add `--collect-all comtypes`.
- Add an icon: put the `.ico` path into `icon=` in `mochi.spec`.
- Antivirus may false-positive on PyInstaller-built exes (a common issue — just whitelist it); `build\` and `dist\` are already in `.gitignore`.

---

## 6. Testing & Troubleshooting

There are no automated UI tests; verification relies on a **manual walkthrough checklist**, item by item (action → expected). Before running it, make sure Mochi is started and the control panel's API is configured. Three observation channels:

1. The **bubble / blackboard / polaroid / confirm panel** beside the pet;
2. The **control panel** (Endpoint / Chat / Permissions / About — four pages);
3. The **audit log** `data/logs/audit-YYYYMMDD.jsonl` (use `Get-Content` to view the latest lines).

Walkthrough coverage: basic conversation and expressions, command actions (perform / skits), idle behavior, interruption, proactive messages, memory and episodic journal, global hotkeys, clipboard and windows, control panel, reminders and scheduling, thinking animation, blackboard and images, reflection gating.

**Common Troubleshooting**:

- **Wrong reply language** → the "reply language" box on the control panel's "Chat" page (empty = follow the language you speak).
- **Certain capabilities "can't be done"** → the corresponding capability group is turned off on the "Permissions" page (Internet / Control / Commands); the tools are hidden from the model's tool table — this is expected.
- **Proactive messages don't appear** → it's restrained: requires present + not busy + rapport met + cooldown elapsed; to verify quickly set the proactive frequency to "Chatty," but it's still not instant.
- **Startup says "couldn't grab hotkey"** → `Ctrl+Alt+S` is taken by another program; you can still chat by clicking the pet.
- **No reflection model call should happen after pure small talk** (short chats skip reflection); only substantive tasks that used tools trigger reflection and may update memory / journal / self-portrait.

> See **[TESTING.md](TESTING.md)** for the full item-by-item checklist.

---

## 7. Capabilities & Safety

Mochi **can execute arbitrary commands and code on your machine, control the mouse and keyboard, and read and write files** — this is the source of its power, and it also means risk:

- It essentially has **the same computer-operation privileges as you do**.
- The control panel lets you **turn off capabilities by group** (Internet / Control / Command execution), downgrading privileges for scenarios you're unsure about.
- **Irreversible / high-risk operations go through the `confirm` panel**, popping "execute / don't execute" and waiting for your nod before acting.
- The **safety guardrail** (`executor/safety.py`) only hard-blocks an **extremely small, high-precision set of catastrophic, irreversible** operations (formatting disks, `diskpart` / `remove-partition`, `reg delete HKLM /f`, recursive force-deletes against bare drive roots / system directories, etc.); it deliberately doesn't sandbox and doesn't block ordinary file deletion.
- Configuration such as the API Key, and memory / knowledge base / logs are all **stored locally**; the "wipe memory" button erases it all in one click (including the self-portrait, returning to the factory base color).

---

## 8. Local Data

Everything lives in `data/` (in-project during development, moved to `%APPDATA%\Mochi` after packaging; overridable with `STAR_DATA_DIR`):

| File | Content |
| --- | --- |
| `settings.json` | Endpoint / model / language / capability toggles / proactive frequency |
| `emotion.json` | valence / arousal / rapport + timestamp |
| `persona.json` | Self-portrait (personality evolution layer) |
| `proactive.json` | Cooldown / count state for proactive messages |
| `reminders.json` | Pending reminders / scheduled tasks |
| `journal.json` | Episodic journal (the most recent entries) |
| `memory/memory.db` | Long-term memory (SQLite) |
| `docs.db` | Knowledge-base chunks + embeddings |
| `skills/` | Self-built skill code + registry |
| `logs/audit-*.jsonl` | Audit log (by day) |
| `mcp.json` | MCP connector configuration (optional) |

---

## 9. License

To be determined (MIT or Apache-2.0 recommended).

---

<div align="center">

**Author**: bdth · ✉️ [2074055628@qq.com](mailto:2074055628@qq.com)

*Mochi is still growing up. If one day it truly takes on a shape of its own, I hope you'll be willing to treat it as a friend, not just a tool.*

</div>
