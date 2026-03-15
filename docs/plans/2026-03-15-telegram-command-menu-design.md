# Telegram Command Menu Design

## Goal

Register the plugin's Telegram slash commands with Telegram itself so users see a command menu when typing `/`, with concise Chinese descriptions for each command.

## Problem

The plugin currently registers commands only inside NoneBot via `on_command(...)`. Telegram clients can execute these commands, but they do not show up in the native slash-command picker because the bot never calls Telegram's command registration API.

## Constraints

- Existing command names and semantics must remain unchanged.
- Chinese descriptions should be consistent across code and documentation.
- Failure to sync the Telegram command menu must not break the bot's runtime behavior.
- The implementation should avoid maintaining command metadata in multiple places.

## Proposed Approach

Add a single command metadata source that defines each slash command and its Chinese description. Use that metadata in two places:

- build the Telegram `BotCommand` payload used to sync the command menu
- generate plugin-facing command summary text such as metadata usage/help strings and README command descriptions

Hook command sync into plugin startup so Telegram receives the command list as soon as the bot is ready. If the API call fails, log a warning and continue without affecting command handling.

## Affected Areas

- `src/nonebot_plugin_codex/__init__.py`
  - centralize command metadata
  - trigger Telegram command sync on startup
- new command metadata helper module
  - define slash commands and Chinese descriptions
  - expose Telegram-compatible command objects
- tests
  - verify Telegram command payload generation
  - verify startup sync tolerates API failures
- `README.md`
  - keep command description table aligned with the metadata wording

## Data Flow

1. Plugin startup builds the runtime service and handlers as before.
2. Startup hook resolves the active Telegram bot instance.
3. The bot receives `set_my_commands(...)` with the plugin command list.
4. Telegram clients cache and display the slash-command menu for the bot.

## Error Handling

- If Telegram command sync fails, catch the exception, log a warning, and keep the plugin running.
- Do not retry aggressively during startup; a later restart is enough to resync after configuration or network recovery.

## Testing Strategy

- Unit test the command metadata output, including command names and Chinese descriptions.
- Unit test startup sync behavior with a fake bot to confirm `set_my_commands(...)` is called correctly.
- Unit test startup sync failure handling so exceptions do not escape.
- Run focused tests, then full `pytest` and `ruff`.

## Risks

- README and runtime metadata can drift if command descriptions are duplicated manually.
- Startup hook behavior can vary if NoneBot startup lifecycles are misunderstood.

## Mitigation

- Keep command descriptions in a single Python module and reuse them wherever possible.
- Implement startup sync in a small helper with direct tests against the hook behavior.
