import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { Journey, LegStatus, Mode } from "../api/types";
import { MODE_COLORS, STATUS_COLORS } from "../globe/geo";
import type { GlobeController, ScreenLabel } from "../globe/scene";
import { MODE_TEXT, formatDuration } from "../lib/format";

interface Props {
  journey: Journey | null;
  statuses?: Record<string, LegStatus>;
  height?: number;
}

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return Boolean(c.getContext("webgl2") ?? c.getContext("webgl"));
  } catch {
    return false;
  }
}

function prefersReducedMotion(): boolean {
  return typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Keep labels readable: endpoints first, then any hub label that doesn't collide. */
export function declutter(labels: ScreenLabel[]): ScreenLabel[] {
  const placed: ScreenLabel[] = [];
  const ordered = [...labels.filter((l) => l.kind === "endpoint"), ...labels.filter((l) => l.kind === "hub")];
  for (const l of ordered) {
    if (!l.visible) continue;
    const width = l.text.length * 6.5 + 12;
    const clash = placed.some((p) => Math.abs(p.y - l.y) < 16 && l.x < p.x + p.text.length * 6.5 + 12 && p.x < l.x + width);
    if (!clash) placed.push(l);
  }
  return placed;
}

/** Describes the route in words: the accessible equivalent of the 3D view. */
export function routeDescription(journey: Journey | null): string {
  if (!journey) return "Globe showing the 14 KogniSync hub cities in India.";
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];
  const modes = journey.legs.map((l) => MODE_TEXT[l.mode].toLowerCase()).join(", then ");
  return `Route from ${first.origin.name} to ${last.destination.name} by ${modes}; ${formatDuration(journey.duration_min)} door to door.`;
}

export function JourneyGlobe({ journey, statuses, height = 380 }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controller = useRef<GlobeController | null>(null);
  const [supported] = useState(webglAvailable);
  const [ready, setReady] = useState(false);
  const [labels, setLabels] = useState<ScreenLabel[]>([]);
  const latest = useRef({ journey, statuses });
  latest.current = { journey, statuses };

  useEffect(() => {
    if (!supported || !canvasRef.current) return;
    let disposed = false;
    const canvas = canvasRef.current;
    import("../globe/scene").then(({ createGlobe }) => {
      if (disposed) return;
      const c = createGlobe(canvas, { reducedMotion: prefersReducedMotion(), onLabels: setLabels });
      controller.current = c;
      c.setJourney(latest.current.journey, latest.current.statuses);
      api.hubs().then((r) => !disposed && c.setHubs(r.hubs), () => undefined);
      setReady(true);
    });
    return () => {
      disposed = true;
      controller.current?.dispose();
      controller.current = null;
    };
  }, [supported]);

  useEffect(() => {
    controller.current?.setJourney(journey, statuses);
  }, [journey, statuses, ready]);

  const modes = journey ? ([...new Set(journey.legs.map((l) => l.mode))] as Mode[]) : [];
  const description = routeDescription(journey);
  const disrupted = Object.values(statuses ?? {}).some((s) => s === "cancelled" || s === "missed_connection");

  if (!supported) {
    return (
      <div className="globe globe--fallback card" role="img" aria-label={description}>
        <p className="muted">3D view needs WebGL. {description}</p>
      </div>
    );
  }

  return (
    <figure className="globe" style={{ height }}>
      <canvas ref={canvasRef} className="globe__canvas" role="img" aria-label={description} />
      <div className="globe__labels" aria-hidden="true">
        {declutter(labels).map((l) => (
            <span
              key={l.id}
              className={`globe__label globe__label--${l.kind}`}
              style={{ transform: `translate(${Math.round(l.x)}px, ${Math.round(l.y)}px)` }}
            >
              {l.text}
            </span>
          ))}
      </div>
      {!ready && <p className="globe__loading muted">Loading 3D globe…</p>}
      {modes.length > 0 && (
        <figcaption className="globe__legend">
          {modes.map((m) => (
            <span key={m}>
              <i style={{ background: MODE_COLORS[m] }} />
              {MODE_TEXT[m]}
            </span>
          ))}
          {disrupted && (
            <span className="globe__legend-alert">
              <i style={{ background: STATUS_COLORS.cancelled }} />
              Disrupted (pulsing)
            </span>
          )}
          <span className="muted">Drag to rotate · scroll to zoom</span>
        </figcaption>
      )}
    </figure>
  );
}
