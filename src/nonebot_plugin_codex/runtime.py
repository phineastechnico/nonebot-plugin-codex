from __future__ import annotations

from pathlib import Path

from .config import Config
from .service import CodexBridgeSettings


def build_service_settings(
    plugin_config: Config, *, plugin_data_dir: Path
) -> CodexBridgeSettings:
    return CodexBridgeSettings(
        binary=plugin_config.codex_binary,
        workdir=str(plugin_config.codex_workdir),
        kill_timeout=plugin_config.codex_kill_timeout,
        progress_history=plugin_config.codex_progress_history,
        diagnostic_history=plugin_config.codex_diagnostic_history,
        chunk_size=plugin_config.codex_chunk_size,
        stream_read_limit=plugin_config.codex_stream_read_limit,
        preferences_path=plugin_data_dir / "preferences.json",
    )
