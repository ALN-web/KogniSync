import { useEffect, useState, type FormEvent } from "react";
import { api } from "../api/client";
import { MODES, type Mode, type SearchRequest } from "../api/types";
import { MODE_TEXT } from "../lib/format";

interface Props {
  onSearch: (req: SearchRequest) => void;
  busy?: boolean;
  initial?: Partial<SearchRequest>;
}

// <input type="datetime-local"> gives "2026-11-24T10:00"; the API reads that as IST.
export function SearchForm({ onSearch, busy, initial }: Props) {
  const [origin, setOrigin] = useState(initial?.origin ?? "Udayapalya, Bengaluru");
  const [destination, setDestination] = useState(initial?.destination ?? "Connaught Place");
  const [departAfter, setDepartAfter] = useState("");
  const [arriveBy, setArriveBy] = useState("");
  const [budget, setBudget] = useState("");
  const [prefer, setPrefer] = useState<Mode[]>([]);
  const [avoid, setAvoid] = useState<Mode[]>([]);
  const [places, setPlaces] = useState<string[]>([]);

  useEffect(() => {
    api.places().then((p) => setPlaces(p.places), () => undefined);
  }, []);

  useEffect(() => {
    if (initial?.origin) setOrigin(initial.origin);
    if (initial?.destination) setDestination(initial.destination);
  }, [initial?.origin, initial?.destination]);

  const toggle = (list: Mode[], set: (m: Mode[]) => void, m: Mode) =>
    set(list.includes(m) ? list.filter((x) => x !== m) : [...list, m]);

  function submit(e: FormEvent) {
    e.preventDefault();
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
      <div className="grid2">
        <label>
          From
          <input list="places" value={origin} onChange={(e) => setOrigin(e.target.value)} required />
        </label>
        <label>
          To
          <input list="places" value={destination} onChange={(e) => setDestination(e.target.value)} required />
        </label>
        <label>
          Leave after
          <input type="datetime-local" value={departAfter} onChange={(e) => setDepartAfter(e.target.value)} />
        </label>
        <label>
          Arrive by (hard limit)
          <input type="datetime-local" value={arriveBy} onChange={(e) => setArriveBy(e.target.value)} />
        </label>
        <label>
          Budget, ₹ (hard limit)
          <input
            type="number"
            min={1}
            inputMode="numeric"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            placeholder="No limit"
          />
        </label>
      </div>
      <fieldset className="modes">
        <legend>Prefer</legend>
        {MODES.map((m) => (
          <label key={m} className="toggle">
            <input
              type="checkbox"
              aria-label={`Prefer ${MODE_TEXT[m]}`}
              checked={prefer.includes(m)}
              onChange={() => toggle(prefer, setPrefer, m)}
            />
            {MODE_TEXT[m]}
          </label>
        ))}
      </fieldset>
      <fieldset className="modes">
        <legend>Avoid</legend>
        {MODES.map((m) => (
          <label key={m} className="toggle">
            <input
              type="checkbox"
              aria-label={`Avoid ${MODE_TEXT[m]}`}
              checked={avoid.includes(m)}
              onChange={() => toggle(avoid, setAvoid, m)}
            />
            {MODE_TEXT[m]}
          </label>
        ))}
      </fieldset>
      <button className="btn" type="submit" disabled={busy}>
        {busy ? "Planning…" : "Plan door to door"}
      </button>
    </form>
  );
}
