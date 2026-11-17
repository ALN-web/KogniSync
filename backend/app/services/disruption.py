"""M5: disruption detection, cascade impact and recovery.

Freshness rules:
- A disruption expires at ``expires_at`` and is then ignored.
- A disruption not updated for 30 minutes is marked ``stale``: still shown and still used for
  impact, but the impact is flagged as based on stale data.

Cascade: delays flow forward through the itinerary. On-demand legs (cab, Rapido, metro, walk)
simply start later. Fixed-schedule legs (flight, train, intercity bus) do not wait: if the
traveler reaches the hub after the boarding cutoff the connection is missed, and everything
after it needs a new plan.

Recovery re-plans from the point where the trip breaks, with the remaining budget and the
original deadline, avoiding cancelled services. It only proposes options; booking one goes
through the normal hold + consent flow. KogniSync never rebooks on its own.
"""

import json
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from app.domain.disruption import (
    Disruption,
    DisruptionCreate,
    DisruptionKind,
    Impact,
    LegImpact,
    Recovery,
)
from app.domain.models import Journey, Leg, ProvenanceKind, SearchRequest
from app.services.journey_store import JourneyStore
from app.services.kv import KV
from app.services.optimizer import fmt_minutes
from app.services.orchestrator import Orchestrator
from app.services.provenance import make
from app.services.telemetry import Telemetry

STALE_AFTER = timedelta(minutes=30)
FEED_SOURCE = "mock:live-disruption-feed"
BLOCKING = {DisruptionKind.CANCELLATION, DisruptionKind.CLOSURE}


def affects(d: Disruption, leg: Leg) -> bool:
    if d.service_id:
        return leg.service_id == d.service_id
    if d.mode and leg.mode != d.mode:
        return False
    if d.provider and d.provider.lower() not in leg.provider.lower():
        return False
    if d.city and d.city not in (leg.origin.city, leg.destination.city):
        return False
    return True


def _minutes(a: datetime, b: datetime) -> int:
    return int((a - b).total_seconds() // 60)


class DisruptionService:
    def __init__(
        self,
        *,
        kv: KV,
        orchestrator: Orchestrator,
        journeys: JourneyStore,
        telemetry: Telemetry,
        clock: Callable[[], datetime],
    ):
        self.kv, self.orchestrator, self.journeys = kv, orchestrator, journeys
        self.telemetry, self.clock = telemetry, clock

    # ---------------- feed ----------------

    async def _load(self) -> list[Disruption]:
        raw = await self.kv.get("disruptions")
        return [Disruption.model_validate(d) for d in json.loads(raw)] if raw else []

    async def _store(self, items: list[Disruption]) -> None:
        await self.kv.set("disruptions", json.dumps([d.model_dump(mode="json") for d in items]))

    async def active(self, city: str | None = None) -> list[Disruption]:
        now = self.clock()
        items = [d for d in await self._load() if d.expires_at > now]
        items = [d.model_copy(update={"stale": now - d.reported_at > STALE_AFTER}) for d in items]
        if city:
            items = [d for d in items if d.city in (None, city)]
        return items

    async def add(self, req: DisruptionCreate) -> Disruption:
        now = self.clock()
        d = Disruption(
            **req.model_dump(),
            id="D" + uuid.uuid4().hex[:10].upper(),
            reported_at=now,
            expires_at=now + timedelta(minutes=req.ttl_min),
            source=FEED_SOURCE,
            provenance=make(
                ProvenanceKind.LIVE, FEED_SOURCE, now, int(STALE_AFTER.total_seconds())
            ),
        )
        items = [x for x in await self._load() if x.expires_at > now]
        await self._store(items + [d])
        self.telemetry.event(
            "disruption_reported", disruption_id=d.id, disruption_kind=d.kind.value
        )
        return d

    async def clear(self) -> None:
        await self._store([])

    async def feed_health(self) -> dict:
        items = await self.active()
        last = max((d.reported_at for d in items), default=None)
        return {
            "source": FEED_SOURCE,
            "status": "stale" if items and all(d.stale for d in items) else "ok",
            "active": len(items),
            "stale": sum(d.stale for d in items),
            "last_update": last,
        }

    # ---------------- impact ----------------

    def assess(self, journey: Journey, disruptions: list[Disruption]) -> Impact:
        legs: list[LegImpact] = []
        prev_arrival: datetime | None = None
        prev_planned: datetime | None = None
        broken: int | None = None
        stale_used = False
        for i, leg in enumerate(journey.legs):
            ds = [d for d in disruptions if affects(d, leg)]
            stale_used |= any(d.stale for d in ds)
            causes = [d.id for d in ds]
            own_delay = timedelta(
                minutes=max((d.delay_min for d in ds if d.kind == DisruptionKind.DELAY), default=0)
            )
            dep, arr = leg.depart.value, leg.arrive.value
            base = dict(
                leg_id=leg.id,
                mode=leg.mode,
                provider=leg.provider,
                planned_depart=dep,
                planned_arrive=arr,
                causes=causes,
            )

            if broken is not None:
                legs.append(
                    LegImpact(
                        **base,
                        status="needs_replan",
                        expected_depart=None,
                        expected_arrive=None,
                        delay_min=0,
                    )
                )
                continue
            if any(d.kind in BLOCKING for d in ds):
                broken = i
                legs.append(
                    LegImpact(
                        **base,
                        status="cancelled",
                        expected_depart=None,
                        expected_arrive=None,
                        delay_min=0,
                    )
                )
                continue

            status = "on_time"
            if leg.fixed_schedule:
                exp_dep = dep + own_delay
                if prev_arrival is not None:
                    # Boarding cutoff is half the recommended buffer (e.g. 45 of 90 min).
                    cutoff = timedelta(minutes=leg.min_connection_min / 2)
                    buffer = timedelta(minutes=leg.min_connection_min)
                    if prev_arrival + cutoff > exp_dep:
                        broken = i
                        legs.append(
                            LegImpact(
                                **base,
                                status="missed_connection",
                                expected_depart=None,
                                expected_arrive=None,
                                delay_min=0,
                            )
                        )
                        continue
                    if prev_arrival + buffer > exp_dep:
                        status = "at_risk"
                exp_arr = arr + own_delay
            else:
                # Keep the planned gap after the previous leg (e.g. 25 min to exit an airport).
                gap = dep - prev_planned if prev_planned is not None else timedelta(0)
                start = dep if prev_arrival is None else max(dep, prev_arrival + gap)
                exp_dep = start + own_delay
                exp_arr = exp_dep + (arr - dep)
            delay = _minutes(exp_arr, arr)
            if status == "on_time" and delay >= 5:
                status = "delayed"
            legs.append(
                LegImpact(
                    **base,
                    status=status,
                    expected_depart=exp_dep,
                    expected_arrive=exp_arr,
                    delay_min=delay,
                )
            )
            prev_arrival, prev_planned = exp_arr, arr

        expected = None if broken is not None else prev_arrival
        arrival_delay = _minutes(expected, journey.arrive) if expected else None
        deadline = journey.constraints.arrive_by
        deadline_missed = (
            broken is not None
            and deadline is not None
            or bool(deadline and expected and expected > deadline)
        )
        if broken is not None:
            severity = "critical"
        elif deadline_missed or (arrival_delay or 0) >= 60:
            severity = "major"
        elif (arrival_delay or 0) >= 10 or any(leg.status == "at_risk" for leg in legs):
            severity = "minor"
        else:
            severity = "none"
        return Impact(
            journey_id=journey.id,
            severity=severity,
            legs=legs,
            first_broken_leg=broken,
            expected_arrival=expected,
            arrival_delay_min=arrival_delay,
            deadline_missed=deadline_missed,
            based_on_stale_data=stale_used,
            summary=self._summary(journey, legs, broken, arrival_delay, deadline_missed),
        )

    @staticmethod
    def _summary(
        journey: Journey,
        legs: list[LegImpact],
        broken: int | None,
        arrival_delay: int | None,
        deadline_missed: bool,
    ) -> str:
        if broken is not None:
            leg = legs[broken]
            what = "is cancelled" if leg.status == "cancelled" else "will be missed"
            later = len(legs) - broken - 1
            tail = f" {later} later leg(s) need a new plan." if later else ""
            return f"{leg.provider} {what}.{tail} See recovery options."
        delayed = [leg for leg in legs if leg.status in ("delayed", "at_risk")]
        if not delayed:
            return "No disruptions affect this trip."
        first = delayed[0]
        msg = (
            f"{first.provider} is running about {fmt_minutes(first.delay_min)} late. "
            f"Expected arrival is {fmt_minutes(arrival_delay or 0)} later than planned."
        )
        if any(leg.status == "at_risk" for leg in legs):
            msg += " A connection is now tight."
        if deadline_missed:
            msg += " You will miss your arrival deadline."
        return msg

    # ---------------- recovery ----------------

    async def recover(self, journey: Journey) -> Recovery:
        active = await self.active()
        impact = self.assess(journey, active)
        if impact.severity in ("none", "minor") and not impact.deadline_missed:
            return Recovery(
                impact=impact,
                replaces_from_leg=None,
                options=[],
                note="No change needed. Your current plan still works.",
            )

        k = impact.first_broken_leg
        if k is None:
            k = next(i for i, leg in enumerate(impact.legs) if leg.status in ("delayed", "at_risk"))
        start_place = journey.legs[k].origin
        reach = impact.legs[k - 1].expected_arrive if k > 0 else None
        start_time = max(self.clock(), reach or self.clock())
        c = journey.constraints
        spent = sum(leg.fare_inr.value for leg in journey.legs[:k])
        budget = c.budget_inr - spent if c.budget_inr else None
        if budget is not None and budget <= 0:
            return Recovery(
                impact=impact,
                replaces_from_leg=k,
                options=[],
                note="Your budget is already used up by the legs travelled so far.",
            )
        broken_service = journey.legs[k].service_id if impact.first_broken_leg is not None else None

        def exclude(leg: Leg) -> bool:
            if broken_service and leg.service_id == broken_service:
                return True
            return any(d.kind in BLOCKING and affects(d, leg) for d in active)

        result = self.orchestrator.search(
            SearchRequest(
                origin=start_place,
                destination=journey.legs[-1].destination,
                depart_after=start_time,
                arrive_by=c.arrive_by,
                budget_inr=budget,
                avoid_modes=c.avoid_modes,
                prefer_modes=c.prefer_modes,
                limit=5,
            ),
            exclude=exclude,
        )
        options = [j for j in result.journeys if not self._delayed_by(j, active)] or result.journeys
        await self.journeys.put_many(options)
        self.telemetry.event("recovery_proposed", journey_id=journey.id, options=len(options))
        note = (
            f"These options replace your plan from {start_place.name} onwards. "
            "Nothing changes until you choose one and confirm the booking."
        )
        if not options:
            note = " ".join(result.relaxation_hints) or "No alternative found."
        return Recovery(impact=impact, replaces_from_leg=k, options=options, note=note)

    def _delayed_by(self, journey: Journey, active: list[Disruption]) -> bool:
        return self.assess(journey, active).severity in ("major", "critical")
