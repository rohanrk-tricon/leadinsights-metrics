import asyncpg

from app.core.config import Settings


class DatabasePool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                dsn=self._settings.postgres_dsn,
                min_size=1,
                max_size=10,
                command_timeout=30,
            )
        return self._pool

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def fetch(self, query: str, *args):
        pool = await self.connect()
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)

    async def fetchval(self, query: str, *args):
        pool = await self.connect()
        async with pool.acquire() as connection:
            return await connection.fetchval(query, *args)

    async def fetch_with_search_path(self, query: str, schema: str, *args):
        pool = await self.connect()
        async with pool.acquire() as connection:
            async with connection.transaction():
                await connection.execute(f"SET LOCAL search_path TO {schema}")
                return await connection.fetch(query, *args)
