# Telegram Command Menu Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Register the plugin's Telegram slash commands with Telegram so clients show the `/` command picker with Chinese descriptions.

**Architecture:** Introduce one command metadata module as the source of truth for command names and Chinese descriptions. Reuse it to build Telegram `BotCommand` payloads and wire a startup sync helper that calls Telegram once the bot is ready, while degrading safely on API failures.

**Tech Stack:** Python 3.10+, NoneBot, nonebot-adapter-telegram, pytest, ruff

---

### Task 1: Add command metadata tests

**Files:**
- Create: `tests/test_telegram_commands.py`

**Step 1: Write the failing test**

Add tests that assert:
- the command metadata contains the expected slash commands
- the Chinese descriptions match the intended menu wording
- the Telegram command payload is built in the same order

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_telegram_commands.py -q`
Expected: FAIL because the command metadata module does not exist yet.

**Step 3: Write minimal implementation**

Create a command metadata module that exposes the command list, plugin usage text, and Telegram command payload builder.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_telegram_commands.py -q`
Expected: PASS

### Task 2: Add startup sync tests

**Files:**
- Modify: `tests/test_telegram_handlers.py`
- Or create: `tests/test_plugin_entry.py`

**Step 1: Write the failing test**

Add tests that assert:
- startup sync calls Telegram `set_my_commands(...)` with the generated payload
- startup sync swallows Telegram API failures and logs a warning

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_plugin_entry.py -q`
Expected: FAIL because startup sync is not implemented.

**Step 3: Write minimal implementation**

Add a startup helper in the plugin entry module and register it with NoneBot's startup lifecycle.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_plugin_entry.py -q`
Expected: PASS

### Task 3: Align plugin metadata and docs

**Files:**
- Modify: `src/nonebot_plugin_codex/__init__.py`
- Modify: `README.md`

**Step 1: Update plugin metadata**

Use the shared command metadata to generate the plugin `usage` string instead of hardcoding command names inline.

**Step 2: Update README command table**

Adjust the command descriptions to match the shared Chinese wording introduced for the Telegram menu.

**Step 3: Run focused verification**

Run: `pdm run pytest tests/test_telegram_commands.py tests/test_plugin_entry.py -q`
Expected: PASS

### Task 4: Run repository verification

**Files:**
- Modify: `src/nonebot_plugin_codex/__init__.py`
- Create: `src/nonebot_plugin_codex/telegram_commands.py`
- Test: `tests/test_telegram_commands.py`
- Test: `tests/test_plugin_entry.py`
- Modify: `README.md`

**Step 1: Run full test suite**

Run: `pdm run pytest -q`
Expected: PASS

**Step 2: Run lint**

Run: `pdm run ruff check .`
Expected: PASS
