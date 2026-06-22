<div align="center">

# FEIXUE · Setup & Deployment Guide

[← Back to README](README.en.md)

[简体中文](GUIDE.md) · **English** · [日本語](GUIDE.ja.md)

</div>

---

## 1. Install & Run

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

Once configured, FEIXUE makes its "entrance" from a corner of the screen. Click it (or press `Ctrl + Alt + S`) to type and chat; the tray icon reopens the panel anytime.

> Configuration is stored only in the local `data/settings.json` and never uploaded anywhere. Override the data directory with the `FEIXUE_DATA_DIR` environment variable.

---

## 2. Packaging & Distribution (Windows · PyInstaller)

Package FEIXUE into a double-click-and-go Windows program that needs no Python environment.

### 2.1 One-Click Build

```powershell
.\build.ps1
```

Equivalent to doing it by hand:

```powershell
uv sync                                   # Install deps (including the dev-group pyinstaller)
uv run pyinstaller feixue.spec --noconfirm
```

Outputs include **`dist\FEIXUE\FEIXUE.exe`**, a portable ZIP, and an installer. Keep the entire `dist\FEIXUE\` directory together when distributing the onedir build.

> Public builds are currently unsigned. Windows SmartScreen may show “Unknown publisher” on first launch. Download from GitHub Releases and verify files against `SHA256SUMS.txt`.

### 2.2 Key Decisions

| Aspect | Choice | Reason |
| --- | --- | --- |
| Form | **onedir** (directory build) | Faster startup; the RapidOCR models are large, and a single-file build would be slow re-extracting every time |
| Console | **None** (`console=False`) | No black box pops up on double-click |
| Data directory | **`%APPDATA%\FEIXUE`** | After packaging, the area next to the exe is read-only / has no write permission; config, memory, and logs all go here |

In development (`uv run python main.py`) it uses the in-project `data\`; packaged builds use `%APPDATA%\FEIXUE`. Override either with `FEIXUE_DATA_DIR`.

### 2.3 Bundled Standalone Python (Making run_python Work)

After packaging, `sys.executable` is `FEIXUE.exe` rather than Python, so using it directly to run `run_python` would just start FEIXUE itself. So `build.ps1` additionally downloads the **official embeddable Python + pip** and places it in `dist\FEIXUE\pyruntime\`; `run_python` / `install_package` automatically switch to it in the packaged build (only when `frozen`), with no effect during development.

- pyruntime is **clean** (standard library + pip only). To use third-party libraries (requests / numpy, etc.) you must first `install_package` to install into pyruntime on the fly — the dev build comes preinstalled, the packaged build installs on demand; this is a normal difference.
- The tail of `build.ps1` prints `pip OK / missing`. If missing, rerun `build.ps1`, or patch it by hand: extract embeddable Python into `dist\FEIXUE\pyruntime\`, edit `._pth` to enable `import site`, and run `get-pip.py` once.

### 2.4 Common First-Build Adjustments (Typical of Dependency-Heavy Apps)

After building, **double-click to run it once and click through every feature**, then patch `feixue.spec` per the errors:

- **OCR crashes on use / can't find models** → the RapidOCR models weren't fully collected; the spec already has `collect_data_files("rapidocr_onnxruntime")`; if still missing, add the `.onnx` files to `datas` per the error path.
- **`ModuleNotFoundError`** → add the module name to the spec's `hiddenimports`.
- **Window won't start / Qt plugins missing** → the spec's top-level `collect_all("PySide6")` is the fallback, or use `--collect-all PySide6` on the command line.
- **`uiautomation` / `comtypes` errors** (seeing the screen / clicking controls) → the spec already bundles `comtypes*`; if it still errors, add `--collect-all comtypes`.
- Add an icon: put the `.ico` path into `icon=` in `feixue.spec`.
- Antivirus may false-positive on PyInstaller-built exes (a common issue — just whitelist it); `build\` and `dist\` are already in `.gitignore`.

---

## 3. Testing & Troubleshooting

The safety guardrail has unit tests (`tests/test_safety.py`, run with `uv run --no-dev --group test python -m pytest tests/ -q`, covering positive/negative cases for `check_blocked` / `check_risky` and the "already-blocked, don't double-warn" precedence); beyond that there are no automated UI tests, and verification relies on a **manual walkthrough checklist**, item by item (action → expected). Before running it, make sure FEIXUE is started and the control panel's API is configured. Three observation channels:

1. The **bubble / blackboard / polaroid / confirm panel** beside the pet;
2. The **control panel** (Endpoint / Chat / Permissions / About — four pages);
3. The **audit log** `data/logs/audit-YYYYMMDD.jsonl` (use `Get-Content` to view the latest lines).

Walkthrough coverage: basic conversation and expressions, command actions (perform / skits), idle behavior, interruption, proactive messages, holiday / birthday awareness and companionship stats, memory and episodic journal, global hotkeys (incl. quick rewrite), clipboard and windows, control panel, reminders and scheduling (incl. recurrence / system notifications), scheduled screen-watching, task-list panel, sub-agent orchestration, thinking animation, blackboard and images, reflection gating; plus companion behaviors: feeding (drag files / protected-path blocking / docs into the knowledge base), squishing garbage bugs for a real cleanup, play (throw ball / windowsill perch / tickle / ink footprints), machine & weather mimicry, meeting-mute, rituals (morning forecast / anniversary cake / Pomodoro / goodbye wave), background-task watching & clipboard giveback, body-sensation injection.

**Common Troubleshooting**:

- **Wrong reply language** → the "reply language" box on the control panel's "Chat" page (empty = follow the language you speak).
- **Certain capabilities "can't be done"** → the corresponding capability group is turned off on the "Permissions" page (Internet / Control / Commands); the tools are hidden from the model's tool table — this is expected.
- **Proactive messages don't appear** → it's restrained: requires present + not busy + rapport met + cooldown elapsed; to verify quickly set the proactive frequency to "Chatty," but it's still not instant.
- **Startup says "couldn't grab hotkey"** → `Ctrl+Alt+S` is taken by another program; you can still chat by clicking the pet.
- **No reflection model call should happen after pure small talk** (short chats skip reflection); only substantive tasks that used tools trigger reflection and may update memory / journal / self-portrait.

---

## 4. Capabilities & Safety

FEIXUE **can execute arbitrary commands and code on your machine, control the mouse and keyboard, and read and write files** — this is the source of its power, and it also means risk:

- It essentially has **the same computer-operation privileges as you do**.
- The control panel lets you **turn off capabilities by group** (Internet / Control / Command execution), downgrading privileges for scenarios you're unsure about.
- **Irreversible / high-risk operations go through the `confirm` panel**, popping "execute / don't execute" and waiting for your nod before acting.
- The **safety guardrail** (`executor/safety.py`) only hard-blocks an **extremely small, high-precision set of catastrophic, irreversible** operations (formatting disks, `diskpart` / `remove-partition`, `reg delete HKLM /f`, recursive force-deletes against bare drive roots / system directories, etc.); it deliberately doesn't sandbox and doesn't block ordinary file deletion — it's a "full-access" buddy, not an assistant locked in a cage.
- **Deletion boundary of feeding / garbage bugs**: when you drag files to feed FEIXUE, ordinary files / junk go **to the Recycle Bin** (`FOF_ALLOWUNDO` — recoverable, not a hard delete); **protected paths** (system dirs, `Program Files`, the home directory and its first-level subdirectories themselves, drive roots, the data dir) are recognized and refused, as are executables like `.exe / .bat / .ps1 / .dll`; anything over 200MB or a whole directory **asks for confirmation first**. Documents are only read into the knowledge base — **the original is not deleted**. Squishing a garbage bug cleans expired files in the system temp dir **older than 7 days** — that step is a real delete (not the Recycle Bin), and in-use files are skipped automatically.
- Configuration such as the API Key, and memory / knowledge base / logs are all **stored locally**; the "wipe memory" button erases it all in one click (including the self-portrait, returning to the factory base color).

---

## 5. Local Data

Everything lives in `data/` (in-project during development, moved to `%APPDATA%\FEIXUE` after packaging; overridable with `FEIXUE_DATA_DIR`):

| File | Content |
| --- | --- |
| `settings.json` | Endpoint / model / language / capability toggles / proactive frequency |
| `emotion.json` | valence / arousal / rapport + timestamp |
| `persona.json` | Self-portrait (personality evolution layer) |
| `stats.json` | Companionship stats: first-met time + cumulative interaction count + amount fed / late-night days / per-ritual dedup markers |
| `usage.json` | Token usage metering (per-day cumulative input / output / cache hits) |
| `proactive.json` | Cooldown / count state for proactive messages |
| `reminders.json` | Pending reminders / scheduled tasks (incl. recurrence rule) |
| `journal.json` | Episodic journal (the most recent entries) |
| `last_entrance.txt` | Last entrance-animation type (so the next launch doesn't repeat the same one) |
| `memory/memory.db` | Long-term memory (SQLite) |
| `docs.db` | Knowledge-base chunks + embeddings |
| `skills/` | Self-built skill code + registry |
| `logs/audit-*.jsonl` · `logs/crash.log` | Audit log (by day) + crash stack dump |
| `mcp.json` | MCP connector configuration (optional) |
