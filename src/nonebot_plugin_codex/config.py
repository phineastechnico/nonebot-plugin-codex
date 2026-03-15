from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class Config(BaseModel):
    codex_binary: str = "codex"
    codex_workdir: Path = Field(default_factory=Path.home)
    codex_kill_timeout: float = 5.0
    codex_progress_history: int = 6
    codex_diagnostic_history: int = 20
    codex_chunk_size: int = 3500
    codex_stream_read_limit: int = 1024 * 1024
