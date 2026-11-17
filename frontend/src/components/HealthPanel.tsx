import { useEffect, useState } from "react";
import { api, type DependencyState, type Liveness, type Readiness } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "loaded"; liveness: Liveness; readiness: Readiness };

const LABELS: Record<DependencyState, string> = {
  ok: "OK",
  error: "Error",
  not_configured: "Not configured",
};

export function HealthPanel() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.liveness(), api.readiness()])
      .then(([liveness, readiness]) => {
        if (!cancelled) setState({ kind: "loaded", liveness, readiness });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state.kind === "loading") {
    return <p role="status">Checking backend…</p>;
  }
  if (state.kind === "error") {
    return (
      <p role="alert" className="health health--down">
        Backend unreachable: {state.message}
      </p>
    );
  }

  const { liveness, readiness } = state;
  return (
    <section className="health" aria-label="System health">
      <p className={`health__summary health--${readiness.status}`}>
        API {liveness.version} ({liveness.environment}): <strong>{readiness.status}</strong>
      </p>
      <ul className="health__deps">
        {readiness.dependencies.map((d) => (
          <li key={d.name} className={`dep dep--${d.status}`}>
            <span className="dep__name">{d.name}</span>
            <span className="dep__status">{LABELS[d.status]}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
