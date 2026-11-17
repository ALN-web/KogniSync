from fastapi import APIRouter, HTTPException

from app.api.v1.deps import ContainerDep
from app.data.cities import UnknownPlaceError, known_place_names
from app.domain.models import Journey, SearchRequest, SearchResponse
from app.services import provenance

router = APIRouter(tags=["journeys"])


@router.post("/journeys/search", response_model=SearchResponse)
async def search_journeys(req: SearchRequest, c: ContainerDep) -> SearchResponse:
    try:
        result = c.orchestrator.search(req)
    except UnknownPlaceError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    await c.journeys.put_many(result.journeys)
    c.telemetry.incr("journey_searches")
    return result


@router.get("/journeys/{journey_id}", response_model=Journey)
async def get_journey(journey_id: str, c: ContainerDep) -> Journey:
    journey = await c.journeys.get(journey_id)
    if journey is None:
        raise HTTPException(status_code=404, detail="Journey not found or expired; search again")
    # Re-apply freshness rules: a live fare that was fresh at search time may be stale now.
    return provenance.refresh_journey(journey, c.clock())


@router.get("/places")
async def list_places() -> dict[str, list[str]]:
    return {"places": known_place_names()}
