"""M3: provenance labels and freshness rules.

Rules:
- ``live`` data carries a TTL. Once older than its TTL it is marked ``stale`` and downgraded to
  ``estimated``: we never show an old live price as if it were current.
- ``scheduled`` data (timetables, published fare charts) does not expire.
- ``estimated`` data is a model output (cab fares, walking times, carbon).
- An aggregate (e.g. a journey's total cost) is only as trustworthy as its weakest input.
"""

from collections import Counter
from collections.abc import Iterable
from datetime import datetime

from app.domain.models import Journey, Leg, Provenance, ProvenanceKind, Sourced

_RANK = {ProvenanceKind.ESTIMATED: 0, ProvenanceKind.SCHEDULED: 1, ProvenanceKind.LIVE: 2}


def make(kind: ProvenanceKind, source: str, as_of: datetime, ttl: int | None = None) -> Provenance:
    return Provenance(kind=kind, source=source, as_of=as_of, ttl_seconds=ttl)


def refresh(prov: Provenance, now: datetime) -> Provenance:
    if prov.kind != ProvenanceKind.LIVE or prov.ttl_seconds is None:
        return prov
    if (now - prov.as_of).total_seconds() > prov.ttl_seconds:
        return prov.model_copy(update={"kind": ProvenanceKind.ESTIMATED, "stale": True})
    return prov


def weakest(kinds: Iterable[ProvenanceKind]) -> ProvenanceKind:
    kinds = list(kinds)
    if not kinds:
        return ProvenanceKind.ESTIMATED
    return min(kinds, key=_RANK.__getitem__)


def _sourced_fields(leg: Leg) -> list[tuple[str, Sourced]]:
    fields = [("depart", leg.depart), ("arrive", leg.arrive), ("fare_inr", leg.fare_inr)]
    if leg.seats_available is not None:
        fields.append(("seats_available", leg.seats_available))
    return fields


def refresh_leg(leg: Leg, now: datetime) -> Leg:
    updates = {
        name: value.model_copy(update={"provenance": refresh(value.provenance, now)})
        for name, value in _sourced_fields(leg)
    }
    return leg.model_copy(update=updates)


def summarize(legs: list[Leg]) -> tuple[ProvenanceKind, dict[str, int]]:
    """Return (cost provenance, counts of every labeled value by kind)."""
    counts: Counter[str] = Counter()
    for leg in legs:
        for _, value in _sourced_fields(leg):
            counts[value.provenance.kind.value] += 1
    cost_kind = weakest(leg.fare_inr.provenance.kind for leg in legs if leg.fare_inr.value > 0)
    if not any(leg.fare_inr.value > 0 for leg in legs):
        cost_kind = ProvenanceKind.SCHEDULED  # all-free journey (walking): the ₹0 total is exact
    return cost_kind, {k.value: counts.get(k.value, 0) for k in ProvenanceKind}


def refresh_journey(journey: Journey, now: datetime) -> Journey:
    legs = [refresh_leg(leg, now) for leg in journey.legs]
    cost_kind, summary = summarize(legs)
    warnings = [w for w in journey.warnings if not w.startswith("Some live data is stale")]
    if any(v.provenance.stale for leg in legs for _, v in _sourced_fields(leg)):
        warnings.append("Some live data is stale and is shown as estimated until refreshed.")
    return journey.model_copy(
        update={
            "legs": legs,
            "cost_provenance": cost_kind,
            "provenance_summary": summary,
            "warnings": warnings,
        }
    )
