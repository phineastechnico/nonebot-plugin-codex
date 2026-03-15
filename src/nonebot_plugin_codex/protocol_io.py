from __future__ import annotations

import asyncio
from typing import Any

READ_CHUNK_SIZE = 4096


def oversized_frame_message(limit: int) -> str:
    return (
        "Codex 返回的单条协议消息超过 "
        f"`codex_stream_read_limit`（当前 {limit} 字节）。"
    )


def incomplete_frame_message() -> str:
    return "Codex 返回了不完整的协议消息。"


def truncated_stderr_message(limit: int) -> str:
    return (
        "Codex stderr 单行输出超过 "
        f"`codex_stream_read_limit`（当前 {limit} 字节），已截断。"
    )


class ProtocolStreamError(RuntimeError):
    pass


class NdjsonProcessReader:
    def __init__(
        self,
        process: Any,
        *,
        frame_limit: int,
        read_chunk_size: int = READ_CHUNK_SIZE,
    ) -> None:
        self._stdout = getattr(process, "stdout", None)
        self._stderr = getattr(process, "stderr", None)
        self._frame_limit = frame_limit
        self._read_chunk_size = max(1, read_chunk_size)
        self._stdout_buffer = bytearray()
        self._stderr_buffer = bytearray()
        self._stderr_lines: list[str] = []
        self._stderr_skipping_line = False
        self._stderr_task: asyncio.Task[None] | None = None
        if self._stderr is not None:
            self._stderr_task = asyncio.create_task(self._drain_stderr())

    async def read_stdout_line(self) -> str | None:
        if self._stdout is None:
            raise RuntimeError("Codex 协议 stdout 不可用。")

        while True:
            newline_index = self._stdout_buffer.find(b"\n")
            if newline_index >= 0:
                frame = bytes(self._stdout_buffer[: newline_index + 1])
                del self._stdout_buffer[: newline_index + 1]
                if newline_index > self._frame_limit:
                    raise ProtocolStreamError(oversized_frame_message(self._frame_limit))
                return frame.decode("utf-8", errors="replace").strip()

            if len(self._stdout_buffer) > self._frame_limit:
                self._stdout_buffer.clear()
                raise ProtocolStreamError(oversized_frame_message(self._frame_limit))

            chunk = await self._stdout.read(self._read_chunk_size)
            if not chunk:
                if self._stdout_buffer:
                    self._stdout_buffer.clear()
                    raise ProtocolStreamError(incomplete_frame_message())
                return None
            self._stdout_buffer.extend(chunk)

    def drain_stderr_lines(self) -> list[str]:
        lines = list(self._stderr_lines)
        self._stderr_lines.clear()
        return lines

    async def wait_closed(self) -> None:
        if self._stderr_task is not None:
            await self._stderr_task

    async def _drain_stderr(self) -> None:
        if self._stderr is None:
            return

        while True:
            chunk = await self._stderr.read(self._read_chunk_size)
            if not chunk:
                break
            self._stderr_buffer.extend(chunk)
            self._consume_stderr_buffer(final=False)

        self._consume_stderr_buffer(final=True)

    def _consume_stderr_buffer(self, *, final: bool) -> None:
        while True:
            if self._stderr_skipping_line:
                newline_index = self._stderr_buffer.find(b"\n")
                if newline_index < 0:
                    if final:
                        self._stderr_buffer.clear()
                        self._stderr_skipping_line = False
                    return
                del self._stderr_buffer[: newline_index + 1]
                self._stderr_skipping_line = False
                continue

            newline_index = self._stderr_buffer.find(b"\n")
            if newline_index >= 0:
                frame = bytes(self._stderr_buffer[: newline_index + 1])
                del self._stderr_buffer[: newline_index + 1]
                line = frame.decode("utf-8", errors="replace").strip()
                if line:
                    self._stderr_lines.append(line)
                continue

            if len(self._stderr_buffer) > self._frame_limit:
                self._stderr_lines.append(truncated_stderr_message(self._frame_limit))
                self._stderr_buffer.clear()
                self._stderr_skipping_line = True
                return

            if final:
                line = self._stderr_buffer.decode("utf-8", errors="replace").strip()
                self._stderr_buffer.clear()
                if line:
                    self._stderr_lines.append(line)
            return
