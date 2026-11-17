# KogniSync roadmap

Product spec: [buildathon/KogniSync_Application_Answers.md](buildathon/KogniSync_Application_Answers.md).

Principle: AI orchestrates and explains; deterministic services own prices, constraints and
bookings.

| # | Milestone | What exists | Status |
|---|---|---|---|
| M1 | Scaffold + health checks | `/api/v1/health`, `/api/v1/health/ready`, health panel, one-command dev and test scripts | Done |
| M2 | Journey orchestration + Pareto optimizer | 14 hubs, mock providers for all 7 modes, first/last-mile chains timed around check-in buffers, Pareto front on time/cost/carbon/reliability, weighted ranking, labels, explanations, hard budget/deadline/avoid limits with "what it would take" hints | Done (mock data) |
| M3 | Data provenance | Every fare, time and seat count is `live` / `scheduled` / `estimated` with source and timestamp; live data goes stale after its TTL and is downgraded; totals take the weakest label; badges in the UI | Done |
| M4 | Booking holds + idempotency | `Idempotency-Key` on holds and bookings, atomic seat inventory (memory or Redis), saga with compensation (release, cancel, refund), two explicit consents, signed TripPass + QR, Postgres storage | Done (mock vendors and payments) |
| M5 | Disruption engine | Disruption feed with expiry and 30-min staleness, cascade through later legs (boarding cutoffs, missed connections), severity, recovery re-planned from the break point with remaining budget; proposals only | Done (simulated feed) |
| M6 | Gemini API copilot | Function calling (`search_journeys`, `get_disruptions`, `explain_route`, `create_hold`, `provider_health`), structured intent output, grounding check on prices, offline fallback, AI Reliability Copilot, rate limit | Done; needs `GEMINI_API_KEY` to use Gemini |
| M7 | Gemini Omni | Voice (audio → transcript, language, intent → reply in that language, spoken by the browser) and vision (tickets, boarding passes, PNR SMS, departure boards) | Done; needs `GEMINI_API_KEY`; browser speech fallback for voice |
| M8 | Google Cloud deploy | Dockerfile, Terraform (Cloud Run, Cloud SQL, Memorystore, Secret Manager, Artifact Registry, VPC), Cloud Build, Firebase Hosting, [DEPLOY.md](DEPLOY.md) | Prepared, not applied or validated |

## Extras

- **3D journey globe** (Plan and My trip tabs). Built after studying Flight Viz
  (flight-viz.com), a live WebGL flight globe. REA (`rea-agents analyze-javascript-application`)
  was run on its public JS bundle and showed raw WebGL driven from Rust/WASM, instanced draw
  calls for thousands of markers, and one `requestAnimationFrame` loop. KogniSync's globe is an
  independent three.js implementation using the same ideas: land drawn as one point cloud from
  public-domain Natural Earth data, hubs as one instanced mesh, routes built once, and only the
  camera, traveler and labels updated per frame. No code or assets were copied.

## Next

- Real providers: Google Routes / Places for local legs and geocoding, GTFS-RT feeds, carrier
  and OTA inventory APIs, a real payment gateway.
- Live feed polling with Pub/Sub + Cloud Scheduler; push alerts to travelers.
- Gemini Live API for real-time voice conversation and camera wayfinding.
- User accounts (JWT auth), API Gateway and Cloud Armor, Alembic migrations, BigQuery analytics.
