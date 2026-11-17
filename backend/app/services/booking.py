"""M4: booking saga.

hold:    hold every bookable leg (flight / train / intercity bus) with its vendor. If any leg
         fails, release the legs already held (compensation) so nothing is half-held.
confirm: requires explicit consent and the exact total the traveler saw. Charge once (keyed by
         hold), ticket every leg; if ticketing fails, cancel issued tickets, release the rest
         and refund. Success produces one TripPass with a signed QR token.

Cab, Rapido, metro and walking legs are not pre-booked; they show as "pay at travel" with an
estimated amount.
"""

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

from app.domain.booking import (
    BookedLeg,
    ConfirmRequest,
    Hold,
    HoldRequest,
    HoldStatus,
    LegHold,
    TripPass,
)
from app.domain.models import Leg
from app.services import provenance
from app.services.booking_repo import TripPassRepo
from app.services.journey_store import JourneyStore
from app.services.kv import KV
from app.services.telemetry import Telemetry
from app.services.trippass import TripPassSigner
from app.services.vendors import MockPayments, MockVendor, VendorError


class BookingError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = status, code, message, extra

    def detail(self) -> dict:
        return {"code": self.code, "message": self.message, **self.extra}


class BookingService:
    def __init__(
        self,
        *,
        kv: KV,
        journeys: JourneyStore,
        vendor: MockVendor,
        payments: MockPayments,
        repo: TripPassRepo,
        signer: TripPassSigner,
        telemetry: Telemetry,
        clock: Callable[[], datetime],
        hold_ttl_s: int = 600,
    ):
        self.kv, self.journeys, self.vendor, self.payments = kv, journeys, vendor, payments
        self.repo, self.signer, self.telemetry, self.clock = repo, signer, telemetry, clock
        self.hold_ttl_s = hold_ttl_s

    # ---------------- holds ----------------

    async def _save(self, hold: Hold) -> None:
        await self.kv.set(f"hold:{hold.id}", hold.model_dump_json(), 7 * 24 * 3600)

    async def get_hold(self, hold_id: str) -> Hold:
        raw = await self.kv.get(f"hold:{hold_id}")
        if raw is None:
            raise BookingError(404, "hold_not_found", "Hold not found")
        hold = Hold.model_validate_json(raw)
        if hold.status == HoldStatus.HELD and self.clock() >= hold.expires_at:
            hold = await self._release(hold, HoldStatus.EXPIRED)
            self.telemetry.event("hold_expired", hold_id=hold.id)
        return hold

    async def create_hold(self, req: HoldRequest) -> Hold:
        journey = await self.journeys.get(req.journey_id)
        if journey is None:
            raise BookingError(
                404, "journey_not_found", "Journey not found or expired; search again"
            )
        now = self.clock()
        journey = provenance.refresh_journey(journey, now)
        if journey.depart < now:
            raise BookingError(409, "journey_departed", "This journey has already started")

        bookable = [leg for leg in journey.legs if leg.bookable]
        held: list[LegHold] = []
        for leg in bookable:
            try:
                ref = await self.vendor.hold(leg, req.passengers, self.hold_ttl_s)
            except VendorError as e:
                for h in held:
                    await self.vendor.release(h.vendor_ref)
                self.telemetry.event(
                    "hold_conflict", service_id=leg.service_id, reason=e.reason, released=len(held)
                )
                raise BookingError(
                    409,
                    "hold_failed",
                    f"Could not hold {leg.provider}: {e.reason}. Nothing was held.",
                    leg_id=leg.id,
                ) from e
            held.append(
                LegHold(
                    leg_id=leg.id,
                    service_id=leg.service_id or "",
                    mode=leg.mode,
                    provider=leg.provider,
                    vendor_ref=ref,
                    fare_inr=leg.fare_inr.value * req.passengers,
                    passengers=req.passengers,
                )
            )
        pay_later = sum(_pay_later(leg, req.passengers) for leg in journey.legs if not leg.bookable)
        hold = Hold(
            id="H" + uuid.uuid4().hex[:12].upper(),
            journey_id=journey.id,
            journey=journey,
            passengers=req.passengers,
            legs=held,
            total_due_now_inr=sum(h.fare_inr for h in held),
            pay_later_estimate_inr=pay_later,
            created_at=now,
            expires_at=now + timedelta(seconds=self.hold_ttl_s),
            status=HoldStatus.HELD,
        )
        await self._save(hold)
        self.telemetry.event("hold_created", hold_id=hold.id, legs=len(held))
        return hold

    async def _release(self, hold: Hold, status: HoldStatus) -> Hold:
        for h in hold.legs:
            await self.vendor.release(h.vendor_ref)
        hold = hold.model_copy(update={"status": status})
        await self._save(hold)
        return hold

    async def release_hold(self, hold_id: str) -> Hold:
        hold = await self.get_hold(hold_id)
        if hold.status == HoldStatus.CONFIRMED:
            raise BookingError(
                409, "already_confirmed", "Hold is already booked", trippass_id=hold.trippass_id
            )
        if hold.status == HoldStatus.HELD:
            hold = await self._release(hold, HoldStatus.RELEASED)
            self.telemetry.event("hold_released", hold_id=hold.id)
        return hold

    # ---------------- confirm (saga) ----------------

    async def confirm(self, req: ConfirmRequest) -> TripPass:
        lock = f"lock:confirm:{req.hold_id}"
        if not await self.kv.set(lock, "1", 60, nx=True):
            raise BookingError(409, "confirm_in_progress", "This hold is already being booked")
        try:
            return await self._confirm(req)
        finally:
            await self.kv.delete(lock)

    async def _confirm(self, req: ConfirmRequest) -> TripPass:
        hold = await self.get_hold(req.hold_id)
        if hold.status == HoldStatus.CONFIRMED:
            raise BookingError(
                409, "already_confirmed", "Hold is already booked", trippass_id=hold.trippass_id
            )
        if hold.status != HoldStatus.HELD:
            raise BookingError(
                410,
                f"hold_{hold.status.value}",
                f"Hold is {hold.status.value}; search and hold again",
            )
        if req.expected_total_inr != hold.total_due_now_inr:
            raise BookingError(
                409,
                "price_mismatch",
                "The total you agreed to does not match the held price",
                total_due_now_inr=hold.total_due_now_inr,
            )

        legs_by_id = {leg.id: leg for leg in hold.journey.legs}
        payment_id = await self.payments.charge(f"hold:{hold.id}", hold.total_due_now_inr)
        pnrs: dict[str, str] = {}
        ticketed: list[LegHold] = []
        for h in hold.legs:
            try:
                pnrs[h.leg_id] = await self.vendor.confirm(legs_by_id[h.leg_id], h.vendor_ref)
                ticketed.append(h)
            except VendorError as e:
                for t in ticketed:
                    await self.vendor.cancel(t.vendor_ref)
                for rest in hold.legs:
                    if rest not in ticketed:
                        await self.vendor.release(rest.vendor_ref)
                await self.payments.refund(f"hold:{hold.id}")
                await self._save(hold.model_copy(update={"status": HoldStatus.RELEASED}))
                self.telemetry.event(
                    "booking_compensated",
                    hold_id=hold.id,
                    failed_service=h.service_id,
                    cancelled=len(ticketed),
                )
                raise BookingError(
                    409,
                    "booking_failed",
                    f"{e.leg.provider} could not issue a ticket. Every other leg "
                    "was cancelled and your payment was refunded.",
                    leg_id=h.leg_id,
                ) from e

        tp_id = "TP-" + uuid.uuid4().hex[:8].upper()
        issued = self.clock()
        token = self.signer.sign(
            {
                "tp": tp_id,
                "j": hold.journey_id,
                "pax": hold.passengers,
                "iat": int(issued.timestamp()),
            }
        )
        tp = TripPass(
            id=tp_id,
            hold_id=hold.id,
            journey=hold.journey,
            passengers=hold.passengers,
            booked_legs=[
                BookedLeg(
                    leg_id=leg.id,
                    mode=leg.mode,
                    provider=leg.provider,
                    status="confirmed" if leg.id in pnrs else "pay_at_travel",
                    pnr=pnrs.get(leg.id),
                )
                for leg in hold.journey.legs
            ],
            total_paid_inr=hold.total_due_now_inr,
            pay_later_estimate_inr=hold.pay_later_estimate_inr,
            payment_id=payment_id,
            issued_at=issued,
            token=token,
            qr_payload=f"KSYNC1:{token}",
        )
        await self.repo.save(tp)
        await self._save(
            hold.model_copy(update={"status": HoldStatus.CONFIRMED, "trippass_id": tp.id})
        )
        self.telemetry.event("booking_confirmed", hold_id=hold.id, trippass_id=tp.id)
        return tp

    async def get_trippass(self, trippass_id: str) -> TripPass:
        tp = await self.repo.get(trippass_id)
        if tp is None:
            raise BookingError(404, "trippass_not_found", "TripPass not found")
        return tp

    def verify_token(self, token: str) -> dict | None:
        return self.signer.verify(token.removeprefix("KSYNC1:"))


def _pay_later(leg: Leg, passengers: int) -> int:
    # Cabs and Rapido are shared by the party (Rapido seats one; assume one bike each).
    if leg.mode.value == "cab":
        return leg.fare_inr.value * (1 + (passengers - 1) // 4)
    return leg.fare_inr.value * passengers
