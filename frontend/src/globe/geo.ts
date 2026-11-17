/**
 * Pure globe geometry: no WebGL, so it is unit-testable.
 * Convention: unit sphere, +Y is the north pole, lon 0 faces +X... see latLonToXyz.
 */
import type { Journey, Leg, LegStatus, Mode } from "../api/types";

export type Vec3 = [number, number, number];

const DEG = Math.PI / 180;

export function latLonToXyz(lat: number, lon: number, radius = 1): Vec3 {
  const phi = (90 - lat) * DEG;
  const theta = (lon + 180) * DEG;
  return [-radius * Math.sin(phi) * Math.cos(theta), radius * Math.cos(phi), radius * Math.sin(phi) * Math.sin(theta)];
}

export const length = (v: Vec3) => Math.hypot(v[0], v[1], v[2]);
export const scale = (v: Vec3, s: number): Vec3 => [v[0] * s, v[1] * s, v[2] * s];
export const normalize = (v: Vec3): Vec3 => scale(v, 1 / (length(v) || 1));
const dot = (a: Vec3, b: Vec3) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];

/** Angle between two surface points, in radians. */
export function angleBetween(a: Vec3, b: Vec3): number {
  return Math.acos(Math.min(1, Math.max(-1, dot(normalize(a), normalize(b)))));
}

/** Spherical interpolation between unit vectors (great-circle path). */
export function slerp(a: Vec3, b: Vec3, t: number): Vec3 {
  const omega = angleBetween(a, b);
  if (omega < 1e-6) return normalize([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]);
  const s = Math.sin(omega);
  const wa = Math.sin((1 - t) * omega) / s;
  const wb = Math.sin(t * omega) / s;
  return [a[0] * wa + b[0] * wb, a[1] * wa + b[1] * wb, a[2] * wa + b[2] * wb];
}

/** Flights arc above the surface (higher for longer hops); ground legs hug it. */
export function legAltitude(mode: Mode, angle: number): number {
  if (mode === "flight") return 0.02 + angle * 0.35;
  return 0;
}

export const SURFACE_LIFT = 0.004;

export function arcPoints(from: Vec3, to: Vec3, mode: Mode, segments = 48): Vec3[] {
  const a = normalize(from);
  const b = normalize(to);
  const peak = legAltitude(mode, angleBetween(a, b));
  const pts: Vec3[] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const r = 1 + SURFACE_LIFT + peak * Math.sin(Math.PI * t);
    pts.push(scale(slerp(a, b, t), r));
  }
  return pts;
}

export interface LegPath {
  legId: string;
  mode: Mode;
  status: LegStatus | "on_time";
  points: Vec3[];
}

export function journeyPaths(journey: Journey, statuses: Record<string, LegStatus> = {}): LegPath[] {
  return journey.legs.map((leg: Leg) => ({
    legId: leg.id,
    mode: leg.mode,
    status: statuses[leg.id] ?? "on_time",
    points: arcPoints(
      latLonToXyz(leg.origin.lat, leg.origin.lon),
      latLonToXyz(leg.destination.lat, leg.destination.lon),
      leg.mode,
      leg.mode === "flight" ? 64 : 24,
    ),
  }));
}

/** Where to put the camera so the whole route is in view. */
export function framing(points: Vec3[]): { direction: Vec3; distance: number } {
  if (!points.length) return { direction: normalize(latLonToXyz(21, 80)), distance: 2.6 };
  const sum = points.reduce<Vec3>((acc, p) => [acc[0] + p[0], acc[1] + p[1], acc[2] + p[2]], [0, 0, 0]);
  const direction = normalize(sum);
  const spread = Math.max(...points.map((p) => angleBetween(p, direction)));
  // Close in for a city trip, pull back for an intercity one; never inside the globe.
  const distance = Math.min(3.2, Math.max(1.12, 1 + spread * 3.2));
  return { direction, distance };
}

/** Cumulative arc lengths, for moving the traveler at constant speed. */
export function cumulativeLengths(points: Vec3[]): number[] {
  const out = [0];
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1];
    const b = points[i];
    out.push(out[i - 1] + Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]));
  }
  return out;
}

export function pointAt(points: Vec3[], lengths: number[], t: number): Vec3 {
  const total = lengths[lengths.length - 1];
  if (!total) return points[0];
  const target = Math.min(1, Math.max(0, t)) * total;
  let i = 1;
  while (i < lengths.length - 1 && lengths[i] < target) i++;
  const span = lengths[i] - lengths[i - 1] || 1;
  const f = (target - lengths[i - 1]) / span;
  const a = points[i - 1];
  const b = points[i];
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];
}

/** Dots spaced evenly over the sphere (fewer per row near the poles). */
export function sphereDots(stepDeg: number): { lat: number; lon: number }[] {
  const out: { lat: number; lon: number }[] = [];
  for (let lat = -84; lat <= 84; lat += stepDeg) {
    const count = Math.max(1, Math.round((360 / stepDeg) * Math.cos(lat * DEG)));
    for (let i = 0; i < count; i++) out.push({ lat, lon: -180 + (360 * i) / count });
  }
  return out;
}

export const MODE_COLORS: Record<Mode, string> = {
  flight: "#ff6b5e",
  train: "#5b9cff",
  bus: "#ffa53d",
  cab: "#d7dbe0",
  rapido: "#ffd34d",
  metro: "#3ddc84",
  walk: "#a0a6ad",
};

export const STATUS_COLORS: Partial<Record<LegStatus, string>> = {
  cancelled: "#ff3b30",
  missed_connection: "#ff3b30",
  needs_replan: "#6b7178",
  delayed: "#ffb020",
  at_risk: "#ffb020",
};

export function legColor(path: Pick<LegPath, "mode" | "status">): string {
  return (path.status !== "on_time" && STATUS_COLORS[path.status]) || MODE_COLORS[path.mode];
}
