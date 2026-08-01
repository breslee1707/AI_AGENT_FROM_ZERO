"""Bridge MCP tools into the project's provider-neutral ``ToolRegistry``.

The Agent itself remains unaware of MCP. This module keeps MCP sessions alive on a
dedicated asyncio worker, converts discovered MCP schemas to ``ToolSpec`` objects,
and exposes synchronous callables that the existing Agent loop can execute.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import re
import sys
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from typing import Any

from mcp import ClientSessionGroup, StdioServerParameters

from .tools.base import ToolSpec


@dataclass(frozen=True)
class MCPServerConfig:
    """Launch configuration for one local stdio MCP server."""

    name: str
    command: str
    args: tuple[str, ...] = ()
    cwd: Path | None = None
    env: dict[str, str] | None = None

    def to_parameters(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.command,
            args=list(self.args),
            cwd=self.cwd,
            env=self.env,
        )


@dataclass
class _ToolCall:
    name: str
    arguments: dict[str, Any]
    future: Future[str]


def _safe_name(value: str) -> str:
    """Return a function-calling-safe identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned or "server"


def _qualified_name(name: str, server_info) -> str:
    """Namespace every MCP tool so multiple servers cannot silently collide."""
    return f"mcp_{_safe_name(server_info.name)}__{_safe_name(name)}"


def load_mcp_server_configs(path: str | Path) -> list[MCPServerConfig]:
    """Read the familiar ``mcpServers`` JSON format used by MCP hosts."""
    config_path = Path(path).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy MCP config: {config_path}")

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_servers = payload.get("mcpServers")
    if not isinstance(raw_servers, dict) or not raw_servers:
        raise ValueError("MCP config phải có object 'mcpServers' và ít nhất một server")

    configs: list[MCPServerConfig] = []
    for name, raw in raw_servers.items():
        if not isinstance(raw, dict) or not raw.get("command"):
            raise ValueError(f"MCP server '{name}' thiếu command")

        command = str(raw["command"])
        if command == "${PYTHON}":
            command = sys.executable

        raw_cwd = raw.get("cwd")
        cwd = None
        if raw_cwd:
            cwd_path = Path(str(raw_cwd))
            cwd = (
                cwd_path.resolve()
                if cwd_path.is_absolute()
                else (config_path.parent / cwd_path).resolve()
            )

        raw_env = raw.get("env")
        env = None
        if raw_env is not None:
            if not isinstance(raw_env, dict):
                raise ValueError(f"env của MCP server '{name}' phải là object")
            env = {str(key): str(value) for key, value in raw_env.items()}

        configs.append(
            MCPServerConfig(
                name=str(name),
                command=command,
                args=tuple(str(arg) for arg in raw.get("args", [])),
                cwd=cwd,
                env=env,
            )
        )
    return configs


def _result_to_text(result) -> str:
    """Convert an MCP ``CallToolResult`` to the text consumed by the model."""
    text_blocks = [
        block.text for block in result.content if getattr(block, "type", None) == "text"
    ]
    if text_blocks:
        text = "\n".join(text_blocks)
    elif result.structured_content is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False, indent=2)
    else:
        text = "[MCP tool không trả về nội dung dạng text]"

    return f"[Lỗi MCP] {text}" if result.is_error else text


class MCPToolProvider:
    """Keep stdio MCP servers alive and expose their tools as ``ToolSpec`` objects."""

    def __init__(
        self,
        servers: list[MCPServerConfig],
        *,
        timeout_seconds: float = 30,
    ) -> None:
        if not servers:
            raise ValueError("Cần ít nhất một MCP server")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds phải lớn hơn 0")

        self._servers = servers
        self._timeout_seconds = timeout_seconds
        self._requests: Queue[_ToolCall | None] = Queue()
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._startup_error: BaseException | None = None
        self._worker_error: BaseException | None = None
        self._specs: tuple[ToolSpec, ...] = ()
        self._thread = threading.Thread(
            target=self._thread_main,
            name="mcp-tool-provider",
            daemon=True,
        )
        self._thread.start()

        if not self._ready.wait(timeout_seconds):
            self.close()
            raise TimeoutError("MCP server khởi động quá thời gian cho phép")
        if self._startup_error is not None:
            self.close()
            raise RuntimeError(f"Không kết nối được MCP server: {self._startup_error}")

        atexit.register(self.close)

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        timeout_seconds: float = 30,
    ) -> MCPToolProvider:
        return cls(
            load_mcp_server_configs(path),
            timeout_seconds=timeout_seconds,
        )

    def specs(self) -> list[ToolSpec]:
        """Return the MCP tools discovered through ``tools/list``."""
        return list(self._specs)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Synchronously submit one ``tools/call`` to the async MCP worker."""
        if self._closed.is_set():
            return "[Lỗi MCP] Kết nối MCP đã đóng."
        if self._worker_error is not None:
            return f"[Lỗi MCP] MCP worker đã dừng: {self._worker_error}"

        future: Future[str] = Future()
        self._requests.put(_ToolCall(name=name, arguments=arguments, future=future))
        try:
            return future.result(timeout=self._timeout_seconds)
        except TimeoutError:
            return f"[Lỗi MCP] Tool '{name}' chạy quá {self._timeout_seconds:g} giây."
        except Exception as exc:  # noqa: BLE001 - surface transport errors to the model
            return f"[Lỗi MCP] Không gọi được tool '{name}': {exc}"

    def _make_invoker(self, registered_name: str):
        def invoke(**kwargs: Any) -> str:
            return self.call_tool(registered_name, kwargs)

        return invoke

    def close(self) -> None:
        """Stop the worker and close all MCP subprocesses."""
        if self._closed.is_set():
            return
        self._closed.set()
        self._requests.put(None)
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=self._timeout_seconds)

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as exc:  # noqa: BLE001 - retain worker failure for callers
            if not self._ready.is_set():
                self._startup_error = exc
                self._ready.set()
            else:
                self._worker_error = exc

    async def _serve(self) -> None:
        async with ClientSessionGroup(component_name_hook=_qualified_name) as group:
            for server in self._servers:
                try:
                    await group.connect_to_server(server.to_parameters())
                except Exception as exc:
                    raise RuntimeError(f"{server.name}: {exc}") from exc

            specs: list[ToolSpec] = []
            for registered_name, tool in sorted(group.tools.items()):
                description = tool.description or f"MCP tool {tool.name}"

                specs.append(
                    ToolSpec(
                        name=registered_name,
                        description=f"[MCP] {description}",
                        parameters=dict(tool.input_schema),
                        func=self._make_invoker(registered_name),
                    )
                )

            self._specs = tuple(specs)
            self._ready.set()

            while True:
                try:
                    request = self._requests.get_nowait()
                except Empty:
                    # Avoid ``asyncio.to_thread(queue.get)`` here. Its executor thread
                    # is non-daemon and can keep Streamlit alive during interpreter
                    # shutdown before our atexit hook gets a chance to close MCP.
                    await asyncio.sleep(0.02)
                    continue
                if request is None:
                    break
                try:
                    result = await group.call_tool(request.name, request.arguments)
                    request.future.set_result(_result_to_text(result))
                except BaseException as exc:  # noqa: BLE001 - deliver failure to caller
                    request.future.set_exception(exc)


__all__ = [
    "MCPServerConfig",
    "MCPToolProvider",
    "load_mcp_server_configs",
]
