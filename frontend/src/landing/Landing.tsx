import type { ReactNode } from "react";
import "./landing.css";
import {
  BookArt,
  ConverseArt,
  OptimizeArt,
  OrchestrateArt,
  ProtectArt,
  TrustArt,
} from "./Illustrations";
import { ThreeCanvas } from "./ThreeCanvas";

export type AppView = "plan" | "trip" | "copilot" | "ops";

interface Props {
  onOpen: (view: AppView) => void;
}

const loadHero = () => import("./scenes").then((m) => m.createHero);
const loadPin = () => import("./scenes").then((m) => m.createPin);

const REPO = "https://github.com/ALN-web/KogniSync";

interface Capability {
  n: string;
  dot: "orange" | "steel" | "lime";
  title: string;
  body: string;
  tag: string;
  art: ReactNode;
  view: AppView;
}

const CAPABILITIES: Capability[] = [
  {
    n: "01", dot: "orange", title: "Orchestrate", view: "plan", tag: "7 modes · 14 hubs", art: <OrchestrateArt />,
    body: "Door to door across flight, train, bus, cab, Rapido, metro and walk. Real transfer buffers, not guesses.",
  },
  {
    n: "02", dot: "steel", title: "Optimize", view: "plan", tag: "Pareto front", art: <OptimizeArt />,
    body: "Ranked on time, cost, carbon and reliability. Your budget and deadline are never quietly relaxed.",
  },
  {
    n: "03", dot: "lime", title: "Trust", view: "plan", tag: "Provenance", art: <TrustArt />,
    body: "Every fare, time and seat is labeled live, scheduled or estimated, so you know what is real.",
  },
  {
    n: "04", dot: "orange", title: "Book safely", view: "plan", tag: "Holds + TripPass", art: <BookArt />,
    body: "Idempotent multi-vendor holds and a booking saga. No double charges, no half-booked trips.",
  },
  {
    n: "05", dot: "steel", title: "Protect", view: "trip", tag: "Cascade impact", art: <ProtectArt />,
    body: "A delay is traced through every later leg, with recovery options you approve. Never auto-rebooked.",
  },
  {
    n: "06", dot: "lime", title: "Converse", view: "copilot", tag: "Gemini API + Omni", art: <ConverseArt />,
    body: "Ask by text, voice or photo, in English, Hindi, Kannada, Tamil or Telugu.",
  },
];

const Arrow = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
    <path d="M1 7h11M8 3l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);

export function Landing({ onOpen }: Props) {
  return (
    <div className="landing">
      <header className="l-nav">
        <a className="l-logo" href="#" aria-label="KogniSync home">
          KOGNISYNC
        </a>
        <nav className="l-links" aria-label="Page sections">
          <a href="#capabilities">Capabilities</a>
          <a href="#ai">Gemini</a>
          <a href="#cloud">Google Cloud</a>
          <button type="button" onClick={() => onOpen("copilot")}>
            Copilot
          </button>
        </nav>
        <button type="button" className="l-btn l-btn--orange l-btn--sm" onClick={() => onOpen("plan")}>
          Plan a trip <Arrow />
        </button>
      </header>

      <section className="l-hero" aria-labelledby="hero-title">
        <ThreeCanvas
          load={loadHero}
          className="l-hero__scene"
          label="A brushed-metal globe with glowing orange routes between Indian cities, circled by a toothed steel ring"
        />
        <div className="l-hero__copy">
          <p className="l-eyebrow">
            Door-to-door journey copilot / India 2026 <span className="l-rule" />
          </p>
          <h1 id="hero-title">
            Every leg.
            <br />
            One journey.
          </h1>
          <p className="l-lede">
            KogniSync plans, books and protects your whole trip across flights, trains, buses, cabs, Rapido, metro and
            walking, in one itinerary you can trust.
          </p>
          <div className="l-actions">
            <button type="button" className="l-btn l-btn--orange" onClick={() => onOpen("plan")}>
              Plan your journey <Arrow />
            </button>
            <span className="l-divider" />
            <button type="button" className="l-link" onClick={() => onOpen("copilot")}>
              Ask the copilot <Arrow />
            </button>
          </div>
          <dl className="l-stats">
            <div>
              <dt>7 modes</dt>
              <dd>Flight to walk</dd>
            </div>
            <div>
              <dt>14 hubs</dt>
              <dd>Indian metro cities</dd>
            </div>
            <div>
              <dt>0 auto-rebooks</dt>
              <dd>Consent first</dd>
            </div>
          </dl>
        </div>
      </section>

      <section id="capabilities" className="l-section" aria-labelledby="cap-title">
        <div className="l-section__head">
          <div>
            <p className="l-eyebrow">
              What KogniSync does <span className="l-rule" />
            </p>
            <h2 id="cap-title">One itinerary. Complete control.</h2>
            <p className="l-sub">From your front door to theirs, every leg is planned, labeled, booked and watched in one place.</p>
          </div>
          <p className="l-side">
            Plan
            <br />
            Protect
            <br />
            Book
          </p>
        </div>
        <ol className="l-cards" aria-label="Capabilities">
          {CAPABILITIES.map((c) => (
            <li key={c.n} className="l-card">
              <div className="l-card__num">
                <i className={`l-dot l-dot--${c.dot}`} />
                {c.n}
                <span className="l-rule" />
              </div>
              <div className="l-card__art">{c.art}</div>
              <h3>{c.title}</h3>
              <p>{c.body}</p>
              <div className="l-card__foot">
                <span className="l-tag">{c.tag}</span>
                <button type="button" className="l-icon" aria-label={`Open ${c.title}`} onClick={() => onOpen(c.view)}>
                  <Arrow />
                </button>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section id="ai" className="l-section l-ai" aria-labelledby="ai-title">
        <p className="l-eyebrow">
          AI that explains, services that decide <span className="l-rule" />
        </p>
        <h2 id="ai-title">Gemini orchestrates. Deterministic services own every price.</h2>
        <div className="l-columns">
          <div>
            <h3>Gemini API</h3>
            <ul>
              <li>Function calling into journey search, disruptions and holds</li>
              <li>Structured JSON: free text to validated trip limits</li>
              <li>Grounded answers with provenance labels</li>
              <li>AI Reliability Copilot for the ops team</li>
            </ul>
          </div>
          <div>
            <h3>Gemini Omni</h3>
            <ul>
              <li>Voice in Hindi, Kannada, Tamil, Telugu and English</li>
              <li>Reads tickets, PNR screenshots and departure boards</li>
              <li>Hands-free updates when a leg is disrupted</li>
            </ul>
          </div>
          <div>
            <h3>Guardrails</h3>
            <ul>
              <li>Any price no tool returned is removed from the answer</li>
              <li>Nothing is held or booked without your consent</li>
              <li>Works offline with a rule-based planner if AI is down</li>
            </ul>
          </div>
        </div>
      </section>

      <section id="cloud" className="l-section l-cloud" aria-label="Built on Google Cloud">
        <p className="l-eyebrow">
          Built on Google Cloud · asia-south1 <span className="l-rule" />
        </p>
        <ul className="l-chips">
          {["Cloud Run", "Cloud SQL", "Memorystore", "Secret Manager", "Firebase Hosting", "Cloud Build", "Gemini API"].map(
            (c) => (
              <li key={c}>{c}</li>
            ),
          )}
        </ul>
      </section>

      <section className="l-cta" aria-labelledby="cta-title">
        <div className="l-cta__copy">
          <p className="l-eyebrow l-eyebrow--dark">
            Let's go door to door <span className="l-rule" />
          </p>
          <h2 id="cta-title">
            Plan the trip
            <br />
            others can't.
          </h2>
          <p>Tell us where, when and your budget. We'll find the route, book it safely and watch it until you arrive.</p>
          <div className="l-actions">
            <button type="button" className="l-btn l-btn--dark" onClick={() => onOpen("plan")}>
              Start planning <Arrow />
            </button>
            <span className="l-note">Demo data · no real bookings or payments</span>
          </div>
        </div>
        <ThreeCanvas
          load={loadPin}
          className="l-cta__scene"
          label="A dark brushed-metal map pin with a glowing orange core"
        />
      </section>

      <footer className="l-foot">
        <div className="l-plate">
          <strong>KOGNISYNC</strong>
          <span>Every leg / one journey</span>
        </div>
        <div className="l-plate l-plate--links">
          <a href={REPO}>GitHub</a>
          <a href={`${REPO}/blob/main/docs/ROADMAP.md`}>Roadmap</a>
          <a href={`${REPO}/blob/main/docs/DEPLOY.md`}>Deploy guide</a>
        </div>
        <div className="l-plate l-plate--right">
          <strong>Bengaluru / India</strong>
          <span>Google Startup Buildathon 2026 · Mad Engineers Hub</span>
        </div>
      </footer>
    </div>
  );
}
