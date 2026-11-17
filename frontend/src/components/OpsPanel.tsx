import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ProviderHealth, ReliabilityReport } from "../api/types";
import { HealthPanel } from "./HealthPanel";

export function OpsPanel() {
  const [health, setHealth] = useState<ProviderHealth | null>(null);
  const [report, setReport] = useState<ReliabilityReport | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.providers().then(setHealth, () => undefined);
  }, []);

  async function summarize() {
    setBusy(true);
    try {
      setReport(await api.reliability());
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ops">
      <HealthPanel />
      {health && (
        <div className="card">
          <h3>Providers ({health.data_mode} data)</h3>
          <ul className="health__deps">
            {health.providers.map((p) => (
              <li key={p.name} className={`dep dep--${p.status}`}>
                <span className="dep__name">
                  {p.name} <span className="muted">· {p.covers}</span>
                </span>
                <span className="dep__status">{p.status}</span>
              </li>
            ))}
            <li className="dep">
              <span className="dep__name">Disruption feed</span>
              <span className="dep__status">
                {health.disruption_feed.status} · {health.disruption_feed.active} active
              </span>
            </li>
          </ul>
        </div>
      )}
      <div className="card">
        <h3>AI Reliability Copilot</h3>
        <button className="btn" onClick={summarize} disabled={busy}>
          {busy ? "Summarizing…" : "Summarize incidents"}
        </button>
        {report && (
          <>
            <p className="summary">
              {report.summary} <span className="muted small">({report.ai_mode === "gemini" ? "Gemini" : "rules"})</span>
            </p>
            <ul className="findings">
              {report.findings.map((f) => (
                <li key={f.title} className={`finding finding--${f.severity}`}>
                  <strong>{f.title}</strong>: {f.detail} <em>Fix: {f.suggested_fix}</em>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
