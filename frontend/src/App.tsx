import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Journey, TripPass } from "./api/types";
import { BookingDialog } from "./components/BookingDialog";
import { Copilot } from "./components/Copilot";
import { OpsPanel } from "./components/OpsPanel";
import { PlanPage } from "./components/PlanPage";
import { TripView } from "./components/TripView";
import { type AppView, Landing } from "./landing/Landing";

type View = "home" | AppView;
const TABS: { id: AppView; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "trip", label: "My trip" },
  { id: "copilot", label: "Copilot" },
  { id: "ops", label: "Ops" },
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

  useEffect(() => {
    const onHash = () => setView(viewFromHash(window.location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const id = readStored();
    if (id) api.trippass(id).then(setTrippass, () => undefined);
  }, []);

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
    <main className="app">
      <header className="top">
        <div>
          <button type="button" className="brand" onClick={() => go("home")} aria-label="KogniSync home">
            KOGNISYNC
          </button>
          <p className="tagline">Door-to-door journeys across flight, train, bus, cab, Rapido, metro and walk.</p>
        </div>
        <nav className="tabs" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${view === t.id ? "tab--active" : ""}`}
              aria-current={view === t.id ? "page" : undefined}
              onClick={() => go(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {view === "plan" && <PlanPage onBook={setBooking} />}
      {view === "trip" &&
        (trippass ? (
          <TripView trippass={trippass} onBook={setBooking} />
        ) : (
          <p className="card muted">No trip booked yet. Plan one and book it to get a TripPass.</p>
        ))}
      {view === "copilot" && <Copilot trippassId={trippass?.id} onReviewJourney={setBooking} />}
      {view === "ops" && <OpsPanel />}

      {booking && <BookingDialog journey={booking} onBooked={booked} onClose={() => setBooking(null)} />}
    </main>
  );
}
