"""Caches journeys returned by search so holds, explanations and the copilot can refer to
them by id."""

from app.domain.models import Journey
from app.services.kv import KV

JOURNEY_TTL_S = 6 * 3600


class JourneyStore:
    def __init__(self, kv: KV):
        self.kv = kv

    async def put(self, journey: Journey) -> None:
        await self.kv.set(f"journey:{journey.id}", journey.model_dump_json(), JOURNEY_TTL_S)

    async def put_many(self, journeys: list[Journey]) -> None:
        for j in journeys:
            await self.put(j)

    async def get(self, journey_id: str) -> Journey | None:
        raw = await self.kv.get(f"journey:{journey_id}")
        return Journey.model_validate_json(raw) if raw else None
