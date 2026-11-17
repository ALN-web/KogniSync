import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Journey, TripPass } from "./api/types";
import { BookingDialog } from "./components/BookingDialog";
import { Copilot } from "./components/Copilot";
import { Icon } from "./components/icons";
import { OpsPanel } from "./components/OpsPanel";
import { PlanPage } from "./components/PlanPage";
import { TripView } from "./components/TripView";
import { type AppView, Landing } from "./landing/Landing";

type View = "home" | AppView;
const TABS: { id: AppView; label: string; icon: "plan" | "ticket" | "chat" | "pulse" }[] = [
  { id: "plan", label: "Plan", icon: "plan" },
  { id: "trip", label: "My trip", icon: "ticket" },
  { id: "copilot", label: "Copilot", icon: "chat" },
  { id: "ops", label: "Ops", icon: "pulse" },
];
const STORE_KEY = "kognisync.trippass";

/** "#/plan" style routes; anything else (including "#capabilities" anchors) is the landing page. */
export function viewFromHash(hash: string): View {
  const id = hash.startsWith("#/") ? hash.slice(2) : "";
  return TABS.some((t) => t.id === id) ? (id as AppView) : "home";
}

function readStored(): string | null {
  try {
    return localStorage.getItem(STORE_KEY);
  } catch {
    return null;
  }
}

export default function App() {
  const [view, setView] = useState<View>(() => viewFromHash(window.location.hash));
  const [booking, setBooking] = useState<Journey | null>(null);
  const [trippass, setTrippass] = useState<TripPass | null>(null);
  const [apiUp, setApiUp] = useState<boolean | null>(null);

  useEffect(() => {
    const onHash = () => setView(viewFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const id = readStored();
    if (id) api.trippass(id).then(setTrippass, () => undefined);
  }, []);

  useEffect(() => {
    if (view === "home") return;
    api.readiness().then(
      (r) => setApiUp(r.status === "ready"),
      () => setApiUp(false),
    );
  }, [view]);

  function go(next: View) {
    window.location.hash = next === "home" ? "" : `/${next}`;
    setView(next);
    window.scrollTo({ top: 0 });
  }

  function booked(tp: TripPass) {
    setTrippass(tp);
    setBooking(null);
    go("trip");
    try {
      localStorage.setItem(STORE_KEY, tp.id);
    } catch {
      /* storage unavailable: the trip still shows for this session */
    }
  }

  if (view === "home") return <Landing onOpen={go} />;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__inner">
          <button type="button" className="brand" onClick={() => go("home")} aria-label="KogniSync home">
            KOGNISYNC
          </button>
          <nav className="nav" aria-label="Sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                className={`nav__item ${view === t.id ? "nav__item--active" : ""}`}
                aria-current={view === t.id ? "page" : undefined}
                onClick={() => go(t.id)}
              >
                <Icon name={t.icon} size={16} />
                {t.label}
              </button>
            ))}
          </nav>
          <span className="topbar__status" role="status">
            <i className={`dot ${apiUp ? "dot--ok" : apiUp === false ? "dot--bad" : ""}`} />
            <span>{apiUp === null ? "Connecting" : apiUp ? "Live · demo data" : "API offline"}</span>
          </span>
        </div>
      </header>

      <main className="page">
        {view === "plan" && <PlanPage onBook={setBooking} />}
        {view === "trip" && <TripView trippass={trippass} onBook={setBooking} onPlan={() => go("plan")} />}
        {view === "copilot" && <Copilot trippassId={trippass?.id} onReviewJourney={setBooking} />}
        {view === "ops" && <OpsPanel />}
      </main>

      <nav className="bottomnav" aria-label="Sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            aria-current={view === t.id ? "page" : undefined}
            onClick={() => go(t.id)}
          >
            <Icon name={t.icon} size={20} />
            {t.label}
          </button>
        ))}
      </nav>

      {booking && <BookingDialog journey={booking} onBooked={booked} onClose={() => setBooking(null)} />}
    </div>
  );
}
