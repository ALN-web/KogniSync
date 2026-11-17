import { useRef, useState } from "react";
import { api, newIdempotencyKey } from "../api/client";
import type { Hold, Journey, TripPass } from "../api/types";
import { MODE_TEXT, formatInr, formatTime } from "../lib/format";
import { ProvenanceBadge } from "./ProvenanceBadge";

interface Props {
  journey: Journey;
  onBooked: (tp: TripPass) => void;
  onClose: () => void;
}

type Step = "review" | "held" | "done";

/**
 * Two explicit consents: one to hold seats, one to pay the exact held total.
 * Each step keeps one Idempotency-Key, so a retry after a network error can never hold or
 * charge twice.
 */
export function BookingDialog({ journey, onBooked, onClose }: Props) {
  const [step, setStep] = useState<Step>("review");
  const [hold, setHold] = useState<Hold | null>(null);
  const [agreeHold, setAgreeHold] = useState(false);
  const [agreePay, setAgreePay] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const holdKey = useRef(newIdempotencyKey());
  const payKey = useRef(newIdempotencyKey());

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const doHold = () =>
    run(async () => {
      setHold(await api.hold(journey.id, holdKey.current));
      setStep("held");
    });

  const doConfirm = () =>
    run(async () => {
      if (!hold) return;
      const tp = await api.confirm(hold.id, hold.total_due_now_inr, payKey.current);
      setStep("done");
      onBooked(tp);
    });

  const cancel = async () => {
    if (hold && step === "held") await api.releaseHold(hold.id).catch(() => undefined);
    onClose();
  };

  const bookable = journey.legs.filter((l) => l.bookable);
  return (
    <div className="dialog-backdrop" role="presentation">
      <div className="dialog card" role="dialog" aria-modal="true" aria-label="Book journey">
        <h2>{step === "review" ? "Review and hold" : "Confirm booking"}</h2>
        <ul className="plain">
          {journey.legs.map((leg) => (
            <li key={leg.id}>
              <span className={`mode mode--${leg.mode}`}>{MODE_TEXT[leg.mode]}</span> {leg.provider} ·{" "}
              {formatTime(leg.depart.value)} · {leg.fare_inr.value ? formatInr(leg.fare_inr.value) : "Free"}{" "}
              <ProvenanceBadge provenance={leg.fare_inr.provenance} />
              <span className="muted"> {leg.bookable ? "· booked now" : "· pay at travel"}</span>
            </li>
          ))}
        </ul>

        {step === "review" && (
          <>
            <p className="muted">
              {bookable.length
                ? `KogniSync will hold ${bookable.length} seat booking(s) for 10 minutes. Nothing is charged yet.`
                : "This trip has no legs to pre-book; you pay each leg when you travel."}
            </p>
            <label className="consent">
              <input type="checkbox" checked={agreeHold} onChange={(e) => setAgreeHold(e.target.checked)} />I want
              to hold these seats
            </label>
            <div className="dialog__actions">
              <button className="btn btn--ghost" type="button" onClick={cancel}>
                Cancel
              </button>
              <button className="btn" type="button" disabled={!agreeHold || busy} onClick={doHold}>
                {busy ? "Holding…" : "Hold seats"}
              </button>
            </div>
          </>
        )}

        {step === "held" && hold && (
          <>
            <p>
              Pay now: <strong>{formatInr(hold.total_due_now_inr)}</strong>
              <br />
              <span className="muted">
                Pay at travel (estimated): {formatInr(hold.pay_later_estimate_inr)} · Hold expires{" "}
                {formatTime(hold.expires_at)}
              </span>
            </p>
            <label className="consent">
              <input type="checkbox" checked={agreePay} onChange={(e) => setAgreePay(e.target.checked)} />I agree to
              pay {formatInr(hold.total_due_now_inr)} now (demo: no real payment)
            </label>
            <div className="dialog__actions">
              <button className="btn btn--ghost" type="button" onClick={cancel}>
                Release hold
              </button>
              <button className="btn" type="button" disabled={!agreePay || busy} onClick={doConfirm}>
                {busy ? "Booking…" : `Confirm and pay ${formatInr(hold.total_due_now_inr)}`}
              </button>
            </div>
          </>
        )}
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}
