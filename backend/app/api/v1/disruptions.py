from fastapi import APIRouter, HTTPException

from app.api.v1.deps import ContainerDep
from app.domain.disruption import Disruption, DisruptionCreate, Impact, Recovery
from app.domain.models import Journey
from app.services.booking import BookingError

router = APIRouter(tags=["disruptions"])


def _require_simulation(c) -> None:
    if not c.settings.enable_simulation:
        raise HTTPException(403, "Disruption simulation is disabled in this environment")


@router.get("/disruptions", response_model=list[Disruption])
async def list_disruptions(c: ContainerDep, city: str | None = None) -> list[Disruption]:
    return await c.disruptions.active(city)


@router.post("/disruptions", response_model=Disruption, status_code=201)
async def report_disruption(req: DisruptionCreate, c: ContainerDep) -> Disruption:
    """Inject a disruption into the mock live feed (demo and testing)."""
    _require_simulation(c)
    return await c.disruptions.add(req)


@router.delete("/disruptions", status_code=204)
async def clear_disruptions(c: ContainerDep) -> None:
    _require_simulation(c)
    await c.disruptions.clear()


async def _journey(c, journey_id: str) -> Journey:
    j = await c.journeys.get(journey_id)
    if j is None:
        raise HTTPException(404, "Journey not found or expired")
    return j


async def _trippass_journey(c, trippass_id: str) -> Journey:
    try:
        return (await c.booking.get_trippass(trippass_id)).journey
    except BookingError as e:
        raise HTTPException(e.status, e.detail()) from e


@router.get("/journeys/{journey_id}/impact", response_model=Impact)
async def journey_impact(journey_id: str, c: ContainerDep) -> Impact:
    return c.disruptions.assess(await _journey(c, journey_id), await c.disruptions.active())


@router.get("/trippass/{trippass_id}/impact", response_model=Impact)
async def trippass_impact(trippass_id: str, c: ContainerDep) -> Impact:
    return c.disruptions.assess(
        await _trippass_journey(c, trippass_id), await c.disruptions.active()
    )


@router.post("/trippass/{trippass_id}/recovery", response_model=Recovery)
async def trippass_recovery(trippass_id: str, c: ContainerDep) -> Recovery:
    """Propose recovery options. Proposals only: booking one needs a new hold and consent."""
    return await c.disruptions.recover(await _trippass_journey(c, trippass_id))


@router.post("/journeys/{journey_id}/recovery", response_model=Recovery)
async def journey_recovery(journey_id: str, c: ContainerDep) -> Recovery:
    return await c.disruptions.recover(await _journey(c, journey_id))
