# /status Rate Limit Visibility

## Feature Summary

Enhance the Telegram `/status` command so it shows the active half-day usage window, current usage percentage, remaining percentage, and the refresh time or countdown.

## Problem Background

Current behavior:

1. Open a Telegram chat that uses `nonebot-plugin-codex`.
2. Send `/status`.
3. The plugin opens the generic workspace panel only.

Current gaps:

- no current morning or afternoon usage state
- no usage percentage for the active quota window
- no remaining percentage
- no refresh time or countdown
- no graceful status text when rate-limit data is temporarily unavailable

Actual behavior today is that `/status` is effectively an alias of `/panel`. The panel shows chat preferences, workdir, session state, and recent history, but it does not expose quota information.

## Proposal

- Keep `/status` as the Telegram entrypoint for operational state.
- Extend the existing workspace or status rendering path with a dedicated rate-limit section.
- Prefer official Codex account rate-limit data from the `codex app-server` lane when available.
- Display percentage-based data and refresh timing, not guessed absolute credits.
- Show morning or afternoon wording based on the active local window.
- Fall back to explicit unavailable text when upstream rate-limit data cannot be fetched.

Expected user-visible result:

- current morning or afternoon status
- used percentage
- remaining percentage
- reset time
- human-readable time until refresh

## Alternatives

- Infer quota state only from local session token-usage logs.
  - This is insufficient because local usage does not equal account-level remaining quota or refresh timing.
- Keep `/status` unchanged and add a separate quota command.
  - This is possible, but weaker for discoverability because users already expect `/status` to answer this question.

## Scope And Constraints

- Preserve command compatibility for `/status` and `/panel` unless a deliberate behavior change is documented.
- Do not silently change documented config semantics.
- Keep the implementation small and reviewable.
- Follow TDD for behavior changes.
- If upstream rate-limit data is unavailable, degrade cleanly instead of estimating.

Affected files or commands likely include:

- `src/nonebot_plugin_codex/service.py`
- `src/nonebot_plugin_codex/telegram.py`
- `src/nonebot_plugin_codex/native_client.py`
- `tests/test_service.py`
- `tests/test_telegram_handlers.py`
- `/status`
- `/panel`
- `codex app-server`

## Verification Plan

- Add service-level tests covering status rendering with and without rate-limit data.
- Add Telegram handler tests confirming `/status` shows the enriched status panel.
- Run `pdm run pytest tests/test_service.py tests/test_telegram_handlers.py -q`.
- Run `pdm run pytest -q`.
- Run `pdm run ruff check .`.
