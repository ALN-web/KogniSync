import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { api, newIdempotencyKey } from "../api/client";
import type { Hold, Journey, TripPass } from "../api/types";
import { MODE_TEXT, formatInr, formatTime } from "../lib/format";
import { Icon } from "./icons";
import { ProvenanceBadge } from "./ProvenanceBadge";

interface Props {
  journey: Journey;
  onBooked: (tp: TripPass) => void;
  onClose: () => void;
}

type Step = "review" | "held" | "done";
const STEPS = ["Review", "Hold seats", "Pay", "TripPass"];

function useCountdown(until: string | undefined): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!until) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [until]);
  if (!until) return null;
  const left = Math.max(0, Math.floor((new Date(until).getTime() - now) / 1000));
  return `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`;
}

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
  const dialogRef = useRef<HTMLDivElement>(null);
  const countdown = useCountdown(step === "held" ? hold?.expires_at : undefined);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialogRef.current?.querySelector<HTMLElement>("input, button")?.focus();
    return () => previous?.focus?.();
  }, []);

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

  const cancel = useCallback(async () => {
    if (hold && step === "held") await api.releaseHold(hold.id).catch(() => undefined);
    onClose();
  }, [hold, step, onClose]);

  // Escape closes; Tab stays inside the dialog.
  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      cancel();
      return;
    }
    if (e.key !== "Tab" || !dialogRef.current) return;
    const items = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not(:disabled), input")];
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  const current = step === "review" ? 0 : step === "held" ? 2 : 3;
  const bookable = journey.legs.filter((l) => l.bookable);
  const first = journey.legs[0];
  const last = journey.legs[journey.legs.length - 1];

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && cancel()}>
      <div
        ref={dialogRef}
        className="dialog card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-title"
        onKeyDown={onKeyDown}
      >
        <div className="dialog__head">
          <div>
            <p className="eyebrow">
              {first.origin.name} → {last.destination.name}
            </p>
            <h2 id="booking-title">{step === "review" ? "Review and hold" : "Confirm booking"}</h2>
          </div>
          <button type="button" className="iconbtn" aria-label="Close" onClick={cancel}>
            <Icon name="close" size={16} />
          </button>
        </div>

        <ol className="steps" aria-label="Booking steps">
          {STEPS.map((s, i) => (
            <li
              key={s}
              data-state={i < current ? "done" : i === current ? "current" : "todo"}
              aria-current={i === current ? "step" : undefined}
            >
              {s}
            </li>
          ))}
        </ol>

        <ul className="summary" aria-label="Legs">
          {journey.legs.map((leg) => (
            <li key={leg.id}>
              <span className={`mode mode--${leg.mode}`}>
                <Icon name={leg.mode} size={14} title={MODE_TEXT[leg.mode]} />
              </span>
              <span>
                {leg.provider}
                <span className="muted small"> · {formatTime(leg.depart.value)}</span>
              </span>
              <span className="summary__price">
                <span>
                  {leg.fare_inr.value ? formatInr(leg.fare_inr.value) : "Free"}{" "}
                  <ProvenanceBadge provenance={leg.fare_inr.provenance} />
                </span>
                <span className="muted small">{leg.bookable ? "booked now" : "pay at travel"}</span>
              </span>
            </li>
          ))}
        </ul>

        {step === "review" && (
          <>
            <p className="muted small">
              {bookable.length
                ? `We'll hold ${bookable.length} booking(s) for 10 minutes. Nothing is charged yet.`
                : "No legs need booking ahead; you pay each one as you travel."}
            </p>
            <label className="consent">
              <input type="checkbox" checked={agreeHold} onChange={(e) => setAgreeHold(e.target.checked)} />
              <span>I want to hold these seats</span>
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
            <dl className="totals">
              <dt>Pay now</dt>
              <dd>
                <strong>{formatInr(hold.total_due_now_inr)}</strong>
              </dd>
              <dt className="muted">Pay at travel (estimated)</dt>
              <dd className="muted">{formatInr(hold.pay_later_estimate_inr)}</dd>
              <dt className="muted">Seats held for</dt>
              <dd className="countdown" aria-live="off">
                {countdown}
              </dd>
            </dl>
            <label className="consent">
              <input type="checkbox" checked={agreePay} onChange={(e) => setAgreePay(e.target.checked)} />
              <span>I agree to pay {formatInr(hold.total_due_now_inr)} now (demo: no real payment)</span>
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
          <div role="alert" className="alert alert--bad">
            <Icon name="alert" />
            <p>{error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
