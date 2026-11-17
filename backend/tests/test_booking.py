import asyncio
import uuid

import fakeredis
import pytest

from app.core.container import build_container
from app.domain.booking import ConfirmRequest, HoldRequest, HoldStatus
from app.domain.models import SearchRequest, Sourced
from app.services.booking import BookingError
from app.services.booking_repo import SqlTripPassRepo
from app.services.kv import MemoryKV, RedisKV
from app.services.orchestrator import build_journey
from tests.conftest import FakeClock, make_settings

INTERCITY = {"origin": "Udayapalya, Bengaluru", "destination": "CP Delhi"}


def key() -> dict:
    return {"Idempotency-Key": uuid.uuid4().hex}


def first_journey(client) -> dict:
    return client.post("/api/v1/journeys/search", json=INTERCITY).json()["journeys"][0]


# ---------------- API ----------------


def test_hold_confirm_issues_trippass_with_qr(client):
    j = first_journey(client)
    hold = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=key())
    assert hold.status_code == 201, hold.text
    h = hold.json()
    assert h["status"] == "held" and len(h["legs"]) == 1
    assert h["total_due_now_inr"] == h["legs"][0]["fare_inr"]
    assert h["total_due_now_inr"] + h["pay_later_estimate_inr"] == j["cost_inr"]

    res = client.post(
        "/api/v1/bookings",
        headers=key(),
        json={"hold_id": h["id"], "expected_total_inr": h["total_due_now_inr"], "consent": True},
    )
    assert res.status_code == 201, res.text
    tp = res.json()
    assert tp["id"].startswith("TP-")
    statuses = {b["status"] for b in tp["booked_legs"]}
    assert statuses == {"confirmed", "pay_at_travel"}
    assert all(b["pnr"] for b in tp["booked_legs"] if b["status"] == "confirmed")

    assert client.get(f"/api/v1/trippass/{tp['id']}").json()["id"] == tp["id"]
    svg = client.get(f"/api/v1/trippass/{tp['id']}/qr.svg")
    assert svg.headers["content-type"].startswith("image/svg+xml") and "<svg" in svg.text
    assert client.post("/api/v1/trippass/verify", json={"token": tp["qr_payload"]}).json() == {
        "valid": True,
        "trippass_id": tp["id"],
        "passengers": 1,
    }
    assert client.get(f"/api/v1/holds/{h['id']}").json()["status"] == "confirmed"


def test_tampered_token_fails_verification(client):
    j = first_journey(client)
    h = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=key()).json()
    tp = client.post(
        "/api/v1/bookings",
        headers=key(),
        json={"hold_id": h["id"], "expected_total_inr": h["total_due_now_inr"], "consent": True},
    ).json()
    body, sig = tp["token"].split(".")
    forged = body[:-2] + ("AA" if body[-2:] != "AA" else "BB") + "." + sig
    assert client.post("/api/v1/trippass/verify", json={"token": forged}).json()["valid"] is False


def test_idempotent_hold_replays_without_holding_twice(client, container):
    j = first_journey(client)
    headers = key()
    a = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=headers)
    b = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=headers)
    assert a.json()["id"] == b.json()["id"]
    assert a.headers["Idempotent-Replayed"] == "false"
    assert b.headers["Idempotent-Replayed"] == "true"
    trunk = next(leg for leg in j["legs"] if leg["bookable"])
    left = asyncio.run(container.kv.get(f"inv:{trunk['service_id']}"))
    assert int(left) == trunk["seats_available"]["value"] - 1


def test_idempotency_key_reuse_with_other_body_rejected(client):
    j = first_journey(client)
    headers = key()
    client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=headers)
    res = client.post(
        "/api/v1/holds", json={"journey_id": j["id"], "passengers": 2}, headers=headers
    )
    assert res.status_code == 422


def test_idempotency_key_required(client):
    j = first_journey(client)
    assert client.post("/api/v1/holds", json={"journey_id": j["id"]}).status_code == 400


def test_booking_requires_consent_and_exact_price(client, container):
    j = first_journey(client)
    h = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=key()).json()
    no_consent = client.post(
        "/api/v1/bookings",
        headers=key(),
        json={"hold_id": h["id"], "expected_total_inr": h["total_due_now_inr"], "consent": False},
    )
    assert no_consent.status_code == 422
    wrong = client.post(
        "/api/v1/bookings",
        headers=key(),
        json={
            "hold_id": h["id"],
            "expected_total_inr": h["total_due_now_inr"] - 1,
            "consent": True,
        },
    )
    assert wrong.status_code == 409 and wrong.json()["detail"]["code"] == "price_mismatch"
    assert container.payments.charges == 0


def test_hold_expires_and_frees_seats(client, container, clock):
    j = first_journey(client)
    trunk = next(leg for leg in j["legs"] if leg["bookable"])
    h = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=key()).json()
    clock.advance(minutes=11)
    assert client.get(f"/api/v1/holds/{h['id']}").json()["status"] == "expired"
    left = asyncio.run(container.kv.get(f"inv:{trunk['service_id']}"))
    assert int(left) == trunk["seats_available"]["value"]
    res = client.post(
        "/api/v1/bookings",
        headers=key(),
        json={"hold_id": h["id"], "expected_total_inr": h["total_due_now_inr"], "consent": True},
    )
    assert res.status_code == 410


def test_release_hold(client):
    j = first_journey(client)
    h = client.post("/api/v1/holds", json={"journey_id": j["id"]}, headers=key()).json()
    assert client.delete(f"/api/v1/holds/{h['id']}").json()["status"] == "released"


def test_unknown_journey_404(client):
    res = client.post("/api/v1/holds", json={"journey_id": "Jnope"}, headers=key())
    assert res.status_code == 404


# ---------------- saga + concurrency (service level) ----------------


@pytest.fixture(params=["memory", "redis"])
def svc(request):
    kv = (
        MemoryKV()
        if request.param == "memory"
        else RedisKV(fakeredis.FakeAsyncRedis(decode_responses=True))
    )
    return build_container(make_settings(), clock=FakeClock(), kv=kv)


async def two_trunk_journey(c, seats: int | None = None):
    res = c.orchestrator.search(SearchRequest(**INTERCITY, limit=20))
    trunks = []
    for j in res.journeys:
        for leg in j.legs:
            if leg.bookable and leg.service_id not in {t.service_id for t in trunks}:
                trunks.append(leg)
    a, b = trunks[:2]
    if seats is not None:
        a = a.model_copy(
            update={
                "seats_available": Sourced(value=seats, provenance=a.seats_available.provenance)
            }
        )
    journey = build_journey(
        [a, b.model_copy(update={"id": b.id + "x"})], res.journeys[0].constraints
    )
    await c.journeys.put(journey)
    return journey, a, b


async def test_failed_hold_releases_earlier_legs(svc):
    journey, a, b = await two_trunk_journey(svc)
    before = await svc.vendor.seats_left(a)
    svc.vendor.fail_hold.add(b.service_id)
    with pytest.raises(BookingError) as e:
        await svc.booking.create_hold(HoldRequest(journey_id=journey.id))
    assert e.value.code == "hold_failed"
    assert await svc.vendor.seats_left(a) == before
    assert svc.telemetry.counters["hold_conflict"] == 1


async def test_failed_ticketing_cancels_refunds_and_frees_seats(svc):
    journey, a, b = await two_trunk_journey(svc)
    before_a, before_b = await svc.vendor.seats_left(a), await svc.vendor.seats_left(b)
    hold = await svc.booking.create_hold(HoldRequest(journey_id=journey.id))
    svc.vendor.fail_confirm.add(b.service_id)
    with pytest.raises(BookingError) as e:
        await svc.booking.confirm(
            ConfirmRequest(hold_id=hold.id, consent=True, expected_total_inr=hold.total_due_now_inr)
        )
    assert e.value.code == "booking_failed"
    assert svc.payments.charges == 1 and svc.payments.refunds == 1
    assert await svc.vendor.seats_left(a) == before_a
    assert await svc.vendor.seats_left(b) == before_b
    assert (await svc.booking.get_hold(hold.id)).status == HoldStatus.RELEASED


async def test_last_seats_are_never_oversold(svc):
    journey, a, _ = await two_trunk_journey(svc, seats=3)
    results = await asyncio.gather(
        *(svc.booking.create_hold(HoldRequest(journey_id=journey.id)) for _ in range(8)),
        return_exceptions=True,
    )
    ok = [r for r in results if not isinstance(r, Exception)]
    assert len(ok) == 3
    assert all(isinstance(r, BookingError) for r in results if r not in ok)
    assert await svc.vendor.seats_left(a) == 0


async def test_concurrent_confirms_charge_once(svc):
    journey, _, _ = await two_trunk_journey(svc)
    hold = await svc.booking.create_hold(HoldRequest(journey_id=journey.id))
    req = ConfirmRequest(hold_id=hold.id, consent=True, expected_total_inr=hold.total_due_now_inr)
    results = await asyncio.gather(
        *(svc.booking.confirm(req) for _ in range(5)), return_exceptions=True
    )
    passes = [r for r in results if not isinstance(r, Exception)]
    assert len(passes) == 1
    assert svc.payments.charges == 1


async def test_sql_trippass_repo_roundtrip():
    from sqlalchemy.pool import StaticPool

    repo = SqlTripPassRepo(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool, pool_pre_ping=False
    )
    c = build_container(make_settings(), clock=FakeClock(), kv=MemoryKV(), repo=repo)
    journey, _, _ = await two_trunk_journey(c)
    hold = await c.booking.create_hold(HoldRequest(journey_id=journey.id))
    tp = await c.booking.confirm(
        ConfirmRequest(hold_id=hold.id, consent=True, expected_total_inr=hold.total_due_now_inr)
    )
    assert (await c.booking.get_trippass(tp.id)).model_dump() == tp.model_dump()
    await c.booking.repo.engine.dispose()
