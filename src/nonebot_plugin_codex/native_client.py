from __future__ import annotations

import json
import asyncio
import inspect
from dataclasses import field, dataclass
from typing import Any
from collections.abc import Callable, Awaitable

Callback = Callable[[str], object]
ProcessLauncher = Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class NativeThreadSummary:
    thread_id: str
    thread_name: str
    updated_at: str
    cwd: str | None
    source_kind: str
    preview: str | None = None


@dataclass(slots=True)
class NativeRunResult:
    exit_code: int
    final_text: str = ""
    thread_id: str | None = None
    diagnostics: list[str] = field(default_factory=list)


def _normalize_source_kind(source: object) -> str:
    if isinstance(source, str) and source:
        return source
    if isinstance(source, dict) and "subAgent" in source:
        sub_agent = source["subAgent"]
        if isinstance(sub_agent, str) and sub_agent:
            return f"subAgent:{sub_agent}"
        if isinstance(sub_agent, dict):
            return "subAgent"
    return "unknown"


def _thread_summary_from_payload(thread: dict[str, Any]) -> NativeThreadSummary:
    thread_id = str(thread.get("id") or "")
    thread_name = str(thread.get("name") or thread.get("preview") or thread_id)
    updated_at = str(thread.get("updatedAt") or thread.get("updated_at") or "")
    cwd = thread.get("cwd")
    preview = thread.get("preview")
    return NativeThreadSummary(
        thread_id=thread_id,
        thread_name=thread_name,
        updated_at=updated_at,
        cwd=cwd if isinstance(cwd, str) else None,
        source_kind=_normalize_source_kind(thread.get("source")),
        preview=preview if isinstance(preview, str) and preview.strip() else None,
    )


async def _maybe_call(callback: Callback | None, text: str) -> None:
    if callback is None:
        return
    result = callback(text)
    if inspect.isawaitable(result):
        await result


def _trim_progress_command(command: str, limit: int = 120) -> str:
    compact = " ".join(command.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


async def _terminate_process(process: Any, timeout: float) -> None:
    if process is None:
        return
    if getattr(process, "returncode", None) is not None:
        return
    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


class NativeCodexClient:
    def __init__(
        self,
        *,
        binary: str = "codex",
        launcher: ProcessLauncher | None = None,
        client_name: str = "tg_bot",
        client_version: str = "0",
        stream_read_limit: int = 1024 * 1024,
    ) -> None:
        self.binary = binary
        self.launcher = launcher or asyncio.create_subprocess_exec
        self.client_name = client_name
        self.client_version = client_version
        self.stream_read_limit = stream_read_limit
        self._process: Any = None
        self._initialized = False
        self._next_request_id = 1

    def clone(self) -> NativeCodexClient:
        return NativeCodexClient(
            binary=self.binary,
            launcher=self.launcher,
            client_name=self.client_name,
            client_version=self.client_version,
            stream_read_limit=self.stream_read_limit,
        )

    async def close(self, timeout: float = 5.0) -> None:
        process = self._process
        self._process = None
        self._initialized = False
        self._next_request_id = 1
        await _terminate_process(process, timeout)

    async def start_thread(
        self,
        *,
        workdir: str,
        model: str,
        reasoning_effort: str,
        permission_mode: str,
    ) -> NativeThreadSummary:
        result = await self._request(
            "thread/start",
            {
                "cwd": workdir,
                "model": model,
                "config": {"model_reasoning_effort": reasoning_effort},
                **self._permission_params(permission_mode),
            },
        )
        thread = result.get("thread")
        if not isinstance(thread, dict):
            raise RuntimeError("thread/start 缺少 thread 响应。")
        return _thread_summary_from_payload(thread)

    async def resume_thread(
        self,
        thread_id: str,
        *,
        workdir: str,
        model: str,
        reasoning_effort: str,
        permission_mode: str,
    ) -> NativeThreadSummary:
        result = await self._request(
            "thread/resume",
            {
                "threadId": thread_id,
                "cwd": workdir,
                "model": model,
                "config": {"model_reasoning_effort": reasoning_effort},
                **self._permission_params(permission_mode),
            },
        )
        thread = result.get("thread")
        if not isinstance(thread, dict):
            raise RuntimeError("thread/resume 缺少 thread 响应。")
        return _thread_summary_from_payload(thread)

    async def run_turn(
        self,
        thread_id: str,
        prompt: str,
        *,
        cwd: str | None = None,
        model: str | None = None,
        reasoning_effort: str | None = None,
        on_progress: Callback | None = None,
        on_stream_text: Callback | None = None,
    ) -> NativeRunResult:
        diagnostics: list[str] = []
        streamed_text = ""
        final_text = ""

        await self._request(
            "turn/start",
            self._turn_start_params(
                thread_id=thread_id,
                prompt=prompt,
                cwd=cwd,
                model=model,
                reasoning_effort=reasoning_effort,
            ),
            diagnostics=diagnostics,
        )

        while True:
            message = await self._read_message(diagnostics)
            if message is None:
                continue

            method = message.get("method")
            params = message.get("params")
            if not isinstance(method, str) or not isinstance(params, dict):
                continue

            if method == "turn/started":
                await _maybe_call(on_progress, "开始处理请求")
                continue

            if method in {"item/started", "item/completed"}:
                item = params.get("item")
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "commandExecution":
                    command = _trim_progress_command(str(item.get("command") or ""))
                    prefix = "执行" if method == "item/started" else "完成"
                    await _maybe_call(on_progress, f"{prefix}: {command}")
                    continue
                if item_type == "agentMessage":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        final_text = text.strip()
                        streamed_text = final_text
                        await _maybe_call(on_stream_text, final_text)
                    continue

            if method == "item/agentMessage/delta":
                delta = params.get("delta")
                if isinstance(delta, str) and delta:
                    streamed_text += delta
                    await _maybe_call(on_stream_text, streamed_text)
                continue

            if method == "turn/completed":
                turn = params.get("turn")
                if not isinstance(turn, dict):
                    return NativeRunResult(
                        exit_code=1,
                        final_text=final_text,
                        thread_id=thread_id,
                        diagnostics=diagnostics,
                    )
                status = turn.get("status")
                error = turn.get("error")
                exit_code = 0 if status == "completed" and error is None else 1
                return NativeRunResult(
                    exit_code=exit_code,
                    final_text=final_text,
                    thread_id=str(params.get("threadId") or thread_id),
                    diagnostics=diagnostics,
                )

    async def list_threads(self) -> list[NativeThreadSummary]:
        threads: list[NativeThreadSummary] = []
        cursor: str | None = None

        while True:
            params: dict[str, Any] = {
                "sortKey": "updated_at",
                "sourceKinds": ["cli", "vscode", "appServer"],
                "limit": 100,
            }
            if cursor is not None:
                params["cursor"] = cursor

            result = await self._request("thread/list", params)
            entries = result.get("data")
            if not isinstance(entries, list):
                raise RuntimeError("thread/list 缺少 data 响应。")
            threads.extend(
                _thread_summary_from_payload(thread)
                for thread in entries
                if isinstance(thread, dict)
            )

            next_cursor = result.get("nextCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor

        return threads

    def _permission_params(self, permission_mode: str) -> dict[str, str]:
        if permission_mode == "safe":
            return {"approvalPolicy": "never", "sandbox": "workspace-write"}
        if permission_mode == "danger":
            return {
                "approvalPolicy": "never",
                "sandbox": "danger-full-access",
            }
        raise ValueError(f"Unsupported permission mode: {permission_mode}")

    def _turn_start_params(
        self,
        *,
        thread_id: str,
        prompt: str,
        cwd: str | None,
        model: str | None,
        reasoning_effort: str | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": prompt}],
        }
        if cwd is not None:
            params["cwd"] = cwd
        if model is not None:
            params["model"] = model
        if reasoning_effort is not None:
            params["effort"] = reasoning_effort
        return params

    async def _ensure_initialized(self) -> None:
        if self._initialized and self._process is not None:
            return
        self._process = await self.launcher(
            self.binary,
            "app-server",
            "--listen",
            "stdio://",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            limit=self.stream_read_limit,
        )
        request_id = self._allocate_request_id()
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": self.client_name,
                        "version": self.client_version,
                    }
                },
            }
        )
        await self._read_response(request_id, diagnostics=[])
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        self._initialized = True

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        diagnostics: list[str] | None = None,
    ) -> dict[str, Any]:
        await self._ensure_initialized()
        request_id = self._allocate_request_id()
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        return await self._read_response(request_id, diagnostics=diagnostics or [])

    async def _write_message(self, payload: dict[str, Any]) -> None:
        if self._process is None or getattr(self._process, "stdin", None) is None:
            raise RuntimeError("Codex app-server 尚未启动。")
        data = json.dumps(payload, ensure_ascii=False) + "\n"
        self._process.stdin.write(data.encode("utf-8"))
        await self._process.stdin.drain()

    async def _read_response(
        self,
        request_id: int,
        *,
        diagnostics: list[str],
    ) -> dict[str, Any]:
        while True:
            message = await self._read_message(diagnostics)
            if message is None:
                continue
            if message.get("id") != request_id:
                continue
            error = message.get("error")
            if isinstance(error, dict):
                raise RuntimeError(
                    str(error.get("message") or "Codex app-server 请求失败。")
                )
            result = message.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("Codex app-server 返回了无效响应。")
            return result

    async def _read_message(self, diagnostics: list[str]) -> dict[str, Any] | None:
        if self._process is None or getattr(self._process, "stdout", None) is None:
            raise RuntimeError("Codex app-server 尚未启动。")
        raw_line = await self._process.stdout.readline()
        if not raw_line:
            raise RuntimeError("Codex app-server 已提前退出。")
        line = raw_line.decode("utf-8", errors="replace").strip()
        if not line:
            return None
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            diagnostics.append(line)
            return None
        return message if isinstance(message, dict) else None

    def _allocate_request_id(self) -> int:
        request_id = self._next_request_id
        self._next_request_id += 1
        return request_id
