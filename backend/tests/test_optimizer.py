from datetime import timedelta

from app.domain.models import Constraints, Journey, Mode, ProvenanceKind, Weights
from app.services import optimizer
from tests.conftest import NOW


def J(jid, minutes, cost, carbon, rel, modes=(Mode.CAB,)) -> Journey:
    from app.domain.models import Leg, Place, Provenance, Sourced

    prov = Provenance(kind=ProvenanceKind.ESTIMATED, source="test", as_of=NOW)
    p = Place(name="x", lat=0, lon=0)
    legs = [
        Leg(
            id=f"{jid}{i}",
            mode=m,
            provider="t",
            origin=p,
            destination=p,
            depart=Sourced(value=NOW, provenance=prov),
            arrive=Sourced(value=NOW + timedelta(minutes=minutes), provenance=prov),
            fare_inr=Sourced(value=cost, provenance=prov),
            distance_km=1,
            carbon_g=0,
            reliability=1,
        )
        for i, m in enumerate(modes)
    ]
    return Journey(
        id=jid,
        legs=legs,
        depart=NOW,
        arrive=NOW + timedelta(minutes=minutes),
        duration_min=minutes,
        cost_inr=cost,
        carbon_kg=carbon,
        reliability=rel,
        transfers=len(modes) - 1,
        cost_provenance=ProvenanceKind.ESTIMATED,
    )


def test_dominated_journeys_are_removed():
    fast = J("fast", 100, 5000, 100, 0.9)
    cheap = J("cheap", 600, 1000, 20, 0.8)
    worse = J("worse", 700, 6000, 120, 0.7)  # worse than `fast` on everything
    front = optimizer.pareto_front([fast, cheap, worse], "duration")
    assert {j.id for j in front} == {"fast", "cheap"}


def test_identical_objectives_keep_one():
    a, b = J("a", 100, 100, 1, 0.9), J("b", 100, 100, 1, 0.9)
    assert len(optimizer.pareto_front([a, b], "duration")) == 1


def test_trade_off_on_any_objective_keeps_journey():
    base = J("base", 100, 100, 10, 0.9)
    greener = J("greener", 100, 100, 5, 0.8)
    assert len(optimizer.pareto_front([base, greener], "duration")) == 2


def test_hard_constraints_never_relaxed():
    js = [J("a", 100, 9000, 1, 0.9), J("b", 300, 7000, 1, 0.9, (Mode.FLIGHT,))]
    c = Constraints(budget_inr=8000, avoid_modes=[Mode.FLIGHT])
    ok, rejected = optimizer.apply_constraints(js, c)
    assert ok == []
    assert rejected == {"over_budget": 1, "avoided_mode": 1}


def test_deadline_constraint():
    c = Constraints(arrive_by=NOW + timedelta(minutes=200))
    ok, rejected = optimizer.apply_constraints([J("a", 100, 1, 1, 1), J("b", 300, 1, 1, 1)], c)
    assert [j.id for j in ok] == ["a"]
    assert rejected == {"misses_deadline": 1}


def test_relaxation_hint_states_gap():
    hints = optimizer.relaxation_hints([J("a", 100, 9140, 1, 0.9)], Constraints(budget_inr=8000))
    assert "₹9,140" in hints[0] and "₹1,140 over" in hints[0]


def test_weights_change_ranking():
    fast, cheap = J("fast", 100, 5000, 100, 0.9), J("cheap", 600, 1000, 20, 0.9)
    by_time = optimizer.rank(
        [fast, cheap], Weights(time=1, cost=0, carbon=0, reliability=0), [], "duration"
    )
    by_cost = optimizer.rank(
        [fast, cheap], Weights(time=0, cost=1, carbon=0, reliability=0), [], "duration"
    )
    assert by_time[0].id == "fast"
    assert by_cost[0].id == "cheap"


def test_labels_and_explanations():
    fast, cheap = J("fast", 100, 5000, 100, 0.95), J("cheap", 600, 1000, 20, 0.8)
    ranked = optimizer.rank([fast, cheap], Weights(), [], "duration")
    chosen = optimizer.explain(
        optimizer.select_and_label(ranked, 5, "duration"), Constraints(budget_inr=6000)
    )
    by_id = {j.id: j for j in chosen}
    assert "fastest" in by_id["fast"].labels and "most_reliable" in by_id["fast"].labels
    assert "cheapest" in by_id["cheap"].labels and "greenest" in by_id["cheap"].labels
    assert sum("recommended" in j.labels for j in chosen) == 1
    assert any("budget" in line for line in by_id["cheap"].explanation)


def test_fmt_inr_indian_grouping():
    assert optimizer.fmt_inr(123456) == "₹1,23,456"
    assert optimizer.fmt_inr(999) == "₹999"
    assert optimizer.fmt_inr(1000) == "₹1,000"
