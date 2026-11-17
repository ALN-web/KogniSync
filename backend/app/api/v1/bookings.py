from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.v1.deps import ContainerDep
from app.domain.booking import ConfirmRequest, Hold, HoldRequest, TripPass
from app.services.booking import BookingError
from app.services.idempotency import IdempotencyError
from app.services.trippass import qr_svg

router = APIRouter(tags=["booking"])

IdemKey = Annotated[
    str | None,
    Header(alias="Idempotency-Key", description="Unique per logical request; reuse it on retry"),
]


def _require_key(key: str | None) -> str:
    if not key or not (1 <= len(key) <= 128):
        raise HTTPException(400, "Idempotency-Key header (1-128 chars) is required")
    return key


async def _idempotent(c, scope: str, key: str | None, payload: Any, fn) -> JSONResponse:
    key = _require_key(key)

    async def run():
        try:
            result = await fn()
        except BookingError as e:
            raise HTTPException(e.status, e.detail()) from e
        return 201, result.model_dump(mode="json")

    try:
        status, body, replayed = await c.idempotency.run(scope, key, payload, run)
    except IdempotencyError as e:
        raise HTTPException(e.status, e.detail) from e
    if replayed:
        c.telemetry.incr("idempotent_replays")
    return JSONResponse(
        body, status_code=status, headers={"Idempotent-Replayed": "true" if replayed else "false"}
    )


@router.post("/holds", status_code=201, response_model=Hold)
async def create_hold(req: HoldRequest, c: ContainerDep, idempotency_key: IdemKey = None):
    return await _idempotent(
        c, "hold", idempotency_key, req.model_dump(), lambda: c.booking.create_hold(req)
    )


@router.get("/holds/{hold_id}", response_model=Hold)
async def get_hold(hold_id: str, c: ContainerDep) -> Hold:
    try:
        return await c.booking.get_hold(hold_id)
    except BookingError as e:
        raise HTTPException(e.status, e.detail()) from e


@router.delete("/holds/{hold_id}", response_model=Hold)
async def release_hold(hold_id: str, c: ContainerDep) -> Hold:
    try:
        return await c.booking.release_hold(hold_id)
    except BookingError as e:
        raise HTTPException(e.status, e.detail()) from e


@router.post("/bookings", status_code=201, response_model=TripPass)
async def confirm_booking(req: ConfirmRequest, c: ContainerDep, idempotency_key: IdemKey = None):
    return await _idempotent(
        c, "booking", idempotency_key, req.model_dump(), lambda: c.booking.confirm(req)
    )


@router.get("/trippass/{trippass_id}", response_model=TripPass)
async def get_trippass(trippass_id: str, c: ContainerDep) -> TripPass:
    try:
        return await c.booking.get_trippass(trippass_id)
    except BookingError as e:
        raise HTTPException(e.status, e.detail()) from e


@router.get("/trippass/{trippass_id}/qr.svg")
async def trippass_qr(trippass_id: str, c: ContainerDep) -> Response:
    tp = await get_trippass(trippass_id, c)
    return Response(
        qr_svg(tp.qr_payload),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=3600"},
    )


class VerifyRequest(BaseModel):
    token: str


class VerifyResponse(BaseModel):
    valid: bool
    trippass_id: str | None = None
    passengers: int | None = None


@router.post("/trippass/verify", response_model=VerifyResponse)
async def verify_trippass(req: VerifyRequest, c: ContainerDep) -> VerifyResponse:
    claims = c.booking.verify_token(req.token)
    if claims is None:
        return VerifyResponse(valid=False)
    return VerifyResponse(valid=True, trippass_id=claims["tp"], passengers=claims["pax"])
