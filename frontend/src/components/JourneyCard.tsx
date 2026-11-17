import { useState } from "react";
import type { Journey } from "../api/types";
import { LABEL_TEXT, MODE_TEXT, formatDay, formatDuration, formatInr, formatTime } from "../lib/format";
import { ProvenanceBadge } from "./ProvenanceBadge";

interface Props {
  journey: Journey;
  onBook?: (j: Journey) => void;
  bookLabel?: string;
  selected?: boolean;
  onSelect?: (j: Journey) => void;
}

export function JourneyCard({ journey: j, onBook, bookLabel = "Book", selected, onSelect }: Props) {
  const [open, setOpen] = useState(j.labels.includes("recommended"));
  return (
    <article className={`card journey ${selected ? "journey--selected" : ""}`} aria-label={`Journey ${j.id}`}>
      <div className="journey__labels">
        {j.labels.map((l) => (
          <span key={l} className={`chip chip--${l}`}>
            {LABEL_TEXT[l] ?? l}
          </span>
        ))}
      </div>
      <div className="journey__head">
        <div className="journey__times">
          <strong>
            {formatTime(j.depart)} → {formatTime(j.arrive)}
          </strong>
          <span className="muted">
            {formatDay(j.depart)}
            {formatDay(j.depart) !== formatDay(j.arrive) && ` – ${formatDay(j.arrive)}`} ·{" "}
            {formatDuration(j.duration_min)}
          </span>
        </div>
        <div className="journey__cost">
          <strong>{formatInr(j.cost_inr)}</strong> <ProvenanceBadge kind={j.cost_provenance} />
        </div>
      </div>
      <div className="journey__route" aria-label="Route">
        {j.legs.map((leg) => (
          <span key={leg.id} className={`mode mode--${leg.mode}`} title={leg.provider}>
            {MODE_TEXT[leg.mode]}
          </span>
        ))}
      </div>
      <div className="journey__stats muted">
        <span>{j.carbon_kg.toFixed(1)} kg CO₂</span>
        <span>{Math.round(j.reliability * 100)}% on-plan</span>
        <span>
          {j.transfers} transfer{j.transfers === 1 ? "" : "s"}
        </span>
      </div>
      {j.warnings.map((w) => (
        <p key={w} className="warning">
          {w}
        </p>
      ))}
      <div className="journey__actions">
        <button type="button" className="btn btn--ghost" onClick={() => setOpen(!open)} aria-expanded={open}>
          {open ? "Hide details" : "Details"}
        </button>
        {onSelect && (
          <button
            type="button"
            className="btn btn--ghost"
            aria-pressed={selected}
            onClick={() => onSelect(j)}
          >
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
                <span className={`mode mode--${leg.mode}`}>{MODE_TEXT[leg.mode]}</span>
                <div className="leg__body">
                  <div>
                    <strong>{leg.provider}</strong>
                    {leg.seats_available && (
                      <span className="muted">
                        {" "}
                        · {leg.seats_available.value} seats <ProvenanceBadge provenance={leg.seats_available.provenance} />
                      </span>
                    )}
                  </div>
                  <div className="muted">
                    {leg.origin.name} → {leg.destination.name}
                  </div>
                  <div className="leg__facts">
                    <span>
                      {formatTime(leg.depart.value)}–{formatTime(leg.arrive.value)}{" "}
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
