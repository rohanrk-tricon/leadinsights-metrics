import asyncio
import json
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import Settings


class MCPDatabaseClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._session is not None:
            return

        self._exit_stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp.server"],
            cwd=str(self._settings.backend_root),
            env=self._settings.mcp_env,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self._session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self._session.initialize()

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict) -> dict:
        await self.connect()
        if self._session is None:
            raise RuntimeError("MCP client session is not connected.")

        async with self._lock:
            result = await self._session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            payload = self._extract_payload(result)
            message = payload.get("text") or payload.get("message") or str(payload)
            raise RuntimeError(message)
        return self._extract_payload(result)

    def _extract_payload(self, result) -> dict:
        structured = getattr(result, "structuredContent", None)
        if structured:
            return self._normalize_payload(structured)

        content = getattr(result, "content", None) or []
        text_parts = []
        for item in content:
            text = getattr(item, "text", None)
            if text:
                text_parts.append(text)

        if not text_parts:
            raise RuntimeError("MCP tool returned no content.")

        payload = "\n".join(text_parts)
        try:
            return self._normalize_payload(json.loads(payload))
        except json.JSONDecodeError:
            return {"text": payload}

    def _normalize_payload(self, payload: dict):
        if (
            isinstance(payload, dict)
            and set(payload.keys()) == {"result"}
            and isinstance(payload["result"], str)
        ):
            try:
                return json.loads(payload["result"])
            except json.JSONDecodeError:
                return payload
        return payload
