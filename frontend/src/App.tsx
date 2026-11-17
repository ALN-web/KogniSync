import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { Journey, TripPass } from "./api/types";
import { BookingDialog } from "./components/BookingDialog";
import { Copilot } from "./components/Copilot";
import { OpsPanel } from "./components/OpsPanel";
import { PlanPage } from "./components/PlanPage";
import { TripView } from "./components/TripView";

type Tab = "plan" | "trip" | "copilot" | "ops";
const TABS: { id: Tab; label: string }[] = [
  { id: "plan", label: "Plan" },
  { id: "trip", label: "My trip" },
  { id: "copilot", label: "Copilot" },
  { id: "ops", label: "Ops" },
];
const STORE_KEY = "kognisync.trippass";

function readStored(): string | null {
  try {
    return localStorage.getItem(STORE_KEY);
  } catch {
    return null;
  }
}

export default function App() {
  const [tab, setTab] = useState<Tab>("plan");
  const [booking, setBooking] = useState<Journey | null>(null);
  const [trippass, setTrippass] = useState<TripPass | null>(null);

  useEffect(() => {
    const id = readStored();
    if (id) api.trippass(id).then(setTrippass, () => undefined);
  }, []);

  function booked(tp: TripPass) {
    setTrippass(tp);
    setBooking(null);
    setTab("trip");
    try {
      localStorage.setItem(STORE_KEY, tp.id);
    } catch {
      /* storage unavailable: the trip still shows for this session */
    }
  }

  return (
    <main className="app">
      <header className="top">
        <div>
          <h1>KogniSync</h1>
          <p className="tagline">Door-to-door journeys across flight, train, bus, cab, Rapido, metro and walk.</p>
        </div>
        <nav className="tabs" aria-label="Sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`tab ${tab === t.id ? "tab--active" : ""}`}
              aria-current={tab === t.id ? "page" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      {tab === "plan" && <PlanPage onBook={setBooking} />}
      {tab === "trip" &&
        (trippass ? (
          <TripView trippass={trippass} onBook={setBooking} />
        ) : (
          <p className="card muted">No trip booked yet. Plan one and book it to get a TripPass.</p>
        ))}
      {tab === "copilot" && <Copilot trippassId={trippass?.id} onReviewJourney={setBooking} />}
      {tab === "ops" && <OpsPanel />}

      {booking && <BookingDialog journey={booking} onBooked={booked} onClose={() => setBooking(null)} />}
    </main>
  );
}
