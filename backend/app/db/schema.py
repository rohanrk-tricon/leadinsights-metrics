import time
from collections import defaultdict

from app.core.config import Settings
from app.db.pool import DatabasePool

SCHEMA_SQL = """
SELECT
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable
FROM information_schema.columns AS c
WHERE c.table_schema = 'leadinsights'
  AND c.table_name NOT IN (
      SELECT child.relname
      FROM pg_inherits
      JOIN pg_class AS child ON pg_inherits.inhrelid = child.oid
      JOIN pg_namespace AS n ON child.relnamespace = n.oid
      WHERE n.nspname = 'leadinsights'
  )
ORDER BY c.table_name, c.ordinal_position;
""".strip()


class SchemaCache:
    def __init__(self, settings: Settings, db: DatabasePool) -> None:
        self._settings = settings
        self._db = db
        self._snapshot: dict | None = None
        self._loaded_at = 0.0

    async def get_snapshot(self, force_refresh: bool = False) -> dict:
        is_stale = (time.time() - self._loaded_at) > self._settings.schema_cache_ttl_seconds
        if self._snapshot and not force_refresh and not is_stale:
            return self._snapshot

        rows = await self._db.fetch(SCHEMA_SQL)
        tables: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            tables[row["table_name"]].append(
                {
                    "column_name": row["column_name"],
                    "data_type": row["data_type"],
                    "is_nullable": row["is_nullable"],
                }
            )

        rendered_tables = []
        for table_name, columns in tables.items():
            rendered_columns = ", ".join(
                f'{column["column_name"]} ({column["data_type"]}, nullable={column["is_nullable"]})'
                for column in columns
            )
            rendered_tables.append(
                f"- leadinsights.{table_name} (usable alias: {table_name}): {rendered_columns}"
            )

        self._snapshot = {
            "tables": dict(tables),
            "prompt_text": "\n".join(rendered_tables),
        }
        self._loaded_at = time.time()
        return self._snapshot
