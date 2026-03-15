# Telegram Group Command Menu Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend Telegram command registration so slash commands appear in both private chats and group chats for all members.

**Architecture:** Keep the existing shared command metadata unchanged and update the startup sync helper to register the same command payload to both the private-chat and group-chat Telegram scopes. Preserve warning-only failure handling.

**Tech Stack:** Python 3.10+, NoneBot, nonebot-adapter-telegram, pytest, ruff

---

### Task 1: Update failing startup sync tests

**Files:**
- Modify: `tests/test_plugin_entry.py`

**Step 1: Write the failing test**

Adjust tests to assert:
- `set_my_commands(...)` is called twice
- scopes are `all_private_chats` then `all_group_chats`
- partial failure returns `False` and logs a warning

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_plugin_entry.py -q`
Expected: FAIL because only private chats are synced today.

**Step 3: Write minimal implementation**

Update the sync helper to iterate over both scopes and accumulate success state.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_plugin_entry.py -q`
Expected: PASS

### Task 2: Run verification

**Files:**
- Modify: `src/nonebot_plugin_codex/__init__.py`
- Modify: `tests/test_plugin_entry.py`

**Step 1: Run focused verification**

Run: `pdm run pytest tests/test_plugin_entry.py tests/test_telegram_commands.py -q`
Expected: PASS

**Step 2: Run full verification**

Run: `pdm run pytest -q`
Expected: PASS

Run: `pdm run ruff check .`
Expected: PASS
