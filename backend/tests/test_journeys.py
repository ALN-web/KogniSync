from app.domain.models import Mode

INTERCITY = {"origin": "Udayapalya, Bengaluru", "destination": "CP Delhi"}


def test_intercity_search_is_door_to_door(client):
    res = client.post("/api/v1/journeys/search", json=INTERCITY)
    assert res.status_code == 200
    body = res.json()
    assert body["data_mode"] == "mock"
    assert body["considered"] > body["pareto_size"] >= len(body["journeys"]) > 0
    for j in body["journeys"]:
        legs = j["legs"]
        assert legs[0]["origin"]["name"] == "Udayapalya"
        assert legs[-1]["destination"]["name"] == "Connaught Place"
        # Legs connect in space and never overlap in time.
        for a, b in zip(legs, legs[1:], strict=False):
            assert a["destination"]["name"] == b["origin"]["name"]
            assert a["arrive"]["value"] <= b["depart"]["value"]
        trunks = [
            leg for leg in legs if leg["mode"] in ("flight", "train", "bus") and leg["bookable"]
        ]
        assert len(trunks) == 1


def test_flight_has_check_in_buffer(client):
    from datetime import datetime

    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    flights = [j for j in body["journeys"] if any(leg["mode"] == "flight" for leg in j["legs"])]
    assert flights
    legs = flights[0]["legs"]
    i = next(i for i, leg in enumerate(legs) if leg["mode"] == "flight")
    if i > 0:
        gap = datetime.fromisoformat(legs[i]["depart"]["value"]) - datetime.fromisoformat(
            legs[i - 1]["arrive"]["value"]
        )
        assert gap.total_seconds() >= 90 * 60


def test_exactly_one_recommended_and_all_labels_present(client):
    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    labels = [lab for j in body["journeys"] for lab in j["labels"]]
    assert labels.count("recommended") == 1
    for name in ("fastest", "cheapest", "greenest", "most_reliable"):
        assert name in labels
    assert all(j["explanation"] for j in body["journeys"])


def test_seven_modes_reachable(client):
    seen: set[str] = set()
    for req in (
        INTERCITY,
        {"origin": "Koramangala", "destination": "Whitefield"},
        {"origin": "MG Road", "destination": "Indiranagar"},
        {"origin": "Bengaluru", "destination": "Chennai", "limit": 20},
    ):
        for j in client.post("/api/v1/journeys/search", json=req).json()["journeys"]:
            seen.update(leg["mode"] for leg in j["legs"])
    assert seen == {m.value for m in Mode}


def test_budget_is_never_exceeded(client):
    body = client.post("/api/v1/journeys/search", json={**INTERCITY, "budget_inr": 5000}).json()
    assert body["journeys"]
    assert all(j["cost_inr"] <= 5000 for j in body["journeys"])
    assert body["rejected"]["over_budget"] > 0


def test_impossible_budget_returns_hint_not_results(client):
    body = client.post("/api/v1/journeys/search", json={**INTERCITY, "budget_inr": 500}).json()
    assert body["journeys"] == []
    assert "over your ₹500 budget" in body["relaxation_hints"][0]


def test_deadline_respected_and_uses_duration(client):
    req = {**INTERCITY, "arrive_by": "2026-11-23T20:00:00+05:30"}
    body = client.post("/api/v1/journeys/search", json=req).json()
    assert body["time_objective"] == "duration"
    assert body["journeys"]
    assert all(j["arrive"] <= "2026-11-23T20:00:00+05:30" for j in body["journeys"])


def test_avoid_and_prefer_modes(client):
    body = client.post(
        "/api/v1/journeys/search", json={**INTERCITY, "avoid_modes": ["flight"]}
    ).json()
    assert all("flight" not in [leg["mode"] for leg in j["legs"]] for j in body["journeys"])
    body = client.post(
        "/api/v1/journeys/search", json={**INTERCITY, "prefer_modes": ["train"]}
    ).json()
    rec = next(j for j in body["journeys"] if "recommended" in j["labels"])
    assert "train" in [leg["mode"] for leg in rec["legs"]]


def test_search_is_deterministic(client):
    a = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    b = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    assert [j["id"] for j in a["journeys"]] == [j["id"] for j in b["journeys"]]


def test_unknown_place_is_422(client):
    res = client.post("/api/v1/journeys/search", json={"origin": "Atlantis", "destination": "CP"})
    assert res.status_code == 422


def test_get_journey_by_id(client):
    j = client.post("/api/v1/journeys/search", json=INTERCITY).json()["journeys"][0]
    res = client.get(f"/api/v1/journeys/{j['id']}")
    assert res.status_code == 200 and res.json()["id"] == j["id"]
    assert client.get("/api/v1/journeys/Jnope").status_code == 404


def test_metro_and_city_bus_only_in_service_hours(client, clock):
    from datetime import datetime, time

    clock.now = clock.now.replace(hour=22, minute=5)
    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    for j in body["journeys"]:
        for leg in j["legs"]:
            if leg["mode"] in ("metro", "bus") and not leg["bookable"]:
                for f in ("depart", "arrive"):
                    t = datetime.fromisoformat(leg[f]["value"]).time()
                    assert time(5, 30) <= t <= time(23, 0)
