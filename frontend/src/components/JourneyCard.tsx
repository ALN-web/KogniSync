import { useState } from "react";
import type { Journey } from "../api/types";
import { MODE_COLORS } from "../globe/geo";
import { LABEL_TEXT, MODE_TEXT, formatDay, formatDuration, formatInr, formatTime } from "../lib/format";
import { Icon } from "./icons";
import { ProvenanceBadge } from "./ProvenanceBadge";

interface Props {
  journey: Journey;
  onBook?: (j: Journey) => void;
  bookLabel?: string;
  selected?: boolean;
  onSelect?: (j: Journey) => void;
}

/** Days between departure and arrival in IST (for the "+1" marker). */
export function dayOffset(departIso: string, arriveIso: string): number {
  const day = (iso: string) => {
    const d = new Date(new Date(iso).getTime() + 5.5 * 3600 * 1000);
    return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  };
  return Math.round((day(arriveIso) - day(departIso)) / 86400000);
}

export function JourneyCard({ journey: j, onBook, bookLabel = "Book", selected, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const start = new Date(j.depart).getTime();
  const total = new Date(j.arrive).getTime() - start || 1;
  const plus = dayOffset(j.depart, j.arrive);
  const lowSeats = j.legs.find((l) => l.seats_available && l.seats_available.value <= 5);

  return (
    <article className={`card journey ${selected ? "journey--selected" : ""}`} aria-label={`Journey ${j.id}`}>
      {j.labels.length > 0 && (
        <div className="journey__labels">
          {j.labels.map((l) => (
            <span key={l} className={`chip chip--${l}`}>
              {LABEL_TEXT[l] ?? l}
            </span>
          ))}
        </div>
      )}
      <div className="journey__head">
        <div>
          <div className="journey__times">
            {formatTime(j.depart)} → {formatTime(j.arrive)}
            {plus > 0 && <sup title={`Arrives ${plus} day(s) later`}>+{plus}</sup>}
          </div>
          <div className="journey__meta">
            {formatDay(j.depart)} · {formatDuration(j.duration_min)} · {j.transfers} transfer
            {j.transfers === 1 ? "" : "s"}
          </div>
        </div>
        <div className="journey__price">
          <strong>{formatInr(j.cost_inr)}</strong>
          <ProvenanceBadge kind={j.cost_provenance} />
        </div>
      </div>

      <div className="timeline" aria-hidden="true">
        {j.legs.map((leg) => {
          const left = ((new Date(leg.depart.value).getTime() - start) / total) * 100;
          const width = Math.max(1.5, ((new Date(leg.arrive.value).getTime() - new Date(leg.depart.value).getTime()) / total) * 100);
          return (
            <span
              key={leg.id}
              style={{ left: `${left}%`, width: `${width}%`, background: MODE_COLORS[leg.mode] }}
              title={`${MODE_TEXT[leg.mode]} · ${leg.provider}`}
            />
          );
        })}
      </div>
      <div className="journey__legs" aria-label="Route">
        {j.legs.map((leg, i) => (
          <span key={leg.id} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            {i > 0 && <Icon name="chevron" size={12} />}
            <span className={`mode mode--${leg.mode}`} title={`${MODE_TEXT[leg.mode]} · ${leg.provider}`}>
              <Icon name={leg.mode} size={15} title={MODE_TEXT[leg.mode]} />
            </span>
          </span>
        ))}
      </div>

      <div className="journey__stats">
        <span>
          <Icon name="leaf" size={15} /> {j.carbon_kg.toFixed(1)} kg CO₂
        </span>
        <span>
          <Icon name="shield" size={15} /> {Math.round(j.reliability * 100)}% on plan
        </span>
        {lowSeats && (
          <span className="warning" style={{ margin: 0 }}>
            <Icon name="alert" size={15} /> {lowSeats.seats_available!.value} seats left
          </span>
        )}
      </div>
      {j.warnings
        .filter((w) => !w.startsWith("Only "))
        .map((w) => (
          <p key={w} className="warning">
            {w}
          </p>
        ))}

      <div className="journey__actions">
        <button type="button" className="btn btn--quiet" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide details" : "Details"}
        </button>
        {onSelect && (
          <button type="button" className="btn btn--ghost" aria-pressed={selected} onClick={() => onSelect(j)}>
            {selected ? "On globe" : "Show on globe"}
          </button>
        )}
        {onBook && (
          <button type="button" className="btn" onClick={() => onBook(j)}>
            {bookLabel}
          </button>
        )}
      </div>

      {open && (
        <div className="journey__details">
          <ul className="why">
            {j.explanation.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
          <ol className="legs">
            {j.legs.map((leg) => (
              <li key={leg.id} className="leg">
                <span className={`mode mode--${leg.mode}`}>
                  <Icon name={leg.mode} size={16} title={MODE_TEXT[leg.mode]} />
                </span>
                <div className="leg__body">
                  <div className="leg__title">
                    <strong>{leg.provider}</strong>
                    {leg.seats_available && (
                      <span className="muted small">
                        {leg.seats_available.value} seats <ProvenanceBadge provenance={leg.seats_available.provenance} />
                      </span>
                    )}
                  </div>
                  <div className="leg__place">
                    {leg.origin.name} → {leg.destination.name}
                  </div>
                  <div className="leg__facts">
                    <span>
                      <Icon name="clock" size={14} /> {formatTime(leg.depart.value)}–{formatTime(leg.arrive.value)}{" "}
                      <ProvenanceBadge provenance={leg.depart.provenance} />
                    </span>
                    <span>
                      {leg.fare_inr.value ? formatInr(leg.fare_inr.value) : "Free"}{" "}
                      <ProvenanceBadge provenance={leg.fare_inr.provenance} />
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </article>
  );
}
