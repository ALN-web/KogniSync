"""Idempotency keys for money-moving endpoints (holds, bookings).

The first request with a key runs; every retry with the same key and the same body gets the
stored response back (marked as a replay), so a flaky network can never double-hold seats or
double-charge. Reusing a key with a different body is an error. A request that crashes (5xx)
is not stored, so the client can retry it.
"""

import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException

from app.services.kv import KV

RECORD_TTL_S = 24 * 3600
LOCK_TTL_S = 60


class IdempotencyError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


def body_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class IdempotencyService:
    def __init__(self, kv: KV):
        self.kv = kv

    async def run(
        self,
        scope: str,
        key: str,
        payload: Any,
        fn: Callable[[], Awaitable[tuple[int, Any]]],
    ) -> tuple[int, Any, bool]:
        """Return (status, body, replayed)."""
        rkey = f"idem:{scope}:{key}"
        digest = body_hash(payload)
        claimed = await self.kv.set(
            rkey, json.dumps({"state": "in_progress", "hash": digest}), LOCK_TTL_S, nx=True
        )
        if not claimed:
            raw = await self.kv.get(rkey)
            if raw is None:  # expired between calls; treat as new
                return await self.run(scope, key, payload, fn)
            record = json.loads(raw)
            if record["hash"] != digest:
                raise IdempotencyError(
                    422, "Idempotency-Key was already used with a different request body"
                )
            if record["state"] == "in_progress":
                raise IdempotencyError(409, "A request with this Idempotency-Key is in progress")
            return record["status"], record["body"], True

        try:
            status, body = await fn()
        except HTTPException as e:
            if e.status_code >= 500:
                await self.kv.delete(rkey)
                raise
            status, body = e.status_code, {"detail": e.detail}
        except Exception:
            await self.kv.delete(rkey)
            raise
        await self.kv.set(
            rkey,
            json.dumps(
                {"state": "done", "hash": digest, "status": status, "body": body}, default=str
            ),
            RECORD_TTL_S,
        )
        return status, body, False
