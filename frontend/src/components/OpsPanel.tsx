import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ProviderHealth, ReliabilityReport } from "../api/types";
import { HealthPanel } from "./HealthPanel";
import { Icon } from "./icons";

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

  const okProviders = health?.providers.filter((p) => p.status === "ok").length ?? 0;
  return (
    <>
      <div className="page__head">
        <p className="eyebrow">Operations</p>
        <h1>System health</h1>
        <p>Providers, feeds and the AI layer, with an AI Reliability Copilot summary for on-call.</p>
      </div>
      {health && (
        <dl className="tiles">
          <div className="card tile">
            <dt>Providers</dt>
            <dd>
              <i className={`dot ${okProviders === health.providers.length ? "dot--ok" : "dot--bad"}`} />
              {okProviders}/{health.providers.length} ok
            </dd>
          </div>
          <div className="card tile">
            <dt>Disruption feed</dt>
            <dd>
              <i className={`dot ${health.disruption_feed.status === "ok" ? "dot--ok" : "dot--bad"}`} />
              {health.disruption_feed.active} active
            </dd>
          </div>
          <div className="card tile">
            <dt>Gemini</dt>
            <dd>
              <i className={`dot ${health.ai.gemini_configured ? "dot--ok" : ""}`} />
              {health.ai.gemini_configured ? "Connected" : "Offline mode"}
            </dd>
          </div>
          <div className="card tile">
            <dt>Data</dt>
            <dd>{health.data_mode === "mock" ? "Demo (mock)" : "Live"}</dd>
          </div>
        </dl>
      )}
      <div className="grid2">
        <div>
          <HealthPanel />
          {health && (
            <section className="card" style={{ marginTop: 16 }} aria-labelledby="providers-title">
              <h2 id="providers-title">Providers</h2>
              <ul className="health__deps">
                {health.providers.map((p) => (
                  <li key={p.name} className={`dep dep--${p.status}`}>
                    <span>
                      {p.name} <span className="muted">· {p.covers}</span>
                    </span>
                    <span className="dep__status">{p.status}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
        <section className="card" aria-labelledby="rel-title">
          <h2 id="rel-title">AI Reliability Copilot</h2>
          <p className="muted small">Turns telemetry (hold conflicts, rollbacks, stale feeds, AI errors) into an incident summary.</p>
          <button className="btn" onClick={summarize} disabled={busy}>
            <Icon name="pulse" size={16} /> {busy ? "Summarizing…" : "Summarize incidents"}
          </button>
          {report && (
            <>
              <p style={{ marginTop: 14 }}>
                {report.summary}{" "}
                <span className="muted small">({report.ai_mode === "gemini" ? "Gemini" : "rules"})</span>
              </p>
              <ul className="findings">
                {report.findings.map((f) => (
                  <li key={f.title} className={`finding finding--${f.severity}`}>
                    <strong>{f.title}</strong>: {f.detail} <em className="muted">Fix: {f.suggested_fix}</em>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </>
  );
}
