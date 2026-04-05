from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
import sys

import pytest

from nonebot_plugin_codex.native_client import NativeThreadSummary
from nonebot_plugin_codex.service import (
    RunResult,
    _ensure_agent_panel,
    CodexBridgeService,
    CodexBridgeSettings,
    HistoricalSessionSummary,
    build_exec_argv,
    chunk_text,
    format_result_text,
)


class DummyNativeClient:
    def __init__(
        self,
        threads: list[NativeThreadSummary] | None = None,
        *,
        rate_limits: dict[str, object] | None = None,
        rate_limit_error: Exception | None = None,
    ) -> None:
        self._threads = threads or []
        self.compact_calls: list[str] = []
        self.compact_notice = "已压缩当前 resume 会话上下文。"
        self.resume_calls: list[str] = []
        self.require_resume_before_compact = False
        self.rate_limits = rate_limits
        self.rate_limit_error = rate_limit_error

    def clone(self) -> DummyNativeClient:
        clone = DummyNativeClient(
            list(self._threads),
            rate_limits=self.rate_limits,
            rate_limit_error=self.rate_limit_error,
        )
        clone.compact_notice = self.compact_notice
        clone.require_resume_before_compact = self.require_resume_before_compact
        return clone

    async def close(self, timeout: float = 5.0) -> None:
        return None

    async def list_threads(self) -> list[NativeThreadSummary]:
        return list(self._threads)

    async def resume_thread(
        self,
        thread_id: str,
        *,
        workdir: str,
        model: str,
        reasoning_effort: str,
        permission_mode: str,
    ) -> NativeThreadSummary:
        self.resume_calls.append(thread_id)
        return NativeThreadSummary(
            thread_id=thread_id,
            thread_name="Native Session",
            updated_at="2025-03-01T00:00:00Z",
            cwd=workdir,
            source_kind="cli",
        )

    async def compact_thread(self, thread_id: str) -> str:
        if self.require_resume_before_compact and thread_id not in self.resume_calls:
            raise RuntimeError(f"thread not found: {thread_id}")
        self.compact_calls.append(thread_id)
        return self.compact_notice

    async def read_rate_limits(self) -> dict[str, object]:
        if self.rate_limit_error is not None:
            raise self.rate_limit_error
        if self.rate_limits is None:
            raise RuntimeError("rate limits unavailable")
        return self.rate_limits


def make_service(
    tmp_path: Path,
    model_cache_file: Path,
    *,
    threads: list[NativeThreadSummary] | None = None,
    rate_limits: dict[str, object] | None = None,
    rate_limit_error: Exception | None = None,
    launcher=None,
    stream_read_limit: int = 1024 * 1024,
) -> CodexBridgeService:
    codex_config = tmp_path / "config.toml"
    codex_config.write_text('model = "gpt-5"\nmodel_reasoning_effort = "xhigh"\n')
    return CodexBridgeService(
        CodexBridgeSettings(
            binary="codex",
            workdir=str(tmp_path),
            models_cache_path=model_cache_file,
            codex_config_path=codex_config,
            stream_read_limit=stream_read_limit,
            preferences_path=(
                tmp_path / "data" / "nonebot_plugin_codex" / "preferences.json"
            ),
            session_index_path=tmp_path / ".codex" / "session_index.jsonl",
            sessions_dir=tmp_path / ".codex" / "sessions",
            archived_sessions_dir=tmp_path / ".codex" / "archived_sessions",
        ),
        launcher=launcher,
        native_client=DummyNativeClient(
            threads,
            rate_limits=rate_limits,
            rate_limit_error=rate_limit_error,
        ),
        which_resolver=lambda _: "/usr/bin/codex",
    )


def make_service_without_model_cache(tmp_path: Path) -> CodexBridgeService:
    codex_config = tmp_path / "config.toml"
    codex_config.write_text('model = "gpt-5"\nmodel_reasoning_effort = "xhigh"\n')
    return CodexBridgeService(
        CodexBridgeSettings(
            binary="codex",
            workdir=str(tmp_path),
            models_cache_path=tmp_path / "missing-models.json",
            codex_config_path=codex_config,
            preferences_path=(
                tmp_path / "data" / "nonebot_plugin_codex" / "preferences.json"
            ),
            session_index_path=tmp_path / ".codex" / "session_index.jsonl",
            sessions_dir=tmp_path / ".codex" / "sessions",
            archived_sessions_dir=tmp_path / ".codex" / "archived_sessions",
        ),
        which_resolver=lambda _: "/usr/bin/codex",
    )


def write_history_session(
    tmp_path: Path,
    *,
    session_id: str = "exec-1",
    thread_name: str = "Exec Session",
    user_text: str = "user hello",
    assistant_text: str = "assistant world",
) -> Path:
    index_path = tmp_path / ".codex" / "session_index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(
            {
                "id": session_id,
                "thread_name": thread_name,
                "updated_at": "2025-03-01T00:00:02Z",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    session_path = (
        tmp_path / ".codex" / "sessions" / "2025" / "03" / f"{session_id}.jsonl"
    )
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2025-03-01T00:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": session_id,
                            "cwd": str(tmp_path / "workspace"),
                            "source": "exec",
                            "timestamp": "2025-03-01T00:00:02Z",
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2025-03-01T00:00:01Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "user_message",
                            "message": user_text,
                        },
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "timestamp": "2025-03-01T00:00:02Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": assistant_text,
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return session_path


def test_build_exec_argv_for_safe_and_resume_mode() -> None:
    argv = build_exec_argv(
        "codex",
        "/tmp/work",
        "hello",
        model="gpt-5",
        reasoning_effort="xhigh",
        permission_mode="safe",
        thread_id="thread-1",
    )

    assert argv[:3] == ["codex", "exec", "resume"]
    assert "--full-auto" in argv
    assert "--sandbox" not in argv
    assert argv[-2:] == ["thread-1", "hello"]


def test_chunk_text_preserves_whitespace_and_newlines() -> None:
    text = "  foo\n  bar\nbaz  "

    chunks = chunk_text(text, 6)

    assert "".join(chunks) == text


def test_default_preferences_use_configured_workdir(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)

    preferences = service.get_preferences("private_1")

    assert preferences.workdir == str(tmp_path.resolve())


def test_default_preferences_use_codex_config_when_model_cache_is_missing(
    tmp_path: Path,
) -> None:
    service = make_service_without_model_cache(tmp_path)

    preferences = service.get_preferences("private_1")

    assert preferences.model == "gpt-5"
    assert preferences.reasoning_effort == "xhigh"
    assert preferences.workdir == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_render_status_panel_shows_rate_limit_summary(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    primary_resets_at = int(
        (datetime.now().astimezone() + timedelta(hours=2, minutes=5)).timestamp()
    )
    secondary_resets_at = int(
        (datetime.now().astimezone() + timedelta(days=3, hours=4)).timestamp()
    )
    service = make_service(
        tmp_path,
        model_cache_file,
        rate_limits={
            "limitId": "codex",
            "primary": {
                "usedPercent": 48,
                "windowDurationMins": 300,
                "resetsAt": primary_resets_at,
            },
            "secondary": {
                "usedPercent": 38,
                "windowDurationMins": 10080,
                "resetsAt": secondary_resets_at,
            },
        },
    )
    session = service.get_session("private_1")
    session.context_used_tokens = 12345
    session.context_window_tokens = 200000

    panel = service.open_status_panel("private_1")
    text, markup = await service.render_status_panel("private_1")
    primary_reset_text = service._format_status_reset_time(primary_resets_at)  # noqa: SLF001
    secondary_reset_text = service._format_status_reset_time(secondary_resets_at)  # noqa: SLF001

    assert "当前额度状态" in text
    assert "上午窗口" not in text
    assert "下午窗口" not in text
    assert "上下文：12,345 / 200,000 tokens" in text
    assert "5小时：剩余 52%" in text
    assert f"5小时刷新时间：{primary_reset_text}" in text
    assert "1周：剩余 62%" in text
    assert f"1周刷新时间：{secondary_reset_text}" in text
    assert markup.inline_keyboard[0][0].text == "刷新"
    assert markup.inline_keyboard[0][0].callback_data == (
        f"cst:{panel.token}:{panel.version}:refresh"
    )
    assert markup.inline_keyboard[0][1].text == "关闭"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("primary_used_percent", "secondary_used_percent"),
    [
        (0.48, 0.38),
        (4800, 3800),
    ],
)
async def test_render_status_panel_normalizes_rate_limit_percent_units(
    tmp_path: Path,
    model_cache_file: Path,
    primary_used_percent: float,
    secondary_used_percent: float,
) -> None:
    service = make_service(
        tmp_path,
        model_cache_file,
        rate_limits={
            "limitId": "codex",
            "primary": {
                "usedPercent": primary_used_percent,
                "windowDurationMins": 300,
                "resetsAt": int(datetime.now().astimezone().timestamp()) + 3600,
            },
            "secondary": {
                "usedPercent": secondary_used_percent,
                "windowDurationMins": 10080,
                "resetsAt": int(datetime.now().astimezone().timestamp()) + 7200,
            },
        },
    )

    service.open_status_panel("private_1")
    text, _markup = await service.render_status_panel("private_1")

    assert "5小时：剩余 52%" in text
    assert "1周：剩余 62%" in text


@pytest.mark.asyncio
async def test_render_status_panel_degrades_cleanly_when_rate_limits_unavailable(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(
        tmp_path,
        model_cache_file,
        rate_limit_error=RuntimeError("Codex app-server 请求失败。"),
    )

    service.open_status_panel("private_1")
    text, _markup = await service.render_status_panel("private_1")

    assert "当前额度状态" in text
    assert "上下文：暂不可用" in text
    assert "额度状态：暂不可用" in text
    assert "Codex app-server 请求失败。" in text


@pytest.mark.asyncio
async def test_reset_chat_clears_status_context_usage(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session = service.get_session("private_1")
    session.context_used_tokens = 12345
    session.context_window_tokens = 200000

    await service.reset_chat("private_1", keep_active=False)

    assert session.context_used_tokens is None
    assert session.context_window_tokens is None


@pytest.mark.asyncio
async def test_update_workdir_clears_status_context_usage(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session = service.get_session("private_1")
    session.context_used_tokens = 12345
    session.context_window_tokens = 200000
    target = tmp_path / "workspace"
    target.mkdir()

    await service.update_workdir("private_1", str(target))

    assert session.context_used_tokens is None
    assert session.context_window_tokens is None


def test_chat_session_tracks_agent_panels_in_creation_order(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session = service.get_session("private_1")

    main_panel = _ensure_agent_panel(session, "main")
    first_sub = _ensure_agent_panel(session, "thread-sub-1")
    second_sub = _ensure_agent_panel(session, "thread-sub-2")

    assert main_panel.agent_label == "主 agent"
    assert first_sub.agent_label == "子 agent 1"
    assert second_sub.agent_label == "子 agent 2"
    assert session.agent_order == ["main", "thread-sub-1", "thread-sub-2"]


def test_directory_browser_home_uses_configured_workdir(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    outside_dir = tmp_path.parent

    browser = service._replace_browser_state(  # noqa: SLF001
        "private_1",
        str(outside_dir),
        page=0,
    )

    browser = service.navigate_directory_browser(
        "private_1",
        browser.token,
        browser.version,
        "home",
    )

    assert browser.current_path == str(tmp_path.resolve())


def test_load_models_reuses_cached_result_when_file_unchanged(
    tmp_path: Path,
    model_cache_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    calls = 0
    path_type = type(model_cache_file)
    original_read_text = path_type.read_text

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        nonlocal calls
        if self == model_cache_file:
            calls += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "read_text", counting_read_text)

    first = service.load_models()
    second = service.load_models()

    assert set(first) == {"gpt-5", "gpt-4.1"}
    assert set(second) == {"gpt-5", "gpt-4.1"}
    assert calls == 1


@pytest.mark.asyncio
async def test_update_default_mode_persists_preference_and_switches_active_mode(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session = service.activate_chat("private_1")
    session.thread_id = "legacy"
    session.exec_thread_id = "exec-1"
    session.native_thread_id = "native-1"

    notice = await service.update_default_mode("private_1", "exec")

    assert notice == "当前默认模式：exec"
    assert session.thread_id == "exec-1"
    assert session.native_thread_id == "native-1"
    stored = json.loads(service.settings.preferences_path.read_text(encoding="utf-8"))
    assert stored["private_1"]["default_mode"] == "exec"


@pytest.mark.asyncio
async def test_update_default_mode_accepts_plan(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)

    notice = await service.update_default_mode("private_1", "plan")

    assert notice == "当前默认模式：plan"
    assert service.get_preferences("private_1").default_mode == "plan"


@pytest.mark.asyncio
async def test_update_workdir_clears_bound_threads(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(
        tmp_path,
        model_cache_file,
        threads=[
            NativeThreadSummary(
                thread_id="native-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=str(tmp_path / "missing"),
                source_kind="cli",
            )
        ],
    )
    target_dir = tmp_path / "workspace"
    target_dir.mkdir()
    session = service.activate_chat("private_1")
    session.thread_id = "legacy"
    session.exec_thread_id = "exec-1"
    session.native_thread_id = "native-1"

    notice = await service.update_workdir("private_1", str(target_dir))

    assert str(target_dir.resolve()) in notice
    assert session.thread_id is None
    assert session.exec_thread_id is None
    assert session.native_thread_id is None


@pytest.mark.asyncio
async def test_apply_history_session_uses_existing_cwd_when_original_missing(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(
        tmp_path,
        model_cache_file,
        threads=[
            NativeThreadSummary(
                thread_id="native-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=str(tmp_path / "missing"),
                source_kind="cli",
            )
        ],
    )
    current_dir = tmp_path / "current"
    current_dir.mkdir()
    await service.update_workdir("private_1", str(current_dir))
    await service.refresh_history_sessions()
    browser = service._replace_history_browser_state(  # noqa: SLF001
        "private_1",
        page=0,
        scope="resume",
        selected_session_id="native-1",
    )
    browser.entries = [
        HistoricalSessionSummary(
            session_id="native-1",
            thread_name="Native Session",
            updated_at="2025-03-01T00:00:00Z",
            kind="native",
            cwd=str(tmp_path / "missing"),
        )
    ]
    notice = await service.apply_history_session(
        "private_1", browser.token, browser.version
    )

    assert "原工作目录不存在，已保留当前工作目录。" in notice
    assert f"当前工作目录：{current_dir.resolve()}" in notice


@pytest.mark.asyncio
async def test_compact_chat_uses_bound_native_resume_thread(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session = service.activate_chat("private_1")
    session.active_mode = "resume"
    session.native_thread_id = "native-1"
    session.thread_id = "native-1"

    notice = await service.compact_chat("private_1")

    assert notice == "已压缩当前 resume 会话上下文。"
    assert service.native_client.resume_calls == ["native-1"]
    assert service.native_client.compact_calls == ["native-1"]


@pytest.mark.asyncio
async def test_compact_chat_resumes_thread_before_compacting(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    service.native_client.require_resume_before_compact = True
    session = service.activate_chat("private_1")
    session.active_mode = "resume"
    session.native_thread_id = "native-1"
    session.thread_id = "native-1"

    notice = await service.compact_chat("private_1")

    assert notice == "已压缩当前 resume 会话上下文。"
    assert service.native_client.resume_calls == ["native-1"]
    assert service.native_client.compact_calls == ["native-1"]


@pytest.mark.asyncio
async def test_compact_chat_requires_bound_native_resume_thread(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)

    with pytest.raises(ValueError, match="当前聊天没有可压缩的 resume 会话。"):
        await service.compact_chat("private_1")


@pytest.mark.asyncio
async def test_refresh_history_sessions_keeps_exec_list_entries_lightweight_until_open(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    write_history_session(tmp_path)

    entries = await service.refresh_history_sessions()

    exec_entry = next(entry for entry in entries if entry.session_id == "exec-1")
    assert exec_entry.preview == "Exec Session"
    assert exec_entry.last_user_text is None
    assert exec_entry.last_assistant_text is None

    browser = service._replace_history_browser_state(  # noqa: SLF001
        "private_1",
        page=0,
        scope="exec",
        selected_session_id="exec-1",
    )
    selected = next(entry for entry in browser.entries if entry.session_id == "exec-1")

    assert selected.preview == "assistant world"
    assert selected.last_user_text == "user hello"
    assert selected.last_assistant_text == "assistant world"


@pytest.mark.asyncio
async def test_refresh_history_sessions_collects_history_logs_once_with_native_client(
    tmp_path: Path,
    model_cache_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(
        tmp_path,
        model_cache_file,
        threads=[
            NativeThreadSummary(
                thread_id="native-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=str(tmp_path / "workspace"),
                source_kind="cli",
                preview="native preview",
            )
        ],
    )
    write_history_session(tmp_path)
    calls = 0
    original = service._collect_history_log_summaries  # noqa: SLF001

    def counting_collect_history_log_summaries(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        service,
        "_collect_history_log_summaries",
        counting_collect_history_log_summaries,
    )

    await service.refresh_history_sessions()

    assert calls == 1


def test_list_history_sessions_reuses_cached_exec_log_summary_when_file_unchanged(
    tmp_path: Path,
    model_cache_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    session_path = write_history_session(tmp_path)
    calls = 0
    path_type = type(session_path)
    original_open = path_type.open

    def counting_open(self: Path, *args: object, **kwargs: object):
        nonlocal calls
        if self == session_path:
            calls += 1
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(path_type, "open", counting_open)

    service.list_history_sessions()
    service.list_history_sessions()

    assert calls == 1


@pytest.mark.parametrize(
    ("kind", "expected_heading"),
    [
        ("mode", "模式设置"),
        ("model", "模型设置"),
        ("effort", "推理强度设置"),
        ("permission", "权限模式设置"),
    ],
)
def test_render_setting_panels_show_expected_headings(
    tmp_path: Path,
    model_cache_file: Path,
    kind: str,
    expected_heading: str,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    service.activate_chat("private_1")

    service.open_setting_panel("private_1", kind)
    text, markup = service.render_setting_panel("private_1")

    assert expected_heading in text
    assert markup.inline_keyboard


def test_render_mode_setting_panel_shows_plan_option(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)

    service.open_setting_panel("private_1", "mode")
    _, markup = service.render_setting_panel("private_1")

    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data is not None
    ]
    assert any(callback.endswith(":set:plan") for callback in callbacks)


def test_render_workspace_panel_shows_current_state_and_recent_history(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)
    workdir = tmp_path / "workspace"
    workdir.mkdir()
    service.preference_overrides["private_1"] = service._default_preferences()  # noqa: SLF001
    service.preference_overrides["private_1"].workdir = str(workdir.resolve())
    session = service.activate_chat("private_1")
    session.active_mode = "exec"
    session.exec_thread_id = "exec-1"
    session.thread_id = "exec-1"
    write_history_session(
        tmp_path,
        session_id="exec-1",
        thread_name="Recent Session",
        assistant_text="assistant world",
    )

    service.open_workspace_panel("private_1")
    text, markup = service.render_workspace_panel("private_1")

    assert "当前工作台" in text
    assert "当前模式：exec" in text
    assert "模型: gpt-5 | 推理: xhigh | 权限: safe" in text
    assert f"当前工作目录：{workdir.resolve()}" in text
    assert "当前会话：exec | exec-1" in text
    assert "Recent Session" in text
    assert markup.inline_keyboard


def test_navigate_workspace_panel_refresh_reuses_token_and_bumps_version(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_file)

    panel = service.open_workspace_panel("private_1")
    refreshed = service.navigate_workspace_panel(
        "private_1",
        panel.token,
        panel.version,
        "refresh",
    )

    assert refreshed.token == panel.token
    assert refreshed.version == panel.version + 1


@pytest.mark.asyncio
async def test_apply_permission_setting_panel_updates_preference(
    tmp_path: Path, model_cache_file: Path
) -> None:
    service = make_service(tmp_path, model_cache_file)
    panel = service.open_setting_panel("private_1", "permission")

    notice = await service.apply_setting_panel_selection(
        "private_1",
        panel.token,
        panel.version,
        "danger",
    )

    assert "danger" in notice
    assert service.get_preferences("private_1").permission_mode == "danger"


@pytest.mark.asyncio
async def test_apply_effort_setting_panel_accepts_model_supported_medium(
    tmp_path: Path,
    model_cache_with_medium_file: Path,
) -> None:
    service = make_service(tmp_path, model_cache_with_medium_file)
    panel = service.open_setting_panel("private_1", "effort")
    text, _ = service.render_setting_panel("private_1")

    assert "medium" in text

    notice = await service.apply_setting_panel_selection(
        "private_1",
        panel.token,
        panel.version,
        "medium",
    )

    assert "medium" in notice
    assert service.get_preferences("private_1").reasoning_effort == "medium"


@pytest.mark.asyncio
async def test_run_prompt_exec_ignores_large_stderr_frames(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    huge_stderr = "E" * 4096
    completed_payload = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "done"},
    }
    script = (
        "import json, sys\n"
        f"huge_stderr = {huge_stderr!r}\n"
        "messages = [\n"
        "    {'type': 'thread.started', 'thread_id': 'exec-1'},\n"
        "    {'type': 'turn.started'},\n"
        f"    {completed_payload!r},\n"
        "]\n"
        "sys.stderr.write(huge_stderr + '\\n')\n"
        "sys.stderr.flush()\n"
        "for message in messages:\n"
        "    sys.stdout.write(json.dumps(message) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )

    async def launcher(*_args, **kwargs):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    service = make_service(
        tmp_path,
        model_cache_file,
        launcher=launcher,
        stream_read_limit=1024,
    )

    result = await service.run_prompt("private_1", "hello", mode_override="exec")

    assert result.exit_code == 0
    assert result.final_text == "done"


@pytest.mark.asyncio
async def test_run_prompt_exec_returns_friendly_protocol_error_and_cleans_up(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    long_text = "A" * 4096
    completed_payload = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": long_text},
    }
    script = (
        "import json, sys\n"
        f"long_text = {long_text!r}\n"
        "messages = [\n"
        "    {'type': 'thread.started', 'thread_id': 'exec-1'},\n"
        "    {'type': 'turn.started'},\n"
        f"    {completed_payload!r},\n"
        "]\n"
        "for message in messages:\n"
        "    sys.stdout.write(json.dumps(message) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )

    async def launcher(*_args, **kwargs):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    service = make_service(
        tmp_path,
        model_cache_file,
        launcher=launcher,
        stream_read_limit=1024,
    )

    result = await service.run_prompt("private_1", "hello", mode_override="exec")
    session = service.get_session("private_1")

    assert result.exit_code == 1
    assert any("codex_stream_read_limit" in line for line in result.diagnostics)
    assert session.running is False
    assert session.process is None


@pytest.mark.asyncio
async def test_run_prompt_exec_preserves_agent_message_whitespace(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    streamed_text = "  done\n"
    completed_payload = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": streamed_text},
    }
    script = (
        "import json, sys\n"
        f"messages = [{completed_payload!r}]\n"
        "for message in messages:\n"
        "    sys.stdout.write(json.dumps(message) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )

    async def launcher(*_args, **kwargs):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    service = make_service(tmp_path, model_cache_file, launcher=launcher)

    result = await service.run_prompt("private_1", "hello", mode_override="exec")

    assert result.final_text == streamed_text


@pytest.mark.asyncio
async def test_run_prompt_resume_preserves_stream_whitespace(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    streamed_text = "  line 1\n  line 2\n"

    class StreamingNativeClient:
        def clone(self) -> StreamingNativeClient:
            return self

        async def close(self, timeout: float = 5.0) -> None:
            return None

        async def start_thread(
            self,
            *,
            workdir: str,
            model: str,
            reasoning_effort: str,
            permission_mode: str,
        ) -> NativeThreadSummary:
            return NativeThreadSummary(
                thread_id="thread-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=workdir,
                source_kind="cli",
            )

        async def resume_thread(self, *_args, **_kwargs) -> NativeThreadSummary:
            raise AssertionError("resume_thread should not be called")

        async def run_turn(
            self,
            thread_id: str,
            prompt: str,
            *,
            cwd: str,
            model: str,
            reasoning_effort: str,
            on_progress,
            on_stream_text,
            on_token_usage,
        ):
            await on_stream_text(
                type(
                    "NativeUpdate",
                    (),
                    {"agent_key": "main", "text": streamed_text},
                )()
            )
            return type(
                "NativeResult",
                (),
                {
                    "thread_id": thread_id,
                    "exit_code": 0,
                    "final_text": streamed_text,
                    "diagnostics": [],
                },
            )()

    service = make_service(tmp_path, model_cache_file)
    service.native_client = StreamingNativeClient()
    stream_updates: list[str] = []

    async def capture_stream(update) -> None:  # noqa: ANN001
        stream_updates.append(update.text)

    result = await service.run_prompt(
        "private_1",
        "hello",
        on_stream_text=capture_stream,
    )

    assert stream_updates == [streamed_text]
    assert result.final_text == streamed_text


def test_format_result_text_prefers_friendly_failure_notice() -> None:
    text = format_result_text(
        RunResult(
            exit_code=1,
            failure_notice=(
                "Codex 当前额度已用尽，请稍后重试或使用 /status 查看刷新时间。"
            ),
            diagnostics=["insufficient_quota"],
        )
    )

    assert text == "Codex 当前额度已用尽，请稍后重试或使用 /status 查看刷新时间。"


def test_format_result_text_keeps_regular_notice_and_failure_details() -> None:
    text = format_result_text(
        RunResult(
            exit_code=1,
            notice="原会话未成功恢复，已新开会话。",
            diagnostics=["boom"],
        )
    )

    assert text == "原会话未成功恢复，已新开会话。\n\nCodex 执行失败。\n\nboom"


@pytest.mark.asyncio
async def test_run_prompt_resume_surfaces_quota_exhausted_notice(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    class QuotaFailingNativeClient:
        def clone(self) -> QuotaFailingNativeClient:
            return self

        async def close(self, timeout: float = 5.0) -> None:
            return None

        async def start_thread(
            self,
            *,
            workdir: str,
            model: str,
            reasoning_effort: str,
            permission_mode: str,
        ) -> NativeThreadSummary:
            return NativeThreadSummary(
                thread_id="thread-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=workdir,
                source_kind="cli",
            )

        async def resume_thread(self, *_args, **_kwargs) -> NativeThreadSummary:
            raise AssertionError("resume_thread should not be called")

        async def run_turn(
            self,
            thread_id: str,
            prompt: str,
            *,
            cwd: str,
            model: str,
            reasoning_effort: str,
            on_progress,
            on_stream_text,
            on_token_usage,
        ):
            raise RuntimeError(
                "OpenAI API error: insufficient_quota: You exceeded your current quota."
            )

    service = make_service(tmp_path, model_cache_file)
    service.native_client = QuotaFailingNativeClient()

    result = await service.run_prompt("private_1", "hello")
    expected_notice = "Codex 当前额度已用尽，请稍后重试或使用 /status 查看刷新时间。"

    assert result.exit_code == 1
    assert result.failure_notice == expected_notice


@pytest.mark.asyncio
async def test_run_prompt_resume_surfaces_quota_notice_from_native_diagnostics(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    class NativeDiagnosticClient:
        def clone(self) -> NativeDiagnosticClient:
            return self

        async def close(self, timeout: float = 5.0) -> None:
            return None

        async def start_thread(
            self,
            *,
            workdir: str,
            model: str,
            reasoning_effort: str,
            permission_mode: str,
        ) -> NativeThreadSummary:
            return NativeThreadSummary(
                thread_id="thread-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=workdir,
                source_kind="cli",
            )

        async def resume_thread(self, *_args, **_kwargs) -> NativeThreadSummary:
            raise AssertionError("resume_thread should not be called")

        async def run_turn(
            self,
            thread_id: str,
            prompt: str,
            *,
            cwd: str,
            model: str,
            reasoning_effort: str,
            on_progress,
            on_stream_text,
            on_token_usage,
        ):
            return type(
                "NativeResult",
                (),
                {
                    "thread_id": thread_id,
                    "exit_code": 1,
                    "final_text": "",
                    "diagnostics": [
                        "insufficient_quota",
                        (
                            "You exceeded your current quota, please check "
                            "your plan and billing details."
                        ),
                    ],
                },
            )()

    service = make_service(tmp_path, model_cache_file)
    service.native_client = NativeDiagnosticClient()

    result = await service.run_prompt("private_1", "hello")

    assert result.exit_code == 1
    assert result.failure_notice == (
        "Codex 当前额度已用尽，请稍后重试或使用 /status 查看刷新时间。"
    )


@pytest.mark.asyncio
async def test_run_prompt_resume_preserves_usage_limit_retry_time(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    class NativeUsageLimitClient:
        def clone(self) -> NativeUsageLimitClient:
            return self

        async def close(self, timeout: float = 5.0) -> None:
            return None

        async def start_thread(
            self,
            *,
            workdir: str,
            model: str,
            reasoning_effort: str,
            permission_mode: str,
        ) -> NativeThreadSummary:
            return NativeThreadSummary(
                thread_id="thread-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=workdir,
                source_kind="cli",
            )

        async def resume_thread(self, *_args, **_kwargs) -> NativeThreadSummary:
            raise AssertionError("resume_thread should not be called")

        async def run_turn(
            self,
            thread_id: str,
            prompt: str,
            *,
            cwd: str,
            model: str,
            reasoning_effort: str,
            on_progress,
            on_stream_text,
            on_token_usage,
        ):
            return type(
                "NativeResult",
                (),
                {
                    "thread_id": thread_id,
                    "exit_code": 1,
                    "final_text": "",
                    "diagnostics": [
                        (
                            "You've hit your usage limit. To get more access now, "
                            "send a request to your admin or try again at "
                            "Mar 24th, 2026 1:04 PM."
                        ),
                    ],
                },
            )()

    service = make_service(tmp_path, model_cache_file)
    service.native_client = NativeUsageLimitClient()

    result = await service.run_prompt("private_1", "hello")

    assert result.exit_code == 1
    assert result.failure_notice == (
        "Codex 当前额度已用尽。\n"
        "You've hit your usage limit. To get more access now, send a request "
        "to your admin or try again at Mar 24th, 2026 1:04 PM."
    )


@pytest.mark.asyncio
async def test_run_prompt_resume_surfaces_rate_limit_notice(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    class RateLimitNativeClient:
        def clone(self) -> RateLimitNativeClient:
            return self

        async def close(self, timeout: float = 5.0) -> None:
            return None

        async def start_thread(
            self,
            *,
            workdir: str,
            model: str,
            reasoning_effort: str,
            permission_mode: str,
        ) -> NativeThreadSummary:
            return NativeThreadSummary(
                thread_id="thread-1",
                thread_name="Native Session",
                updated_at="2025-03-01T00:00:00Z",
                cwd=workdir,
                source_kind="cli",
            )

        async def resume_thread(self, *_args, **_kwargs) -> NativeThreadSummary:
            raise AssertionError("resume_thread should not be called")

        async def run_turn(
            self,
            thread_id: str,
            prompt: str,
            *,
            cwd: str,
            model: str,
            reasoning_effort: str,
            on_progress,
            on_stream_text,
            on_token_usage,
        ):
            raise RuntimeError("OpenAI API error: rate_limit_exceeded")

    service = make_service(tmp_path, model_cache_file)
    service.native_client = RateLimitNativeClient()

    result = await service.run_prompt("private_1", "hello")

    assert result.exit_code == 1
    assert result.failure_notice == (
        "Codex 当前请求过于频繁，请稍后重试或使用 /status 查看刷新时间。"
    )


@pytest.mark.asyncio
async def test_run_prompt_exec_surfaces_quota_exhausted_notice_from_diagnostics(
    tmp_path: Path,
    model_cache_file: Path,
) -> None:
    script = (
        "import sys\n"
        "sys.stderr.write('OpenAI API error: insufficient_quota\\n')\n"
        "sys.stderr.flush()\n"
        "raise SystemExit(1)\n"
    )

    async def launcher(*_args, **kwargs):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    service = make_service(tmp_path, model_cache_file, launcher=launcher)

    result = await service.run_prompt("private_1", "hello", mode_override="exec")

    assert result.exit_code == 1
    assert result.failure_notice == (
        "Codex 当前额度已用尽，请稍后重试或使用 /status 查看刷新时间。"
    )
