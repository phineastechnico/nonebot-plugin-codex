# Multi-Agent Telegram Panels Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the main agent and each spawned subagent its own fixed Telegram progress/reply message pair, ordered by creation time after the main agent.

**Architecture:** Extend native event handling so progress and stream updates carry an `agent_key` and label rather than plain text. Replace chat-level single-message state with per-agent panel state in the service and Telegram layers, with `main` always first and subagents appended when first observed.

**Tech Stack:** Python 3.10+, NoneBot 2, nonebot-adapter-telegram, pytest, Codex app-server JSON-RPC

---

### Task 1: Lock multi-agent native event expectations

**Files:**
- Modify: `tests/test_native_client.py`
- Modify: `src/nonebot_plugin_codex/native_client.py`

- [ ] **Step 1: Write the failing test**

Add a native-client test that emits:

- main-agent commentary
- `collabAgentToolCall` spawn/wait events for one subagent
- subagent commentary/final text
- main-agent final text

Assert that callbacks receive structured events that distinguish:

- `main`
- the spawned subagent thread id
- progress vs temporary reply vs final answer

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_native_client.py::test_native_client_emits_per_agent_updates_for_spawned_subagent -q`
Expected: FAIL because the current client only emits plain strings with no agent identity.

- [ ] **Step 3: Write minimal implementation**

Update `src/nonebot_plugin_codex/native_client.py` to:

- define a structured native update payload
- map collaboration events and agent messages to an `agent_key`
- track spawned subagent thread ids in creation order
- emit separate updates for each agent

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_native_client.py::test_native_client_emits_per_agent_updates_for_spawned_subagent -q`
Expected: PASS

### Task 2: Replace chat-level single message state with per-agent panel state

**Files:**
- Modify: `tests/test_service.py`
- Modify: `src/nonebot_plugin_codex/service.py`

- [ ] **Step 1: Write the failing test**

Add a service-level test that proves one chat session can track:

- `main` panel first
- spawned subagent panel second
- separate progress/stream state for each
- final main-agent answer without overwriting subagent stream state

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_service.py::test_chat_session_tracks_agent_panels_in_creation_order -q`
Expected: FAIL because the session only stores a single pair of Telegram message ids and stream buffers.

- [ ] **Step 3: Write minimal implementation**

Update `src/nonebot_plugin_codex/service.py` to add:

- per-agent panel state dataclass
- `agent_order`
- `agent_panels`
- helper methods to reset, register, update, and finalize agent panels

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_service.py::test_chat_session_tracks_agent_panels_in_creation_order -q`
Expected: PASS

### Task 3: Render fixed-order multi-agent message pairs in Telegram

**Files:**
- Modify: `tests/test_telegram_handlers.py`
- Modify: `src/nonebot_plugin_codex/telegram.py`

- [ ] **Step 1: Write the failing test**

Add a Telegram handler test that simulates:

- main-agent progress and temporary reply
- subagent creation
- subagent progress and temporary reply

Assert that Telegram sends four editable messages in order:

- main progress
- main temporary reply
- subagent progress
- subagent temporary reply

And later edits each agent’s own pair rather than mixing them.

- [ ] **Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_telegram_handlers.py::test_execute_prompt_keeps_separate_message_pairs_per_agent -q`
Expected: FAIL because Telegram currently edits only one progress message and one stream message per chat.

- [ ] **Step 3: Write minimal implementation**

Update `src/nonebot_plugin_codex/telegram.py` to:

- render/update progress by `agent_key`
- render/update temporary reply by `agent_key`
- preserve fixed creation order from service
- finalize each agent’s progress line independently

- [ ] **Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_telegram_handlers.py::test_execute_prompt_keeps_separate_message_pairs_per_agent -q`
Expected: PASS

### Task 4: Verify integrated behavior

**Files:**
- Modify: `docs/maintenance/2026-03-17-telegram-subagent-visibility.md`

- [ ] **Step 1: Update maintenance note**

Add the new requirement that TG keeps independent message pairs per agent in fixed creation order.

- [ ] **Step 2: Run targeted verification**

Run:

- `pdm run pytest tests/test_native_client.py -q`
- `pdm run pytest tests/test_service.py -q`
- `pdm run pytest tests/test_telegram_handlers.py -q`

Expected: PASS

- [ ] **Step 3: Run full verification**

Run:

- `pdm run pytest -q`
- `pdm run ruff check .`

Expected: PASS
