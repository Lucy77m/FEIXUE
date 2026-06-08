# author: bdth
# email: 2074055628@qq.com
# MCP 连接中枢:后台线程跑事件循环连接 stdio MCP 服务,汇总工具 schema 并转发调用

from __future__ import annotations

import asyncio
import atexit
import json
import os
import re
import threading

from desktop_pet.audit import audit
from desktop_pet.settings import DATA_DIR, atomic_write_text

_CONFIG_PATH = DATA_DIR / "mcp.json"
_CONNECT_TIMEOUT = 30.0
_CALL_TIMEOUT = 120.0
_READY_TIMEOUT = 45.0
_NAME_CAP = 64


def _sanitize(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)


def _render_result(result) -> str:
    parts: list[str] = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        parts.append(text if text is not None else f"[{getattr(item, 'type', 'content')} content]")
    body = "\n".join(parts).strip() or "(no content returned)"
    if getattr(result, "isError", False):
        return f"[MCP tool error] {body}"
    return body


class MCPHub:

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stop: asyncio.Event | None = None
        self._ready = threading.Event()
        self._sessions: dict[str, object] = {}
        self._schemas: list[dict] = []
        self._routes: dict[str, tuple[str, str]] = {}
        self._errors: dict[str, str] = {}

    def _load_servers(self) -> dict[str, dict]:
        if not _CONFIG_PATH.exists():
            atomic_write_text(_CONFIG_PATH, json.dumps({"mcpServers": {}}, indent=2))
            return {}
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self._errors["<config>"] = str(exc)
            return {}
        servers = data.get("mcpServers", {})
        return servers if isinstance(servers, dict) else {}

    def start(self) -> None:
        if self._thread is not None:
            return
        servers = self._load_servers()
        if not servers:
            self._ready.set()
            return
        self._thread = threading.Thread(target=self._run, args=(servers,), daemon=True, name="mcp-hub")
        self._thread.start()
        self._ready.wait(timeout=_READY_TIMEOUT)
        atexit.register(self.shutdown)

    def _run(self, servers: dict[str, dict]) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve(servers))
        finally:
            self._loop.close()

    async def _serve(self, servers: dict[str, dict]) -> None:
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._stop = asyncio.Event()
        async with AsyncExitStack() as stack:
            for name, spec in servers.items():
                try:
                    await asyncio.wait_for(
                        self._connect(stack, name, spec, ClientSession, StdioServerParameters, stdio_client),
                        timeout=_CONNECT_TIMEOUT,
                    )
                except Exception as exc:
                    self._errors[name] = f"{type(exc).__name__}: {exc}"
            for srv, err in self._errors.items():
                audit.system("MCP 连接失败", server=srv, error=err)
            if self._sessions:
                audit.system(
                    "MCP 已连接",
                    servers=sorted(self._sessions),
                    tools=len(self._routes),
                )
            self._ready.set()
            await self._stop.wait()

    async def _connect(self, stack, name, spec, ClientSession, StdioServerParameters, stdio_client) -> None:
        command = spec.get("command") if isinstance(spec, dict) else None
        if not isinstance(command, str) or not command.strip():
            raise ValueError("missing or invalid 'command' (need a non-empty string)")
        params = StdioServerParameters(
            command=command,
            args=[str(a) for a in (spec.get("args") or [])],
            env={**os.environ, **(spec.get("env") or {})},
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        listed = await session.list_tools()
        self._sessions[name] = session
        for tool in listed.tools:
            base = f"mcp__{_sanitize(name)}__{_sanitize(tool.name)}"[:_NAME_CAP]
            namespaced = base
            dedup = 0
            while namespaced in self._routes:
                dedup += 1
                suffix = f"_{dedup}"
                namespaced = base[: _NAME_CAP - len(suffix)] + suffix
            self._routes[namespaced] = (name, tool.name)
            schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
            if schema.get("type") != "object":
                schema = {"type": "object", "properties": {}}
            description = (tool.description or tool.name)[:1024]
            self._schemas.append(
                {"type": "function", "function": {
                    "name": namespaced,
                    "description": f"[MCP·{name}] {description}",
                    "parameters": schema,
                }}
            )

    def shutdown(self) -> None:
        if self._loop is None or self._stop is None or not self._loop.is_running():
            return
        self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    def tool_schemas(self) -> list[dict]:
        return list(self._schemas)

    def handles(self, name: str) -> bool:
        return name in self._routes

    def call(self, name: str, arguments: dict) -> str:
        route = self._routes.get(name)
        if route is None:
            return f"[unknown MCP tool: {name}]"
        server, tool = route
        session = self._sessions.get(server)
        if session is None or self._loop is None:
            return f"[MCP service \"{server}\" not connected]"
        try:
            future = asyncio.run_coroutine_threadsafe(
                session.call_tool(tool, arguments or {}), self._loop
            )
            return _render_result(future.result(timeout=_CALL_TIMEOUT))
        except Exception as exc:
            return f"[MCP call failed: {type(exc).__name__}: {exc}]"

    def status(self) -> str:
        lines: list[str] = []
        for server in sorted(self._sessions):
            tools = [t for t, (s, _) in self._routes.items() if s == server]
            lines.append(f"● {server}: {len(tools)} tools")
        for server, err in sorted(self._errors.items()):
            lines.append(f"× {server}: {err}")
        return "\n".join(lines) if lines else "(no MCP connectors configured; edit data/mcp.json to add some)"


mcp_hub = MCPHub()
