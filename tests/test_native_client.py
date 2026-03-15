from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
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

    async def read(self, _size: int = -1) -> bytes:
        return await self.readline()


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
    stderr: FakeStdout | None = None
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


@pytest.mark.asyncio
async def test_native_client_reads_large_stdout_frame_without_readline_limit(
    tmp_path: Path,
) -> None:
    long_text = "A" * (2 * 1024 * 1024)
    thread_payload = {
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
    item_payload = {
        "jsonrpc": "2.0",
        "method": "item/completed",
        "params": {
            "threadId": "thread-1",
            "item": {
                "id": "msg-1",
                "type": "agentMessage",
                "text": long_text,
            },
        },
    }
    completed_payload = {
        "jsonrpc": "2.0",
        "method": "turn/completed",
        "params": {
            "threadId": "thread-1",
            "turn": {"status": "completed", "error": None},
        },
    }
    script = (
        "import json, sys\n"
        f"long_text = {long_text!r}\n"
        "messages = [\n"
        "    {'jsonrpc': '2.0', 'id': 1, 'result': {}},\n"
        f"    {thread_payload!r},\n"
        "    {'jsonrpc': '2.0', 'id': 3, 'result': {}},\n"
        f"    {item_payload!r},\n"
        f"    {completed_payload!r},\n"
        "]\n"
        "for message in messages:\n"
        "    sys.stdout.write(json.dumps(message) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )
    script_path = tmp_path / "large_native_stdout.py"
    script_path.write_text(script, encoding="utf-8")

    async def launcher(*_args: Any, **_kwargs: Any):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=1024,
        )

    client = NativeCodexClient(
        binary="codex",
        launcher=launcher,
        stream_read_limit=8 * 1024 * 1024,
    )
    try:
        thread = await client.start_thread(
            workdir="/tmp/work",
            model="gpt-5",
            reasoning_effort="xhigh",
            permission_mode="safe",
        )
        result = await client.run_turn(thread.thread_id, "hello")

        assert result.exit_code == 0
        assert result.final_text == long_text
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_native_client_ignores_large_stderr_frames() -> None:
    huge_stderr = "E" * 4096
    thread_payload = {
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
    script = (
        "import json, sys\n"
        f"huge_stderr = {huge_stderr!r}\n"
        "sys.stdout.write("
        "json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {}}) + '\\n'"
        ")\n"
        "sys.stdout.flush()\n"
        "sys.stderr.write(huge_stderr + '\\n')\n"
        "sys.stderr.flush()\n"
        f"sys.stdout.write(json.dumps({thread_payload!r}) + '\\n')\n"
        "sys.stdout.flush()\n"
    )

    async def launcher(*_args: Any, **kwargs: Any):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
    )

    client = NativeCodexClient(binary="codex", launcher=launcher, stream_read_limit=1024)
    try:
        thread = await client.start_thread(
            workdir="/tmp/work",
            model="gpt-5",
            reasoning_effort="xhigh",
            permission_mode="safe",
        )

        assert thread.thread_id == "thread-1"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_native_client_reports_friendly_error_for_oversized_frame() -> None:
    long_text = "A" * 4096
    thread_payload = {
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
    item_payload = {
        "jsonrpc": "2.0",
        "method": "item/completed",
        "params": {
            "threadId": "thread-1",
            "item": {
                "id": "msg-1",
                "type": "agentMessage",
                "text": long_text,
            },
        },
    }
    script = (
        "import json, sys\n"
        f"long_text = {long_text!r}\n"
        "sys.stdout.write("
        "json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {}}) + '\\n'"
        ")\n"
        "sys.stdout.flush()\n"
        f"sys.stdout.write(json.dumps({thread_payload!r}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "sys.stdout.write("
        "json.dumps({'jsonrpc': '2.0', 'id': 3, 'result': {}}) + '\\n'"
        ")\n"
        "sys.stdout.flush()\n"
        f"sys.stdout.write(json.dumps({item_payload!r}) + '\\n')\n"
        "sys.stdout.flush()\n"
    )

    async def launcher(*_args: Any, **kwargs: Any):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    client = NativeCodexClient(binary="codex", launcher=launcher, stream_read_limit=1024)
    try:
        thread = await client.start_thread(
            workdir="/tmp/work",
            model="gpt-5",
            reasoning_effort="xhigh",
            permission_mode="safe",
        )

        with pytest.raises(RuntimeError, match="codex_stream_read_limit"):
            await client.run_turn(thread.thread_id, "hello")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_native_client_reports_incomplete_protocol_frame() -> None:
    thread_payload = {
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
    script = (
        "import json, sys\n"
        "sys.stdout.write("
        "json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {}}) + '\\n'"
        ")\n"
        "sys.stdout.flush()\n"
        f"sys.stdout.write(json.dumps({thread_payload!r}) + '\\n')\n"
        "sys.stdout.flush()\n"
        "sys.stdout.write("
        "json.dumps({'jsonrpc': '2.0', 'id': 3, 'result': {}}) + '\\n'"
        ")\n"
        "sys.stdout.flush()\n"
        "sys.stdout.write('{\"jsonrpc\":\"2.0\",\"method\":\"turn/completed\"')\n"
        "sys.stdout.flush()\n"
    )

    async def launcher(*_args: Any, **kwargs: Any):
        return await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=kwargs.get("stderr", asyncio.subprocess.PIPE),
            limit=int(kwargs.get("limit", 1024)),
        )

    client = NativeCodexClient(binary="codex", launcher=launcher, stream_read_limit=1024)
    try:
        thread = await client.start_thread(
            workdir="/tmp/work",
            model="gpt-5",
            reasoning_effort="xhigh",
            permission_mode="safe",
        )

        with pytest.raises(RuntimeError, match="不完整的协议消息"):
            await client.run_turn(thread.thread_id, "hello")
    finally:
        await client.close()
