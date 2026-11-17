from datetime import timedelta

from app.domain.models import Provenance, ProvenanceKind
from app.services import provenance
from tests.conftest import NOW

INTERCITY = {"origin": "Udayapalya, Bengaluru", "destination": "CP Delhi"}


def test_every_value_is_labeled(client):
    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    for j in body["journeys"]:
        assert j["cost_provenance"] in {"live", "scheduled", "estimated"}
        for leg in j["legs"]:
            for field in ("depart", "arrive", "fare_inr"):
                prov = leg[field]["provenance"]
                assert prov["kind"] in {"live", "scheduled", "estimated"}
                assert prov["source"].startswith("mock:")


def test_all_three_kinds_appear(client):
    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    kinds = {
        leg[f]["provenance"]["kind"]
        for j in body["journeys"]
        for leg in j["legs"]
        for f in ("depart", "fare_inr")
    }
    assert kinds == {"live", "scheduled", "estimated"}


def test_live_value_goes_stale_after_ttl():
    p = Provenance(kind=ProvenanceKind.LIVE, source="x", as_of=NOW, ttl_seconds=600)
    assert provenance.refresh(p, NOW + timedelta(seconds=599)).kind == ProvenanceKind.LIVE
    stale = provenance.refresh(p, NOW + timedelta(seconds=601))
    assert stale.kind == ProvenanceKind.ESTIMATED and stale.stale


def test_scheduled_never_goes_stale():
    p = Provenance(kind=ProvenanceKind.SCHEDULED, source="x", as_of=NOW)
    assert provenance.refresh(p, NOW + timedelta(days=30)) == p


def test_weakest_label_wins():
    K = ProvenanceKind
    assert provenance.weakest([K.LIVE, K.SCHEDULED]) == K.SCHEDULED
    assert provenance.weakest([K.LIVE, K.ESTIMATED, K.SCHEDULED]) == K.ESTIMATED


def test_stored_journey_downgrades_when_stale(client, clock):
    body = client.post("/api/v1/journeys/search", json=INTERCITY).json()
    j = next(
        j
        for j in body["journeys"]
        if any(leg["fare_inr"]["provenance"]["kind"] == "live" for leg in j["legs"])
    )
    clock.advance(minutes=15)
    fresh = client.get(f"/api/v1/journeys/{j['id']}").json()
    kinds = [leg["fare_inr"]["provenance"] for leg in fresh["legs"]]
    assert not any(p["kind"] == "live" for p in kinds)
    assert any(p["stale"] for p in kinds)
    assert fresh["cost_provenance"] == "estimated"
    assert any("stale" in w for w in fresh["warnings"])
