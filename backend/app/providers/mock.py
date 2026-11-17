"""Deterministic mock transport providers for all 7 modes.

These stand in for Google Routes / Valhalla (local legs), GTFS feeds (metro, city bus) and
carrier inventory (flight, train, intercity bus) until real providers are connected. Output is
stable for a given city pair and date, so tests and demos are reproducible.

Every value is labeled with the provenance kind the real provider would give it, and the
source names start with ``mock:`` so nobody mistakes demo data for real data.
"""

import hashlib
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.data.cities import CITIES, City
from app.domain.geo import haversine_km, interpolate
from app.domain.models import (
    IST,
    Leg,
    Mode,
    Place,
    PlaceKind,
    ProvenanceKind,
    Sourced,
)
from app.services.provenance import make

LIVE, SCHED, EST = ProvenanceKind.LIVE, ProvenanceKind.SCHEDULED, ProvenanceKind.ESTIMATED


def stable_hash(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(digest[:12], 16)


def _round_to(value: float, step: int) -> int:
    return int(round(value / step) * step)


def _is_peak(t: datetime) -> bool:
    return 8 <= t.hour < 11 or 17 <= t.hour < 21


@dataclass
class LegDraft:
    """A local leg before it is placed in time."""

    mode: Mode
    provider: str
    origin: Place
    destination: Place
    distance_km: float
    fare_inr: int
    carbon_g: int
    reliability: float
    time_kind: ProvenanceKind
    fare_kind: ProvenanceKind
    source: str
    speed_kmh: float
    peak_speed_kmh: float
    wait_min: int

    def duration_min(self, at: datetime) -> int:
        speed = self.peak_speed_kmh if _is_peak(at) else self.speed_kmh
        return max(1, math.ceil(self.wait_min + self.distance_km / speed * 60))


class MockTransport:
    def __init__(self, now: datetime):
        self.now = now

    # ---------- local legs (first / last mile, same-city trips) ----------

    def _walk(self, a: Place, b: Place) -> LegDraft:
        km = haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.25
        return LegDraft(
            Mode.WALK, "Walk", a, b, km, 0, 0, 0.99, EST, EST, "mock:walking-model", 4.8, 4.8, 0
        )

    def _cab(self, a: Place, b: Place) -> LegDraft:
        km = haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.35
        fare = _round_to(60 + 16 * km, 10)
        return LegDraft(
            Mode.CAB,
            "Uber / Ola",
            a,
            b,
            km,
            fare,
            int(130 * km),
            0.9,
            EST,
            EST,
            "mock:cab-fare-estimate",
            24,
            16,
            7,
        )

    def _rapido(self, a: Place, b: Place) -> LegDraft:
        km = haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.3
        fare = _round_to(20 + 7 * km, 5)
        return LegDraft(
            Mode.RAPIDO,
            "Rapido Bike",
            a,
            b,
            km,
            fare,
            int(40 * km),
            0.86,
            EST,
            EST,
            "mock:rapido-fare-estimate",
            26,
            21,
            5,
        )

    def _metro(self, city: City, a: Place, b: Place) -> LegDraft:
        km = haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.2
        fare = int(min(90, max(10, 10 + 2.2 * km)))
        return LegDraft(
            Mode.METRO,
            city.metro or "Metro",
            a,
            b,
            km,
            fare,
            int(30 * km),
            0.96,
            SCHED,
            SCHED,
            "mock:gtfs-metro",
            33,
            33,
            9,
        )

    def _city_bus(self, city: City, a: Place, b: Place) -> LegDraft:
        km = haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.3
        if b.kind == PlaceKind.AIRPORT and city.airport_bus:
            provider, fare = city.airport_bus, 250
        else:
            provider, fare = city.city_bus, int(min(60, max(5, 5 + 1.6 * km)))
        return LegDraft(
            Mode.BUS,
            provider,
            a,
            b,
            km,
            fare,
            int(35 * km),
            0.78,
            SCHED,
            SCHED,
            "mock:gtfs-bus",
            18,
            12,
            10,
        )

    def local_chains(self, a: Place, b: Place) -> list[list[LegDraft]]:
        """Alternative leg chains between two points in the same city."""
        d = haversine_km(a.lat, a.lon, b.lat, b.lon)
        if d < 0.3:
            return [[]]
        city = CITIES[a.city or b.city or ""]
        chains: list[list[LegDraft]] = []
        if d <= 2.5:
            chains.append([self._walk(a, b)])
        chains.append([self._cab(a, b)])
        if d * 1.3 <= 30:
            chains.append([self._rapido(a, b)])
        if city.metro and d >= 4:
            near_a = self._metro_station(city, a, b, 0.06, "near " + a.name)
            near_b = self._metro_station(city, a, b, 0.94, "near " + b.name)
            chains.append(
                [self._walk(a, near_a), self._metro(city, near_a, near_b), self._walk(near_b, b)]
            )
            if d >= 10:
                hub_a = self._metro_station(city, a, b, 0.2, "interchange towards " + b.name)
                chains.append(
                    [
                        self._rapido(a, hub_a),
                        self._metro(city, hub_a, near_b),
                        self._walk(near_b, b),
                    ]
                )
        if d >= 4:
            stop_a = self._bus_stop(city, a, b, 0.04, a.name)
            chains.append([self._walk(a, stop_a), self._city_bus(city, stop_a, b)])
        return chains

    @staticmethod
    def _metro_station(city: City, a: Place, b: Place, f: float, label: str) -> Place:
        lat, lon = interpolate(a.lat, a.lon, b.lat, b.lon, f)
        return Place(
            name=f"Metro station {label} (approx.)",
            lat=lat,
            lon=lon,
            city=city.key,
            kind=PlaceKind.METRO_STATION,
        )

    @staticmethod
    def _bus_stop(city: City, a: Place, b: Place, f: float, label: str) -> Place:
        lat, lon = interpolate(a.lat, a.lon, b.lat, b.lon, f)
        return Place(
            name=f"{city.city_bus} stop near {label} (approx.)", lat=lat, lon=lon, city=city.key
        )

    def time_chain(
        self, drafts: list[LegDraft], *, start: datetime | None = None, end: datetime | None = None
    ) -> list[Leg]:
        """Place drafts in time, either forward from ``start`` or backward to ``end``."""
        if not drafts:
            return []
        gap = timedelta(minutes=3)
        if start is None:
            assert end is not None
            # Walk backward once to find the start, then time forward from there.
            t = end
            for draft in reversed(drafts):
                t -= timedelta(minutes=draft.duration_min(t)) + gap
            start = t + gap
        legs, t = [], start
        for draft in drafts:
            dur = draft.duration_min(t)
            arrive = t + timedelta(minutes=dur)
            legs.append(self._leg_from_draft(draft, t, arrive))
            t = arrive + gap
        return legs

    def _leg_from_draft(self, d: LegDraft, depart: datetime, arrive: datetime) -> Leg:
        leg_id = (
            "L"
            + format(
                stable_hash(d.mode, d.origin.name, d.destination.name, depart.isoformat()), "x"
            )[:10]
        )
        return Leg(
            id=leg_id,
            mode=d.mode,
            provider=d.provider,
            origin=d.origin,
            destination=d.destination,
            depart=Sourced(value=depart, provenance=make(d.time_kind, d.source, self.now)),
            arrive=Sourced(value=arrive, provenance=make(d.time_kind, d.source, self.now)),
            fare_inr=Sourced(value=d.fare_inr, provenance=make(d.fare_kind, d.source, self.now)),
            distance_km=round(d.distance_km, 1),
            carbon_g=d.carbon_g,
            reliability=d.reliability,
            min_connection_min=0,
        )

    # ---------- trunk legs (flight, train, intercity bus) ----------

    def trunk_services(self, a: City, b: City, start: datetime, end: datetime) -> list[Leg]:
        legs: list[Leg] = []
        day = start.date() - timedelta(days=2)  # overnight trains may depart before `start`
        while day <= end.date():
            legs += self._flights(a, b, day)
            legs += self._trains(a, b, day)
            legs += self._buses(a, b, day)
            day += timedelta(days=1)
        return [leg for leg in legs if start <= leg.depart.value <= end]

    def _trunk_leg(
        self,
        *,
        mode: Mode,
        provider: str,
        service_id: str,
        origin: Place,
        destination: Place,
        depart: datetime,
        duration_min: int,
        fare: int,
        fare_kind: ProvenanceKind,
        fare_source: str,
        fare_ttl: int | None,
        distance_km: float,
        carbon_g: int,
        reliability: float,
        seats: int,
        min_connection: int,
    ) -> Leg:
        arrive = depart + timedelta(minutes=duration_min)
        schedule = make(SCHED, f"mock:{mode.value}-timetable", self.now)
        return Leg(
            id="L" + format(stable_hash(service_id), "x")[:10],
            mode=mode,
            provider=provider,
            service_id=service_id,
            origin=origin,
            destination=destination,
            depart=Sourced(value=depart, provenance=schedule),
            arrive=Sourced(value=arrive, provenance=schedule),
            fare_inr=Sourced(
                value=fare, provenance=make(fare_kind, fare_source, self.now, fare_ttl)
            ),
            distance_km=round(distance_km, 1),
            carbon_g=carbon_g,
            reliability=reliability,
            seats_available=Sourced(
                value=seats,
                provenance=make(LIVE, f"mock:{mode.value}-inventory", self.now, 300),
            ),
            bookable=True,
            fixed_schedule=True,
            min_connection_min=min_connection,
        )

    def _flights(self, a: City, b: City, day: date) -> list[Leg]:
        gc = haversine_km(*a.center, *b.center)
        if gc < 250:
            return []
        carriers = [("IndiGo", "6E"), ("Air India", "AI"), ("Akasa Air", "QP"), ("SpiceJet", "SG")]
        slots = [time(6, 10), time(8, 40), time(11, 15), time(14, 5), time(17, 30), time(20, 45)]
        out = []
        for i, slot in enumerate(slots):
            h = stable_hash("flight", a.key, b.key, day, i)
            carrier, prefix = carriers[h % len(carriers)]
            number = f"{prefix}-{100 + h % 900}"
            depart = datetime.combine(day, slot, IST) + timedelta(minutes=h % 25)
            duration = int(25 + gc / 12.5 + 10)
            mult = 0.85 + (h % 50) / 100 + (0.15 if depart.hour in (6, 7, 8, 17, 18) else 0)
            fare = _round_to((1800 + 2.6 * gc) * mult, 10)
            seats = (h >> 8) % 40
            if seats == 0:
                continue  # sold out: not offered
            out.append(
                self._trunk_leg(
                    mode=Mode.FLIGHT,
                    provider=f"{carrier} {number}",
                    service_id=f"{number}-{day.isoformat()}",
                    origin=a.airport_place(),
                    destination=b.airport_place(),
                    depart=depart,
                    duration_min=duration,
                    fare=fare,
                    fare_kind=LIVE,
                    fare_source="mock:airline-fare-api",
                    fare_ttl=600,
                    distance_km=gc,
                    carbon_g=int(gc * 100),
                    reliability=0.85,
                    seats=seats,
                    min_connection=90,
                )
            )
        return out

    def _trains(self, a: City, b: City, day: date) -> list[Leg]:
        gc = haversine_km(*a.center, *b.center)
        rail = gc * 1.3
        if rail > 3000 or gc < 40:
            return []
        kinds = [
            ("Superfast Express", 58, 1.5, 0.75, time(9, 30)),
            ("Rajdhani Express", 72, 2.3, 0.82, time(19, 50)),
        ]
        if rail <= 900:
            kinds.append(("Vande Bharat Express", 82, 2.0, 0.9, time(6, 0)))
        out = []
        for name, speed, per_km, rel, slot in kinds:
            h = stable_hash("train", a.key, b.key, day, name)
            number = 12000 + h % 8000
            depart = datetime.combine(day, slot, IST) + timedelta(minutes=(h % 9) * 5)
            seats = (h >> 8) % 120
            if seats == 0:
                continue
            out.append(
                self._trunk_leg(
                    mode=Mode.TRAIN,
                    provider=f"{number} {a.name}-{b.name} {name}",
                    service_id=f"{number}-{day.isoformat()}",
                    origin=a.station_place(),
                    destination=b.station_place(),
                    depart=depart,
                    duration_min=int(rail / speed * 60),
                    fare=_round_to(rail * per_km, 5),
                    fare_kind=SCHED,
                    fare_source="mock:irctc-fare-chart",
                    fare_ttl=None,
                    distance_km=rail,
                    carbon_g=int(rail * 20),
                    reliability=rel,
                    seats=seats,
                    min_connection=30,
                )
            )
        return out

    def _buses(self, a: City, b: City, day: date) -> list[Leg]:
        gc = haversine_km(*a.center, *b.center)
        road = gc * 1.3
        if road > 1000 or gc < 40:
            return []
        operators = ["VRL Travels", "SRS Travels", "Zingbus", "IntrCity SmartBus"]
        out = []
        for i, slot in enumerate([time(7, 30), time(21, 15)]):
            h = stable_hash("bus", a.key, b.key, day, i)
            operator = operators[h % len(operators)]
            depart = datetime.combine(day, slot, IST) + timedelta(minutes=(h % 6) * 5)
            seats = (h >> 8) % 30
            if seats == 0:
                continue
            out.append(
                self._trunk_leg(
                    mode=Mode.BUS,
                    provider=f"{operator} AC Sleeper",
                    service_id=f"BUS{h % 100000:05d}-{day.isoformat()}",
                    origin=a.bus_terminal_place(),
                    destination=b.bus_terminal_place(),
                    depart=depart,
                    duration_min=int(road / 48 * 60),
                    fare=_round_to(road * 1.7, 10),
                    fare_kind=LIVE,
                    fare_source="mock:bus-aggregator-fare",
                    fare_ttl=600,
                    distance_km=road,
                    carbon_g=int(road * 30),
                    reliability=0.75,
                    seats=seats,
                    min_connection=20,
                )
            )
        return out


EGRESS_MIN = {Mode.FLIGHT: 25, Mode.TRAIN: 10, Mode.BUS: 10}
