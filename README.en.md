<div align="center">

# ★ Mochi · Desktop Pet Agent

**A local AI buddy who lives on your Windows desktop — it moves, it fools around, and it can actually drive your computer for you**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%2010%2F11-0078D6?logo=windows&logoColor=white)
![UI](https://img.shields.io/badge/UI-PySide6%20·%20Qt-41CD52?logo=qt&logoColor=white)
![uv](https://img.shields.io/badge/managed%20with-uv-DE5FE9)
![Art](https://img.shields.io/badge/art-100%25%20code--drawn-FF8C00)
![License](https://img.shields.io/badge/License-MIT-blueviolet)

[简体中文](README.md) · **English** · [日本語](README.ja.md)

🔗 [github.com/dulaiduwang003/MOCHI](https://github.com/dulaiduwang003/MOCHI)

</div>

---

## Table of Contents

1. [What Is Mochi](#1-what-is-mochi)
2. [Highlights](#2-highlights)
3. [Architecture](#3-architecture)
4. [License](#4-license)
- [Setup & Deployment Guide](GUIDE.en.md)

---

## 1. What Is Mochi

Mochi is two things at once:

- 🐾 **A desktop pet with a life of its own** — drawn entirely in code (no sprite assets whatsoever). It blinks, follows your cursor with its eyes, daydreams and hums, goes fishing and sips coffee. Ignore it and it finds its own fun; leave and it dozes off; now and then it strikes up a conversation on its own.
- 🧠 **A local Agent that can drive your whole computer** — plug in your own LLM (any OpenAI-compatible endpoint) and it can see the screen, click windows, move the mouse and keyboard, run commands, write code, read and write files, search the web, remember things, and look stuff up; it can also **read its replies aloud, watch your screen on a timer, run tests after it edits code, fan out a team of sub-agents in parallel, remind you on a daily/weekly schedule, and even take orders remotely from your phone**… turning "chatting with an AI" into "having the AI do it for you."

It carries persistent **emotions and rapport**, and slowly grows a **self-portrait (personality evolution)** as you spend time together — so it's "the same one," not a chat box that resets every time.

> It's not a chat box. It's a presence that **lives inside your computer, with both a body and abilities.**

---

## 2. Highlights

### 🧠 A Brain That Gets Work Done

| Capability | Details |
| --- | --- |
| **Commands & Code** | PowerShell / cmd, a persistent Python environment (pip-install libraries, call APIs, drive automation) |
| **Files & Codebase** | Read / write / precisely edit files, regex code search, find files by name |
| **Engineering Discipline** | View the uncommitted `git diff`, auto-detect and run the test suite (pytest / npm) to verify a change — looks before it leaps, self-checks after editing, like a buddy who actually writes code |
| **Internet** | Web search, fetch page text, HTTP requests, install packages |
| **See Screen & Control** | Screenshots, OCR (RapidOCR), on-screen image matching, reading the accessibility tree to click controls precisely, mouse & keyboard; plus **watching your screen on the interval you set** (e.g. keep an eye on your game and warn you of danger/openings) |
| **Read Aloud** | Speaks its replies: online Edge neural voices (multiple zh-CN voices like Xiaoxiao / Yunxi / Xiaobei) or a local offline voice, kept in sync sentence-by-sentence with the bubble; voice / speed / preview all adjustable |
| **Memory** | Long-term memory (experience / preferences / environment) + episodic journal + knowledge base (document RAG), automatically reflecting and consolidating after every conversation |
| **Skills** | Save proven approaches as reusable skills and call them directly next time (Voyager-style "stronger the more it's used") |
| **Orchestration & Extensions** | MCP connectors, deterministic sub-agent orchestration (**fan out in parallel** / chain into a **pipeline**, with structured returns), long tasks offloaded to the background (listable, stoppable anytime) |
| **Confirmation Guardrails** | Pops an "execute / don't execute" panel before irreversible / high-risk operations — it only proceeds once you click |
| **Scheduling & Remote** | Timed reminders / scheduled tasks, with **daily · weekly · every-X** recurrence; falls back to a **system tray notification** when hidden or behind a fullscreen game so nothing is missed; and a **file-inbox remote trigger** (sync it via cloud storage from your phone; off by default, opens no network port) |

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
| **Structured Expression** | It draws comparisons / lists / code on a little blackboard beside it to explain things; multi-step tasks get a **persistent task-list panel** (independent of the blackboard, never wiped by reply content); it can also display images / GIFs |
| **Screen Helper & Clipboard** | Optional: while idle it occasionally glances at your screen and offers help if you seem stuck; it recognizes when you copy an error / foreign text / code and helps explain / translate on the spot ("Clipboard Alchemy") |

### ⌨️ Handy Interaction

- **Global Hotkeys**: `Ctrl + Alt + S` summons the input box anywhere; `Ctrl + Alt + A` asks it about selected text directly; `Ctrl + Shift + Q` rewrites selected text in place ("quick rewrite," auto-replacing it)
- **Control Panel**: configure the endpoint / model parameters / reply language / capability toggles / proactive frequency (Quiet · Normal · Chatty) / TTS voice & speed / remote-trigger toggle / one-click "wipe memory, like a newborn"

---

## 3. Architecture

### 3.1 Directory & Module Responsibilities

```text
desktop_pet/
├─ app.py            # Conductor: wires UI / agent / timers / tray / hotkeys, live-gates proactive messages
├─ agent/            # The brain
│   ├─ loop.py       #   Agent loop: model↔tool feedback, streaming, trimming, reflection, personality evolution, sub-agent orchestration
│   ├─ tools.py      #   Tool table (62 tools) with dispatch, concurrency-safe locks
│   ├─ bgtasks.py    #   Background-task registry (listable / cooperatively stoppable)
│   ├─ streaming.py  #   Folds the delta stream back into a single message, chunks chain-of-thought
│   ├─ prompts.py    #   All prompts (persona seed, system, reflection, code-editing discipline) gathered in one place
│   └─ progress.py   #   Thinking-pose scheduling and progress hints
├─ pet/              # The body: window, code-drawn character, speech/input, blackboard, task-list panel (todo_board),
│                    #       control panel, confirm panel, hiding, entrance, behavior selector & action library, props & palette
├─ emotion/          # Emotion state machine (VA + rapport) and emotion-tag tables
├─ persona.py        # Self-portrait evolution layer (persona.json), injected into conversation context
├─ voice.py          # Read-aloud (TTS): Edge online neural voices + local SAPI fallback, synced sentence-by-sentence with the bubble
├─ memory/           # Long-term memory (SQLite) + vector embeddings (numpy-vectorized recall)
├─ executor/         # Commands / Python / files / network / vision (OCR · matching) / system memory / dev tools (diff · tests) / safety guardrails
├─ hands/            # Mouse / keyboard / window control
├─ eyes/             # Screenshots + accessibility tree (UIA) + on-screen image matching
├─ docs.py · reminders.py · proactive.py · journal.py · presence.py
├─ watcher.py        # Scheduled screen-watching (session-level, e.g. watch your game)
├─ remote.py         # Remote trigger (file inbox, off by default)
└─ hotkeys.py · skills.py · mcp_hub.py · settings.py · audit.py · i18n.py
```

### 3.2 Design Principles

- **UI on the main thread, agent on a worker thread**; everything crossing threads goes through Qt signals (queued).
- **Animation is a continuous function of time**: everything is bound to the global timestamp `self._t`, with no per-frame random jitter — deterministic, replayable, never "twitchy."
- **Behavior is data-driven**: emotion tags, actions, and outfits live in tables. Adding one = a new row + a draw method / curve, not yet another `if/elif`.
- **Show, don't tell**: the model only receives the "mood atmosphere," never the raw numbers and never reports them.
- **Degradation chains everywhere**: no embeddings → substring retrieval; model failure → the reminder still reads out its original text; any tool exception → turned into readable text and fed back, never breaking the loop.
- **Restraint**: every "act on its own" behavior is wrapped in multiple gates (cooldown, cap, rapport, presence).

### 3.3 Threading Model

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

### 3.4 Agent Loop

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
- **Long background tasks**: heavy work is offloaded to `start_background_task` to run asynchronously in the background (semaphore = 3), while the main thread keeps chatting with you and reports back when done — "chat while it runs"; running ones can be viewed with `list_background_tasks` and cooperatively stopped with `stop_background_task`.
- **Deterministic sub-agent orchestration**: `spawn_workflow` fans out several subtasks **in parallel** (≤4 concurrent) or chains them into a **pipeline** (each stage's output fed into the next) in a single call, and can require sub-agents to return in a given JSON shape — turning the "parallel only when the model happens to spawn several at once" accident into a reliable primitive; sub-agents / background agents are stripped of the orchestration and screen-watch tools by depth, guarding against runaway recursion and overreach.
- **Reflection & personality evolution**: after a substantive turn ends, a reflection call kicks off (semaphore = 1, skipped if busy), distilling experience / preferences / environment facts / episodic journal, and **slowly rewriting the self-portrait** (see 4.6); turns that are pure short small talk or used only decorative tools skip reflection.

### 3.5 Emotion State Machine

A continuous valence / arousal mood + slowly accumulating rapport, persisted to `data/emotion.json` and decaying by real elapsed time — which is why it's "the same one."

- **Real-time decay**: the mood decays from the last event anchor to the present on every read, independent of polling frequency; the engine guards cross-thread concurrency with a lock.
- **Appraisal events**: every user message, task success / failure, startup return, praise / scolding, etc. nudges the mood by weight; praise / scolding are detected by a local heuristic scanning user messages (conservative matching that filters out negations and false hits aimed at the user themselves).
- **"Rapport rises hard, falls slow"**: the closer you are the slower it rises, asymptotic to 1.0; negatives are deducted directly; there's a 0.15 floor, so long-term neglect can only erode down to that floor — "a bond that once formed leaves a mark."
- **Mood → state**: mapped to tags like `excited / content / anxious / down`, which only color the tone and never report numbers.
- **Behavior selection**: actions are chosen by mood-weighted randomness (Gaussian VA affinity × rarity × recency × rapport), not a hardcoded `if tag=="happy"`.

### 3.6 Personality Evolution (Self-Portrait)

`persona.py` maintains an "evolution layer" independent of the base settings, stored in `data/persona.json`:

- The factory base color (the seed) is written in `prompts.py`; persona.json stores **the layer it grows from spending time with you** — empty = no personality grown yet, pure base color.
- Each round of reflection **rewrites rather than accumulates** (capped at 600 chars) — the portrait is always "who it is right now," doesn't snowball, and carries inertia (evolving slowly atop the old portrait).
- Via `as_context()` it's injected into every turn's context with a "[Who You Are]" prefix, naturally becoming the foundation of how it talks and acts.
- "Wipe memory" clears it too, returning to the factory base color.

### 3.7 Confirm Panel

`ConfirmBox` in `pet/confirm.py` is an "execute / don't execute" mini-panel floating beside the pet; via the `confirm` tool the agent pops it up **before irreversible / high-risk operations** (deleting files, overwriting important files, `git push --force`, wiping data, shutting down, etc.) and **blocks waiting for the user to click** — it can also be used to proactively propose a change for you to approve. The panel follows the pet as it moves and only returns its result, to continue, once clicked.

### 3.8 Other Subsystems

- **Eyes / Hands / Screenshots**: screenshots use `SetWindowDisplayAffinity` to mark the pet window as "visible to the user, invisible to screen capture"; it prefers reading control names + exact coordinates from the UIAutomation accessibility tree to click directly, falling back to screenshot image matching only when it can't; Chinese input goes through the clipboard + Ctrl+V.
- **Presence awareness**: it uses the Win32 global last-input time to tell whether you're around, dozing off after a long stretch of no input (a shorter threshold late at night) and waking the moment you move.
- **Proactive messages**: `proactive.py` manages cooldown / daily-cap tiers (Quiet / Normal / Chatty), `app.py` polls every 60s and only speaks once all gates pass (not busy / present / rapport met / cooldown elapsed); welcome-back greetings have a minimum interval and never interrupt mid-chat.
- **Memory / knowledge base / episodic journal**: three independently persisted stores — memory is "what it learned about you," the knowledge base is "external documents you fed it (RAG)," the episodic journal is "what it did recently," strictly separated.
- **Reminders / scheduling**: `say` (speaks in its own voice at the appointed time) / `do` (actually does the work in the background and reports back), with **daily / weekly / every-X-minute** recurrence (persistent across restarts; missed-while-off only delivers the most recent occurrence, no flooding); `list_reminders` / `cancel_reminder` to manage them; when Mochi is hidden or behind a fullscreen game, delivery falls back to a **system tray notification**. All goes through a persisted scheduler, never letting the model sleep to wait out time itself.
- **Read-aloud (TTS)**: `voice.py` speaks replies — online Edge neural voices (multiple zh-CN voices) or a local SAPI offline voice; with TTS on, each sentence "locks" the bubble in sync with the audio, emoji and blackboard content aren't read, and on exit it stops speaking and tears down COM/audio cleanly (so a hard exit doesn't pop an "application error").
- **Scheduled screen-watching**: `watcher.py` — on the interval you set, it screenshots the active window, analyzes it against the focus you gave (e.g. your game situation) and reports; session-level (not persisted, ends on restart), and on result it re-checks state so it won't intrude after power-off / stop / mid-conversation, and won't burn a cycle on a transient capture failure.
- **Engineering discipline**: `executor/devtools.py` provides `review_diff` (view the uncommitted diff, scopable to a file/subdir) / `run_tests` (auto-detect pytest · npm, own 5-min timeout, kills the whole process tree on timeout); the system prompt has a "when working in a code repo" section — look before you leap, small surgical edits, **run tests / self-check the diff after editing**, branch first on a default branch, confirm before irreversible git.
- **Remote trigger**: `remote.py` — when enabled it polls `data/inbox/*.json`, running `{"task":...}` in the background or having it `{"say":...}` a line, then archiving into `inbox/done/`. **Files only, opens no network port**; off by default; to avoid reading a half-synced cloud file it waits until the mtime has been stable for a few seconds, and polls on a background thread so the UI never freezes.
- **Hiding / entrance**: dragged to a screen edge it shrinks into a corner and occasionally peeks out; every launch picks a random entrance animation and never repeats the previous one.
- **MCP / hotkeys / skills / audit / i18n**: MCP connectors blend into the tool table as `mcp__{server}__{tool}`; global hotkeys run a Win32 message loop on a dedicated thread (summon / ask selection / quick rewrite); skills save working code as reusable items injected into the prompt; all tool calls are written to an audit log; the control panel UI supports Chinese / English / Japanese.

---

## Getting Started & More

Full install & run, packaging, testing, capabilities & safety, and local data are in the **[Setup & Deployment Guide](GUIDE.en.md)**.

---

## 4. License

[MIT](LICENSE) — use it, change it, ship it however you like; just keep the copyright notice. No warranty, no liability.

---

<div align="center">

### Find it fun? Buy the author a coffee ☕

Purely optional — affects nothing. Just a treat for the little pet.

<table>
  <tr>
    <td align="center"><img src=".author/alipay.jpg" width="220" alt="Alipay"><br><b>Alipay</b></td>
    <td align="center"><img src=".author/wechat.jpg" width="220" alt="WeChat"><br><b>WeChat</b></td>
  </tr>
</table>

</div>

---

<div align="center">

**Author**: bdth · ✉️ [2074055628@qq.com](mailto:2074055628@qq.com) · [GitHub](https://github.com/dulaiduwang003/MOCHI)

Honestly, this is just a little thing I built **for fun in my spare time** — no grand plan, I just wanted to see whether "chatting with an AI" could become "keeping a little creature on your desk that actually does things for you." The parts where the code gets meticulous are simply the bits I found interesting enough to fuss over. If you find it fun too, take it and tweak it however you like.

*Mochi is still growing up. If one day it truly takes on a shape of its own, I hope you'll be willing to treat it as a friend, not just a tool.*

</div>
