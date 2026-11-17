# KogniSync

A Gemini-powered, door-to-door multimodal journey copilot for India. It plans, books and
protects one itinerary across flight, train, bus, cab, Rapido, metro and walking.

Built by **Mad Engineers Hub** for the Google Startup Buildathon India 2026.
Milestones: [docs/ROADMAP.md](docs/ROADMAP.md) · Deployment: [docs/DEPLOY.md](docs/DEPLOY.md) ·
Spec: [docs/buildathon/](docs/buildathon/)

> **Demo data.** Transport providers, seat inventory, payments and the disruption feed are
> deterministic mocks. Every value is still labeled with the provenance a real provider would
> give it (live, scheduled or estimated), and source names start with `mock:`.

## What it does

- **Plan:** door-to-door options across 7 modes in 14 Indian metro hubs, ranked on a Pareto
  front of time, cost, carbon and reliability. Budget and arrival deadlines are hard limits;
  if nothing fits, it says what it would take.
- **Trust:** every fare, time and seat count shows whether it is live, scheduled or estimated.
  Live data older than its TTL is downgraded to estimated.
- **Book safely:** idempotent holds across vendors, a saga that rolls back on failure, two
  explicit consents, one signed TripPass with a QR code.
- **Protect:** disruptions cascade through later legs (missed connections, deadline misses);
  recovery options are proposed, never booked automatically.
- **Landing page:** a dark, brushed-metal landing page with a 3D hero (metal globe, toothed
  steel ring, glowing routes over India) and a 3D map pin, then links into the app
  (`#/plan`, `#/trip`, `#/copilot`, `#/ops`).
- **See it in 3D:** a WebGL globe (three.js) shows the 14 hubs and the selected door-to-door
  route: flights arc above the surface, ground legs follow it, a traveler dot moves along the
  trip, and disrupted legs pulse red. It falls back to a text description without WebGL.
- **Converse:** a Gemini copilot with function calling and a price-grounding check; voice in
  Indian languages and photo reading (tickets, PNR screenshots, departure boards) via Gemini.
  Without an API key it falls back to a rule-based planner.

## Repository layout

```
backend/    Python 3.13 · FastAPI · uv          API at /api/v1 (docs at /api/docs)
  app/domain      models (Journey, Leg, provenance-labeled values, bookings, disruptions)
  app/providers   mock transport providers for all 7 modes
  app/services    orchestrator, optimizer, provenance, booking saga, disruptions, stores
  app/ai          Gemini adapter, copilot + tools, intent parsing, Omni voice/vision, reliability
frontend/   React · TypeScript · Vite · Vitest   web app
  src/globe       3D journey globe (three.js, lazily loaded) and its pure geometry helpers
  src/landing     landing page, its two 3D scenes and card illustrations
infra/      Terraform + Cloud Build for Google Cloud (asia-south1)
docs/       roadmap, deployment guide, buildathon spec
scripts/    one-command dev and test scripts
```

## Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and npm

Postgres, Redis and a Gemini API key are **optional** locally. Without Postgres/Redis, data
lives in memory and resets on restart.

## Run locally

Windows (PowerShell):

```powershell
.\scripts\dev.ps1
```

macOS / Linux / Git Bash:

```bash
./scripts/dev.sh
```

The script creates `.env` from `.env.example` on first run, installs dependencies, and starts:

- Web app: http://localhost:5173
- API docs: http://127.0.0.1:8000/api/docs

Press Ctrl+C to stop both. To run each part by hand:

```bash
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

### Try it

1. **Plan**: Udayapalya, Bengaluru → Connaught Place, optionally with a budget or deadline.
2. **Book** a result: hold seats, then confirm. You get a TripPass with PNRs and a QR code.
3. **My trip**: delay or cancel the flight/train (demo buttons), see the impact on later legs,
   then **Find recovery options**.
4. **Copilot**: “Udayapalya, Bengaluru to CP Delhi by 10am tomorrow under ₹9,000, prefer train”.
5. **Ops**: provider health and the AI Reliability Copilot's incident summary.

### Turn on Gemini

Put your key from Google AI Studio in `.env` and restart:

```
GEMINI_API_KEY=your-key
```

`GEMINI_MODEL` and `GEMINI_OMNI_MODEL` choose the models (default `gemini-2.5-flash`; set them
to the newest Gemini models you have access to). `.env` is git-ignored: **never commit keys**.

## Tests

```powershell
.\scripts\test.ps1
```

```bash
./scripts/test.sh
```

Runs ruff and pytest for the backend, then type checks and Vitest for the frontend. Gemini is
never called in tests: a scripted fake drives the copilot, and the real adapter is checked
against google-genai response objects.

## API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health`, `/health/ready` | Liveness; readiness of Postgres, Redis, Gemini |
| `POST /api/v1/journeys/search` | Door-to-door search with constraints and weights |
| `GET /api/v1/journeys/{id}` | A journey, with provenance freshness re-applied |
| `POST /api/v1/holds` | Hold seats (needs `Idempotency-Key`) |
| `POST /api/v1/bookings` | Confirm with consent and the exact total (needs `Idempotency-Key`) |
| `GET /api/v1/trippass/{id}`, `/qr.svg`; `POST /trippass/verify` | TripPass, QR code, token check |
| `GET/POST/DELETE /api/v1/disruptions` | Live feed (POST/DELETE simulate, when enabled) |
| `GET /api/v1/trippass/{id}/impact`, `POST /recovery` | Cascade impact and recovery proposals |
| `POST /api/v1/copilot/chat`, `/intent`, `/voice`, `/vision` | Gemini copilot, intent, Omni |
| `GET /api/v1/ops/providers`, `/telemetry`; `POST /ops/reliability-summary` | Ops and AI Reliability Copilot |
