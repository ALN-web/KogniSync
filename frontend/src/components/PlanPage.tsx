import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { Journey, SearchRequest, SearchResponse } from "../api/types";
import { Icon } from "./icons";
import { JourneyCard } from "./JourneyCard";
import { JourneyGlobe } from "./JourneyGlobe";
import { SearchForm } from "./SearchForm";

const REASONS: Record<string, string> = {
  over_budget: "over budget",
  misses_deadline: "miss the deadline",
  avoided_mode: "use an avoided mode",
  too_many_transfers: "too many transfers",
};

type Sort = "recommended" | "fastest" | "cheapest" | "greenest";
const SORTS: { id: Sort; label: string; by: (a: Journey, b: Journey) => number }[] = [
  { id: "recommended", label: "Best", by: (a, b) => a.score - b.score },
  { id: "fastest", label: "Fastest", by: (a, b) => a.duration_min - b.duration_min },
  { id: "cheapest", label: "Cheapest", by: (a, b) => a.cost_inr - b.cost_inr },
  { id: "greenest", label: "Greenest", by: (a, b) => a.carbon_kg - b.carbon_kg },
];

export function PlanPage({ onBook }: { onBook: (j: Journey) => void }) {
  const [result, setResult] = useState<SearchResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [sort, setSort] = useState<Sort>("recommended");

  async function search(req: SearchRequest) {
    setBusy(true);
    setError(null);
    try {
      const res = await api.search(req);
      setResult(res);
      setSort("recommended");
      setSelectedId((res.journeys.find((j) => j.labels.includes("recommended")) ?? res.journeys[0])?.id ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const journeys = useMemo(
    () => [...(result?.journeys ?? [])].sort(SORTS.find((s) => s.id === sort)!.by),
    [result, sort],
  );
  const selected = result?.journeys.find((j) => j.id === selectedId) ?? null;
  const rejected = result
    ? Object.entries(result.rejected)
        .map(([k, n]) => `${n} ${REASONS[k] ?? k}`)
        .join(", ")
    : "";

  return (
    <>
      <div className="page__head">
        <p className="eyebrow">Plan · door to door</p>
        <h1>Where to?</h1>
        <p>Every leg from your door to theirs, ranked on time, cost, carbon and reliability.</p>
      </div>
      <div className="split">
        <div>
          <SearchForm onSearch={search} busy={busy} />
          {error && (
            <div className="alert alert--bad" role="alert">
              <Icon name="alert" />
              <p>{error}</p>
            </div>
          )}
          {busy && (
            <div aria-label="Loading results" role="status">
              <div className="skeleton" />
              <div className="skeleton" />
              <div className="skeleton" />
            </div>
          )}
          {!busy && result && (
            <section aria-label="Results">
              <div className="results__bar">
                <p className="muted">
                  {result.origin.name} → {result.destination.name} · {result.considered} options checked,{" "}
                  {result.pareto_size} on the Pareto front
                  {rejected && ` · ${rejected} (hard limits never relaxed)`}
                </p>
                {journeys.length > 1 && (
                  <div className="tabs-sort" role="group" aria-label="Sort results">
                    {SORTS.map((s) => (
                      <button key={s.id} type="button" aria-pressed={sort === s.id} onClick={() => setSort(s.id)}>
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {result.data_mode === "mock" && (
                <div className="alert alert--info">
                  <Icon name="shield" />
                  <p>Demo data from mock providers. Badges show what each value would be: live, scheduled or estimated.</p>
                </div>
              )}
              {result.relaxation_hints.map((h) => (
                <div key={h} className="alert alert--warn" role="status">
                  <Icon name="alert" />
                  <p>{h}</p>
                </div>
              ))}
              {journeys.map((j) => (
                <JourneyCard
                  key={j.id}
                  journey={j}
                  onBook={onBook}
                  selected={j.id === selectedId}
                  onSelect={(sel) => setSelectedId(sel.id)}
                />
              ))}
            </section>
          )}
        </div>
        <aside className="split__aside" aria-label="Route on the globe">
          <JourneyGlobe journey={selected} height={520} />
        </aside>
      </div>
    </>
  );
}
