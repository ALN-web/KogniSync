"""Core domain models shared by every service.

Every user-visible fare, time and seat count is a ``Sourced`` value: the value plus where it
came from (live, scheduled or estimated). That is the M3 provenance contract.
"""

from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def as_ist(value: datetime) -> datetime:
    """Treat naive datetimes as IST; convert aware ones to IST."""
    if value.tzinfo is None:
        return value.replace(tzinfo=IST)
    return value.astimezone(IST)


class Mode(StrEnum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"
    CAB = "cab"
    RAPIDO = "rapido"
    METRO = "metro"
    WALK = "walk"


class ProvenanceKind(StrEnum):
    LIVE = "live"
    SCHEDULED = "scheduled"
    ESTIMATED = "estimated"


class Provenance(BaseModel):
    kind: ProvenanceKind
    source: str
    as_of: datetime
    ttl_seconds: int | None = None
    stale: bool = False


T = TypeVar("T")


class Sourced(BaseModel, Generic[T]):  # noqa: UP046 (pydantic generic)
    value: T
    provenance: Provenance


class PlaceKind(StrEnum):
    ADDRESS = "address"
    AIRPORT = "airport"
    STATION = "station"
    BUS_TERMINAL = "bus_terminal"
    METRO_STATION = "metro_station"


class Place(BaseModel):
    name: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    city: str | None = None
    kind: PlaceKind = PlaceKind.ADDRESS
    code: str | None = None


class Leg(BaseModel):
    id: str
    mode: Mode
    provider: str
    service_id: str | None = None
    origin: Place
    destination: Place
    depart: Sourced[datetime]
    arrive: Sourced[datetime]
    fare_inr: Sourced[int]
    distance_km: float
    carbon_g: int
    reliability: float = Field(ge=0, le=1)
    seats_available: Sourced[int] | None = None
    bookable: bool = False
    fixed_schedule: bool = False
    min_connection_min: int = 0

    @property
    def duration_min(self) -> int:
        return int((self.arrive.value - self.depart.value).total_seconds() // 60)


class Weights(BaseModel):
    time: float = Field(0.35, ge=0)
    cost: float = Field(0.30, ge=0)
    carbon: float = Field(0.15, ge=0)
    reliability: float = Field(0.20, ge=0)

    @model_validator(mode="after")
    def _non_zero(self) -> "Weights":
        if self.time + self.cost + self.carbon + self.reliability <= 0:
            raise ValueError("at least one weight must be positive")
        return self


class Constraints(BaseModel):
    depart_after: datetime | None = None
    arrive_by: datetime | None = None
    budget_inr: int | None = Field(None, gt=0)
    max_transfers: int | None = Field(None, ge=0, le=10)
    prefer_modes: list[Mode] = Field(default_factory=list)
    avoid_modes: list[Mode] = Field(default_factory=list)

    @field_validator("depart_after", "arrive_by")
    @classmethod
    def _to_ist(cls, value: datetime | None) -> datetime | None:
        return as_ist(value) if value else None


class Journey(BaseModel):
    id: str
    legs: list[Leg]
    depart: datetime
    arrive: datetime
    duration_min: int
    cost_inr: int
    carbon_kg: float
    reliability: float
    transfers: int
    cost_provenance: ProvenanceKind
    provenance_summary: dict[str, int] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    score: float = 0.0
    constraints: Constraints = Field(default_factory=Constraints)

    @property
    def modes(self) -> list[Mode]:
        return [leg.mode for leg in self.legs]


PlaceInput = str | Place


class SearchRequest(Constraints):
    origin: PlaceInput
    destination: PlaceInput
    weights: Weights = Field(default_factory=Weights)
    limit: int = Field(8, ge=1, le=20)


class SearchResponse(BaseModel):
    search_id: str
    origin: Place
    destination: Place
    journeys: list[Journey]
    considered: int
    pareto_size: int
    rejected: dict[str, int]
    relaxation_hints: list[str]
    time_objective: Literal["arrival", "duration"]
    data_mode: Literal["mock", "live"] = "mock"
