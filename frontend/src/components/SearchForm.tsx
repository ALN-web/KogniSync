import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { MODES, type Mode, type SearchRequest } from "../api/types";
import { MODE_TEXT } from "../lib/format";
import { Icon } from "./icons";

interface Props {
  onSearch: (req: SearchRequest) => void;
  busy?: boolean;
}

const EXAMPLES: { label: string; origin: string; destination: string }[] = [
  { label: "Udayapalya → Connaught Place", origin: "Udayapalya, Bengaluru", destination: "Connaught Place" },
  { label: "Koramangala → Whitefield", origin: "Koramangala", destination: "Whitefield" },
  { label: "Andheri → HITEC City", origin: "Andheri", destination: "HITEC City" },
  { label: "Bengaluru → Chennai", origin: "Bengaluru", destination: "Chennai" },
];

// <input type="datetime-local"> gives "2026-11-24T10:00"; the API reads that as IST.
export function SearchForm({ onSearch, busy }: Props) {
  const [origin, setOrigin] = useState("Udayapalya, Bengaluru");
  const [destination, setDestination] = useState("Connaught Place");
  const [departAfter, setDepartAfter] = useState("");
  const [arriveBy, setArriveBy] = useState("");
  const [budget, setBudget] = useState("");
  const [prefer, setPrefer] = useState<Mode[]>([]);
  const [avoid, setAvoid] = useState<Mode[]>([]);
  const [places, setPlaces] = useState<string[]>([]);

  useEffect(() => {
    api.places().then((p) => setPlaces(p.places), () => undefined);
  }, []);

  // A mode can't be both preferred and avoided: choosing one clears the other.
  function toggle(kind: "prefer" | "avoid", m: Mode) {
    const [list, set, other, setOther] =
      kind === "prefer" ? [prefer, setPrefer, avoid, setAvoid] : [avoid, setAvoid, prefer, setPrefer];
    set(list.includes(m) ? list.filter((x) => x !== m) : [...list, m]);
    if (other.includes(m)) setOther(other.filter((x) => x !== m));
  }

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const req: SearchRequest = { origin: origin.trim(), destination: destination.trim() };
    if (departAfter) req.depart_after = departAfter;
    if (arriveBy) req.arrive_by = arriveBy;
    if (budget) req.budget_inr = Number(budget);
    if (prefer.length) req.prefer_modes = prefer;
    if (avoid.length) req.avoid_modes = avoid;
    onSearch(req);
  }

  return (
    <form className="card search" onSubmit={submit} aria-label="Plan a journey">
      <datalist id="places">
        {places.map((p) => (
          <option key={p} value={p} />
        ))}
      </datalist>
      <div className="search__route">
        <label className="field">
          From
          <input list="places" value={origin} onChange={(e) => setOrigin(e.target.value)} required autoComplete="off" />
        </label>
        <button
          type="button"
          className="iconbtn"
          aria-label="Swap start and destination"
          onClick={() => {
            setOrigin(destination);
            setDestination(origin);
          }}
        >
          <Icon name="swap" />
        </button>
        <label className="field">
          To
          <input
            list="places"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            required
            autoComplete="off"
          />
        </label>
      </div>

      <div className="search__grid">
        <label className="field">
          Leave after
          <input type="datetime-local" value={departAfter} onChange={(e) => setDepartAfter(e.target.value)} />
        </label>
        <label className="field">
          Arrive by (hard limit)
          <input type="datetime-local" value={arriveBy} onChange={(e) => setArriveBy(e.target.value)} />
        </label>
        <label className="field">
          Budget, ₹ (hard limit)
          <span className="prefix">
            <span aria-hidden="true">₹</span>
            <input
              type="number"
              min={1}
              step={1}
              inputMode="numeric"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              placeholder="No limit"
              aria-label="Budget, ₹ (hard limit)"
            />
          </span>
        </label>
      </div>

      <div className="search__modes">
        <div className="row" role="group" aria-label="Preferred modes">
          <span>Prefer</span>
          {MODES.map((m) => (
            <button
              key={m}
              type="button"
              className="toggle-chip"
              aria-pressed={prefer.includes(m)}
              aria-label={`Prefer ${MODE_TEXT[m]}`}
              onClick={() => toggle("prefer", m)}
            >
              <Icon name={m} size={15} />
              {MODE_TEXT[m]}
            </button>
          ))}
        </div>
        <div className="row" role="group" aria-label="Modes to avoid">
          <span>Avoid</span>
          {MODES.map((m) => (
            <button
              key={m}
              type="button"
              className="toggle-chip toggle-chip--avoid"
              aria-pressed={avoid.includes(m)}
              aria-label={`Avoid ${MODE_TEXT[m]}`}
              onClick={() => toggle("avoid", m)}
            >
              <Icon name={m} size={15} />
              {MODE_TEXT[m]}
            </button>
          ))}
        </div>
      </div>

      <div className="search__foot">
        <div className="suggestions" aria-label="Example trips">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              type="button"
              className="suggestion"
              onClick={() => {
                setOrigin(ex.origin);
                setDestination(ex.destination);
              }}
            >
              {ex.label}
            </button>
          ))}
        </div>
        <button className="btn btn--lg" type="submit" disabled={busy}>
          {busy ? "Planning…" : "Plan door to door"} <Icon name="arrow" size={16} />
        </button>
      </div>
    </form>
  );
}
