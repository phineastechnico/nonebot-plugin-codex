from __future__ import annotations

from typing import Any

import pytest

from nonebot_plugin_codex import sync_telegram_commands
from nonebot_plugin_codex.telegram_commands import build_telegram_commands


class FakeTelegramBot:
    def __init__(self, *, failed_scope_types: set[str] | None = None) -> None:
        self.failed_scope_types = failed_scope_types or set()
        self.calls: list[dict[str, Any]] = []

    async def set_my_commands(self, commands, scope=None, language_code=None) -> bool:
        self.calls.append(
            {
                "commands": commands,
                "scope": scope,
                "language_code": language_code,
            }
        )
        scope_type = getattr(scope, "type", None)
        if scope_type in self.failed_scope_types:
            raise RuntimeError(f"telegram unavailable for {scope_type}")
        return True


@pytest.mark.asyncio
async def test_sync_telegram_commands_registers_private_and_group_chat_menus() -> None:
    bot = FakeTelegramBot()

    synced = await sync_telegram_commands(bot)

    assert synced is True
    assert len(bot.calls) == 2
    assert [command.model_dump() for command in bot.calls[0]["commands"]] == [
        command.model_dump() for command in build_telegram_commands()
    ]
    assert [command.model_dump() for command in bot.calls[1]["commands"]] == [
        command.model_dump() for command in build_telegram_commands()
    ]
    assert bot.calls[0]["scope"].model_dump() == {"type": "all_private_chats"}
    assert bot.calls[1]["scope"].model_dump() == {"type": "all_group_chats"}
    assert bot.calls[0]["language_code"] is None
    assert bot.calls[1]["language_code"] is None


@pytest.mark.asyncio
async def test_sync_telegram_commands_logs_and_swallows_partial_failures(
    monkeypatch,
) -> None:
    bot = FakeTelegramBot(failed_scope_types={"all_group_chats"})
    warnings: list[str] = []

    class FakeLogger:
        def warning(self, message: str) -> None:
            warnings.append(message)

    monkeypatch.setattr("nonebot_plugin_codex.logger", FakeLogger())

    synced = await sync_telegram_commands(bot)

    assert synced is False
    assert len(bot.calls) == 2
    assert warnings == [
        "Telegram 命令菜单同步失败（all_group_chats）：telegram unavailable for "
        "all_group_chats"
    ]
