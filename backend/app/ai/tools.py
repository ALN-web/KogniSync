"""Tools the copilot may call. Every argument set is validated with Pydantic before running.

``create_hold`` never holds anything: it returns a proposal that the traveler must confirm in
the app (which then calls the normal idempotent hold + consent flow).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.ai.intent import ModeName, parse_dt
from app.ai.llm import ToolSpec
from app.data.cities import UnknownPlaceError
from app.domain.models import Journey, SearchRequest
from app.services import provenance
from app.services.optimizer import fmt_inr, fmt_minutes


class SearchArgs(BaseModel):
    origin: str = Field(description="Start place, e.g. 'Udayapalya, Bengaluru'")
    destination: str = Field(description="End place, e.g. 'Connaught Place, Delhi'")
    depart_after: str | None = Field(None, description="ISO 8601 IST datetime")
    arrive_by: str | None = Field(None, description="ISO 8601 IST datetime deadline")
    budget_inr: int | None = Field(None, description="Hard budget in rupees")
    prefer_modes: list[ModeName] = Field(default_factory=list)
    avoid_modes: list[ModeName] = Field(default_factory=list)


class DisruptionArgs(BaseModel):
    city: str | None = Field(None, description="City code such as BLR or DEL")
    trippass_id: str | None = Field(None, description="Assess impact on this booked trip")


class JourneyArgs(BaseModel):
    journey_id: str


class HoldArgs(BaseModel):
    journey_id: str
    passengers: int = Field(1, ge=1, le=6)


class NoArgs(BaseModel):
    pass


class ProposedAction(BaseModel):
    type: Literal["hold"] = "hold"
    journey_id: str
    passengers: int
    cost_inr: int
    cost_provenance: str
    summary: str
    requires_consent: Literal[True] = True


def route_text(j: Journey) -> str:
    parts = []
    for leg in j.legs:
        label = leg.mode.value
        if leg.mode.value in ("flight", "train", "bus") and leg.bookable:
            label += f" ({leg.provider}, fare {leg.fare_inr.provenance.kind.value})"
        parts.append(label)
    return " -> ".join(parts)


def journey_summary(j: Journey) -> dict[str, Any]:
    return {
        "journey_id": j.id,
        "labels": j.labels,
        "route": route_text(j),
        "depart": j.depart.strftime("%a %d %b %H:%M"),
        "arrive": j.arrive.strftime("%a %d %b %H:%M"),
        "duration": fmt_minutes(j.duration_min),
        "cost_inr": j.cost_inr,
        "cost_display": fmt_inr(j.cost_inr),
        "cost_provenance": j.cost_provenance.value,
        "carbon_kg": j.carbon_kg,
        "reliability": j.reliability,
        "why": j.explanation[:3],
        "warnings": j.warnings,
    }


@dataclass
class ToolContext:
    journeys: list[Journey] = field(default_factory=list)
    proposed_action: ProposedAction | None = None
    payloads: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Tool:
    spec: ToolSpec
    args: type[BaseModel]
    run: Callable[[Any, ToolContext], Awaitable[dict[str, Any]]]


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    schema = model.model_json_schema()
    schema.pop("title", None)
    for prop in schema.get("properties", {}).values():
        prop.pop("title", None)
    return schema


class ToolRegistry:
    def __init__(self, container):
        self.c = container
        self.tools: dict[str, Tool] = {}
        self._add(
            "search_journeys",
            "Plan door-to-door journeys across flight, train, bus, cab, Rapido, metro and "
            "walking. Returns ranked Pareto-optimal options with provenance labels.",
            SearchArgs,
            self._search,
        )
        self._add(
            "get_disruptions",
            "List live disruptions, and the impact on a booked trip if trippass_id is given.",
            DisruptionArgs,
            self._disruptions,
        )
        self._add(
            "explain_route",
            "Full detail of one journey: every leg, fare and time with its provenance "
            "(live, scheduled or estimated) and the reasons it was ranked.",
            JourneyArgs,
            self._explain,
        )
        self._add(
            "create_hold",
            "Propose holding seats on a journey. Does NOT hold or book: the traveler must "
            "confirm in the app.",
            HoldArgs,
            self._hold,
        )
        self._add(
            "provider_health",
            "Health of data feeds, booking vendors and the AI layer.",
            NoArgs,
            self._health,
        )

    def _add(self, name, description, args, run) -> None:
        self.tools[name] = Tool(ToolSpec(name, description, _schema(args)), args, run)

    @property
    def specs(self) -> list[ToolSpec]:
        return [t.spec for t in self.tools.values()]

    async def execute(self, name: str, args: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"unknown tool {name}"}
        try:
            parsed = tool.args.model_validate(args or {})
        except ValidationError as e:
            return {"error": "invalid arguments", "details": e.errors(include_url=False)}
        result = await tool.run(parsed, ctx)
        ctx.payloads.append(result)
        self.c.telemetry.incr(f"tool_{name}")
        return result

    # ---------------- implementations ----------------

    async def _search(self, a: SearchArgs, ctx: ToolContext) -> dict[str, Any]:
        try:
            req = SearchRequest(
                origin=a.origin,
                destination=a.destination,
                depart_after=parse_dt(a.depart_after),
                arrive_by=parse_dt(a.arrive_by),
                budget_inr=a.budget_inr,
                prefer_modes=a.prefer_modes,
                avoid_modes=a.avoid_modes,
                limit=5,
            )
            result = self.c.orchestrator.search(req)
        except (UnknownPlaceError, ValueError) as e:
            return {"error": str(e)}
        await self.c.journeys.put_many(result.journeys)
        ctx.journeys = result.journeys
        return {
            "origin": result.origin.name,
            "destination": result.destination.name,
            "data_mode": result.data_mode,
            "journeys": [journey_summary(j) for j in result.journeys],
            "relaxation_hints": result.relaxation_hints,
        }

    async def _disruptions(self, a: DisruptionArgs, ctx: ToolContext) -> dict[str, Any]:
        active = await self.c.disruptions.active(a.city)
        out: dict[str, Any] = {
            "disruptions": [
                {
                    "id": d.id,
                    "kind": d.kind.value,
                    "mode": d.mode,
                    "provider": d.provider,
                    "service_id": d.service_id,
                    "city": d.city,
                    "delay_min": d.delay_min,
                    "message": d.message,
                    "stale": d.stale,
                }
                for d in active
            ]
        }
        if a.trippass_id:
            tp = await self.c.booking.repo.get(a.trippass_id)
            if tp is None:
                out["error"] = "TripPass not found"
            else:
                impact = self.c.disruptions.assess(tp.journey, active)
                out["impact"] = {
                    "severity": impact.severity,
                    "summary": impact.summary,
                    "arrival_delay_min": impact.arrival_delay_min,
                    "deadline_missed": impact.deadline_missed,
                }
        return out

    async def _explain(self, a: JourneyArgs, ctx: ToolContext) -> dict[str, Any]:
        j = await self.c.journeys.get(a.journey_id)
        if j is None:
            return {"error": "journey not found; search again"}
        j = provenance.refresh_journey(j, self.c.clock())
        ctx.journeys = [j]
        return {
            **journey_summary(j),
            "explanation": j.explanation,
            "legs": [
                {
                    "mode": leg.mode.value,
                    "provider": leg.provider,
                    "from": leg.origin.name,
                    "to": leg.destination.name,
                    "depart": leg.depart.value.strftime("%H:%M"),
                    "depart_provenance": leg.depart.provenance.kind.value,
                    "fare_inr": leg.fare_inr.value,
                    "fare_provenance": leg.fare_inr.provenance.kind.value,
                    "fare_source": leg.fare_inr.provenance.source,
                }
                for leg in j.legs
            ],
        }

    async def _hold(self, a: HoldArgs, ctx: ToolContext) -> dict[str, Any]:
        j = await self.c.journeys.get(a.journey_id)
        if j is None:
            return {"error": "journey not found; search again"}
        ctx.proposed_action = ProposedAction(
            journey_id=j.id,
            passengers=a.passengers,
            cost_inr=j.cost_inr * a.passengers,
            cost_provenance=j.cost_provenance.value,
            summary=route_text(j),
        )
        return {
            "status": "awaiting_user_consent",
            "journey_id": j.id,
            "cost_inr": j.cost_inr * a.passengers,
            "note": "Nothing is held yet. The traveler must review and confirm in the app.",
        }

    async def _health(self, a: NoArgs, ctx: ToolContext) -> dict[str, Any]:
        from app.ai.reliability import provider_health

        return await provider_health(self.c)
