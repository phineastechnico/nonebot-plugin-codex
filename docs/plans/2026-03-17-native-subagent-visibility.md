# Native Subagent Visibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop leaking native subagent/commentary text into Telegram user replies and show clearer main-agent/subagent progress in the Telegram progress panel.

**Architecture:** Keep the existing native app-server lane and Telegram rendering flow intact. Tighten native protocol parsing so only `final_answer` becomes user-visible assistant text, buffer intermediate agent-message deltas until completion metadata is known, and translate collaboration tool-call items into concise progress lines that explain what the main agent and subagents are doing.

**Tech Stack:** Python 3.10+, NoneBot 2, nonebot-adapter-telegram, pytest, Codex app-server JSON-RPC

---

### Task 1: Lock native client expectations for commentary vs final answer

**Files:**
- Modify: `tests/test_native_client.py`
- Modify: `src/nonebot_plugin_codex/native_client.py`

**Step 1: Write the failing test**

Add a focused native-client test that simulates:

- one `agentMessage` streamed by delta and completed with `phase: "commentary"`
- one `collabAgentToolCall` item showing subagent progress
- one final `agentMessage` completed with `phase: "final_answer"`

Assert that:

- commentary text never reaches `on_stream_text`
- `final_text` is only the final answer
- progress updates mention both the main agent and the subagent state

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_native_client.py -q`
Expected: FAIL because the client currently streams all `agentMessage` deltas immediately and does not format collaboration tool calls.

**Step 3: Write minimal implementation**

Update `src/nonebot_plugin_codex/native_client.py` to:

- buffer `item/agentMessage/delta` text by `itemId`
- only forward agent text when `item/completed` confirms `phase == "final_answer"` or phase is absent for legacy compatibility
- ignore `phase == "commentary"` for user-visible output
- translate `collabAgentToolCall` items into concise progress lines for main-agent and subagent activity

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_native_client.py -q`
Expected: PASS

### Task 2: Verify service-level native prompt integration still renders the right message

**Files:**
- Modify: `tests/test_service.py`
- Modify: `src/nonebot_plugin_codex/service.py` only if a thin integration adjustment is needed

**Step 1: Write the failing test**

Add a focused service test, if needed, that proves:

- native progress lines coming from collaboration items are preserved in session progress
- final visible text stays bound to the final answer only

**Step 2: Run test to verify it fails for the right reason**

Run: `pdm run pytest tests/test_service.py -q`
Expected: FAIL only if the service needs an extra integration tweak beyond the native client fix.

**Step 3: Write minimal implementation**

Keep service changes minimal. Prefer no service-layer behavior changes unless required by the new tests.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_service.py -q`
Expected: PASS

### Task 3: Run focused verification and full repository checks

**Files:**
- Modify: `docs/maintenance/2026-03-17-telegram-subagent-visibility.md`

**Step 1: Capture the maintenance note**

Document the bug with:

- reproduction shape
- expected behavior
- actual behavior
- affected modules/tests

**Step 2: Run focused tests**

Run:

- `pdm run pytest tests/test_native_client.py -q`
- `pdm run pytest tests/test_service.py -q`
- `pdm run pytest tests/test_telegram_handlers.py -q`

Expected: PASS

**Step 3: Run full verification**

Run:

- `pdm run pytest -q`
- `pdm run ruff check .`

Expected: PASS
