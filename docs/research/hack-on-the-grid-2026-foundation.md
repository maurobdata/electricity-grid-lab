# Hack on the Grid 2026 — Foundation Document

**Purpose:** Reusable context for a Claude Project. Contains the event facts, the data-capability map, the prior-art/saturation audit, the behavioural evidence base, the identified white space, the primary recommendation and its runners-up, plus the reasoning principles used to get there.

**Method note:** This document was produced from an *independent* exploration brief — deliberately not constrained by prior ideas, preferred technologies, or assumptions about form factor (app / game / dashboard / dev tool). It should be treated as a parallel line of reasoning, not a continuation of earlier work.

**Confidence labelling used throughout:**
- `[VERIFIED]` — directly sourced, cited below
- `[INFERRED]` — reasoning from verified facts
- `[ASSUMPTION]` — unconfirmed, needs checking before it drives a decision

---

## 1. The event

| Field | Detail |
|---|---|
| Name | Hack on the Grid: Electricity Maps Hackathon |
| Date | Friday 11 September 2026, 09:00–18:00 |
| Venue | The Library co-working space, Bragesgade 8B, 2200 København |
| Host | Electricity Maps (their own office) |
| Context | Part of Copenhagen Climate Week |
| Format | Full day, solo or teams, free, approval-required registration |
| Attendance | ~77 registered at time of research |
| Cost | Free |

`[VERIFIED]` Source: https://luma.com/hki2v950

### What is opened up for the day
`[VERIFIED]` The full Electricity Maps API: ~10 years of history, real-time data, and 72-hour forecasts for electricity mix, prices and carbon intensity across grids worldwide.

### The two official tracks
1. **Sustainability & impact** — making the energy transition tangible.
2. **Power markets** — the economics of the transition.

### The host's own example ideas (CRITICAL — treat as a "what everyone will build" list)
Listed verbatim in spirit on the event page:
- Carbon-aware home and appliance automation
- Smart EV charging
- Tools that measure the footprint of AI or any activity
- Apps that help people/companies act on when the grid is clean
- Battery (BESS) charge/discharge optimizers
- Day-ahead arbitrage signals
- Cross-border price and flow visualizers
- Tools that turn complex market data into something anyone can read

`[INFERRED]` **These are the given ideas, not the winning ones.** Any of the eight will likely appear multiple times in the room. Differentiation requires stepping outside this list while staying legible to one of the two tracks.

### Audience composition
`[VERIFIED]` Explicitly open to non-developers: "Modern AI app builders let anyone ship a working app in a day" — sustainability and energy professionals, students, designers and first-time builders are all welcomed.

`[INFERRED]` Two implications:
- The median submission will be an AI-builder-generated web app. Polish alone will not differentiate.
- **Conceptual originality and demo staging will differentiate more than engineering depth.**

### Unknowns to confirm with organisers
- `[ASSUMPTION]` Agenda, prizes and judges were "to come" at research time — no rubric was published.
- `[ASSUMPTION]` Judges likely include Electricity Maps staff and energy-sector professionals. If so: they look at grid charts professionally. A chart cannot impress them; their own data doing something they've never seen can.

---

## 2. The data: what it actually makes possible

### API essentials
`[VERIFIED]` Source: https://app.electricitymaps.com/api/docs/quick-start and `/concepts-and-parameters`

- Auth via `auth-token` header. Zones via `/v4/zones`, or `lat`/`lon`, or the `/v4/zone` lookup. Offline coordinate→zone mapping available via the open-source `zone-finder` repo.
- Auto-fallback to caller IP geolocation unless `disableCallerLookup=true`.
- Official Python and TypeScript SDKs exist.

### Signals available
Carbon Intensity · Fossil-Only Carbon Intensity · Renewable Percentage · Carbon-Free Percentage · Day-Ahead Price · Day-Ahead LMP (preview) · Electricity Mix · Electricity Flows · Electricity Source · Total Load · Total Reported Load · Net Load · Carbon/Renewable/Carbon-Free **Level** (beta)

### Parameters that unlock non-obvious ideas
- **Temporal granularity:** `5_minutes`, `15_minutes`, `hourly` (default), plus `daily`/`monthly`/`quarterly`/`yearly` for past data.
- **Emission factor type:** `lifecycle` (default) or `direct`.
- **Flow-tracing:** `flowtraced` / `breakdownType`. Domestic production mix vs. the flow-traced consumption mix.
- **Estimations:** on by default, flagged via `isEstimated` and `estimationMethod`; disable with `disableEstimations=true`.
- **Coverage tiers:** Tier A (full measured hourly), Tier B (partial), Tier C (monthly/yearly totals only). Zone quality varies — check before designing anything multi-zone.
- **Availability:** history since 2017, real-time, 72-hour forecast, globally. Day-ahead prices mostly Europe plus a few other zones.
- **Load definitions:** Total reported load (as TSOs report), Total load (EM-calculated: net generation − exports + imports − charge + discharge), Net load (minus wind and solar).

### The three under-exploited assets
`[INFERRED]` Most builders will reach for carbon intensity, renewable %, and day-ahead price. The genuinely differentiating material is:

1. **Flow-tracing = a provenance engine.** It computes the mix actually *available on* a grid including imports. It can answer "whose wind is in this room right now." Essentially no consumer-facing product does this.
2. **72-hour forecasts, globally = the near future of every grid is a queryable object.** Nearly everything built on this data is *reactive* ("it's clean now"). Very little is *anticipatory*.
3. **Hourly history since 2017 = a decade of the transition at narrative resolution.** Supports story, not just analysis.

### Known free-tier constraint
`[VERIFIED]` The Green Web Foundation reported that free API use became restricted to a **single region**, which broke their multi-region plans and prompted Electricity Maps to build the Carbon Intensity **Level** API as a workaround.
`[ACTION]` Day-one priority at the event: confirm the access tier granted to participants. A single-zone limit would eliminate most multi-zone concepts. A 14-day trial should be started ~5–8 September so it is live on event day.

---

## 3. Prior art and saturation audit

### Saturated — avoid or radically re-angle

| Genre | Evidence |
|---|---|
| Carbon-aware scheduling / compute shifting | Carbon Hack 22 winners were a carbon-aware federated-learning scheduler (Lowcarb), a GPU power-limit optimizer (Zeus), and a C library that waits for the lowest-carbon window (Circa). ~400 participants, 51 projects, $100k pool. |
| Software footprint measurement | Carbon Hack 24 (500+ participants, 50+ solutions) was entirely about the Impact Framework and measurement plugins. |
| Grid-aware web experiences | Green Web Foundation's Grid-aware Websites project — open-source library, Cloudflare Workers demo, WordPress plugin, Branch magazine redesign — built *with* Electricity Maps, who created the Level API for it. |
| Ambient grid awareness | Home Assistant integration (tens of thousands of users), xbar macOS plugin, IFTTT integration, Microsoft Power Platform connector. |
| Consumer spot-price apps | Nordic market is a commodity: Tibber, Barry, EcoRay, euenergy, kwhprice, gridio, etc. Cheapest-hour calculators are table stakes. |
| AI/LLM footprint calculators | Explicitly listed on the event page; will be built by multiple teams. |
| Zone leaderboards / rankings | Electricity Maps itself publishes "Grid in Review" per-country pages. |

### Adjacent creative precedent worth learning from (not competing with)
- **Solar Protocol** (Tega Brain, Alex Nathanson, Benedetta Piantella; Mozilla Creative Media Award, S+T+ARTS): a network of volunteer-run solar-powered servers where web requests are routed to whichever server is in the most sunlight; page fidelity degrades with battery level. Demonstrates that *environmental logic as system logic* is legible, award-winning and press-friendly.
- **Griddle** (jmelville.science): a hobbyist Wordle-like guess-the-country game using annual generation data. Proves the daily-game format has been *attempted* in this space, but only on annual, non-live data.
- **Open Electricity (AU)** showcase projects (Buzz, Coalwatch): minimalist live-grid views. Proves the "beautiful live view" is a well-trodden path.

### Genuinely white
- No product treats live electricity data as **time** (something delivered into your existing schedule) rather than as **a number to check**.
- No consumer product uses **flow-tracing as storytelling** (provenance, origin, "whose electrons").
- No **utility-independent collective flexibility event** mechanic exists — the demonstrated mass behaviour requires a retailer to convene it.
- No **public forecast-skill contest** (human vs. model) exists on grid data.

---

## 4. Evidence base: how people actually behave

This is the section most hackathon teams skip and the one that most changes the answer.

### Feedback and dashboards decay — reliably
- `[VERIFIED]` Users pay less attention to in-home display feedback after ~4 weeks; one study measured a **60% decrease in interactions**. A UK government survey found **one in five people never looked at their in-home display**. ("The question of energy reduction: The problem(s) with feedback", Energy Policy)
- `[VERIFIED]` A 23-household Australian interview study is literally titled **"Curiosity to cupboard: self-reported disengagement with energy use feedback over time"** — high initial engagement giving way to disinterest, neglect and technical malfunction.
- `[VERIFIED]` A one-year data-sculpture study saw decreased engagement by the **third week**.
- `[VERIFIED]` The known effect has a name in the literature: the **"fallback effect"** (Wilhite & Ling, 1995).

### Naive gamification does not rescue it
- `[VERIFIED]` In co-design work with participants, **motivational gamification elements (competing with a team, earning points) were ranked lowest** of all app features, especially between-household competition. Participants wanted *their own* data, not group achievements.
- `[INFERRED]` Points-and-badges layered onto a chore fails. A game that is intrinsically fun to people who already find the domain interesting is a different proposition and is not refuted by this evidence.

### What does work at scale: time-bound collective events with a stake
- `[VERIFIED]` **700,000** Octopus customers signed up for Saving Sessions, diverting **£5.4 million** to households instead of gas plants.
- `[VERIFIED]` **400,000+** customers took part in a single ~90-minute session, cutting demand by roughly **60%** on average; ~200–250 MWh reduction, described as a UK city going off-grid for an hour.
- `[VERIFIED]` Octopus "Power-ups" inverts this: free electricity when it's very windy/sunny and generators would otherwise be curtailed.
- `[INFERRED]` The winning shape is **an appointment, not a dashboard.**

### Design implication
`[INFERRED]` Any concept whose success depends on people *voluntarily opening a thing to look at grid data* is fighting twenty years of contrary evidence. Concepts that ride an existing habit, or that convene a moment, are structurally advantaged.

---

## 5. Danish / Copenhagen context (September 2026)

This is unusually charged right now and creates enormous topical resonance.

### Grid physics and markets
- `[VERIFIED]` Wind supplied ~**60%** of Danish electricity production in 2025, yet output fell and imports rose — the system leans on interconnectors, flexible generation and price signals during low-wind hours.
- `[VERIFIED]` **DK1 recorded 441 negative-price hours in 2025**, up from 375 in 2024. (Finland 459; Norway only 57 thanks to hydro buffering.)
- `[VERIFIED]` Denmark's negative-hour count rose from 169 (2019) across both zones to ~650 (2024), matched again by mid-September 2025.
- `[VERIFIED]` Average daily price swing ≈ **€116/MWh**; max single-day swing €469/MWh (20 Jan 2025). Renewable share ↔ price correlation −0.77 in 2025.
- `[VERIFIED]` Two bidding zones: **DK1** (Jutland/Funen, synchronous with Germany) and **DK2** (Zealand/Bornholm, Nordic grid). Copenhagen is DK2. Viking Link (1.4 GW, UK) opened 2024.
- `[VERIFIED]` EU-27 saw 1,223 negative-price hours in Q1 2026 — more than double Q1 2025 — though Nordic markets fell back toward zero.

### The data-centre / grid-capacity crisis (the story of the year)
- `[VERIFIED]` Energinet **paused new large-scale grid connection agreements** after requests reached roughly **60 GW** against a national peak demand of about **7 GW** — a queue ~9× peak load.
- `[VERIFIED]` Data centres account for close to a quarter of the projects waiting for connection. Installed capacity ~398 MW at the start of 2026, ~208 MW under construction, projections toward ~1.2 GW by 2030; hyperscalers ~60% of the footprint.
- `[VERIFIED]` **20 August 2026: Denmark published an emergency grid law making most data centres the lowest priority for grid access**, with the energy minister warning the current system risks derailing the green transition.
- `[VERIFIED]` Political framing in the press has included "Hunger Games-style energy policy" — a contest between tech, other businesses and households for limited electricity.

`[INFERRED]` Electricity *timing and scarcity* is currently front-page politics in the host country, during the host city's Climate Week, at a company whose customers include hyperscalers. Anything that makes grid scarcity or grid timing legible to the public has maximal contextual resonance — but note the connection-queue data is **not** in the Electricity Maps API, so a one-day build cannot rest on it.

---

## 6. The four seams of white space

Ranked by estimated size:

1. **Anticipation instead of observation.** Everyone builds "the grid *is* clean now." Almost nobody builds "the grid *will be* clean on Thursday at 14:00, and here is how that lands in your life."
2. **Provenance instead of intensity.** gCO₂/kWh is an abstraction. "Norwegian hydro and German lignite are in this room" is a story. Flow-tracing makes it computable; nobody has made it *felt*.
3. **Collective moments instead of individual optimisation.** The one demonstrated mass behaviour in this domain is the shared, time-bound event — and it currently requires a utility to convene. It shouldn't.
4. **Delivery into existing habits instead of new attention.** Every product in this space asks for a new app, widget or habit. That is precisely what the research says fails.

---

## 7. Primary recommendation: **Windfall — the grid, delivered as a calendar**

### The concept
A subscribable `.ics` calendar feed of the next 72 hours of a chosen grid zone. Not an app. Not a dashboard. A URL pasted once into Google Calendar / Apple Calendar / Outlook, after which the user's ordinary weekly view quietly contains the grid:

- **"Windfall — 82% wind, cheapest hour of the week"** — Sunday 02:00–05:00
- **"Dirty peak — imported German coal"** — Wednesday 17:30–19:00
- **"Best window to charge / run laundry / train the model"** — Thursday 13:00–15:00

Each event carries:
- A one-line **provenance story** derived from flow-tracing ("82% wind; remainder Norwegian hydro")
- A link back to the Electricity Maps view
- A **"commit" action** that makes the event public — a shared layer showing how many people in the zone are doing the same thing in that window, and roughly how much load that represents

### Why it wins
- **It attacks the actual failure mode of the whole category.** Dashboards die because people stop visiting them. This refuses to compete for attention and rides a habit with ~100% daily engagement.
- **It converts the least-used, most valuable API asset** (global 72-hour forecast) into something a non-developer can adopt in ten seconds.
- **It gets more useful the less you look at it** — rare in this space.
- **It works identically in Copenhagen, Lagos and São Paulo** — Electricity Maps' global coverage story made tangible.
- **The collective layer has a second life as flexibility infrastructure**: a public, opt-in demand-shift signal that costs nothing to join and needs no utility — the Saving Sessions mechanic, unbundled.
- **It spans both tracks**: clean-hour framing for sustainability, price/negative-hour framing for power markets.

### The demo
QR code on screen → ~70 people scan → within seconds every phone in the room contains the Danish grid, including a shared "Windfall" event scheduled during the hackathon itself with a live counter of commitments. **The room becomes the demo.** This is the memorability mechanism.

### Known risks and mitigations
| Risk | Mitigation |
|---|---|
| Calendar spam / instant unsubscribe | Hard cap: max two events per day. Quiet/no-alert by default. One "windfall", one "avoid". |
| Savings are small for Danish households (tariffs and taxes dominate retail price) | Lead with **clean**, not cheap. Foreground EVs, heat pumps, batteries and compute where the numbers are real. Let price framing serve the power-markets track, not the household pitch. |
| Empty-network problem — collective layer looks dead on stage | Seed it in the room. Consider making the room's own commitments the headline metric rather than global adoption. |
| Free-tier single-zone limit | Confirm access tier on arrival; design so single-zone still fully works and multi-zone is an enhancement. |
| Timezone / DST correctness in `.ics` | Non-trivial and unglamorous; budget real time for it. This is where the build actually fails. |

### Open strategic question (unresolved)
**Is the collective layer the heart of the product or a distraction?** A calendar that quietly makes clean hours legible is useful to one person; a calendar where 500 people converge on the same windy Sunday hour is a movement — but the latter needs enough day-one users to not look empty on stage. This trade-off should be decided before building, not during.

---

## 8. Runners-up and why they lose

| Concept | Description | Why it loses |
|---|---|---|
| **Public forecasting tournament** | Daily predictions about the grid (will DK1 go negative? which fuel wins? cheapest hour?), Brier-scored against reality, with a human-vs-model leaderboard against Electricity Maps' own forecast | Excellent loop, novel use of forecasts as *sport*, flatters the host's core product — but appeal is narrow: it is for people who already care |
| **Provenance receipts / "Radio Windfall"** | Flow-traced storytelling; or a stream broadcasting from whichever grid is cleanest right now (Solar Protocol logic, no hardware) | Highest artistic ceiling and most memorable in the room; lowest repeat use |
| **Daily battery-arbitrage game on real DK1 prices** | "You are a 10 MW battery today" — trade against real day-ahead prices, resolve at midnight | Fun and genuinely educational, but it is a simulator, and simulators rarely leave the room |
| **"Who gets the electrons" scarcity explainer** | Public-facing tool making the connection-queue crisis and grid headroom legible | Maximum topical resonance in August 2026, but the queue data is not in the API — one day is not enough |

---

## 9. Reusable reasoning principles

Extracted so they can be reapplied to new ideas without redoing the analysis:

1. **The host's example list is the anti-brief.** Anything named on the event page will be built multiple times. Stay in-track, out of the list.
2. **You cannot impress grid professionals with a chart.** You impress them by making their own data do something they haven't seen.
3. **Anything requiring voluntary repeated visits to look at energy data is fighting the evidence.** Ride an existing habit or convene a moment.
4. **Points and badges layered on a chore fail; an intrinsically enjoyable artefact for people who already care is a different thing.** Don't confuse the two.
5. **Reactive is crowded; anticipatory is empty.** Forecast > real-time as a differentiator.
6. **Flow-tracing is the host's methodological differentiator and a storytelling engine nobody has used for consumers.**
7. **Demo staging is a design variable, not an afterthought.** The strongest concepts turn the room into the demo.
8. **Raw zone rankings are strategically dead** (the clean grids always win). Relative, baseline-adjusted or personally-anchored framings are what make comparison interesting.
9. **Be honest about the money.** In high-tax retail markets, spot-price savings for households are small; overclaiming is the fastest way to lose credible judges.
10. **Check the tier before the idea.** Data availability (Tier A/B/C, single-zone free limits, Europe-only day-ahead prices) can silently kill a concept.

---

## 10. Pre-event checklist

- [ ] Start the 14-day Electricity Maps API trial ~**5–8 September** so it is active on 11 September
- [ ] Confirm participant API access tier on arrival (single-zone vs. multi-zone) — **day-one blocker**
- [ ] Confirm judging criteria, prize structure and judges with organisers (unpublished at research time)
- [ ] Verify DK2 (Copenhagen) data tier and day-ahead price availability
- [ ] Test `/v4/zones` output against the concept's zone requirements
- [ ] Pre-validate `.ics` timezone/DST handling if pursuing the primary recommendation

---

## 11. Sources

**Event & API**
- https://luma.com/hki2v950
- https://app.electricitymaps.com/api/docs/quick-start
- https://app.electricitymaps.com/api/docs/concepts-and-parameters
- https://app.electricitymaps.com/coverage
- https://pypi.org/project/electricitymaps/
- https://github.com/electricitymaps/zone-finder

**Prior art / saturation**
- https://greensoftware.foundation/articles/carbonhack22-a-big-leap-in-carbon-aware-computing/
- https://apiumhub.com/tech-blog-barcelona/green-software-carbon-hack/
- https://greensoftware.foundation/articles/carbon-hack-24-expanding-the-ecosystem-of-software-measurement/
- https://www.thegreenwebfoundation.org/tools/grid-aware-websites/
- https://www.thegreenwebfoundation.org/news/a-new-api-for-grid-aware-websites-and-beyond/
- https://github.com/thegreenwebfoundation/grid-aware-websites
- https://www.electricitymaps.com/free-tier-api
- https://solarprotocol.net/ · https://tegabrain.com/Solar-Protocol · https://ars.electronica.art/starts-prize/en/solar-protocol/
- https://jmelville.science/griddle/
- https://platform.openelectricity.org.au/

**Behavioural evidence**
- https://www.sciencedirect.com/science/article/pii/S0301421514006739 (feedback decay, 60% drop, 1-in-5 never look)
- https://eprints.soton.ac.uk/386441 ("Curiosity to cupboard")
- https://www.researchgate.net/publication/258239195 (one-year eco-feedback limitations)
- https://www.sciencedirect.com/science/article/pii/S2214629623003183 (gamification ranked lowest in co-design)
- https://octopus.energy/press/free-whizz-octopus-launches-power-ups-free-energy-when-the-sun-shines-and-the-wind-blows/ (700k signups, £5.4m)
- https://en.wikipedia.org/wiki/Demand_Flexibility_Service

**Danish context**
- https://www.solarplaza.com/resource/13528/ (441 negative hours DK1 2025)
- https://www.electricitymaps.com/grid-in-review-2025/denmark (price swings, correlations, duck curve)
- https://spacedaily.com/... (60% wind share 2025, import dependence)
- https://www.pv-magazine.com/2026/05/08/europes-negative-electricity-price-hours-double-in-q1-amid-renewables-surpluses-market-imbalances/
- https://thenextweb.com/news/denmark-data-centre-grid-pause-ai-energy (60 GW queue vs 7 GW peak)
- https://www.cnbc.com/2026/05/04/denmark-data-centers-moratorium-grid-pause-power-demand.html
- https://www.bloomberg.com/news/articles/2026-08-20/denmark-publishes-emergency-grid-law-that-puts-data-centers-last
- https://euenergy.live/denmark (DK1/DK2 structure, interconnectors)

**Related events in the trip**
- Hacker Night — 9 Sep, 17:00–21:00 — https://ida.dk/en/arrangementer-og-kurser/arrangementer/hacker-night-366733
- Engineering the Future: A Secure, AI-First Path to GitHub — 10 Sep, 09:00–16:30 — https://msevents.microsoft.com/event?id=978663000
