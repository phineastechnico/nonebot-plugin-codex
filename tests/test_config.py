from __future__ import annotations

from pathlib import Path

from nonebot_plugin_codex.config import Config


def _field_names() -> set[str]:
    if hasattr(Config, "model_fields"):
        return set(Config.model_fields)
    return set(Config.__fields__)


def test_config_only_exposes_supported_fields() -> None:
    assert _field_names() == {
        "codex_binary",
        "codex_workdir",
        "codex_kill_timeout",
        "codex_progress_history",
        "codex_diagnostic_history",
        "codex_chunk_size",
        "codex_stream_read_limit",
    }


def test_config_accepts_supported_field_values() -> None:
    config = Config(
        codex_binary="codex-bin",
        codex_workdir="/tmp/workdir",
        codex_kill_timeout=9.5,
        codex_progress_history=9,
        codex_diagnostic_history=30,
        codex_chunk_size=2048,
        codex_stream_read_limit=4096,
    )

    assert config.codex_binary == "codex-bin"
    assert config.codex_workdir == Path("/tmp/workdir")
    assert config.codex_kill_timeout == 9.5
    assert config.codex_progress_history == 9
    assert config.codex_diagnostic_history == 30
    assert config.codex_chunk_size == 2048
    assert config.codex_stream_read_limit == 4096


def test_config_defaults_stream_limit_to_8_mib() -> None:
    config = Config()

    assert config.codex_stream_read_limit == 8 * 1024 * 1024


def test_config_ignores_removed_legacy_fields() -> None:
    config = Config(
        legacy_binary="legacy-bin",
        legacy_workdir="/tmp/legacy",
    )

    assert config.codex_binary == "codex"
    assert config.codex_workdir == Path.home()
