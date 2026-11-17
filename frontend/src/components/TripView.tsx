import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { DisruptionCreate, Impact, Journey, Recovery, TripPass } from "../api/types";
import { MODE_TEXT, formatDuration, formatInr, formatTime } from "../lib/format";
import { JourneyCard } from "./JourneyCard";

interface Props {
  trippass: TripPass;
  onBook: (j: Journey) => void;
}

const STATUS_TEXT: Record<string, string> = {
  on_time: "On time",
  delayed: "Delayed",
  at_risk: "Tight connection",
  missed_connection: "Connection missed",
  cancelled: "Cancelled",
  needs_replan: "Needs new plan",
};

export function TripView({ trippass: tp, onBook }: Props) {
  const [impact, setImpact] = useState<Impact | null>(null);
  const [recovery, setRecovery] = useState<Recovery | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setImpact(await api.impact(tp.id));
      setRecovery(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [tp.id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const trunk = tp.journey.legs.find((l) => l.bookable);
  const metro = tp.journey.legs.find((l) => l.mode === "metro");

  async function simulate(d: DisruptionCreate | null) {
    setBusy(true);
    try {
      await api.clearDisruptions();
      if (d) await api.addDisruption(d);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function findRecovery() {
    setBusy(true);
    try {
      setRecovery(await api.recovery(tp.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const statusOf = (legId: string) => impact?.legs.find((l) => l.leg_id === legId);

  return (
    <section className="trip">
      <div className="card trippass">
        <div>
          <p className="muted">TripPass</p>
          <h2>{tp.id}</h2>
          <p>
            Paid {formatInr(tp.total_paid_inr)} · pay at travel about {formatInr(tp.pay_later_estimate_inr)} ·{" "}
            {tp.passengers} traveler{tp.passengers > 1 ? "s" : ""}
          </p>
          <ol className="legs">
            {tp.journey.legs.map((leg) => {
              const booked = tp.booked_legs.find((b) => b.leg_id === leg.id);
              const st = statusOf(leg.id);
              return (
                <li key={leg.id} className="leg">
                  <span className={`mode mode--${leg.mode}`}>{MODE_TEXT[leg.mode]}</span>
                  <div className="leg__body">
                    <strong>{leg.provider}</strong>{" "}
                    {booked?.pnr ? <code>PNR {booked.pnr}</code> : <span className="muted">pay at travel</span>}
                    <div className="muted">
                      {formatTime(leg.depart.value)} {leg.origin.name} → {leg.destination.name}
                    </div>
                    {st && st.status !== "on_time" && (
                      <span className={`status status--${st.status}`}>
                        {STATUS_TEXT[st.status]}
                        {st.delay_min > 0 && ` +${formatDuration(st.delay_min)}`}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
        <img className="qr" src={api.qrUrl(tp.id)} alt={`QR code for TripPass ${tp.id}`} width={180} height={180} />
      </div>

      <div className="card">
        <h3>Disruption watch</h3>
        {impact && (
          <p className={`impact impact--${impact.severity}`} role="status">
            {impact.summary}
            {impact.based_on_stale_data && " (based on data older than 30 min)"}
          </p>
        )}
        <p className="muted">Demo: inject a disruption into the mock live feed.</p>
        <div className="row">
          {trunk && (
            <>
              <button
                className="btn btn--ghost"
                disabled={busy}
                onClick={() =>
                  simulate({ kind: "delay", service_id: trunk.service_id!, delay_min: 90, message: "Late inbound" })
                }
              >
                Delay {MODE_TEXT[trunk.mode].toLowerCase()} 90 min
              </button>
              <button
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => simulate({ kind: "cancellation", service_id: trunk.service_id! })}
              >
                Cancel {MODE_TEXT[trunk.mode].toLowerCase()}
              </button>
            </>
          )}
          {metro && (
            <button
              className="btn btn--ghost"
              disabled={busy}
              onClick={() =>
                simulate({ kind: "closure", provider: metro.provider, city: metro.origin.city ?? undefined })
              }
            >
              Close {metro.provider}
            </button>
          )}
          <button className="btn btn--ghost" disabled={busy} onClick={() => simulate(null)}>
            Clear
          </button>
        </div>
        {impact && impact.severity !== "none" && (
          <button className="btn" disabled={busy} onClick={findRecovery}>
            Find recovery options
          </button>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </div>

      {recovery && (
        <div className="recovery">
          <p className="note">{recovery.note}</p>
          {recovery.options.map((j) => (
            <JourneyCard key={j.id} journey={j} onBook={onBook} bookLabel="Review and book" />
          ))}
        </div>
      )}
    </section>
  );
}
