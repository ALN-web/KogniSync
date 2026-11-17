import uuid

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.kv import MemoryKV
from tests.conftest import make_settings

INTERCITY = {"origin": "Udayapalya, Bengaluru", "destination": "CP Delhi"}


def book(client, pick) -> dict:
    journeys = client.post("/api/v1/journeys/search", json=INTERCITY).json()["journeys"]
    j = next(j for j in journeys if pick(j))
    h = client.post(
        "/api/v1/holds", json={"journey_id": j["id"]}, headers={"Idempotency-Key": uuid.uuid4().hex}
    ).json()
    tp = client.post(
        "/api/v1/bookings",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json={"hold_id": h["id"], "expected_total_inr": h["total_due_now_inr"], "consent": True},
    ).json()
    return tp


def modes(j) -> list[str]:
    return [leg["mode"] for leg in j["legs"]]


def flight_of(tp) -> dict:
    return next(leg for leg in tp["journey"]["legs"] if leg["mode"] == "flight")


def test_no_disruption_means_no_impact(client):
    tp = book(client, lambda j: "flight" in modes(j))
    impact = client.get(f"/api/v1/trippass/{tp['id']}/impact").json()
    assert impact["severity"] == "none"
    assert all(leg["status"] == "on_time" for leg in impact["legs"])
    rec = client.post(f"/api/v1/trippass/{tp['id']}/recovery").json()
    assert rec["options"] == [] and "No change needed" in rec["note"]


def test_flight_delay_cascades_to_later_legs(client):
    tp = book(client, lambda j: "flight" in modes(j))
    flight = flight_of(tp)
    client.post(
        "/api/v1/disruptions",
        json={
            "kind": "delay",
            "service_id": flight["service_id"],
            "delay_min": 90,
            "message": "Late inbound aircraft",
        },
    )
    impact = client.get(f"/api/v1/trippass/{tp['id']}/impact").json()
    assert impact["severity"] == "major"
    assert impact["arrival_delay_min"] >= 85
    i = next(i for i, leg in enumerate(impact["legs"]) if leg["mode"] == "flight")
    assert impact["legs"][i]["status"] == "delayed" and impact["legs"][i]["causes"]
    assert all(leg["status"] == "delayed" for leg in impact["legs"][i + 1 :])
    assert all(leg["status"] == "on_time" for leg in impact["legs"][:i])
    assert "late" in impact["summary"]


def test_cancellation_breaks_trip_and_recovery_avoids_it(client, container):
    tp = book(client, lambda j: "flight" in modes(j))
    flight = flight_of(tp)
    client.post(
        "/api/v1/disruptions", json={"kind": "cancellation", "service_id": flight["service_id"]}
    )
    impact = client.get(f"/api/v1/trippass/{tp['id']}/impact").json()
    assert impact["severity"] == "critical"
    k = impact["first_broken_leg"]
    assert impact["legs"][k]["status"] == "cancelled"
    assert all(leg["status"] == "needs_replan" for leg in impact["legs"][k + 1 :])

    holds_before = container.telemetry.counters["hold_created"]
    rec = client.post(f"/api/v1/trippass/{tp['id']}/recovery").json()
    assert rec["requires_consent"] is True
    assert rec["replaces_from_leg"] == k
    assert rec["options"]
    for opt in rec["options"]:
        assert opt["legs"][0]["origin"]["name"] == flight["origin"]["name"]
        assert opt["legs"][-1]["destination"]["name"] == "Connaught Place"
        assert flight["service_id"] not in [leg["service_id"] for leg in opt["legs"]]
    # Proposals only: nothing was held or booked.
    assert container.telemetry.counters["hold_created"] == holds_before
    # An option can be booked through the normal flow.
    res = client.post(
        "/api/v1/holds",
        json={"journey_id": rec["options"][0]["id"]},
        headers={"Idempotency-Key": uuid.uuid4().hex},
    )
    assert res.status_code == 201


def test_first_mile_delay_misses_flight(client):
    tp = book(client, lambda j: modes(j)[:4] == ["walk", "metro", "walk", "flight"])
    client.post(
        "/api/v1/disruptions",
        json={"kind": "delay", "provider": "Namma Metro", "city": "BLR", "delay_min": 120},
    )
    impact = client.get(f"/api/v1/trippass/{tp['id']}/impact").json()
    assert impact["legs"][1]["status"] == "delayed"
    assert impact["legs"][3]["status"] == "missed_connection"
    assert impact["severity"] == "critical"


def test_metro_closure_recovery_uses_other_modes(client):
    tp = book(client, lambda j: modes(j)[:4] == ["walk", "metro", "walk", "flight"])
    client.post(
        "/api/v1/disruptions", json={"kind": "closure", "provider": "Namma Metro", "city": "BLR"}
    )
    rec = client.post(f"/api/v1/trippass/{tp['id']}/recovery").json()
    assert rec["impact"]["legs"][1]["status"] == "cancelled"
    assert rec["options"]
    assert all("Namma Metro" not in leg["provider"] for o in rec["options"] for leg in o["legs"])


def test_stale_and_expired_disruptions(client, clock):
    tp = book(client, lambda j: "flight" in modes(j))
    client.post(
        "/api/v1/disruptions",
        json={
            "kind": "delay",
            "service_id": flight_of(tp)["service_id"],
            "delay_min": 30,
            "ttl_min": 60,
        },
    )
    clock.advance(minutes=31)
    assert client.get("/api/v1/disruptions").json()[0]["stale"] is True
    assert client.get(f"/api/v1/trippass/{tp['id']}/impact").json()["based_on_stale_data"]
    clock.advance(minutes=30)
    assert client.get("/api/v1/disruptions").json() == []
    assert client.get(f"/api/v1/trippass/{tp['id']}/impact").json()["severity"] == "none"


def test_disruption_needs_scope(client):
    assert client.post("/api/v1/disruptions", json={"kind": "closure"}).status_code == 422
    assert (
        client.post("/api/v1/disruptions", json={"kind": "delay", "mode": "flight"}).status_code
        == 422
    )


def test_simulation_can_be_disabled():
    c = TestClient(create_app(make_settings(enable_simulation=False), kv=MemoryKV()))
    res = c.post("/api/v1/disruptions", json={"kind": "closure", "city": "BLR"})
    assert res.status_code == 403
