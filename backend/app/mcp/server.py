import json
from time import perf_counter

from mcp.server.fastmcp import FastMCP

from app.core.config import get_settings
from app.db.pool import DatabasePool
from app.db.schema import SchemaCache
from app.db.sql_guard import build_explain_query, build_limited_query

settings = get_settings()
db = DatabasePool(settings)
schema_cache = SchemaCache(settings, db)
mcp = FastMCP(
    "LeadDB MCP Server",
    instructions="Read-only MCP tools for schema inspection and SQL execution on leaddb.",
)


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


@mcp.tool()
async def health_check() -> str:
    await db.connect()
    current_db = await db.fetchval("SELECT current_database()")
    return json.dumps(
        {
            "status": "ok",
            "database": current_db,
            "schema_cache_ttl_seconds": settings.schema_cache_ttl_seconds,
        }
    )


@mcp.tool()
async def list_tables() -> str:
    snapshot = await schema_cache.get_snapshot()
    return json.dumps({"tables": sorted(snapshot["tables"].keys())})


@mcp.tool()
async def describe_schema(table_name: str | None = None) -> str:
    snapshot = await schema_cache.get_snapshot()
    if table_name:
        table = snapshot["tables"].get(table_name)
        if table is None:
            raise ValueError(f"Unknown table: {table_name}")
        return json.dumps(
            {
                "table_name": table_name,
                "columns": table,
                "prompt_text": f"- {table_name}: "
                + ", ".join(
                    f'{column["column_name"]} ({column["data_type"]}, nullable={column["is_nullable"]})'
                    for column in table
                ),
            }
        )
    return json.dumps(snapshot)


@mcp.tool()
async def explain_query(query: str) -> str:
    explain_sql = build_explain_query(query)
    rows = await db.fetch_with_search_path(explain_sql, "leadinsights")
    return json.dumps(
        {
            "query": query,
            "explain_sql": explain_sql,
            "plan": _rows_to_dicts(rows),
        },
        default=str,
    )


@mcp.tool()
async def run_readonly_sql(query: str, limit: int = 200) -> str:
    started_at = perf_counter()
    bounded_query = build_limited_query(query, limit)
    rows = await db.fetch_with_search_path(bounded_query, "leadinsights")
    execution_ms = round((perf_counter() - started_at) * 1000, 2)
    records = _rows_to_dicts(rows)
    columns = list(records[0].keys()) if records else []
    return json.dumps(
        {
            "original_sql": query,
            "executed_sql": bounded_query,
            "columns": columns,
            "rows": records,
            "row_count": len(records),
            "execution_ms": execution_ms,
        },
        default=str,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
