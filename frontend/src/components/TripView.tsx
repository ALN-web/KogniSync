import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { DisruptionCreate, Impact, Journey, Recovery, TripPass } from "../api/types";
import { MODE_TEXT, formatDay, formatDuration, formatInr, formatTime } from "../lib/format";
import { Icon } from "./icons";
import { JourneyCard } from "./JourneyCard";
import { JourneyGlobe } from "./JourneyGlobe";

interface Props {
  trippass: TripPass | null;
  onBook: (j: Journey) => void;
  onPlan?: () => void;
}

const STATUS_TEXT: Record<string, string> = {
  on_time: "On time",
  delayed: "Delayed",
  at_risk: "Tight connection",
  missed_connection: "Connection missed",
  cancelled: "Cancelled",
  needs_replan: "Needs new plan",
};

const SEVERITY_ALERT: Record<Impact["severity"], string> = {
  none: "alert--ok",
  minor: "alert--warn",
  major: "alert--warn",
  critical: "alert--bad",
};

export function TripView({ trippass, onBook, onPlan }: Props) {
  if (!trippass) {
    return (
      <div className="card" style={{ textAlign: "center", padding: "48px 20px" }}>
        <p className="eyebrow">My trip</p>
        <h1 style={{ fontSize: 28, fontWeight: 300, marginBottom: 8 }}>No trip booked yet</h1>
        <p className="muted">Plan a journey and book it to get a TripPass with QR code and live disruption watch.</p>
        {onPlan && (
          <button className="btn btn--lg" type="button" onClick={onPlan} style={{ marginTop: 12 }}>
            Plan a journey <Icon name="arrow" size={16} />
          </button>
        )}
      </div>
    );
  }
  return <BookedTrip tp={trippass} onBook={onBook} />;
}

function BookedTrip({ tp, onBook }: { tp: TripPass; onBook: (j: Journey) => void }) {
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

  const legs = tp.journey.legs;
  const trunk = legs.find((l) => l.bookable);
  const metro = legs.find((l) => l.mode === "metro");
  const first = legs[0];
  const last = legs[legs.length - 1];

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
  const statuses = useMemo(
    () => Object.fromEntries((impact?.legs ?? []).map((l) => [l.leg_id, l.status])),
    [impact],
  );

  return (
    <>
      <div className="page__head">
        <p className="eyebrow">My trip</p>
        <h1>Your TripPass</h1>
      </div>
      <div className="split">
        <div>
          <article className="pass" aria-label={`TripPass ${tp.id}`}>
            <div className="pass__main">
              <p className="eyebrow">TripPass · {tp.id}</p>
              <div className="pass__route">
                {first.origin.name} <Icon name="arrow" size={22} /> {last.destination.name}
              </div>
              <dl className="pass__facts">
                <div>
                  <dt>Departs</dt>
                  <dd>
                    {formatDay(tp.journey.depart)} {formatTime(tp.journey.depart)}
                  </dd>
                </div>
                <div>
                  <dt>Arrives</dt>
                  <dd>
                    {formatDay(tp.journey.arrive)} {formatTime(tp.journey.arrive)}
                  </dd>
                </div>
                <div>
                  <dt>Travelers</dt>
                  <dd>{tp.passengers}</dd>
                </div>
                <div>
                  <dt>Paid</dt>
                  <dd>{formatInr(tp.total_paid_inr)}</dd>
                </div>
                <div>
                  <dt>At travel (est.)</dt>
                  <dd>{formatInr(tp.pay_later_estimate_inr)}</dd>
                </div>
              </dl>
            </div>
            <div className="pass__stub">
              <img className="qr" src={api.qrUrl(tp.id)} alt={`QR code for TripPass ${tp.id}`} width={156} height={156} />
              <span className="muted small">Show at boarding</span>
            </div>
          </article>

          <section className="card" aria-labelledby="watch-title">
            <h2 id="watch-title">Disruption watch</h2>
            {impact && (
              <div className={`alert ${SEVERITY_ALERT[impact.severity]}`} role="status">
                <Icon name={impact.severity === "none" ? "check" : "alert"} />
                <p>
                  {impact.summary}
                  {impact.based_on_stale_data && " (based on data older than 30 min)"}
                </p>
              </div>
            )}
            {impact && impact.severity !== "none" && (
              <button className="btn" disabled={busy} onClick={findRecovery}>
                Find recovery options
              </button>
            )}

            <ol className="legs" style={{ marginTop: 16 }}>
              {legs.map((leg) => {
                const booked = tp.booked_legs.find((b) => b.leg_id === leg.id);
                const st = statusOf(leg.id);
                const ok = !st || st.status === "on_time";
                return (
                  <li key={leg.id} className="leg">
                    <span className={`mode mode--${leg.mode}`}>
                      <Icon name={leg.mode} size={16} title={MODE_TEXT[leg.mode]} />
                    </span>
                    <div className="leg__body">
                      <div className="leg__title">
                        <strong>{leg.provider}</strong>
                        {booked?.pnr ? <span className="pnr">PNR {booked.pnr}</span> : <span className="muted small">pay at travel</span>}
                        <span className={`status ${ok ? "status--ok" : `status--${st!.status}`}`}>
                          {STATUS_TEXT[st?.status ?? "on_time"]}
                          {st && st.delay_min > 0 && ` +${formatDuration(st.delay_min)}`}
                        </span>
                      </div>
                      <div className="leg__place">
                        {formatTime(leg.depart.value)} · {leg.origin.name} → {leg.destination.name}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>

            <details className="demo" open>
              <summary>Demo: simulate a disruption in the mock live feed</summary>
              <div className="row" style={{ marginTop: 10 }}>
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
                    onClick={() => simulate({ kind: "closure", provider: metro.provider, city: metro.origin.city ?? undefined })}
                  >
                    Close {metro.provider}
                  </button>
                )}
                <button className="btn btn--quiet" disabled={busy} onClick={() => simulate(null)}>
                  Clear
                </button>
              </div>
            </details>
            {error && (
              <div role="alert" className="alert alert--bad">
                <Icon name="alert" />
                <p>{error}</p>
              </div>
            )}
          </section>

          {recovery && (
            <section aria-label="Recovery options" style={{ marginTop: 16 }}>
              <div className="alert alert--info">
                <Icon name="shield" />
                <p>{recovery.note}</p>
              </div>
              {recovery.options.map((j) => (
                <JourneyCard key={j.id} journey={j} onBook={onBook} bookLabel="Review and book" />
              ))}
            </section>
          )}
        </div>
        <aside className="split__aside" aria-label="Trip on the globe">
          <JourneyGlobe journey={tp.journey} statuses={statuses} height={460} />
        </aside>
      </div>
    </>
  );
}
