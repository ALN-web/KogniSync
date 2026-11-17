import type {
  ChatResponse,
  ChatTurn,
  DisruptionCreate,
  Hold,
  Impact,
  Journey,
  ProviderHealth,
  Recovery,
  ReliabilityReport,
  SearchRequest,
  SearchResponse,
  TicketExtraction,
  TripPass,
} from "./types";

// Empty in local dev: requests go to /api and Vite proxies them to the backend.
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export type DependencyState = "ok" | "error" | "not_configured";

export interface DependencyStatus {
  name: string;
  status: DependencyState;
  detail: string | null;
}

export interface Liveness {
  status: "ok";
  service: string;
  version: string;
  environment: string;
  time: string;
}

export interface Readiness {
  status: "ready" | "degraded";
  dependencies: DependencyStatus[];
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(describe(detail) ?? `HTTP ${status}`);
  }
}

function describe(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; detail?: unknown };
    if (d.message) return d.message;
    if (d.detail !== undefined) return describe(d.detail);
    if (Array.isArray(detail)) return detail.map((e) => (e as { msg?: string }).msg).join("; ");
  }
  return undefined;
}

async function request<T>(path: string, init: RequestInit = {}, ok: number[] = []): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;
  if (!res.ok && !ok.includes(res.status)) {
    throw new ApiError(res.status, body?.detail ?? body);
  }
  return body as T;
}

const post = <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), headers });

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

export const api = {
  liveness: () => request<Liveness>("/api/v1/health"),
  // 503 still carries a useful body listing which dependency is down.
  readiness: () => request<Readiness>("/api/v1/health/ready", {}, [503]),
  places: () => request<{ places: string[] }>("/api/v1/places"),
  hubs: () =>
    request<{ hubs: { key: string; name: string; lat: number; lon: number; has_metro: boolean }[] }>(
      "/api/v1/hubs",
    ),

  search: (req: SearchRequest) => post<SearchResponse>("/api/v1/journeys/search", req),
  journey: (id: string) => request<Journey>(`/api/v1/journeys/${id}`),

  hold: (journeyId: string, key: string, passengers = 1) =>
    post<Hold>("/api/v1/holds", { journey_id: journeyId, passengers }, { "Idempotency-Key": key }),
  releaseHold: (holdId: string) => request<Hold>(`/api/v1/holds/${holdId}`, { method: "DELETE" }),
  confirm: (holdId: string, expectedTotal: number, key: string) =>
    post<TripPass>(
      "/api/v1/bookings",
      { hold_id: holdId, expected_total_inr: expectedTotal, consent: true },
      { "Idempotency-Key": key },
    ),
  trippass: (id: string) => request<TripPass>(`/api/v1/trippass/${id}`),
  qrUrl: (id: string) => `${API_BASE}/api/v1/trippass/${id}/qr.svg`,

  addDisruption: (d: DisruptionCreate) => post("/api/v1/disruptions", d),
  clearDisruptions: () => request<void>("/api/v1/disruptions", { method: "DELETE" }),
  impact: (trippassId: string) => request<Impact>(`/api/v1/trippass/${trippassId}/impact`),
  recovery: (trippassId: string) => post<Recovery>(`/api/v1/trippass/${trippassId}/recovery`),

  copilotStatus: () =>
    request<{ gemini_configured: boolean; model: string; omni_model: string }>(
      "/api/v1/copilot/status",
    ),
  chat: (
    message: string,
    history: ChatTurn[],
    context: { trippass_id?: string; journey_id?: string; reply_language?: string },
  ) => post<ChatResponse>("/api/v1/copilot/chat", { message, history, context }),
  voice: (audio: Blob, languageHint?: string, trippassId?: string) => {
    const form = new FormData();
    form.append("audio", audio, "voice.webm");
    if (languageHint) form.append("language_hint", languageHint);
    if (trippassId) form.append("trippass_id", trippassId);
    return request<{
      voice: { transcript: string; language: string; english: string };
      chat: ChatResponse;
    }>("/api/v1/copilot/voice", { method: "POST", body: form });
  },
  vision: (image: File) => {
    const form = new FormData();
    form.append("image", image);
    return request<{
      extraction: TicketExtraction;
      suggested_search: { origin: string | null; destination: string; depart_after: string | null } | null;
    }>("/api/v1/copilot/vision", { method: "POST", body: form });
  },

  providers: () => request<ProviderHealth>("/api/v1/ops/providers"),
  reliability: () => post<ReliabilityReport>("/api/v1/ops/reliability-summary"),
};
