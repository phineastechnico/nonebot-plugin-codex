from __future__ import annotations

from pathlib import Path

from pydantic import Field, BaseModel, AliasChoices


class Config(BaseModel):
    codex_binary: str = Field(
        default="codex",
        validation_alias=AliasChoices("codex_binary", "codex_bridge_binary"),
    )
    codex_workdir: Path = Field(
        default_factory=Path.home,
        validation_alias=AliasChoices("codex_workdir", "codex_bridge_workdir"),
    )
    codex_kill_timeout: float = Field(
        default=5.0,
        validation_alias=AliasChoices("codex_kill_timeout", "codex_bridge_kill_timeout"),
    )
    codex_progress_history: int = Field(
        default=6,
        validation_alias=AliasChoices(
            "codex_progress_history",
            "codex_bridge_progress_history",
        ),
    )
    codex_diagnostic_history: int = Field(
        default=20,
        validation_alias=AliasChoices(
            "codex_diagnostic_history",
            "codex_bridge_diagnostic_history",
        ),
    )
    codex_chunk_size: int = Field(
        default=3500,
        validation_alias=AliasChoices("codex_chunk_size", "codex_bridge_chunk_size"),
    )
    codex_stream_read_limit: int = Field(
        default=1024 * 1024,
        validation_alias=AliasChoices(
            "codex_stream_read_limit",
            "codex_bridge_stream_read_limit",
        ),
    )
    codex_models_cache_path: Path = Field(
        default_factory=lambda: Path.home() / ".codex" / "models_cache.json",
        validation_alias=AliasChoices(
            "codex_models_cache_path",
            "codex_bridge_models_cache_path",
        ),
    )
    codex_codex_config_path: Path = Field(
        default_factory=lambda: Path.home() / ".codex" / "config.toml",
        validation_alias=AliasChoices(
            "codex_codex_config_path",
            "codex_bridge_codex_config_path",
        ),
    )
    codex_preferences_path: Path = Field(
        default_factory=lambda: Path("data") / "codex_bridge" / "preferences.json",
        validation_alias=AliasChoices(
            "codex_preferences_path",
            "codex_bridge_preferences_path",
        ),
    )
    codex_session_index_path: Path = Field(
        default_factory=lambda: Path.home() / ".codex" / "session_index.jsonl",
        validation_alias=AliasChoices(
            "codex_session_index_path",
            "codex_bridge_session_index_path",
        ),
    )
    codex_sessions_dir: Path = Field(
        default_factory=lambda: Path.home() / ".codex" / "sessions",
        validation_alias=AliasChoices("codex_sessions_dir", "codex_bridge_sessions_dir"),
    )
    codex_archived_sessions_dir: Path = Field(
        default_factory=lambda: Path.home() / ".codex" / "archived_sessions",
        validation_alias=AliasChoices(
            "codex_archived_sessions_dir",
            "codex_bridge_archived_sessions_dir",
        ),
    )
