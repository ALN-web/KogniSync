"""Mock carrier and payment adapters with real concurrency semantics.

Seat inventory is a counter in the KV store (Redis in production). A hold decrements it
atomically; if that takes it below zero the decrement is undone and the hold fails, so seats
are never oversold even when many travelers race for the last seat.
"""

import json
import secrets
import string
import uuid

from app.domain.models import Leg
from app.services.kv import KV

INVENTORY_TTL_S = 3 * 24 * 3600


class VendorError(Exception):
    def __init__(self, leg: Leg, reason: str):
        super().__init__(f"{leg.provider}: {reason}")
        self.leg, self.reason = leg, reason


def _pnr() -> str:
    return "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))


class MockVendor:
    def __init__(self, kv: KV):
        self.kv = kv
        # Fault injection for tests and demos: service ids that fail at hold / confirm time.
        self.fail_hold: set[str] = set()
        self.fail_confirm: set[str] = set()

    async def seats_left(self, leg: Leg) -> int:
        await self._init_inventory(leg)
        return int(await self.kv.get(f"inv:{leg.service_id}") or 0)

    async def _init_inventory(self, leg: Leg) -> None:
        seats = leg.seats_available.value if leg.seats_available else 50
        await self.kv.set(f"inv:{leg.service_id}", str(seats), INVENTORY_TTL_S, nx=True)

    async def hold(self, leg: Leg, passengers: int, ttl_s: int) -> str:
        if leg.service_id in self.fail_hold:
            raise VendorError(leg, "vendor rejected the hold")
        await self._init_inventory(leg)
        left = await self.kv.incrby(f"inv:{leg.service_id}", -passengers)
        if left < 0:
            await self.kv.incrby(f"inv:{leg.service_id}", passengers)
            raise VendorError(leg, "not enough seats left")
        ref = "VH-" + uuid.uuid4().hex[:10].upper()
        await self.kv.set(
            f"vhold:{ref}",
            json.dumps({"service_id": leg.service_id, "passengers": passengers, "state": "held"}),
            ttl_s + 3600,
        )
        return ref

    async def release(self, ref: str) -> None:
        """Give seats back. Safe to call twice: only the first call restores inventory."""
        raw = await self.kv.get(f"vhold:{ref}")
        if raw is None:
            return
        if not await self.kv.set(f"vrel:{ref}", "1", INVENTORY_TTL_S, nx=True):
            return
        rec = json.loads(raw)
        await self.kv.incrby(f"inv:{rec['service_id']}", rec["passengers"])
        await self.kv.delete(f"vhold:{ref}")

    async def confirm(self, leg: Leg, ref: str) -> str:
        if leg.service_id in self.fail_confirm:
            raise VendorError(leg, "vendor failed to ticket")
        raw = await self.kv.get(f"vhold:{ref}")
        if raw is None:
            raise VendorError(leg, "hold expired at vendor")
        rec = json.loads(raw)
        pnr = _pnr()
        rec.update(state="confirmed", pnr=pnr)
        await self.kv.set(f"vhold:{ref}", json.dumps(rec), INVENTORY_TTL_S)
        return pnr

    async def cancel(self, ref: str) -> None:
        """Cancel a confirmed ticket (saga compensation) and return the seats."""
        await self.release(ref)


class MockPayments:
    """Charges are keyed, so the same hold can never be charged twice."""

    def __init__(self, kv: KV):
        self.kv = kv
        self.charges = 0
        self.refunds = 0

    async def charge(self, key: str, amount_inr: int) -> str:
        payment_id = "PAY-" + uuid.uuid4().hex[:12].upper()
        if await self.kv.set(
            f"payment:{key}", json.dumps({"id": payment_id, "amount": amount_inr}), nx=True
        ):
            self.charges += 1
            return payment_id
        return json.loads(await self.kv.get(f"payment:{key}") or "{}")["id"]

    async def refund(self, key: str) -> None:
        if await self.kv.set(f"refund:{key}", "1", nx=True):
            self.refunds += 1
