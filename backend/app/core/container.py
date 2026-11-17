"""Wires services together once per app. Tests build their own with a fixed clock."""

import logging
import secrets
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.ai.copilot import Copilot
from app.ai.llm import LLM, build_llm
from app.ai.omni import Omni
from app.core.config import Settings
from app.domain.models import IST
from app.services.booking import BookingService
from app.services.booking_repo import KVTripPassRepo, SqlTripPassRepo, TripPassRepo
from app.services.disruption import DisruptionService
from app.services.idempotency import IdempotencyService
from app.services.journey_store import JourneyStore
from app.services.kv import KV, MemoryKV, RedisKV
from app.services.orchestrator import Orchestrator
from app.services.telemetry import Telemetry
from app.services.trippass import TripPassSigner
from app.services.vendors import MockPayments, MockVendor

log = logging.getLogger(__name__)


def system_clock() -> datetime:
    return datetime.now(IST)


@dataclass
class Container:
    settings: Settings
    clock: Callable[[], datetime]
    kv: KV
    telemetry: Telemetry
    orchestrator: Orchestrator
    journeys: JourneyStore
    idempotency: IdempotencyService
    vendor: MockVendor
    payments: MockPayments
    booking: BookingService
    disruptions: DisruptionService
    copilot: Copilot = None  # type: ignore[assignment]
    omni: Omni = None  # type: ignore[assignment]
    rate_hits: dict = field(default_factory=lambda: defaultdict(deque))


def _signing_key(settings: Settings) -> bytes:
    if settings.trippass_signing_key:
        return settings.trippass_signing_key.get_secret_value().encode()
    if settings.app_env == "production":
        raise RuntimeError("TRIPPASS_SIGNING_KEY must be set in production")
    log.warning("TRIPPASS_SIGNING_KEY not set; using a random key for this process")
    return secrets.token_bytes(32)


def build_container(
    settings: Settings,
    clock: Callable[[], datetime] | None = None,
    kv: KV | None = None,
    repo: TripPassRepo | None = None,
    llm: LLM | None = None,
) -> Container:
    clock = clock or system_clock
    if kv is None:
        kv = (
            RedisKV.from_url(settings.redis_url.get_secret_value())
            if settings.redis_url
            else MemoryKV()
        )
    if repo is None:
        repo = (
            SqlTripPassRepo(settings.database_url.get_secret_value())
            if settings.database_url
            else KVTripPassRepo(kv)
        )
    telemetry = Telemetry(clock)
    journeys = JourneyStore(kv)
    vendor = MockVendor(kv)
    payments = MockPayments(kv)
    booking = BookingService(
        kv=kv,
        journeys=journeys,
        vendor=vendor,
        payments=payments,
        repo=repo,
        signer=TripPassSigner(_signing_key(settings)),
        telemetry=telemetry,
        clock=clock,
        hold_ttl_s=settings.hold_ttl_seconds,
    )
    orchestrator = Orchestrator(clock)
    disruptions = DisruptionService(
        kv=kv, orchestrator=orchestrator, journeys=journeys, telemetry=telemetry, clock=clock
    )
    if llm is None and settings.gemini_api_key:
        llm = build_llm(settings.gemini_api_key.get_secret_value(), settings.gemini_model)
    container = Container(
        settings=settings,
        clock=clock,
        kv=kv,
        telemetry=telemetry,
        orchestrator=orchestrator,
        journeys=journeys,
        idempotency=IdempotencyService(kv),
        vendor=vendor,
        payments=payments,
        booking=booking,
        disruptions=disruptions,
    )
    container.copilot = Copilot(container, llm)
    container.omni = Omni(llm, settings.gemini_omni_model)
    return container
