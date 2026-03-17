# Telegram Native Subagent Visibility Bug

## Summary

When the plugin uses the native `codex app-server` lane and Codex delegates work to a subagent, the Telegram bridge can surface intermediate agent-message text to the end user as if it were the main agent's final reply. At the same time, the progress panel does not explain the collaboration flow, so users cannot tell what the main agent is doing versus what the subagent is doing.

## Reproduction Shape

1. Start a Telegram chat in the native resume mode.
2. Send a prompt that causes Codex to call a subagent.
3. Observe the native protocol emitting:
   - `item/agentMessage/delta`
   - `item/completed` for `agentMessage` with `phase: "commentary"`
   - `item/started` or `item/completed` for `collabAgentToolCall`
4. Observe the Telegram bridge showing the commentary/subagent text as a user-visible assistant reply.

## Expected Behavior

- Only the main agent's final answer should be user-visible in Telegram.
- Commentary or subagent-related intermediate text should stay out of the final reply stream.
- Telegram progress text should explain:
  - what the main agent is doing
  - which subagent is running
  - the current subagent state when available
- Main agent and each spawned subagent should keep independent Telegram message pairs:
  - one progress/status message
  - one temporary reply message
- Subagent panels should be appended after the main agent in first-seen creation order and stay stable for the rest of the run.

## Actual Behavior

- The native client forwarded all `agentMessage` deltas and completed texts without checking `phase`.
- Commentary text could therefore appear in the stream/final reply path.
- Collaboration tool calls were ignored, so the Telegram progress panel lacked main-agent/subagent context.

## Affected Modules

- `src/nonebot_plugin_codex/native_client.py`
- `src/nonebot_plugin_codex/service.py`
- `src/nonebot_plugin_codex/telegram.py`
- `tests/test_native_client.py`

## Verification

- Add a native-client regression test that includes:
  - commentary `agentMessage`
  - `collabAgentToolCall`
  - final-answer `agentMessage`
- Confirm that only the final answer reaches `on_stream_text`.
- Confirm that progress updates mention both the main agent and the subagent state.
