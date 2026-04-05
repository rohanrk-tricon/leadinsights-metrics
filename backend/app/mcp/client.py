import asyncio
import json
import logging
import sys
from contextlib import AsyncExitStack
from time import perf_counter

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import Settings

logger = logging.getLogger(__name__)


class MCPDatabaseClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        if self._session is not None:
            return

        logger.info("MCP client connecting")
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
        logger.info("MCP client connected")

    async def close(self) -> None:
        if self._exit_stack is not None:
            logger.info("MCP client closing")
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None

    async def call_tool(self, name: str, arguments: dict) -> dict:
        await self.connect()
        if self._session is None:
            raise RuntimeError("MCP client session is not connected.")

        log_context = self._build_log_context(name, arguments)
        started_at = perf_counter()
        logger.info("MCP tool call started", extra=log_context)
        async with self._lock:
            try:
                result = await self._session.call_tool(name, arguments)
            except Exception as exc:
                logger.exception(
                    "MCP tool call failed",
                    extra={
                        **log_context,
                        "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                        "error_type": type(exc).__name__,
                    },
                )
                raise
        if getattr(result, "isError", False):
            payload = self._extract_payload(result)
            message = payload.get("text") or payload.get("message") or str(payload)
            logger.error(
                "MCP tool call returned error",
                extra={
                    **log_context,
                    "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                    "result_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
                },
            )
            raise RuntimeError(message)
        payload = self._extract_payload(result)
        logger.info(
            "MCP tool call succeeded",
            extra={
                **log_context,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
                "result_keys": sorted(payload.keys()) if isinstance(payload, dict) else [],
            },
        )
        return payload

    @staticmethod
    def _build_log_context(name: str, arguments: dict) -> dict:
        context = {
            "tool_name": name,
            "argument_keys": sorted(arguments.keys()),
        }
        if "query" in arguments and isinstance(arguments["query"], str):
            context["query_length"] = len(arguments["query"])
        if "limit" in arguments:
            context["limit"] = arguments["limit"]
        if "table_name" in arguments:
            context["has_table_name"] = arguments["table_name"] is not None
        return context

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
