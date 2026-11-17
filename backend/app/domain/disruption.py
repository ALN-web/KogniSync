from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.models import Journey, Mode, Provenance


class DisruptionKind(StrEnum):
    DELAY = "delay"
    CANCELLATION = "cancellation"
    CLOSURE = "closure"  # e.g. a metro line or road closed


class DisruptionCreate(BaseModel):
    kind: DisruptionKind
    mode: Mode | None = None
    service_id: str | None = None
    provider: str | None = Field(None, description="Substring of the provider, e.g. 'Namma Metro'")
    city: str | None = Field(None, description="City key, e.g. BLR")
    delay_min: int = Field(0, ge=0, le=1440)
    message: str = ""
    ttl_min: int = Field(180, ge=5, le=2880)

    @model_validator(mode="after")
    def _scoped(self) -> "DisruptionCreate":
        if not (self.service_id or self.mode or self.provider or self.city):
            raise ValueError("a disruption needs a service_id, mode, provider or city")
        if self.kind == DisruptionKind.DELAY and self.delay_min <= 0:
            raise ValueError("a delay needs delay_min > 0")
        return self


class Disruption(DisruptionCreate):
    id: str
    reported_at: datetime
    expires_at: datetime
    source: str
    provenance: Provenance
    stale: bool = False


LegStatus = Literal[
    "on_time", "delayed", "at_risk", "missed_connection", "cancelled", "needs_replan"
]
Severity = Literal["none", "minor", "major", "critical"]


class LegImpact(BaseModel):
    leg_id: str
    mode: Mode
    provider: str
    status: LegStatus
    planned_depart: datetime
    planned_arrive: datetime
    expected_depart: datetime | None
    expected_arrive: datetime | None
    delay_min: int
    causes: list[str] = Field(default_factory=list)


class Impact(BaseModel):
    journey_id: str
    severity: Severity
    legs: list[LegImpact]
    first_broken_leg: int | None
    expected_arrival: datetime | None
    arrival_delay_min: int | None
    deadline_missed: bool
    based_on_stale_data: bool
    summary: str


class Recovery(BaseModel):
    impact: Impact
    replaces_from_leg: int | None
    options: list[Journey]
    requires_consent: Literal[True] = True
    note: str
