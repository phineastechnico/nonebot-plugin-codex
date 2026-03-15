from __future__ import annotations

from pathlib import Path

from nonebot_plugin_codex.config import Config
from nonebot_plugin_codex.runtime import build_service_settings


def test_build_service_settings_uses_plugin_data_dir_for_preferences(
    tmp_path: Path,
) -> None:
    workdir = tmp_path / "workspace"
    plugin_data_dir = tmp_path / "plugin-data"
    config = Config(codex_binary="codex-bin", codex_workdir=workdir)

    settings = build_service_settings(config, plugin_data_dir=plugin_data_dir)

    assert settings.binary == "codex-bin"
    assert settings.workdir == str(workdir)
    assert settings.preferences_path == plugin_data_dir / "preferences.json"
    assert settings.models_cache_path == Path.home() / ".codex" / "models_cache.json"
    assert settings.codex_config_path == Path.home() / ".codex" / "config.toml"
    assert settings.session_index_path == Path.home() / ".codex" / "session_index.jsonl"
    assert settings.sessions_dir == Path.home() / ".codex" / "sessions"
    assert settings.archived_sessions_dir == Path.home() / ".codex" / "archived_sessions"
