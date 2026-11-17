import { vi } from "vitest";
import type { Journey, Leg, Provenance, TripPass } from "../api/types";

const prov = (kind: Provenance["kind"], stale = false): Provenance => ({
  kind,
  source: `mock:${kind}`,
  as_of: "2026-11-23T06:00:00+05:30",
  ttl_seconds: null,
  stale,
});

const place = (name: string) => ({ name, lat: 0, lon: 0, city: "BLR", kind: "address", code: null });

export function leg(over: Partial<Leg> = {}): Leg {
  return {
    id: "L1",
    mode: "flight",
    provider: "IndiGo 6E-123",
    service_id: "6E-123-2026-11-23",
    origin: place("BLR"),
    destination: place("DEL"),
    depart: { value: "2026-11-23T11:15:00+05:30", provenance: prov("scheduled") },
    arrive: { value: "2026-11-23T14:10:00+05:30", provenance: prov("scheduled") },
    fare_inr: { value: 6200, provenance: prov("live") },
    distance_km: 1740,
    carbon_g: 174000,
    reliability: 0.85,
    seats_available: { value: 12, provenance: prov("live") },
    bookable: true,
    fixed_schedule: true,
    ...over,
  };
}

export function journey(over: Partial<Journey> = {}): Journey {
  return {
    id: "J1",
    legs: [
      leg({
        id: "L0",
        mode: "cab",
        provider: "Uber / Ola",
        service_id: null,
        bookable: false,
        seats_available: null,
        fare_inr: { value: 700, provenance: prov("estimated") },
      }),
      leg(),
    ],
    depart: "2026-11-23T08:30:00+05:30",
    arrive: "2026-11-23T14:10:00+05:30",
    duration_min: 340,
    cost_inr: 6900,
    carbon_kg: 180.2,
    reliability: 0.77,
    transfers: 1,
    cost_provenance: "estimated",
    provenance_summary: { live: 2, scheduled: 4, estimated: 2 },
    labels: ["recommended", "fastest"],
    explanation: ["Recommended: the best balance."],
    warnings: [],
    score: 0.1,
    ...over,
  };
}

export function trippass(over: Partial<TripPass> = {}): TripPass {
  const j = journey();
  return {
    id: "TP-ABC12345",
    hold_id: "H1",
    journey: j,
    passengers: 1,
    booked_legs: [
      { leg_id: "L0", mode: "cab", provider: "Uber / Ola", status: "pay_at_travel", pnr: null },
      { leg_id: "L1", mode: "flight", provider: "IndiGo 6E-123", status: "confirmed", pnr: "XK42QZ" },
    ],
    total_paid_inr: 6200,
    pay_later_estimate_inr: 700,
    issued_at: "2026-11-23T06:01:00+05:30",
    qr_payload: "KSYNC1:abc.def",
    ...over,
  };
}

type Handler = (init: RequestInit | undefined) => { status?: number; body?: unknown };

/** Route fetch calls by "METHOD path" (e.g. "POST /api/v1/holds"). Records every call. */
export function mockApi(routes: Record<string, Handler | { status?: number; body?: unknown }>) {
  const calls: { key: string; init?: RequestInit }[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = new URL(String(input), "http://localhost");
    const key = `${init?.method ?? "GET"} ${url.pathname}`;
    calls.push({ key, init });
    const route = routes[key];
    if (!route) return new Response(JSON.stringify({ detail: `no mock for ${key}` }), { status: 404 });
    const { status = 200, body } = typeof route === "function" ? route(init) : route;
    return new Response(body === undefined ? null : JSON.stringify(body), { status });
  });
  return calls;
}
