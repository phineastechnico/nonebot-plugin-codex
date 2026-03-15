# Config LocalStore Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the legacy bridge compatibility layer and stop exposing internal plugin storage paths as user config, using `nonebot-plugin-localstore` for plugin-owned files instead.

**Architecture:** Keep the public config model limited to runtime knobs the user actually controls. Resolve Codex's own `~/.codex/*` paths internally in `CodexBridgeSettings`, and resolve plugin-owned persistence paths during plugin initialization via `nonebot_plugin_localstore`.

**Tech Stack:** Python 3.10+, NoneBot2, Pydantic v1/v2 compatible `BaseModel`, nonebot-plugin-localstore, pytest, ruff

---

### Task 1: Lock the new config contract in tests

**Files:**
- Modify: `tests/test_config.py`

**Step 1: Write the failing test**

Add tests that instantiate `Config` without `model_validate`, assert supported fields still parse, and assert removed legacy aliases are ignored or absent from the contract.

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_config.py -q`
Expected: FAIL because tests still use v2-only APIs or removed fields.

**Step 3: Write minimal implementation**

Update `Config` to use plain field defaults only, with no alias-based compatibility layer.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_config.py -q`
Expected: PASS.

### Task 2: Lock internal path sourcing in tests

**Files:**
- Modify: `tests/test_service.py`
- Add: `tests/test_init.py`

**Step 1: Write the failing test**

Add tests proving service behavior still works when settings use internal defaults, and plugin initialization resolves `preferences_path` from localstore instead of plugin config.

**Step 2: Run test to verify it fails**

Run: `pdm run pytest tests/test_service.py tests/test_init.py -q`
Expected: FAIL because initialization still reads removed config fields and localstore is not wired.

**Step 3: Write minimal implementation**

Update initialization to require `nonebot_plugin_localstore`, derive plugin-owned paths from localstore, and keep Codex data paths internal to `CodexBridgeSettings`.

**Step 4: Run test to verify it passes**

Run: `pdm run pytest tests/test_service.py tests/test_init.py -q`
Expected: PASS.

### Task 3: Update docs and package metadata

**Files:**
- Modify: `README.md`
- Modify: `pyproject.toml`

**Step 1: Write the failing test**

No automated doc test; use repository checks after implementation.

**Step 2: Write minimal implementation**

Add `nonebot-plugin-localstore` dependency and rewrite README config documentation so only supported config items remain. Remove the old bridge naming from user-facing docs.

**Step 3: Run verification**

Run: `pdm run pytest -q`
Run: `pdm run ruff check .`
Expected: PASS.
