export type Mode = "flight" | "train" | "bus" | "cab" | "rapido" | "metro" | "walk";
export const MODES: Mode[] = ["flight", "train", "bus", "cab", "rapido", "metro", "walk"];
export type ProvKind = "live" | "scheduled" | "estimated";

export interface Provenance {
  kind: ProvKind;
  source: string;
  as_of: string;
  ttl_seconds: number | null;
  stale: boolean;
}

export interface Sourced<T> {
  value: T;
  provenance: Provenance;
}

export interface Place {
  name: string;
  lat: number;
  lon: number;
  city: string | null;
  kind: string;
  code: string | null;
}

export interface Leg {
  id: string;
  mode: Mode;
  provider: string;
  service_id: string | null;
  origin: Place;
  destination: Place;
  depart: Sourced<string>;
  arrive: Sourced<string>;
  fare_inr: Sourced<number>;
  distance_km: number;
  carbon_g: number;
  reliability: number;
  seats_available: Sourced<number> | null;
  bookable: boolean;
  fixed_schedule: boolean;
}

export interface Journey {
  id: string;
  legs: Leg[];
  depart: string;
  arrive: string;
  duration_min: number;
  cost_inr: number;
  carbon_kg: number;
  reliability: number;
  transfers: number;
  cost_provenance: ProvKind;
  provenance_summary: Record<string, number>;
  labels: string[];
  explanation: string[];
  warnings: string[];
  score: number;
}

export interface SearchRequest {
  origin: string;
  destination: string;
  depart_after?: string;
  arrive_by?: string;
  budget_inr?: number;
  prefer_modes?: Mode[];
  avoid_modes?: Mode[];
  limit?: number;
}

export interface SearchResponse {
  search_id: string;
  origin: Place;
  destination: Place;
  journeys: Journey[];
  considered: number;
  pareto_size: number;
  rejected: Record<string, number>;
  relaxation_hints: string[];
  time_objective: "arrival" | "duration";
  data_mode: "mock" | "live";
}

export interface LegHold {
  leg_id: string;
  provider: string;
  mode: Mode;
  fare_inr: number;
}

export interface Hold {
  id: string;
  journey_id: string;
  journey: Journey;
  passengers: number;
  legs: LegHold[];
  total_due_now_inr: number;
  pay_later_estimate_inr: number;
  expires_at: string;
  status: "held" | "confirmed" | "released" | "expired";
}

export interface BookedLeg {
  leg_id: string;
  mode: Mode;
  provider: string;
  status: "confirmed" | "pay_at_travel";
  pnr: string | null;
}

export interface TripPass {
  id: string;
  hold_id: string;
  journey: Journey;
  passengers: number;
  booked_legs: BookedLeg[];
  total_paid_inr: number;
  pay_later_estimate_inr: number;
  issued_at: string;
  qr_payload: string;
}

export type LegStatus =
  | "on_time"
  | "delayed"
  | "at_risk"
  | "missed_connection"
  | "cancelled"
  | "needs_replan";

export interface LegImpact {
  leg_id: string;
  mode: Mode;
  provider: string;
  status: LegStatus;
  expected_arrive: string | null;
  delay_min: number;
}

export interface Impact {
  severity: "none" | "minor" | "major" | "critical";
  legs: LegImpact[];
  first_broken_leg: number | null;
  expected_arrival: string | null;
  arrival_delay_min: number | null;
  deadline_missed: boolean;
  based_on_stale_data: boolean;
  summary: string;
}

export interface Recovery {
  impact: Impact;
  replaces_from_leg: number | null;
  options: Journey[];
  requires_consent: true;
  note: string;
}

export interface DisruptionCreate {
  kind: "delay" | "cancellation" | "closure";
  service_id?: string;
  provider?: string;
  city?: string;
  mode?: Mode;
  delay_min?: number;
  message?: string;
}

export interface JourneySummary {
  journey_id: string;
  labels: string[];
  route: string;
  depart: string;
  arrive: string;
  duration: string;
  cost_inr: number;
  cost_display: string;
  cost_provenance: ProvKind;
  carbon_kg: number;
}

export interface ProposedAction {
  type: "hold";
  journey_id: string;
  passengers: number;
  cost_inr: number;
  cost_provenance: string;
  summary: string;
}

export interface ChatResponse {
  answer: string;
  ai_mode: "gemini" | "fallback";
  tool_calls: { name: string; args: Record<string, unknown>; ok: boolean }[];
  journeys: JourneySummary[];
  proposed_action: ProposedAction | null;
  grounding: { verified: boolean; ungrounded_amounts: number[] };
  notice: string | null;
}

export interface ChatTurn {
  role: "user" | "model";
  text: string;
}

export interface TicketExtraction {
  document_type: string;
  mode: Mode | null;
  operator: string | null;
  service_number: string | null;
  pnr: string | null;
  origin: string | null;
  destination: string | null;
  depart: string | null;
  seat: string | null;
  platform_or_gate: string | null;
  status: string | null;
  confidence: string;
}

export interface Finding {
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  suggested_fix: string;
}

export interface ReliabilityReport {
  summary: string;
  ai_mode: "gemini" | "fallback";
  findings: Finding[];
}

export interface ProviderHealth {
  data_mode: string;
  providers: { name: string; covers: string; status: string }[];
  disruption_feed: { status: string; active: number; stale: number };
  ai: { gemini_configured: boolean; gemini_errors: number; grounding_rejections: number };
}
