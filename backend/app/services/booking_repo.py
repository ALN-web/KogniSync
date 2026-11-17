"""TripPass storage: Postgres (Cloud SQL) when DATABASE_URL is set, else the KV store."""

import asyncio
from typing import Protocol

from app.domain.booking import TripPass
from app.services.kv import KV


class TripPassRepo(Protocol):
    async def save(self, tp: TripPass) -> None: ...
    async def get(self, trippass_id: str) -> TripPass | None: ...


class KVTripPassRepo:
    def __init__(self, kv: KV):
        self.kv = kv

    async def save(self, tp: TripPass) -> None:
        await self.kv.set(f"trippass:{tp.id}", tp.model_dump_json())

    async def get(self, trippass_id: str) -> TripPass | None:
        raw = await self.kv.get(f"trippass:{trippass_id}")
        return TripPass.model_validate_json(raw) if raw else None


def to_async_url(url: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url


class SqlTripPassRepo:
    """One table, JSON payload. Schema is created on first use (MVP); move to Alembic
    migrations before the schema starts changing."""

    def __init__(self, url: str, **engine_kwargs):
        from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine_kwargs.setdefault("pool_pre_ping", True)
        self.engine = create_async_engine(to_async_url(url), **engine_kwargs)
        self.meta = MetaData()
        self.table = Table(
            "trippasses",
            self.meta,
            Column("id", String(32), primary_key=True),
            Column("hold_id", String(32), unique=True, nullable=False),
            Column("issued_at", DateTime(timezone=True), nullable=False),
            Column("data", Text, nullable=False),
        )
        self._ready = False
        self._lock = asyncio.Lock()

    async def _ensure_schema(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if not self._ready:
                async with self.engine.begin() as conn:
                    await conn.run_sync(self.meta.create_all)
                self._ready = True

    async def save(self, tp: TripPass) -> None:
        await self._ensure_schema()
        async with self.engine.begin() as conn:
            await conn.execute(
                self.table.insert().values(
                    id=tp.id, hold_id=tp.hold_id, issued_at=tp.issued_at, data=tp.model_dump_json()
                )
            )

    async def get(self, trippass_id: str) -> TripPass | None:
        from sqlalchemy import select

        await self._ensure_schema()
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(select(self.table.c.data).where(self.table.c.id == trippass_id))
            ).first()
        return TripPass.model_validate_json(row[0]) if row else None
