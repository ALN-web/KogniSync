"""A tiny async key-value interface with an in-memory and a Redis implementation.

Holds, idempotency records, seat inventory, cached journeys and disruptions all live here.
Locally (no REDIS_URL) the in-memory store is used; on Cloud Run, Memorystore for Redis is
used so every instance shares the same state.
"""

import asyncio
import time
from typing import Protocol


class KV(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(
        self, key: str, value: str, ttl_s: float | None = None, nx: bool = False
    ) -> bool: ...
    async def delete(self, key: str) -> None: ...
    async def incrby(self, key: str, amount: int) -> int: ...
    async def ping(self) -> bool: ...


class MemoryKV:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = asyncio.Lock()

    def _alive(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expires = item
        if expires is not None and expires <= time.monotonic():
            del self._data[key]
            return None
        return value

    async def get(self, key: str) -> str | None:
        async with self._lock:
            return self._alive(key)

    async def set(self, key: str, value: str, ttl_s: float | None = None, nx: bool = False) -> bool:
        async with self._lock:
            if nx and self._alive(key) is not None:
                return False
            expires = time.monotonic() + ttl_s if ttl_s else None
            self._data[key] = (value, expires)
            return True

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def incrby(self, key: str, amount: int) -> int:
        async with self._lock:
            current = self._alive(key)
            expires = self._data[key][1] if current is not None else None
            new = int(current or 0) + amount
            self._data[key] = (str(new), expires)
            return new

    async def ping(self) -> bool:
        return True


class RedisKV:
    def __init__(self, client) -> None:  # redis.asyncio.Redis (decode_responses=True)
        self._r = client

    @classmethod
    def from_url(cls, url: str) -> "RedisKV":
        import redis.asyncio as redis

        return cls(redis.from_url(url, decode_responses=True))

    async def get(self, key: str) -> str | None:
        return await self._r.get(key)

    async def set(self, key: str, value: str, ttl_s: float | None = None, nx: bool = False) -> bool:
        px = int(ttl_s * 1000) if ttl_s else None
        return bool(await self._r.set(key, value, px=px, nx=nx))

    async def delete(self, key: str) -> None:
        await self._r.delete(key)

    async def incrby(self, key: str, amount: int) -> int:
        return int(await self._r.incrby(key, amount))

    async def ping(self) -> bool:
        return bool(await self._r.ping())
