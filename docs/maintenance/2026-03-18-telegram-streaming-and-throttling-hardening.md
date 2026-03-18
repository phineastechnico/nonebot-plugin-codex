# Telegram Streaming And Throttling Hardening

## Summary

Harden Telegram-side streaming so long replies keep their agent header, cancelled runs still deliver the full generated text, and message sends or edits are throttled at the chat level instead of per agent.

## Reproduction Shape

1. Start a Telegram run that produces a long streamed reply, especially after a subagent appears.
2. Observe that the live stream preview can collapse to only the last chunk, with the `🧠 主 agent` or `🛠️ 子 agent N` header missing.
3. Cancel the run before final completion and observe that only the tail chunk may have been visible in-chat, with earlier streamed content missing entirely.
4. Trigger multiple progress and stream updates from main and subagents in the same chat.
5. Observe that updates can be emitted faster than Telegram's recommended per-chat pace because throttling was scoped to individual agents only.
6. Stream code, shell output, or other whitespace-sensitive text with leading spaces or trailing newlines.
7. Observe spaces or line breaks being altered by chunking or stream-state normalization.

## Expected Behavior

- Live stream previews should keep the current agent title when multiple agent panels exist.
- Cancelling a run should still send the full text generated so far.
- Message sends and edits should be serialized and rate-limited per chat.
- Benign edit failures such as `message is not modified` should not create duplicate fallback messages.
- Whitespace-sensitive streamed text should survive chunking and final rendering intact.

## Actual Behavior

- `render_stream_text()` only kept the last chunk, so long previews could lose the agent title.
- The cancelled-run branch finalized progress panels but never sent the accumulated streamed body.
- Progress updates and stream edits were throttled per agent or not throttled at all, which could exceed Telegram's per-chat guidance.
- Generic edit fallback would send a new message even for benign edit outcomes.
- `chunk_text()`, exec agent-message handling, native stream forwarding, and Telegram HTML block rendering all trimmed or collapsed whitespace.

## Affected Modules

- `src/nonebot_plugin_codex/service.py`
- `src/nonebot_plugin_codex/telegram.py`
- `src/nonebot_plugin_codex/telegram_rendering.py`
- `tests/test_service.py`
- `tests/test_telegram_handlers.py`

## Verification

- `pdm run pytest tests/test_service.py tests/test_telegram_handlers.py -q`
- `pdm run pytest -q`
- `pdm run ruff check .`
