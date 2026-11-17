import { useState } from "react";
import { api } from "../api/client";
import type { Journey, SearchRequest, SearchResponse } from "../api/types";
import { JourneyCard } from "./JourneyCard";
import { SearchForm } from "./SearchForm";

const REASONS: Record<string, string> = {
  over_budget: "over budget",
  misses_deadline: "miss the deadline",
  avoided_mode: "use an avoided mode",
  too_many_transfers: "too many transfers",
};

export function PlanPage({ onBook }: { onBook: (j: Journey) => void }) {
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search(req: SearchRequest) {
    setBusy(true);
    setError(null);
    try {
      setResult(await api.search(req));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const rejected = result
    ? Object.entries(result.rejected)
        .map(([k, n]) => `${n} ${REASONS[k] ?? k}`)
        .join(", ")
    : "";

  return (
    <section className="plan">
      <SearchForm onSearch={search} busy={busy} />
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {result && (
        <div className="results">
          <p className="muted">
            {result.origin.name} → {result.destination.name}: {result.considered} door-to-door options checked,{" "}
            {result.pareto_size} on the Pareto front
            {rejected && `, ${rejected} (hard limits are never relaxed)`}.
          </p>
          {result.data_mode === "mock" && (
            <p className="note">Demo data from mock providers. Labels show what each value would be: live, scheduled or estimated.</p>
          )}
          {result.relaxation_hints.map((h) => (
            <p key={h} className="warning" role="status">
              {h}
            </p>
          ))}
          {result.journeys.map((j) => (
            <JourneyCard key={j.id} journey={j} onBook={onBook} />
          ))}
        </div>
      )}
    </section>
  );
}
