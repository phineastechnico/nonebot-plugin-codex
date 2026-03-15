# Telegram Group Command Menu Design

## Goal

Extend Telegram slash-command registration so the same command menu is visible to all group chat members as well as private chat users.

## Problem

The current implementation only syncs commands to the `all_private_chats` scope. That means private chats show the slash-command picker, but group chats do not.

## Constraints

- Keep the same command set and Chinese descriptions across private chats and group chats.
- Do not change command handling semantics or permissions in message processing.
- If one Telegram scope fails to sync, the bot must continue running.

## Proposed Approach

Reuse the existing shared command metadata and register it into two Telegram scopes:

- `BotCommandScopeAllPrivateChats`
- `BotCommandScopeAllGroupChats`

The startup hook remains the single sync entrypoint. It iterates through both scopes and sends the same command payload to each.

## Testing Strategy

- Update startup sync tests to assert two `set_my_commands(...)` calls with private and group scopes.
- Add a failure test that one scope failing does not raise and returns an overall failure result.
