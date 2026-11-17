from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import Journey, Mode


class HoldStatus(StrEnum):
    HELD = "held"
    CONFIRMED = "confirmed"
    RELEASED = "released"
    EXPIRED = "expired"


class LegHold(BaseModel):
    leg_id: str
    service_id: str
    mode: Mode
    provider: str
    vendor_ref: str
    fare_inr: int
    passengers: int


class Hold(BaseModel):
    id: str
    journey_id: str
    journey: Journey
    passengers: int
    legs: list[LegHold]
    total_due_now_inr: int
    pay_later_estimate_inr: int
    created_at: datetime
    expires_at: datetime
    status: HoldStatus
    trippass_id: str | None = None


class HoldRequest(BaseModel):
    journey_id: str
    passengers: int = Field(1, ge=1, le=6)


class ConfirmRequest(BaseModel):
    hold_id: str
    expected_total_inr: int = Field(ge=0)
    # The traveler must explicitly agree. Anything other than `true` is rejected.
    consent: Literal[True]


class BookedLeg(BaseModel):
    leg_id: str
    mode: Mode
    provider: str
    status: Literal["confirmed", "pay_at_travel"]
    pnr: str | None = None


class TripPass(BaseModel):
    id: str
    hold_id: str
    journey: Journey
    passengers: int
    booked_legs: list[BookedLeg]
    total_paid_inr: int
    pay_later_estimate_inr: int
    payment_id: str
    issued_at: datetime
    token: str
    qr_payload: str
