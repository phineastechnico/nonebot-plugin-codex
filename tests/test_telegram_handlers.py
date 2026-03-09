from __future__ import annotations

from typing import Any
from types import SimpleNamespace
from dataclasses import field, dataclass

import pytest

from nonebot_plugin_codex.telegram import TelegramHandlers
from nonebot_plugin_codex.service import ChatSession, encode_browser_callback


@dataclass
class FakeMessage:
    text: str = ""

    def extract_plain_text(self) -> str:
        return self.text


@dataclass
class FakeChat:
    type: str = "private"
    id: int = 1


@dataclass
class FakeEvent:
    text: str = ""
    chat: FakeChat = field(default_factory=FakeChat)

    def get_plaintext(self) -> str:
        return self.text


@dataclass
class FakeCallbackEvent:
    data: str
    id: str = "callback-1"
    chat: FakeChat = field(default_factory=FakeChat)
    message: Any = field(default_factory=lambda: SimpleNamespace(message_id=1))


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.edited: list[dict[str, Any]] = []
        self.answered: list[dict[str, Any]] = []

    async def send(self, event: FakeEvent, text: str, **kwargs: Any) -> SimpleNamespace:
        payload = {"chat_id": event.chat.id, "text": text, **kwargs}
        self.sent.append(payload)
        return SimpleNamespace(message_id=len(self.sent))

    async def send_message(
        self, *, chat_id: int, text: str, **kwargs: Any
    ) -> SimpleNamespace:
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        self.sent.append(payload)
        return SimpleNamespace(message_id=len(self.sent))

    async def edit_message_text(
        self, *, chat_id: int, message_id: int, text: str, **kwargs: Any
    ) -> None:
        self.edited.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                **kwargs,
            }
        )

    async def answer_callback_query(self, callback_id: str, **kwargs: Any) -> None:
        self.answered.append({"id": callback_id, **kwargs})


class FakeService:
    def __init__(self) -> None:
        self.session = ChatSession()
        self.settings = SimpleNamespace(chunk_size=3500)
        self.browser_text = "目录浏览"
        self.history_text = "Codex 历史会话"
        self.default_mode = "resume"
        self.execute_calls: list[tuple[str, str | None]] = []
        self.browser_token = "token"
        self.browser_version = 1
        self.browser_applied = False

    def get_session(self, chat_key: str) -> ChatSession:
        return self.session

    def activate_chat(self, chat_key: str) -> ChatSession:
        self.session.active = True
        return self.session

    def get_preferences(self, chat_key: str) -> SimpleNamespace:
        return SimpleNamespace(default_mode=self.default_mode)

    def describe_preferences(self, chat_key: str) -> str:
        return "模型: gpt-5 | 推理: xhigh | 权限: safe"

    async def run_prompt(
        self,
        chat_key: str,
        prompt: str,
        *,
        mode_override: str | None = None,
        on_progress=None,
        on_stream_text=None,
    ):  # noqa: ANN001,E501
        self.execute_calls.append((prompt, mode_override))
        return SimpleNamespace(
            cancelled=False,
            exit_code=0,
            final_text="完成",
            notice="",
            diagnostics=[],
        )

    async def reset_chat(self, chat_key: str, *, keep_active: bool) -> ChatSession:
        self.session = ChatSession(active=keep_active)
        return self.session

    def open_directory_browser(self, chat_key: str) -> SimpleNamespace:
        return SimpleNamespace(token="token")

    def render_directory_browser(self, chat_key: str) -> tuple[str, None]:
        return self.browser_text, None

    def remember_browser_message(
        self, chat_key: str, token: str, message_id: int | None
    ) -> None:
        return None

    async def update_workdir(self, chat_key: str, target: str) -> str:
        return f"当前工作目录：{target}"

    def get_browser(self, chat_key: str) -> SimpleNamespace:
        return SimpleNamespace(
            token=self.browser_token, version=self.browser_version, message_id=1
        )

    async def apply_browser_directory(
        self, chat_key: str, token: str, version: int
    ) -> str:
        self.browser_applied = True
        return "当前工作目录：/tmp/work"

    def navigate_directory_browser(
        self,
        chat_key: str,
        token: str,
        version: int,
        action: str,
        index: int | None = None,
    ) -> None:
        return None

    def close_directory_browser(self, chat_key: str, token: str, version: int) -> None:
        return None

    async def refresh_history_sessions(self) -> list[Any]:
        return []

    def open_history_browser(self, chat_key: str) -> SimpleNamespace:
        return SimpleNamespace(token="history")

    def render_history_browser(self, chat_key: str) -> tuple[str, None]:
        return self.history_text, None

    def remember_history_browser_message(
        self, chat_key: str, token: str, message_id: int | None
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_handle_codex_without_prompt_sends_status_message() -> None:
    service = FakeService()
    handlers = TelegramHandlers(service)
    bot = FakeBot()
    event = FakeEvent("")

    await handlers.handle_codex(bot, event, FakeMessage(""))

    assert "Codex 已连接" in bot.sent[0]["text"]
    assert "当前模式" in bot.sent[0]["text"]


@pytest.mark.asyncio
async def test_handle_exec_requires_prompt() -> None:
    handlers = TelegramHandlers(FakeService())
    bot = FakeBot()

    await handlers.handle_exec(bot, FakeEvent(""), FakeMessage(""))

    assert bot.sent[0]["text"] == "请在 /exec 后输入要执行的内容。"


@pytest.mark.asyncio
async def test_handle_cd_without_target_opens_browser() -> None:
    handlers = TelegramHandlers(FakeService())
    bot = FakeBot()

    await handlers.handle_cd(bot, FakeEvent(""), FakeMessage(""))

    assert bot.sent[0]["text"] == "目录浏览"


@pytest.mark.asyncio
async def test_handle_sessions_opens_history_browser() -> None:
    handlers = TelegramHandlers(FakeService())
    bot = FakeBot()

    await handlers.handle_sessions(bot, FakeEvent(""))

    assert bot.sent[0]["text"] == "Codex 历史会话"


@pytest.mark.asyncio
async def test_handle_follow_up_rejects_when_running() -> None:
    service = FakeService()
    service.session.active = True
    service.session.running = True
    handlers = TelegramHandlers(service)
    bot = FakeBot()

    await handlers.handle_follow_up(bot, FakeEvent("继续"))

    assert bot.sent[0]["text"] == "Codex 正在运行中，请等待完成或使用 /stop。"


@pytest.mark.asyncio
async def test_handle_browser_callback_apply_updates_directory() -> None:
    service = FakeService()
    handlers = TelegramHandlers(service)
    bot = FakeBot()
    event = FakeCallbackEvent(
        encode_browser_callback(service.browser_token, service.browser_version, "apply")
    )

    await handlers.handle_browser_callback(bot, event)

    assert service.browser_applied is True
    assert bot.answered[0]["text"] == "工作目录已更新。"
