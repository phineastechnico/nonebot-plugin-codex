from __future__ import annotations

import json
import asyncio
from typing import Any
from dataclasses import dataclass

import pytest

from nonebot_plugin_codex.native_client import NativeCodexClient


class FakeStdout:
    def __init__(self, lines: list[str]) -> None:
        self._lines = [line.encode("utf-8") for line in lines]

    async def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        await asyncio.sleep(0)
        return b""


class FakeStdin:
    def __init__(self) -> None:
        self.buffer: list[str] = []

    def write(self, data: bytes) -> None:
        self.buffer.append(data.decode("utf-8"))

    async def drain(self) -> None:
        return None


@dataclass
class FakeProcess:
    stdout: FakeStdout
    stdin: FakeStdin
    returncode: int | None = None

    def terminate(self) -> None:
        self.returncode = 0

    def kill(self) -> None:
        self.returncode = -9

    async def wait(self) -> int:
        self.returncode = self.returncode or 0
        return self.returncode


@pytest.mark.asyncio
async def test_native_client_start_resume_and_stream_text() -> None:
    requests: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    process = FakeProcess(
        stdout=FakeStdout(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": {}}) + "\n",
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "result": {
                            "thread": {
                                "id": "thread-1",
                                "name": "Thread One",
                                "updatedAt": "2025-03-01T00:00:00Z",
                                "cwd": "/tmp/work",
                                "source": "cli",
                            }
                        },
                    }
                )
                + "\n",
                json.dumps({"jsonrpc": "2.0", "id": 3, "result": {}}) + "\n",
                json.dumps({"jsonrpc": "2.0", "method": "turn/started", "params": {}})
                + "\n",
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "item/agentMessage/delta",
                        "params": {"delta": "hello"},
                    }
                )
                + "\n",
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "method": "turn/completed",
                        "params": {
                            "threadId": "thread-1",
                            "turn": {"status": "completed", "error": None},
                        },
                    }
                )
                + "\n",
            ]
        ),
        stdin=FakeStdin(),
    )

    async def launcher(*args: Any, **kwargs: Any) -> FakeProcess:
        requests.append((args, kwargs))
        return process

    client = NativeCodexClient(binary="codex", launcher=launcher)
    progress: list[str] = []
    streamed: list[str] = []

    thread = await client.start_thread(
        workdir="/tmp/work",
        model="gpt-5",
        reasoning_effort="xhigh",
        permission_mode="safe",
    )
    result = await client.run_turn(
        thread.thread_id,
        "hello",
        on_progress=progress.append,
        on_stream_text=streamed.append,
    )

    assert requests[0][0][:3] == ("codex", "app-server", "--listen")
    assert thread.thread_id == "thread-1"
    assert progress == ["开始处理请求"]
    assert streamed == ["hello"]
    assert result.exit_code == 0
    assert result.final_text == ""
