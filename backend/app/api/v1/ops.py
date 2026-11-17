from typing import Any

from fastapi import APIRouter

from app.ai.reliability import ReliabilityReport, provider_health, reliability_report
from app.api.v1.copilot import Limited
from app.api.v1.deps import ContainerDep

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/providers")
async def providers(c: ContainerDep) -> dict[str, Any]:
    return await provider_health(c)


@router.get("/telemetry")
async def telemetry(c: ContainerDep) -> dict[str, Any]:
    return c.telemetry.snapshot()


@router.post("/reliability-summary", response_model=ReliabilityReport)
async def reliability_summary(c: ContainerDep, _: Limited) -> ReliabilityReport:
    return await reliability_report(c)
