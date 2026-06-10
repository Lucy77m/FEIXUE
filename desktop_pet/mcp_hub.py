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
from concurrent.futures import TimeoutError as FuturesTimeout

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
    """把 MCP 工具回包压成给模型看的纯文本——非文本块(图片/资源等)退化成占位符。"""
    parts: list[str] = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        # 用 getattr 一路兜底：不同 server 的 content item 字段不齐，缺啥都不能炸
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
        """读 data/mcp.json 里的 mcpServers；文件不在就先落一个空骨架，方便用户照着填。"""
        if not _CONFIG_PATH.exists():
            atomic_write_text(_CONFIG_PATH, json.dumps({"mcpServers": {}}, indent=2))
            return {}
        try:
            # utf-8-sig：Windows 记事本存出来常带 BOM，普通 utf-8 会在首字节崩
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            # 配置坏了不能拖垮启动——记到 errors，status() 里照样能看见
            self._errors["<config>"] = str(exc)
            return {}
        servers = data.get("mcpServers", {})
        return servers if isinstance(servers, dict) else {}

    def start(self) -> None:
        """起后台线程连所有 MCP server，阻塞等到全部连上(或超时)再返回。幂等，重复调用直接 no-op。"""
        if self._thread is not None:
            return
        servers = self._load_servers()
        if not servers:
            # 没配 server 也得把 ready 点亮，否则后面 wait 的人白等到超时
            self._ready.set()
            return
        self._thread = threading.Thread(target=self._run, args=(servers,), daemon=True, name="mcp-hub")
        self._thread.start()
        # 等连接就绪：超时也照样往下走，连不上的 server 进 errors 不挡主流程
        self._ready.wait(timeout=_READY_TIMEOUT)
        atexit.register(self.shutdown)

    def _run(self, servers: dict[str, dict]) -> None:
        """后台线程入口：开一个专属事件循环，整个 MCP 生命周期都跑在这个 loop 上。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve(servers))
        finally:
            self._loop.close()

    async def _serve(self, servers: dict[str, dict]) -> None:
        """逐个连 server → 点亮 ready → 挂在 _stop 上等关停。所有子进程/会话归 stack 统一收尾。"""
        # mcp 包延迟到这里再 import：没装 mcp 的用户也能正常用，只是没 MCP 功能
        from contextlib import AsyncExitStack

        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        self._stop = asyncio.Event()
        async with AsyncExitStack() as stack:
            for name, spec in servers.items():
                try:
                    await asyncio.wait_for(
                        self._connect(stack, name, spec, ClientSession, StdioServerParameters, stdio_client),
                        # 单个 server 卡 30s 就放弃，别让一个连不上的拖死整批
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
        """拉起一个 stdio server 子进程、握手、把它的工具登记进 routes/schemas。"""
        command = spec.get("command") if isinstance(spec, dict) else None
        if not isinstance(command, str) or not command.strip():
            raise ValueError("missing or invalid 'command' (need a non-empty string)")
        params = StdioServerParameters(
            command=command,
            args=[str(a) for a in (spec.get("args") or [])],
            # 继承当前进程 env 再叠用户配的：子进程要 PATH 等才找得到 node/python 这些
            env={**os.environ, **(spec.get("env") or {})},
        )
        read, write = await stack.enter_async_context(stdio_client(params))
        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        listed = await session.list_tools()
        self._sessions[name] = session
        for tool in listed.tools:
            # 工具名加 server 前缀做命名空间，再砍到 64 字符——OpenAI 那边 function name 有长度上限
            base = f"mcp__{_sanitize(name)}__{_sanitize(tool.name)}"[:_NAME_CAP]
            namespaced = base
            dedup = 0
            # 撞名时挂 _1/_2…，给后缀留位前先把 base 截短，保证加完还在 64 以内
            while namespaced in self._routes:
                dedup += 1
                suffix = f"_{dedup}"
                namespaced = base[: _NAME_CAP - len(suffix)] + suffix
            self._routes[namespaced] = (name, tool.name)
            # server 给的 inputSchema 不一定合规，兜成空 object，免得下游校验直接拒掉这工具
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
        """从主线程发停止信号给后台 loop，等它收尾子进程。atexit 注册，退出时兜底跑一遍。"""
        if self._loop is None or self._stop is None or not self._loop.is_running():
            return
        # _stop 是 loop 线程的 Event，跨线程只能用 call_soon_threadsafe 去点
        self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            # 给 5s 收尸：MCP 子进程偶尔退得慢，等不到也只能放手，别卡死退出
            self._thread.join(timeout=5.0)

    def tool_schemas(self) -> list[dict]:
        return list(self._schemas)

    def call(self, name: str, arguments: dict) -> str:
        """从主线程同步调一个 MCP 工具：把协程丢进后台 loop，阻塞等结果。出啥岔子都包成字符串回去，绝不抛。"""
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
        except Exception as exc:
            return f"[MCP call failed: {type(exc).__name__}: {exc}]"
        try:
            return _render_result(future.result(timeout=_CALL_TIMEOUT))
        except FuturesTimeout:
            # 超时单独拎出来：cancel 掉别让卡死的调用占着 loop，给个能看懂的中文提示
            future.cancel()
            return f"[MCP call timed out after {int(_CALL_TIMEOUT)}s — \"{server}\" 可能卡住了]"
        except Exception as exc:
            future.cancel()
            return f"[MCP call failed: {type(exc).__name__}: {exc}]"

    def status(self) -> str:
        """给控制面板看的连接概览，● 连上、× 没连上带原因。"""
        lines: list[str] = []
        for server in sorted(self._sessions):
            tools = [t for t, (s, _) in self._routes.items() if s == server]
            lines.append(f"● {server}: {len(tools)} tools")
        for server, err in sorted(self._errors.items()):
            lines.append(f"× {server}: {err}")
        return "\n".join(lines) if lines else "(no MCP connectors configured; edit data/mcp.json to add some)"


mcp_hub = MCPHub()
