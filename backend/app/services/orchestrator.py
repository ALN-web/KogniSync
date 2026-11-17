"""M2: journey orchestrator. Composes door-to-door journeys across all 7 modes.

Intercity: first mile (walk / cab / Rapido / metro / city bus) -> trunk (flight / train /
intercity bus) -> last mile. First-mile legs are timed backwards from the trunk departure
minus its connection buffer (e.g. 90 min before a flight), so the traveler leaves home as late
as is safe. Same-city trips use local chains only.
"""

import math
import uuid
from collections.abc import Callable
from datetime import datetime, time, timedelta

from app.data.cities import CITIES, resolve_place
from app.domain.models import (
    Constraints,
    Journey,
    Leg,
    Mode,
    Place,
    SearchRequest,
    SearchResponse,
)
from app.providers.mock import EGRESS_MIN, MockTransport, stable_hash
from app.services import optimizer, provenance

HORIZON = timedelta(hours=30)

LegFilter = Callable[[Leg], bool]


def build_journey(legs: list[Leg], constraints: Constraints) -> Journey:
    vehicle_legs = [leg for leg in legs if leg.mode != Mode.WALK]
    cost_kind, summary = provenance.summarize(legs)
    warnings = []
    for leg in legs:
        seats = leg.seats_available
        if seats is not None and seats.value <= 5:
            warnings.append(f"Only {seats.value} seats left on {leg.provider}.")
    return Journey(
        id="J" + format(stable_hash(*(leg.id for leg in legs)), "x"),
        legs=legs,
        depart=legs[0].depart.value,
        arrive=legs[-1].arrive.value,
        duration_min=int((legs[-1].arrive.value - legs[0].depart.value).total_seconds() // 60),
        cost_inr=sum(leg.fare_inr.value for leg in legs),
        carbon_kg=round(sum(leg.carbon_g for leg in legs) / 1000, 1),
        reliability=round(math.prod(leg.reliability for leg in legs), 3),
        transfers=max(0, len(vehicle_legs) - 1),
        cost_provenance=cost_kind,
        provenance_summary=summary,
        warnings=warnings,
        constraints=constraints,
    )


SERVICE_START, SERVICE_END = time(5, 30), time(23, 0)


def in_service(leg: Leg) -> bool:
    """Metro and city buses only run between about 05:30 and 23:00."""
    if leg.bookable or leg.mode not in (Mode.METRO, Mode.BUS):
        return True
    return (
        SERVICE_START <= leg.depart.value.time() <= SERVICE_END
        and SERVICE_START <= leg.arrive.value.time() <= SERVICE_END
    )


class Orchestrator:
    def __init__(self, clock: Callable[[], datetime]):
        self.clock = clock

    def compose(
        self, origin: Place, dest: Place, depart_after: datetime, exclude: LegFilter | None = None
    ) -> list[list[Leg]]:
        transport = MockTransport(self.clock())
        if origin.city == dest.city:
            chains = transport.local_chains(origin, dest)
            options = [transport.time_chain(c, start=depart_after) for c in chains]
        else:
            options = []
            city_a, city_b = CITIES[origin.city or ""], CITIES[dest.city or ""]
            trunks = transport.trunk_services(
                city_a, city_b, depart_after + timedelta(minutes=20), depart_after + HORIZON
            )
            for trunk in trunks:
                at_hub_by = trunk.depart.value - timedelta(minutes=trunk.min_connection_min)
                if at_hub_by < depart_after:
                    continue
                firsts = []
                for chain in transport.local_chains(origin, trunk.origin):
                    legs = transport.time_chain(chain, end=at_hub_by)
                    if not legs or legs[0].depart.value >= depart_after:
                        firsts.append(legs)
                leave_hub = trunk.arrive.value + timedelta(minutes=EGRESS_MIN[trunk.mode])
                lasts = [
                    transport.time_chain(c, start=leave_hub)
                    for c in transport.local_chains(trunk.destination, dest)
                ]
                options += [f + [trunk] + last for f in firsts for last in lasts]
        options = [legs for legs in options if legs and all(map(in_service, legs))]
        if exclude:
            options = [legs for legs in options if not any(exclude(leg) for leg in legs)]
        return options

    def search(self, req: SearchRequest, exclude: LegFilter | None = None) -> SearchResponse:
        now = self.clock()
        origin = resolve_place(req.origin)
        dest = resolve_place(req.destination)
        constraints = Constraints.model_validate(
            req.model_dump(include=set(Constraints.model_fields))
        )
        depart_after = constraints.depart_after
        if depart_after is None:
            depart_after = (
                constraints.arrive_by - timedelta(hours=24) if constraints.arrive_by else now
            )
        depart_after = max(depart_after, now)

        candidates = [
            build_journey(legs, constraints)
            for legs in self.compose(origin, dest, depart_after, exclude)
        ]
        feasible, rejected = optimizer.apply_constraints(candidates, constraints)
        time_objective: optimizer.TimeObjective = "duration" if constraints.arrive_by else "arrival"
        front = optimizer.pareto_front(feasible, time_objective)
        ranked = optimizer.rank(front, req.weights, constraints.prefer_modes, time_objective)
        chosen = optimizer.select_and_label(ranked, req.limit, time_objective)
        journeys = optimizer.explain(chosen, constraints)
        hints = (
            []
            if journeys
            else (
                optimizer.relaxation_hints(candidates, constraints)
                if candidates
                else ["No route found between these places in the next 30 hours."]
            )
        )
        return SearchResponse(
            search_id="S" + uuid.uuid4().hex[:12],
            origin=origin,
            destination=dest,
            journeys=journeys,
            considered=len(candidates),
            pareto_size=len(front),
            rejected=rejected,
            relaxation_hints=hints,
            time_objective=time_objective,
        )
