import time

from app.agents.models import QueryExecution
from app.core.config import Settings
from app.mcp.client import MCPDatabaseClient


class SQLExecutionAgent:
    def __init__(self, mcp_client: MCPDatabaseClient, settings: Settings) -> None:
        self._mcp_client = mcp_client
        self._settings = settings
        self._schema_prompt: str | None = None
        self._schema_loaded_at = 0.0

    async def get_schema_context(self, force_refresh: bool = False) -> str:
        is_stale = (time.time() - self._schema_loaded_at) > self._settings.schema_cache_ttl_seconds
        if self._schema_prompt and not force_refresh and not is_stale:
            return self._schema_prompt

        payload = await self._mcp_client.call_tool("describe_schema", {"table_name": None})
        self._schema_prompt = payload["prompt_text"]
        self._schema_loaded_at = time.time()
        return self._schema_prompt

    async def execute(self, sql: str) -> QueryExecution:
        payload = await self._mcp_client.call_tool(
            "run_readonly_sql",
            {
                "query": sql,
                "limit": self._settings.query_row_limit,
            },
        )
        return QueryExecution.model_validate(payload)

    async def healthcheck(self) -> dict:
        return await self._mcp_client.call_tool("health_check", {})
