from __future__ import annotations

from pathlib import Path

from nonebot_plugin_codex.config import Config


def test_config_accepts_new_field_names() -> None:
    config = Config.model_validate(
        {
            "codex_binary": "codex-bin",
            "codex_workdir": "/tmp/workdir",
            "codex_session_index_path": "/tmp/session_index.jsonl",
        }
    )

    assert config.codex_binary == "codex-bin"
    assert config.codex_workdir == Path("/tmp/workdir")
    assert config.codex_session_index_path == Path("/tmp/session_index.jsonl")


def test_config_accepts_legacy_bridge_aliases() -> None:
    config = Config.model_validate(
        {
            "codex_bridge_binary": "legacy-bin",
            "codex_bridge_workdir": "/tmp/legacy",
            "codex_bridge_preferences_path": "data/codex_bridge/preferences.json",
        }
    )

    assert config.codex_binary == "legacy-bin"
    assert config.codex_workdir == Path("/tmp/legacy")
    assert config.codex_preferences_path == Path("data/codex_bridge/preferences.json")
