# KogniSync – Startup Buildathon Application Answers

## Provide one sentence summary of your new product/project that you are planning to build

KogniSync is an AI-powered, door-to-door multimodal journey copilot for India that plans, books and protects a whole trip across flights, trains, buses, metro, cabs and walking in one itinerary, balancing cost, time and carbon, showing where every fare and timing comes from, and rerouting travelers in real time when disruptions hit.

## What is the main problem that you are solving with the new product idea?

Intercity travel in India is fragmented. A single trip, such as Udayapalya (Bengaluru) to Connaught Place (Delhi), spans 4–6 legs and 5+ apps for cab, metro, flight, train and bus. No product plans the full door-to-door journey, so travelers stitch legs together by hand, guess transfer buffers and miss connections. Data is opaque: estimated fares and ETAs are shown as if they were confirmed. When a flight is delayed or a metro line is disrupted, nothing tells the traveler which later legs break or what the best recovery is. Booking across several vendors risks double charges and half-booked trips because there is no coordinated, safe hold. The result is lost time and money, stress, missed connections and no easy way to choose greener options.

## Who would be a typical user/customer?

Primary: Indian working professionals and students (22–40) who travel intercity often and mix flights or trains with metro, buses and cabs. Examples are a Bengaluru engineer flying to Delhi for client visits, or a student going home for a festival by train plus bus.

Also: travelers from tier-2/3 cities whose trips need several transfers to reach a hub airport or station.

B2B customers: corporate travel desks that must enforce budget and arrival-time policies and track carbon, and OTAs, mobility apps and transit agencies that want our orchestration and disruption engine through an API.

## What is your solution to this problem?

KogniSync turns "get me from A to B" into one trusted, bookable itinerary:

1. Orchestration: it composes door-to-door options across 7 modes (flight, train, bus, cab, Rapido, metro, walk) with realistic transfer buffers, using OSM + Valhalla, Google Routes, TomTom traffic and GTFS-RT feeds.
2. Optimization: a Pareto optimizer ranks routes by time, cost, carbon and reliability. Budget and deadline limits are never silently relaxed, and every pick is explained.
3. Trust: each fare, time and seat is labeled live, scheduled or estimated.
4. Protection: live disruption detection finds affected legs, assesses the knock-on impact and proposes a recovery. It never rebooks without consent.
5. Safe booking: idempotent multi-vendor holds and a saga produce one TripPass with a QR code.
6. A Gemini copilot handles voice, chat and photo input.

## What is the stage of your product or project?

**Minimal Viable Product (MVP)**

## What is the potential business model of this product?

1. B2C freemium: trip planning is free. KogniSync Plus (about ₹99/month or ₹799/year) adds live disruption alerts, one-tap recovery options, priority holds and a multilingual voice copilot.
2. Booking commissions: 2–8% affiliate or commission on flights, trains, buses and cabs booked through partner OTAs and carriers.
3. B2B SaaS for corporate travel desks: per-employee or per-trip pricing for policy enforcement (budget and arrival deadlines), duty-of-care disruption alerts and carbon reports.
4. API licensing: orchestration, Pareto optimization and disruption-recovery APIs for OTAs, mobility apps and city transit agencies, priced on usage.
5. Later: anonymized, aggregated mobility and disruption insights for cities and operators, privacy-safe and opt-in only.

## Who will be your primary competitor(s) and how is your solution different from them?

- MakeMyTrip, ixigo, Cleartrip and Goibibo book single-mode legs (flight, train or bus). They do not plan door-to-door across modes or handle first and last mile.
- Google Maps routes well within a city, but it does not combine intercity flights and trains with cabs and metro into one bookable, budget-limited plan.
- Rome2Rio lists options, but its India data is thin and it has no live disruption handling or booking.
- Uber, Ola, Rapido and metro apps cover a single leg each.

KogniSync is different in five ways:
1. One door-to-door itinerary across 7 modes.
2. Pareto ranking by time, cost and carbon, with explanations and strict budget and deadline limits.
3. Every data point labeled live, scheduled or estimated.
4. Real-time detection of how a disruption spreads to later legs, with recovery options.
5. Concurrency-safe, idempotent multi-vendor holds, plus a multimodal Gemini copilot.

## What will be your primary and secondary target countries, if applicable?

Primary: India. We start with the 14 metro hubs already modeled in the MVP, led by Bengaluru, Delhi NCR, Mumbai, Hyderabad, Chennai and Pune. Next come tier-2/3 cities that feed into them, where multi-leg trips are the norm.

Secondary:
1. Southeast Asia (Indonesia, Vietnam, the Philippines, Thailand), which has similarly fragmented multimodal transport and a fast-growing mobile-first middle class.
2. The Middle East (UAE, Saudi Arabia), with strong India travel corridors and large diaspora travel.
3. The UK and EU later, where open GTFS-Realtime feeds make data onboarding fast.

## How are you planning to use AI for this solution?

AI makes KogniSync conversational, explainable and proactive. The core that handles money and safety (constraints, optimizer, booking checks) stays deterministic.

1. Intent understanding: a request like "Reach CP Delhi by 10am Monday under ₹8,000, prefer train" becomes validated, structured constraints.
2. Tool-using copilot: the AI calls our journey search, disruption and booking-hold APIs, and answers only from their results.
3. Explanations: it explains trade-offs and recovery options in plain English and Indian languages.
4. Multimodal input: voice queries and photos of tickets, PNR SMS or station boards.
5. Disruption reasoning: it summarizes alerts and ranks recovery plans.
6. AI Reliability Copilot: it reads telemetry (hold conflicts, provider health, feed freshness) and summarizes incidents and fixes for the ops team.

Guardrails: the AI never makes up fares and never books without the user's consent.

## Please describe how are you planning to leverage the above selected Google's AI models to tackle the problem you mentioned?

**Gemini API**
1. Function calling connects the copilot to our tools: search_journeys, get_disruptions, explain_route, create_hold and provider_health.
2. Structured JSON output, validated against Pydantic schemas, turns free-text requests into exact constraints.
3. Answers are grounded in tool results and carry provenance labels.
4. Long context lets it read a full itinerary plus live feeds and explain the effect of a disruption.
5. It powers the AI Reliability Copilot, which summarizes logs and incidents.

**Gemini Omni**
1. Real-time voice conversation in Hindi, Kannada, Tamil, Telugu and English for travelers on the move.
2. Image understanding to read tickets, boarding passes, PNR screenshots, departure boards and signage, and turn them into trip data.
3. Live camera and spoken guidance for wayfinding at stations and airports.

Every action is checked against schemas, and bookings need the user's explicit consent.

## How do you intend to deploy and scale your product on Google Cloud?

KogniSync runs as containerized services in Mumbai (asia-south1), with Delhi (asia-south2) as a failover region:

1. Cloud Run hosts the stateless FastAPI services (journeys, optimizer, disruption, booking) and scales them automatically.
2. Firebase Hosting with Cloud CDN serves the web app.
3. Cloud SQL for PostgreSQL (high availability, read replicas) stores inventory and bookings.
4. Memorystore for Redis holds temporary seat holds, idempotency keys and the route cache.
5. GKE Autopilot runs the self-hosted Valhalla routing engine with India map tiles.
6. Pub/Sub and Cloud Scheduler drive live-feed polling and disruption events.
7. Vertex AI provides the Gemini models; Secret Manager stores provider keys.
8. Cloud Monitoring, Logging and Trace feed the AI Reliability Copilot; BigQuery handles analytics.
9. API Gateway and Cloud Armor protect the APIs; Cloud Build and Artifact Registry run CI/CD.

## How did you hear about the Buildathon?

Through Hack2skill (H2S), the Buildathon's powered-by partner, via its platform and community announcements.
