"""M2: Pareto optimizer, ranking and plain-language explanations.

Objectives (all minimized): time, cost, carbon and (1 - reliability). "Time" is arrival time
when the user gave no deadline, and door-to-door duration when they did (with a deadline,
arriving earlier is not better; a shorter trip is).

Hard constraints (budget, deadline, transfers, avoided modes) are filters, applied before
optimization and never relaxed. If nothing passes, the caller gets hints about what it would
take instead of a silently relaxed answer.
"""

from collections.abc import Callable
from typing import Literal

from app.domain.models import Constraints, Journey, Mode, Weights

TimeObjective = Literal["arrival", "duration"]


def fmt_inr(amount: int) -> str:
    """Indian digit grouping: 123456 -> ₹1,23,456."""
    s = str(abs(int(amount)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-₹" if amount < 0 else "₹") + s


def fmt_minutes(minutes: int) -> str:
    h, m = divmod(abs(int(minutes)), 60)
    return f"{h} h {m:02d} min" if h else f"{m} min"


def objectives(j: Journey, time_objective: TimeObjective) -> tuple[float, float, float, float]:
    t = j.arrive.timestamp() / 60 if time_objective == "arrival" else j.duration_min
    # Round so trivial differences (1 rupee, 0.1 kg) don't keep near-duplicates on the front.
    return (round(t), j.cost_inr, round(j.carbon_kg * 2) / 2, round(1 - j.reliability, 2))


def dominates(a: tuple, b: tuple) -> bool:
    return all(x <= y for x, y in zip(a, b, strict=True)) and any(
        x < y for x, y in zip(a, b, strict=True)
    )


def pareto_front(journeys: list[Journey], time_objective: TimeObjective) -> list[Journey]:
    keyed = sorted(((objectives(j, time_objective), j) for j in journeys), key=lambda kj: kj[0])
    front: list[tuple[tuple, Journey]] = []
    seen: set[tuple] = set()
    for key, j in keyed:
        if key in seen:
            continue  # identical objectives: keep the first (earliest-sorted) one
        if any(dominates(fk, key) for fk, _ in front):
            continue
        front = [(fk, fj) for fk, fj in front if not dominates(key, fk)]
        front.append((key, j))
        seen.add(key)
    return [j for _, j in front]


RejectReason = Literal["avoided_mode", "too_many_transfers", "over_budget", "misses_deadline"]


def apply_constraints(
    journeys: list[Journey], c: Constraints
) -> tuple[list[Journey], dict[str, int]]:
    rejected: dict[str, int] = {}
    ok: list[Journey] = []
    avoid = set(c.avoid_modes)
    for j in journeys:
        reason: str | None = None
        if avoid and avoid.intersection(j.modes):
            reason = "avoided_mode"
        elif c.max_transfers is not None and j.transfers > c.max_transfers:
            reason = "too_many_transfers"
        elif c.budget_inr is not None and j.cost_inr > c.budget_inr:
            reason = "over_budget"
        elif c.arrive_by is not None and j.arrive > c.arrive_by:
            reason = "misses_deadline"
        if reason:
            rejected[reason] = rejected.get(reason, 0) + 1
        else:
            ok.append(j)
    return ok, rejected


def relaxation_hints(candidates: list[Journey], c: Constraints) -> list[str]:
    """Explain what it would take to get a result. Never relaxes anything itself."""
    avoid = set(c.avoid_modes)
    pool = [j for j in candidates if not (avoid and avoid.intersection(j.modes))]
    if c.max_transfers is not None:
        pool = [j for j in pool if j.transfers <= c.max_transfers]
    if not pool:
        return ["No route avoids the modes you excluded. Try allowing another mode."]
    hints = []
    if c.budget_inr is not None:
        on_time = [j for j in pool if c.arrive_by is None or j.arrive <= c.arrive_by] or pool
        cheapest = min(on_time, key=lambda j: j.cost_inr)
        if cheapest.cost_inr > c.budget_inr:
            hints.append(
                f"The cheapest option costs {fmt_inr(cheapest.cost_inr)}, "
                f"{fmt_inr(cheapest.cost_inr - c.budget_inr)} over your "
                f"{fmt_inr(c.budget_inr)} budget. KogniSync will not go over budget unless "
                "you raise it."
            )
    if c.arrive_by is not None:
        affordable = [j for j in pool if c.budget_inr is None or j.cost_inr <= c.budget_inr]
        affordable = affordable or pool
        earliest = min(affordable, key=lambda j: j.arrive)
        if earliest.arrive > c.arrive_by:
            late = int((earliest.arrive - c.arrive_by).total_seconds() // 60)
            hints.append(
                f"The earliest arrival is {earliest.arrive:%a %d %b %H:%M}, {fmt_minutes(late)} "
                f"after your deadline. Leave earlier or move the deadline."
            )
    if not hints:
        hints.append("No option meets all your limits together. Try relaxing one of them.")
    return hints


def rank(
    front: list[Journey], weights: Weights, prefer: list[Mode], time_objective: TimeObjective
) -> list[Journey]:
    if not front:
        return []
    # Relative excess over the best value ("40% slower than the fastest"), capped at 300%.
    # Min-max scaling would make a 2-hour and a 40-hour gap look the same.
    start = min(j.depart for j in front)

    def time_cost(j: Journey) -> float:
        if time_objective == "duration":
            return j.duration_min
        # Without a deadline, blend time spent travelling with when you get there, so an
        # overnight wait for the first flight doesn't make a 40-hour train look competitive.
        return 0.5 * j.duration_min + 0.5 * (j.arrive - start).total_seconds() / 60

    keys = [(time_cost(j), j.cost_inr, j.carbon_kg, 1 - j.reliability) for j in front]
    lows = [min(k[i] for k in keys) for i in range(4)]
    w = [weights.time, weights.cost, weights.carbon, weights.reliability]
    total_w = sum(w)
    prefer_set = set(prefer)
    scored = []
    for j, k in zip(front, keys, strict=True):
        norm = [
            min(3.0, (k[i] - lows[i]) / max(lows[i], 1e-6)) if k[i] > lows[i] else 0.0
            for i in range(3)
        ]
        # Reliability: compare failure probabilities (0.25 vs 0.30 = 20% more risk).
        norm.append(min(3.0, (k[3] - lows[3]) / max(lows[3], 0.01)))
        score = sum(wi * ni for wi, ni in zip(w, norm, strict=True)) / total_w
        if prefer_set and prefer_set.intersection(j.modes):
            score *= 0.5  # a stated preference is a strong signal, but never a hard limit
        scored.append(j.model_copy(update={"score": round(score, 4)}))
    return sorted(scored, key=lambda j: j.score)


_LABELS: list[tuple[str, Callable[[Journey], float]]] = [
    ("cheapest", lambda j: j.cost_inr),
    ("greenest", lambda j: j.carbon_kg),
    ("most_reliable", lambda j: -j.reliability),
]


def select_and_label(
    ranked: list[Journey], limit: int, time_objective: TimeObjective
) -> list[Journey]:
    if not ranked:
        return []
    labels: dict[str, set[str]] = {j.id: set() for j in ranked}
    labels[ranked[0].id].add("recommended")
    time_key = (lambda j: j.arrive) if time_objective == "arrival" else (lambda j: j.duration_min)
    labels[min(ranked, key=time_key).id].add("fastest")
    for name, key in _LABELS:
        labels[min(ranked, key=key).id].add(name)
    chosen = [j for j in ranked if labels[j.id]]
    # Fill the rest by score, at most two variants per trunk service so the list stays diverse.
    per_trunk: dict[str, int] = {}
    for j in chosen:
        per_trunk[_trunk_key(j)] = per_trunk.get(_trunk_key(j), 0) + 1
    for j in ranked:
        if len(chosen) >= limit:
            break
        if j in chosen or per_trunk.get(_trunk_key(j), 0) >= 2:
            continue
        chosen.append(j)
        per_trunk[_trunk_key(j)] = per_trunk.get(_trunk_key(j), 0) + 1
    chosen = sorted(chosen[: max(limit, 1)], key=lambda j: j.score)
    order = ["recommended", "fastest", "cheapest", "greenest", "most_reliable"]
    return [
        j.model_copy(update={"labels": [o for o in order if o in labels[j.id]]}) for j in chosen
    ]


def _trunk_key(j: Journey) -> str:
    return next((leg.service_id for leg in j.legs if leg.service_id), "local:" + j.id)


def explain(journeys: list[Journey], c: Constraints) -> list[Journey]:
    if not journeys:
        return []
    best = next((j for j in journeys if "recommended" in j.labels), journeys[0])
    out = []
    for j in journeys:
        lines: list[str] = []
        if "recommended" in j.labels:
            lines.append(
                "Recommended: the best balance of time, cost, carbon and reliability "
                "for your priorities."
            )
        if "fastest" in j.labels:
            lines.append(
                f"Fastest: arrives {j.arrive:%a %H:%M} "
                f"({fmt_minutes(j.duration_min)} door to door)."
            )
        if "cheapest" in j.labels:
            lines.append(f"Cheapest: {fmt_inr(j.cost_inr)} in total.")
        if "greenest" in j.labels:
            lines.append(f"Greenest: about {j.carbon_kg:.1f} kg CO2.")
        if "most_reliable" in j.labels:
            lines.append(f"Most reliable: {j.reliability:.0%} chance every leg runs to plan.")
        if j is not best:
            lines.append(_compare(j, best))
        lines.append(
            "Pareto-optimal: no other option is better on time, cost, carbon and "
            "reliability all at once."
        )
        if c.budget_inr is not None:
            lines.append(
                f"Within your {fmt_inr(c.budget_inr)} budget "
                f"({fmt_inr(c.budget_inr - j.cost_inr)} to spare)."
            )
        if c.arrive_by is not None:
            spare = int((c.arrive_by - j.arrive).total_seconds() // 60)
            lines.append(
                f"Arrives {fmt_minutes(spare)} before your {c.arrive_by:%a %H:%M} deadline."
            )
        out.append(j.model_copy(update={"explanation": lines}))
    return out


def _compare(j: Journey, best: Journey) -> str:
    parts = []
    dc = j.cost_inr - best.cost_inr
    if dc:
        parts.append(f"{fmt_inr(abs(dc))} {'more' if dc > 0 else 'less'}")
    dt = j.duration_min - best.duration_min
    if dt:
        parts.append(f"{fmt_minutes(abs(dt))} {'longer' if dt > 0 else 'shorter'}")
    dco2 = j.carbon_kg - best.carbon_kg
    if abs(dco2) >= 0.5:
        parts.append(f"{abs(dco2):.1f} kg {'more' if dco2 > 0 else 'less'} CO2")
    if not parts:
        return "Similar to the recommended option."
    return "Compared with the recommended option: " + ", ".join(parts) + "."
