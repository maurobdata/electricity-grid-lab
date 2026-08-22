# Hack on the Grid 2026 — Independent Project Research & Recommendation

*Prepared 20 August 2026. Event: Copenhagen, 11 September 2026.*

---

## 0. How to read this, and how confident I am

I have separated everything into three confidence tiers, as requested:

- **[FACT]** — verified against a primary/official source (Electricity Maps docs, Lovable docs, Green Web Foundation, EU/IEA/Ofgem material, market press).
- **[SECONDARY]** — reported by a credible third party, not the primary source.
- **[INFERENCE]** — my own reasoning. Treat as a hypothesis, not a finding.

**The single most important caveat:** I could not locate an official public page for *Hack on the Grid*. The only trace in the index is a LinkedIn post by Anton Vedel titled "Hack on the Grid: Electricity Maps Hackathon," and LinkedIn blocks automated retrieval. There is **no confirmed brief, no confirmed tracks, no confirmed judging rubric, no confirmed prize list, no confirmed judge panel, and no record of a prior edition.** Anyone who tells you otherwise is guessing.

I have therefore refused to invent judging criteria. Section 2 is an explicitly-labelled model of how a hackathon of this shape *tends* to be judged, and Section 12 lists exactly what you should ask the organisers before 11 September.

One editorial decision: you asked for 30+ concepts with 16 fields each. Written in full that is ~30,000 words of mostly-filler, and it would bury the analysis. The longlist (Section A) is therefore compact — enough to judge each idea and kill it — and the full 16-field treatment appears where it earns its keep, in the Top 10 and Top 5.

---

## 1. Research findings

### 1.1 The event itself

| Item | Status |
|---|---|
| Exists, Copenhagen, 11 Sep 2026, Electricity Maps + Lovable | **[SECONDARY]** — your brief + one LinkedIn post title |
| Official brief | **Not found** |
| Tracks | **Not found** |
| Judging criteria | **Not found** |
| Prizes | **Not found** |
| Organisers / judges | **Not found** (Anton Vedel appears to be a promoter or participant) |
| Prior editions / past projects | **None found** |
| Expected participants | **Not found** |

**[INFERENCE]** Electricity Maps is a Copenhagen company (Electricity Maps ApS). A one-day, sponsor-run hackathon at a data company's home city, co-branded with an AI app builder, will draw a mixed crowd: Danish energy-sector engineers and analysts, climate-tech people, a contingent of Lovable-curious builders who are not deep energy people, and some students. **[INFERENCE]** The judging panel will almost certainly include Electricity Maps staff — which is the single most exploitable fact in this document, and I return to it repeatedly.

### 1.2 What Electricity Maps actually gives you (all [FACT], from their own docs)

**Auth & access**
- API v4. Header: `auth-token: <key>`. Basic Auth also supported. `/v4/zones` is the only unauthenticated endpoint.
- **14-day free API trial, no payment details required.** This is your route in.
- Data is available globally: **historical since 2017, real-time, and forecast to 72 hours ahead.**
- **130+ zones.** Zones are tiered A/B/C by source-data quality. Standard real-time plans include **3 months of trailing history**; deeper history requires a custom arrangement.
- Commercial list price, for context on what you're being handed: €4,500–6,000 per signal per country per year; €18,000 for the all-grid bundle; €12,000 for all sustainability signals.

**Signals (each with `past`, `past-range`, `history`, `latest`, `forecast` variants)**
- `carbon-intensity` — gCO₂eq/kWh
- `carbon-intensity-fossil-only` — proxy for residual mix
- `renewable-energy` and `carbon-free-energy` — percentages
- `electricity-mix` — full generation breakdown incl. `battery-discharge`, `hydro-discharge`
- `electricity-source/<type>` — per-source series (`solar`, `wind`, `hydro`, `nuclear`, `gas`, `coal`, `oil`, `biomass`, `geothermal`, …)
- `electricity-flows` — cross-border imports/exports, **including a forecast variant**
- `price-day-ahead` — with `past`, `actual`, `forecast`, and a `combined` endpoint that returns published prices where they exist and Electricity Maps' own modelled prices where they don't
- `locational-marginal-price-day-ahead` — preview, node-level, USD/MWh
- `total-load`, `total-reported-load`, `net-load` (load minus variable renewables)
- `carbon-intensity-level`, `renewable-level`, `carbon-free-level` — beta

**Parameters that matter enormously and that most teams will not notice**
- `temporalGranularity`: `5_minutes`, `15_minutes`, `hourly` (default), `daily`, `monthly`, `quarterly`, `yearly`.
- `flowTraced` / `breakdownType`: consumption-based (default) vs. production-based. Flow-tracing is Electricity Maps' crown jewel and the thing no free alternative replicates.
- `emissionFactorType`: `lifecycle` (default) vs. `direct`.
- `disableEstimations`: responses carry `isEstimated` and `estimationMethod` fields.
- **`dataCenterProvider` + `dataCenterRegion`** — you can query carbon intensity directly for e.g. `gcp` / `europe-west1` instead of resolving a zone yourself. This is a recent, commercially-motivated addition.
- `lat`/`lon` geolocation, with an offline `zone-finder` repo if you can't send coordinates.

**Documented limits**
- `past-range` is capped at **10 days at hourly granularity, 100 days at daily**. Loop for more.
- Forecast horizon `horizonHours` accepts 6/24/48/72 but **availability depends on your plan** — a trial key may cap you at 24h.
- **Day-ahead prices are Europe-only** (plus a few other zones). Fine in Copenhagen.
- Day-ahead LMP forecast is not offered; calling it returns 400.
- No published numeric rate limit found. **[INFERENCE]** Assume it exists and is not generous. Never call the API from the browser.

**Free routes that require no trial at all — your insurance policy**
- **Carbon Intensity Level API** (plus Renewable Level and Carbon-Free Level): **free for all Electricity Maps zones**, hourly. Returns `low` / `moderate` / `high` relative to a rolling 10-day average, with thresholds at ratio <0.85, 0.85–1.15, and >1.15. It exists because the Green Web Foundation asked for it during their Grid-aware Websites project, after free access to the raw Live Carbon Intensity API was narrowed to a single region. Sign-up is via a form at `forms.electricitymaps.com/carbon-aware`.
- **Home Assistant tier**: free carbon intensity and fossil-fuel percentage for **one** home grid zone, hourly, via a free account.
- **Data portal**: downloadable historical datasets.
- **`electricitymaps-contrib`** on GitHub: 4k stars, the parser collection. **License: AGPL-3.0** since v1.5.0 (MIT before one specific 2021 commit). The map frontend is **no longer open source**. The `geo/` directory holds zone geometries — see the licensing warning in Section E.

### 1.3 What Electricity Maps is trying to encourage

**[INFERENCE, but well-supported]** Three signals point the same way:

1. They built free *Level* APIs specifically to grow a grid-aware developer ecosystem, in direct collaboration with the Green Web Foundation. They want people building things that *respond* to the grid, not things that *display* the grid.
2. They added `dataCenterProvider`/`dataCenterRegion` parameters and market their platform to "Data Centers & IT", "Energy Trading", "Battery & Storage", "Energy Management", "Utility & Industry", "Carbon Accounting". Google Cloud uses their data for its customer-facing Carbon Footprint report.
3. They added day-ahead price *forecasting*, LMP, and net load — they are pushing hard from "sustainability data" into "power markets."

**[INFERENCE] The corollary is brutal and worth internalising:** an Electricity Maps employee has looked at more carbon-intensity dashboards than anyone alive. `GET /v4/carbon-intensity/latest` rendered as a gauge will register as *nothing*. The endpoints that will make an EM judge sit up are `electricity-flows`, `electricity-source`, `flowTraced=true` used deliberately, `price-day-ahead/combined`, `net-load`, and the forecast horizon.

### 1.4 What Lovable is, in August 2026

**[FACT / SECONDARY]** Lovable turns natural-language prompts into full-stack web apps: React + Vite + Tailwind + shadcn/ui on the front, and **Lovable Cloud** — built on Supabase's open-source stack — providing Postgres, Auth, Storage, **Edge Functions**, and Realtime with zero setup. You can connect your own Supabase project instead. **Bidirectional GitHub sync** means you can export and keep hacking in a real editor. Recent additions include Visual Edits, Agent Mode, a draw-to-build canvas, and a Claude MCP integration that lets you drive Lovable from Claude or Claude Code. Free tier is ~5 credits/day; Pro is ~$25/mo.

**[INFERENCE] Three consequences for architecture:**
- **Edge Functions are where your Electricity Maps key lives.** Never in the client. This also gives you a natural caching and rate-limit shield.
- **Realtime subscriptions** are free and make a live-updating incident feed trivial. Use them; a page that visibly changes on stage is worth more than three static charts.
- **GitHub sync means Lovable does not have to be the whole product.** Build the sophisticated engine in Python where you're fast, expose it as an API, and let Lovable be the experience layer. That is the "platform + experience" split you asked about, and Lovable's own docs support it.

### 1.5 The 2026 landscape — your "why now"

All **[FACT]**, all from 2026 reporting, and all usable verbatim in a pitch:

- **EU-27 day-ahead markets cleared 1,223 negative-price hours in Q1 2026** — more than double Q1 2025's 593, and over ten times Q1 2022's 119.
- **Spain logged 596 negative-price hours in H1 2026; Portugal 462; France 370.** Spain's Q1 alone jumped from 48 hours (Q1 2025) to 397.
- Exchanges **lowered the price floor from −€500/MWh to −€600/MWh** in 2026 because prices kept hitting the old limit.
- Bloomberg estimated **~40 TWh of European electricity could be curtailed and wasted** in the 2026 solar season — *enough to power Greater London for a year* — up about 25% on 2025.
- **Since 1 October 2025 the EU day-ahead market settles in quarter-hours,** not hours. Electricity Maps' `15_minutes` granularity and their map's `fifteen_minutes` default are not decoration.
- Meanwhile: **power availability is the #1 constraint on European data-centre growth (cited by 67% of operators, EUDCA 2026).** Ireland now requires new data centres to bring dispatchable power or storage and source 80% of demand from Irish renewables. Ofgem is consulting on whether flexibility should be a *condition of connection*. The European Commission published a Strategic Roadmap for Digitalisation and AI in Energy on 3 June 2026. IEA and WEF are both pushing non-firm/interruptible connections.
- Emerald AI, EPRI, National Grid and Nebius ran a **March 2026 UK demonstration** of AI data centres operating as power-flexible assets.

**[INFERENCE] The story that writes itself:** Europe is simultaneously throwing away clean electricity it cannot use *and* refusing grid connections to the loads that would happily eat it. The gap is not generation and it is not demand. It is **coordination and signalling** — which is a software problem, which is why you're in the room.

### 1.6 Prior art you must not accidentally rebuild

- **Carbon Aware SDK** (GSF, MIT, *Graduated*) — the canonical carbon-aware scheduling toolkit. Deployed at UBS and Vestas.
- **GreenScheduled** (Apache-2.0) — `@GreenScheduled` annotation for Spring Boot/Quarkus.
- **Carbon Aware Computing Hangfire Extension**, **Kubernetes Carbon Intensity Exporter**, **PSElectricityMaps**, and roughly forty similar repos under the `carbon-intensity` GitHub topic.
- **Grid-aware Websites** (Green Web Foundation) — already built, already published, already the reason the Level API exists. Their blog even lists the ideas they'd like to see next: grid-aware Home Assistant, grid-aware backends, grid-aware LLM queueing. **Those three are now, effectively, homework assignments with published answers. Avoid.**
- **NESO Carbon Intensity API / dashboard, gridwatch.ca, energydashboard.co.uk, Singularity, Climatiq, Cloud Carbon Footprint, GCP Region Picker** — the "show me clean regions" space is saturated.
- **Monta** — Danish EV charging software, and *an Electricity Maps customer whose logo is on their homepage*. Do not pitch EV smart charging to these judges.
- Grid simulation games already exist (*Power the Grid*, *electrobillion*, *BijliBanaLe*).

### 1.7 Recurring characteristics of winning hackathon projects

**[SECONDARY]**, synthesised from judge write-ups (JetBrains 2026, Devpost, HackerEarth, GitLab AI Hackathon 2026) and consistent across all of them:

1. **The first 30 seconds decide it.** Judging 30–50 demos forces heuristics. A weaker project with a sharp opening beats a stronger one with a muddled one.
2. **Show, don't slide.** A live product beats a deck, every time.
3. **A broken demo is fatal.** Rehearse; have a deterministic fallback.
4. **Judges reward evident personal need.** They can distinguish "we thought this would score well" from "I have wanted this for two years."
5. **Judges quietly ask: could this be funded on Monday?** Projects with a life beyond the weekend win.
6. **Allocate ~20% of your time to the pitch.** Almost nobody does.
7. **[SECONDARY, 2026-specific]** With agentic AI and no-code backends, "we built a working app" is no longer differentiating. Value proof and framing now carry more weight than build volume — which cuts *against* pure engineering flexes and *for* the two-layer pattern you identified.

---

## 2. A model of the judging — explicitly labelled as inference

Since nothing is published, here is what I would bet on, and why:

**[INFERENCE]** For a one-day, single-sponsor-pair event, the panel will weigh roughly: originality of the *idea*, quality of the *live demo*, whether the Electricity Maps data is used in a way that flatters the data (i.e. uses signals a free API couldn't give you), whether Lovable was used to produce something that looks good, plausibility as a real product, and technical substance as a tiebreaker.

**[INFERENCE] Two judge-specific asymmetries you can exploit:**

- **The Electricity Maps judge is bored of carbon intensity and excited about flow-tracing, forecasts, and prices.** Flow-tracing is their published methodology, their differentiator, and their pride. A project whose core mechanic is *impossible without flow-tracing* is a direct compliment to the panel.
- **The Lovable judge wants a screenshot they can put in a launch post.** Give them one gorgeous, unmistakably-Lovable screen.

**What makes a project memorable after 50 demos [INFERENCE]:** an unexpected *framing* of familiar data. Not a new dataset — you all have the same dataset. Not a prettier chart. A framing that makes people say "oh, that's what this data *is*." The best hackathon projects are usually a metaphor that turns out to be load-bearing.

---

## A. The longlist — 34 concepts

Format per idea: **Name** — one-line pitch · *user* · why EM data matters · wow moment · MVP-in-a-day · main risk.

### Consumer / home

**1. Grid Receipt** — Every kWh you used today, itemised by where it physically came from, like a supermarket receipt. · *Any household* · Only flow-tracing can say "31% of your evening was German lignite that crossed the Baltic." · A printed-looking receipt: "Kettle, 18:42, 0.11 kWh — Norwegian hydro 44%, Danish wind 22%, German lignite 19%." · Receipt renderer + `electricity-mix?breakdownType=flow-traced` + a synthetic appliance schedule. · Thin: it informs, it doesn't act.

**2. Appliance Time Machine** — Replay last month and show what shifting your dishwasher would have saved. · *Homeowner* · `past-range` + `price-day-ahead/past`. · A slider that drags your load through time and watches € and gCO₂ fall. · Trivially achievable. · Extremely reproducible; several teams will build this.

**3. Preheat** — Heat-pump pre-charging coach: heat the house on cheap clean power, coast through the expensive dirty hours. · *Nordic homeowner* · 24–72h price + carbon forecast. · Thermal-mass simulation showing comfort maintained at half the cost. · Needs a thermal model; RC model is enough. · Crowded consumer space.

**4. Tenant Flex** — Flexibility for the 60% who can't install solar: aggregate renters' shiftable load into one signal. · *Renters, landlords* · Forecast + zone-level load. · "This building just became a 40 kW battery." · Aggregation logic is simple; UI is the work. · Hard to demo without real devices.

**5. Standby Hour** — A single daily push: "18:00–19:00 is the dirtiest hour today. Do nothing for 60 minutes." · *Everyone* · Forecast, ranked. · Radical simplicity. · Half a day. · Too simple to win a technical prize.

### Social / collective

**6. Street League** — Neighbourhood leaderboard for clean-hours consumption. · *Communities* · Zone carbon intensity as the shared scoreboard. · Live rankings between Copenhagen postcodes. · Feasible with synthetic data. · Fake data undermines the impact claim.

**7. Grid Karma** — Shareable proof-of-shift: a signed badge showing you moved load into a clean window. · *Climate-conscious users* · Verifiable against historical carbon intensity. · Social-card generator. · Easy. · Gimmick risk.

**8. Blackout Party** — Coordinated demand-drop events; a city collectively unplugs during a forecast peak. · *Municipalities* · Net-load forecast identifies the moment. · Countdown timer over a live load curve. · Feasible. · Impact is unquantifiable in one day.

### Gaming

**9. Balance** — A real-time grid-operator roguelike whose difficulty *is* today's actual European grid. · *Anyone* · Live mix, load, flows drive the game state. · You lose because the wind actually dropped in DK1 at 19:00. · Ambitious for one day. · Games score low on "real-world impact" with B2B judges.

**10. Zone Wars** — Daily country-vs-country league table on carbon-free percentage, with commentary. · *Public* · CFE% + flows for "assists." · A football-style table of Europe. · Very feasible. · It's a dashboard with a hat on.

**11. Grid Escape Room** — Educational scenario: prevent a blackout using only real historical data. · *Schools* · Historical replay. · Genuine tension. · Content-heavy. · Not a product.

**12. Counterfactual Europe** — "Delete Germany's coal fleet and re-run yesterday." Interactive what-if over real historical data. · *Public, policy* · Requires mix + flow-tracing to recompute a counterfactual consumption mix. · Drag a slider, watch every neighbouring country's carbon intensity change because of *flow-tracing*. · Recomputing flow-tracing is the hard part. · Methodologically contestable in front of the people who invented the method.

### AI / agents

**13. Grid Copilot** — Chat over Electricity Maps. · *Analysts* · All endpoints as tools. · Natural-language querying. · Very easy. · **Every third team will build this. Do not.**

**14. Flex Broker** — Agents representing assets negotiate flexibility against a live price/carbon signal. · *VPP operators* · Price forecast + net load. · Watching agents bid. · Ambitious. · Hard to make legible in 3 minutes.

**15. Green Router** — Route LLM inference to the cleanest available cloud region in real time. · *AI platform teams* · `dataCenterProvider`/`dataCenterRegion` endpoints. · Live token routing across regions with a carbon counter. · Feasible. · Green Web Foundation already published this as a suggested project.

**16. Grid Narrator** — Auto-generated daily news bulletin about the grid, written from the data. · *Public* · Flows + sources supply the causal story. · A readable article about the grid, generated live. · Easy. · Content, not product.

### Developer / SRE / infrastructure

**17. BROWNOUT — status page and on-call for the electricity grid.** SLOs, error budgets, burn-rate alerts, auto-generated postmortems, and runbooks that fire. · *Engineers, operators, data centres, homes* · Needs flow-traced attribution, per-source series, flows, forecast, and price — the full surface. · An incident fires live; the system pages; an auto-written postmortem attributes 71% of a carbon spike to imports from a named neighbour. · Yes — see Section E. · Must *act*, not just observe, or it collapses into a dashboard.

**18. Carbon-aware CI/CD** — Delay non-urgent builds to clean hours. · *Platform teams* · Forecast. · A build queue that waits. · Trivial. · **Solved five times over. Rejected.**

**19. Carbon-aware Kubernetes scheduler** — Bin-pack by carbon. · *SREs* · Forecast + region data. · Pods migrating. · Hard to demo. · **Solved. Rejected.**

**20. Chaos Grid** — Chaos engineering for energy assumptions: replay real grid stress events against your system. · *SREs* · Historical replay of genuine events. · "Your service's carbon budget dies in this scenario." · Feasible. · Niche; needs a system under test.

**21. Grid Flags** — Feature flags that evaluate against grid state: ship the heavy video encoder only when the local grid is clean. · *Frontend/platform teams* · Level API works free and globally. · Toggle a flag, watch a site downgrade itself. · Very feasible. · Green Web Foundation's grid-aware-websites overlaps heavily.

**22. Carbon Policy-as-Code** — A Terraform/OPA provider that refuses to deploy into a region above a carbon threshold. · *Platform engineering* · Region-level carbon data. · `terraform apply` fails with a carbon error. · Feasible and funny. · Small surface; hard to make visually rich.

### Energy markets

**23. Surplus Radar** — Alarm for negative-price and surplus events, with a marketplace of things that could eat the surplus. · *Industrials, BESS, data centres* · `price-day-ahead/combined` + net load + forecast. · "Spain is paying you €41/MWh to consume, for the next 3 hours." · Very feasible. · Alerting alone is a feature, not a company.

**24. BESS Backtester** — Backtest battery arbitrage strategies against real prices and carbon. · *Storage developers* · Price history + forecast + carbon. · A revenue curve that's real. · Feasible. · Commercial tools exist; hard to wow non-experts.

**25. Interconnector Sankey** — Live animated flow-tracing of electrons across Europe. · *Public, educators* · Pure `electricity-flows` + flow-tracing. · Genuinely beautiful. · Feasible. · It's a visualisation. It's also close to Electricity Maps' own map — a risky compliment.

**26. Carbon Passport** — Who *exported* their emissions? Ranks countries by emissions embedded in exported power. · *Policy, journalists* · Only computable with flow-tracing. · "Germany's clean-power narrative, minus what it sends abroad." · Feasible. · Politically spiky; may age badly on stage.

**27. Forecast Scoreboard** — Grade grid forecasts against outturn; publish the error. · *Traders, forecasters* · `forecast` vs `past-range`. · A public accuracy league table. · Feasible. · You would be grading your judges' own forecasts. Bold or suicidal.

**28. Curtailment Claim** — Estimate how much clean generation was wasted in a zone and what it was worth. · *Developers, policy* · Net load + mix + price. · A running "wasted euros" counter. · Feasible with proxies. · The estimate is a proxy, and EM judges will know it.

### Climate / corporate

**29. 24/7 Gap** — Hourly carbon-free-energy matching gap for a company's real consumption. · *Corporate sustainability* · Hourly CFE% + flow-tracing. · The gap between an annual "100% renewable" claim and hourly reality. · Feasible. · Google has evangelised 24/7 CFE for years; low originality.

**30. Greenwash Check** — Compare market-based vs location-based Scope 2 for a stated claim. · *Journalists, auditors* · Fossil-only carbon intensity as residual-mix proxy. · A claim, debunked live. · Feasible. · Adversarial framing; legal caution.

### Mobility

**31. Charge Window** — EV charging optimiser. · *EV drivers* · Price + carbon forecast. · A charging plan. · Trivial. · **Monta is an Electricity Maps customer. Rejected.**

**32. Freight Slack** — Schedule electric truck depot charging around depot-level grid constraints. · *Fleet operators* · Zone forecast + load. · A depot schedule that fits inside a connection limit. · Feasible. · Requires fleet data you don't have.

### Business / industrial

**33. Siting & Flex Advisor** — Where should this data centre go, and how flexible must it be to get connected? · *Data-centre developers* · `dataCenterProvider`/`dataCenterRegion`, net load, price, forecast. · A map of Europe scored by "connectable if you'll flex X%." · Feasible. · Yottar, Gridcare, Emerald AI occupy this; and it's a slow, static demo.

### Deliberately outside the categories

**34. Grid Radio** — Sonify the European grid live: wind is strings, coal is bass, imports are percussion, price is tempo. · *Anyone* · Every signal maps to a musical parameter. · The room hears the grid. Nobody forgets it. · Feasible with Tone.js. · Zero real-world impact; wins Audience Choice, loses the grand prize.

---

## B. Scored ranking

Weights: Originality 15 · Wow 15 · Real-world impact 15 · Demo quality 15 · Feasibility 10 · Technical sophistication 10 · Effective use of Electricity Maps 10 · Startup potential 5 · Accessibility 5.

| # | Concept | Orig | Wow | Impact | Demo | Feas | Tech | EM | Startup | Access | **Score** |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 17 | **BROWNOUT** | 9 | 8 | 8 | 8 | 7 | 9 | 10 | 8 | 7 | **8.30** |
| 23 | Surplus Radar | 7 | 8 | 8 | 9 | 9 | 6 | 9 | 7 | 9 | **8.00** |
| 1 | Grid Receipt | 8 | 9 | 5 | 9 | 8 | 6 | 10 | 5 | 10 | **7.80** |
| 33 | Siting & Flex Advisor | 7 | 6 | 9 | 6 | 7 | 8 | 10 | 9 | 5 | **7.40** |
| 26 | Carbon Passport | 9 | 7 | 7 | 6 | 7 | 8 | 10 | 5 | 6 | **7.40** |
| 12 | Counterfactual Europe | 9 | 8 | 6 | 7 | 5 | 9 | 9 | 4 | 6 | **7.30** |
| 24 | BESS Backtester | 6 | 6 | 8 | 7 | 8 | 8 | 10 | 8 | 4 | **7.25** |
| 20 | Chaos Grid | 9 | 7 | 6 | 7 | 7 | 8 | 8 | 6 | 5 | **7.20** |
| 9 | Balance (game) | 8 | 9 | 4 | 9 | 5 | 7 | 7 | 4 | 9 | **7.05** |
| 21 | Grid Flags | 8 | 6 | 6 | 7 | 8 | 7 | 8 | 6 | 6 | **6.95** |
| 34 | Grid Radio | 10 | 9 | 2 | 8 | 7 | 5 | 7 | 2 | 9 | **6.80** |
| 29 | 24/7 Gap | 6 | 5 | 8 | 6 | 7 | 7 | 10 | 8 | 4 | **6.75** |
| 15 | Green Router | 4 | 7 | 7 | 7 | 7 | 7 | 9 | 6 | 6 | **6.65** |
| 27 | Forecast Scoreboard | 8 | 6 | 6 | 5 | 7 | 8 | 9 | 5 | 4 | **6.60** |
| 4 | Tenant Flex | 7 | 6 | 7 | 6 | 6 | 6 | 7 | 7 | 8 | **6.55** |
| 6 | Street League | 6 | 7 | 6 | 7 | 7 | 5 | 7 | 6 | 9 | **6.55** |
| 2 | Appliance Time Machine | 5 | 6 | 5 | 8 | 9 | 4 | 8 | 4 | 9 | **6.35** |
| 16 | Grid Narrator | 7 | 6 | 4 | 7 | 9 | 4 | 8 | 4 | 9 | **6.35** |
| 31 | Charge Window | 2 | 5 | 7 | 7 | 8 | 5 | 8 | 5 | 9 | **5.95** |
| 13 | Grid Copilot | 3 | 5 | 4 | 6 | 9 | 4 | 8 | 3 | 8 | **5.35** |
| 18 | Carbon-aware CI/CD | 2 | 4 | 6 | 5 | 9 | 5 | 7 | 5 | 4 | **5.10** |
| 19 | Carbon-aware k8s | 2 | 4 | 7 | 4 | 6 | 8 | 7 | 6 | 3 | **5.10** |

*(Ideas 3, 5, 7, 8, 10, 11, 14, 22, 25, 28, 30, 32 all scored between 5.5 and 6.5 and are cut for brevity. Full reasoning available on request.)*

**Threshold: 7.0.** Everything below is discarded.

**The uncomfortable conclusions this exercise forces:**
- **Carbon-aware CI/CD and carbon-aware Kubernetes are bad hackathon projects.** They are technically respectable and score 5.1. Originality is a 15% weight and they score 2. You cannot recover from that.
- **EV charging scores 5.95 and is aimed at a judge whose employer's logo sits next to Monta's.**
- **Grid Copilot scores 5.35** despite being the easiest thing to build, because feasibility is only 10%.
- **Grid Radio scores 10/10 on originality and still finishes 11th.** Novelty without impact does not win.

---

## C. Top 10 — second-round analysis

### 1. BROWNOUT (8.30)

- **Competitive landscape:** Status pages exist for software (Statuspage, Better Stack). Carbon dashboards exist for grids (NESO, gridwatch, Electricity Maps' own map). **Nobody has merged them.** I found no product applying SLOs, error budgets, burn-rate alerting, or incident postmortems to an electricity grid. The nearest neighbours — Carbon Aware SDK, Kubernetes Carbon Intensity Exporter — are schedulers and exporters, not incident systems.
- **Open-source landscape:** The primitives are all free (DuckDB, FastAPI, prometheus_client, MapLibre) but nobody has assembled them this way. Could someone rebuild it in a weekend? The status page, yes. The flow-traced attribution engine and correct multi-window burn-rate maths, no.
- **Differentiation:** The postmortem. Anyone can say "carbon intensity spiked." Only flow-tracing lets you say *"and 71% of that spike arrived over the interconnector from DE-LU."*
- **Data feasibility:** Fully supported. Needs `electricity-mix` (flow-traced), `electricity-source/*`, `electricity-flows`, `carbon-intensity/forecast`, `price-day-ahead/combined`, `past-range` for baselines.
- **Demo feasibility:** Strong, and — critically — **replayable from cached history**, so it works with no network.
- **Judge reaction:** Every engineer in the room has been paged at 3am. The moment you show an error-budget burn-down for *carbon* they will laugh, and then realise you're serious. That's the "I haven't seen this before" beat.
- **Product potential:** Real. Ofgem is consulting on flexibility as a connection condition; Ireland mandates dispatchable power; the EU published an AI-and-energy roadmap in June. "Grid SLOs" is a plausible category name for something the market is about to need. It also sells straight into Electricity Maps' existing customer segments.
- **Viral potential:** Public status pages are inherently shareable — `brownout.app/DK2` is a link people send each other.
- **Technical depth:** Delta decomposition, rolling baselines, multi-window multi-burn-rate alerting, forecast-driven pre-emptive paging. Plenty.
- **Weakness:** Could be mistaken for a dashboard if the runbooks don't visibly fire. This is the whole risk, and it is manageable.

### 2. Surplus Radar (8.00)

- **Landscape:** Price alerting is a commodity (Tibber, Nord Pool tools, dozens of apps). The *marketplace* framing is fresher than the alerting.
- **Differentiation:** Would have to come from matching surplus to specific willing loads — which is a two-sided-market problem you cannot validate in a day.
- **Data feasibility:** Excellent. `price-day-ahead/combined` is almost purpose-built for it.
- **Demo:** The best in the longlist. "Spain is paying you to consume, right now" is unanswerable.
- **Judge reaction:** Positive but not startled. They will have seen price alerts.
- **Verdict:** Superb *component*, insufficient *product*. Its best use is as a feature of something larger. (See Section E — I fold it in.)

### 3. Grid Receipt (7.80)

- **Landscape:** Nothing quite like it. Closest is Electricity Maps' own zone panel.
- **Differentiation:** The receipt metaphor is genuinely good and genuinely under-used.
- **Data:** Perfect showcase for flow-tracing.
- **Demo:** Beautiful. Emotional. 30 seconds.
- **Judge reaction:** Delight, then "…and?"
- **Technical depth:** Low. A talented designer beats you at this.
- **Verdict:** Best supporting actor in the entire longlist. Its DNA belongs inside the winner as the *postmortem artifact*.

### 4. Siting & Flex Advisor (7.40)

- **Landscape:** Crowded and well-funded — Yottar, Gridcare, Emerald AI, plus every cloud provider's region picker.
- **Data:** The `dataCenterProvider`/`dataCenterRegion` endpoints make this suspiciously easy, which is a warning sign: EM built those parameters, so EM has thought about this.
- **Demo:** A map that doesn't move. Static, analytical, slow.
- **Verdict:** Highest *commercial* score in the list, one of the lowest *demo* scores. Wrong shape for a 3-minute pitch.

### 5. Carbon Passport (7.40)

- **Landscape:** Academically explored, not productised.
- **Differentiation:** Strong; flow-tracing is the only way to compute it.
- **Risk:** You would stand in Copenhagen and rank European countries by exported emissions in front of Danish energy professionals. High variance. Could be brilliant. Could be a room-freezer.
- **Verdict:** Keep as a stretch feature, not a headline.

### 6. Counterfactual Europe (7.30)

- **Differentiation:** Genuinely novel and genuinely hard.
- **Fatal flaw:** You would present a re-implementation of flow-tracing to the company that invented flow-tracing, built in eight hours. Any methodological question sinks you.
- **Verdict:** Wonderful idea, wrong venue.

### 7. BESS Backtester (7.25)

- **Landscape:** Commercial tools exist (KYOS and others). EM sells to this segment directly.
- **Weakness:** Accessibility 4/10. Half the room won't follow it.
- **Verdict:** Would place respectably. Won't win a mixed-audience prize.

### 8. Chaos Grid (7.20)

- **Differentiation:** Excellent framing, and adjacent to BROWNOUT.
- **Weakness:** Requires a system-under-test you don't have.
- **Verdict:** **Merge into BROWNOUT as the demo mechanism** — "replay a real historical incident on demand" is exactly how you make a live demo deterministic.

### 9. Balance (7.05)

- **Weakness:** Impact 4/10, feasibility 5/10. One day is not enough to make a game *good*, and a mediocre game is worse than no game.
- **Verdict:** Cut.

### 10. Grid Flags (6.95)

- **Fatal flaw:** Green Web Foundation shipped the library and Electricity Maps built an API *specifically for it*. You would be presenting the judges' own collaboration back to them.
- **Verdict:** Cut.

---

## D. Top 5 finalists

### Finalist 1 — BROWNOUT

| | |
|---|---|
| **Pitch** | Status page and on-call for the electricity grid. SLOs, error budgets, alerts, auto-written postmortems, and runbooks that actually fire. |
| **Target user** | Anyone who runs something that consumes electricity and could, in principle, run it at a different time — SREs and platform teams first, then data centres, EMS vendors, and households. |
| **Problem** | Software teams have thirty years of tooling for "the system is degraded." The grid degrades constantly — dirty evenings, negative-price middays, curtailment — and nobody gets paged. Every response is manual, after the fact, or nonexistent. |
| **Solution** | Treat each grid zone as a service. Define SLOs (carbon, price, carbon-free share). Compute error budgets and burn rates. Detect incidents. Attribute causes using flow-tracing. Auto-generate a postmortem. Fire runbooks at registered responders. |
| **Why now** | 1,223 negative-price hours in EU-27 in Q1 2026; ~40 TWh of curtailment expected this season; Ofgem consulting on flexibility as a connection condition; Ireland mandating dispatchable power; EU AI-and-energy roadmap published June 2026. Flexibility is shifting from virtue to obligation. |
| **Why Electricity Maps** | It is *unbuildable* without flow-tracing. Attribution across interconnectors, forecast-driven pre-emptive paging, and price-aware severity all require signals only this API provides globally. |
| **Wow moment** | An incident fires on stage. The system pages. Ten seconds later a written postmortem appears: *"SEV2 — DK2 carbon intensity SLO breach at 18:00 CEST. Root cause: 3.1 GW wind ramp-down. 71% of the +180 gCO₂/kWh delta attributable to imports from DE-LU at 612 g/kWh; 29% to domestic gas. Error budget consumed: 63% of the 28-day window."* |
| **Demo flow** | World status board → zone page with burn-down → live incident + page → auto-postmortem → runbook fires, a job defers and a home appliance delays → impact ledger. |
| **Architecture** | Python collector → DuckDB → SLO engine + attribution engine → FastAPI → Lovable Cloud Edge Function → Lovable React app with Realtime. |
| **Open-source stack** | DuckDB (MIT), FastAPI (MIT), APScheduler, prometheus_client (Apache-2.0), MapLibre GL (BSD-3), Natural Earth (public domain), Home Assistant (Apache-2.0) as a responder, shadcn/ui + Recharts via Lovable. |
| **Data requirements** | `carbon-intensity` past-range/latest/forecast · `electricity-mix` flow-traced · `electricity-source/*` · `electricity-flows` · `price-day-ahead/combined` · `net-load` forecast. Free-tier fallback: Carbon Intensity Level API. |
| **Technical difficulty** | Medium-high. The attribution decomposition and burn-rate windows are the only genuinely hard parts, and both are closed-form. |
| **Hackathon feasibility** | High **if** the collector and DuckDB cache are prepared beforehand and the build day is spent on the engine and UI. |
| **Differentiation** | Nobody has applied incident-response primitives to the grid. The metaphor is not decorative — error budgets are exactly the right maths for "how much dirty consumption can I tolerate this month." |
| **Weaknesses** | Dashboard risk if runbooks don't fire. Attribution is a decomposition, not causal inference — say so before a judge does. |
| **Likely judge reaction** | Engineers: recognition, then delight. EM: "they used the parts of our API we're proud of." Lovable: a beautiful status page screenshot. |
| **Potential to win** | Highest in the field. |

### Finalist 2 — Surplus Radar

| | |
|---|---|
| **Pitch** | An alarm for the moments Europe is paying people to consume electricity — and a directory of things that could be doing so. |
| **Target user** | Industrial consumers, BESS operators, data centres, crypto/compute buyers. |
| **Problem** | Negative-price and curtailment events are frequent, forecastable, and almost entirely unexploited by anyone without a trading desk. |
| **Solution** | Forecast surplus windows 24–72h ahead; rank by depth and duration; alert; match to registered flexible loads. |
| **Why now** | The negative-price numbers in Section 1.5 are the story of European power in 2026. |
| **Why Electricity Maps** | `price-day-ahead/combined` blends published and modelled prices in one call — nobody else offers that shape. |
| **Wow moment** | "Right now, Spain will pay you €41 per MWh to switch something on. That window closes in 3 hours 20 minutes." |
| **Demo flow** | Live surplus map → a specific window → a registered load switches on → money counter. |
| **Architecture** | Same as Finalist 1, minus the attribution and SLO engines. |
| **Technical difficulty** | Low-medium. |
| **Feasibility** | Very high — comfortably done in a day. |
| **Weaknesses** | It is an alerting feature. The marketplace half cannot be validated in eight hours, and judges will spot the empty side of the two-sided market. |
| **Judge reaction** | Immediate comprehension, moderate excitement. |
| **Potential to win** | Solid podium contender; unlikely outright winner. |

### Finalist 3 — Grid Receipt

| | |
|---|---|
| **Pitch** | An itemised receipt for the electricity you used today, showing where each kilowatt-hour physically came from. |
| **Target user** | The general public; secondarily, energy educators and utilities. |
| **Problem** | Electricity is the most abstract thing people buy. Nobody has any physical intuition about it, so nobody changes behaviour. |
| **Solution** | Map a household load profile onto flow-traced hourly mix, and render it as a receipt. |
| **Why Electricity Maps** | The entire product *is* flow-tracing, rendered legibly. |
| **Wow moment** | A receipt scrolling out of a virtual till, line by line, with country flags. |
| **Demo flow** | Enter postcode → today's receipt → tap a line item → the electrons' route across Europe. |
| **Technical difficulty** | Low. |
| **Feasibility** | Very high. |
| **Weaknesses** | It changes no decision. Impact 5/10 and technical sophistication 6/10 are hard ceilings. A design-led team beats you at your own game. |
| **Judge reaction** | Genuine delight, then a question you can't answer: "what does the user *do*?" |
| **Potential to win** | Wins a design or audience prize. Won't win the main one. |

### Finalist 4 — Siting & Flex Advisor

| | |
|---|---|
| **Pitch** | Tells a data-centre developer where in Europe they can actually get connected, and how flexible they'd have to be to get there faster. |
| **Target user** | Data-centre developers, hyperscaler siting teams, colo operators. |
| **Problem** | Power availability is the top constraint on European data-centre growth (67% of operators, EUDCA 2026); connection queues run 7–10 years in legacy hubs. |
| **Solution** | Score zones by headroom proxies (net load, price volatility, carbon), then model how much flexibility would satisfy a non-firm connection. |
| **Why Electricity Maps** | The `dataCenterProvider`/`dataCenterRegion` parameters and net-load signal are the natural inputs. |
| **Wow moment** | "Accept 8% curtailment and this site connects in 18 months instead of 8 years." |
| **Technical difficulty** | Medium — the flexibility model is the interesting part. |
| **Weaknesses** | Crowded by funded startups. Demo is a static map. Half the audience is locked out. Headroom is a *proxy* — you don't have real connection-queue data, and a judge from the sector will know it. |
| **Potential to win** | High commercial credibility, low stage presence. |

### Finalist 5 — Carbon Passport

| | |
|---|---|
| **Pitch** | Ranks countries by the emissions they *export* rather than the ones they report. |
| **Target user** | Policy analysts, journalists, corporate carbon accountants. |
| **Problem** | Production-based accounting lets a country look clean while exporting dirty power — a distortion Electricity Maps has argued against publicly for years. |
| **Solution** | Compute embedded emissions in cross-border flows and publish a league table. |
| **Why Electricity Maps** | Impossible without flow-tracing; it *is* their thesis. |
| **Wow moment** | A national clean-energy claim, adjusted live. |
| **Technical difficulty** | Medium-high. |
| **Weaknesses** | Politically charged, in Denmark, in front of energy professionals. High variance. And it's an analysis, not a product. |
| **Potential to win** | Memorable. Risky. |

---

## E. Final recommendation

## Build BROWNOUT.

**And to be explicit, since you asked me to challenge you: it is not GridPilot, it is not carbon-aware SRE in the usual sense, it is not carbon-aware CI/CD, and it is not EV charging.** Those score between 5.1 and 6.0 on the rubric you gave me. Carbon-aware CI/CD is a solved problem with at least five open-source implementations; EV charging is aimed at a room containing a vendor whose customer logo sits on Electricity Maps' homepage. BROWNOUT uses the same underlying instincts — observability, incident response, distributed systems — but points them at something nobody has built.

### Why it's the strongest candidate

**It is the only concept where your background is an unfair advantage rather than a coincidence.** Twenty teams will build something with grid data. Perhaps two will contain someone who has been an incident commander at 3am. That person is the only one in the building who can credibly say "the grid is a distributed system with no on-call rotation" and then produce a working error-budget burn-down. The idea is inseparable from you, and judges reward that — it reads as conviction rather than idea-shopping.

**It flatters the panel with their own crown jewel.** Flow-tracing is Electricity Maps' published methodology and their loudest differentiator. BROWNOUT's central moment — attributing 71% of a carbon spike to a named neighbouring country — is *only possible* with their data. That is a far better compliment than a nicer-looking map.

**It has genuine two-layer structure.**
- *Simple layer:* "It's a status page. Green means fine, red means don't run the dishwasher." Comprehensible to anyone, in four seconds.
- *Sophisticated layer:* rolling-baseline anomaly detection, additive delta decomposition across a flow-traced mix, multi-window multi-burn-rate alerting borrowed verbatim from the Google SRE Workbook, and forecast-driven pre-emptive paging.

**The metaphor is load-bearing, not decorative.** This is the test that separates good hackathon ideas from cute ones. An error budget is *precisely* the right mathematical object for "how much high-carbon consumption can I tolerate this month before I've blown my target" — it's the same integral, with a different unit. Nothing is being forced.

**It absorbs the best of the other finalists without dilution.** A negative-price event is simply an incident of a different severity — `SEV-GREEN: SURPLUS`, "the grid is paying you." That folds in Finalist 2. The postmortem *is* the receipt, rendered for engineers. That folds in Finalist 3. The historical-replay mechanism is Chaos Grid, and it doubles as your demo-safety net.

**It survives contact with a bad wifi connection**, because everything can replay from a local DuckDB cache.

### Product vision

> Every internet service has a status page. The grid — the largest machine ever built, and the one every other system depends on — has none.
>
> BROWNOUT gives every grid zone a status page, every consumer a grid SLO, and every grid event a runbook. In a Europe where flexibility is becoming a condition of connection rather than a virtue, that's not a dashboard. It's the control plane.

Name alternative if BROWNOUT reads too negatively: **GridPager**. I'd keep BROWNOUT and neutralise it in the first line of the pitch — "the grid doesn't have outages any more, it has brownouts: moments when it's dirty, expensive, or drowning in surplus, and nobody gets paged."

### MVP (must exist by 15:00 on the day)

1. **Status board** — Europe, ~8 zones, each `OPERATIONAL` / `DEGRADED` / `SURPLUS` / `SEV2`. Auto-refreshing.
2. **Zone page** — current carbon intensity, price, mix; the zone's SLO; a 28-day error-budget burn-down chart.
3. **Incident detection** — threshold + rolling-baseline breach opens an incident; forecast breach opens a *predicted* incident.
4. **Attribution engine** — decompose the delta in flow-traced carbon intensity into per-source and per-neighbour contributions that sum to 100%.
5. **Auto-postmortem** — a rendered incident report: timeline, waterfall attribution chart, contributing factors, prose summary.
6. **Two live responders** — (a) a webhook/GitHub Actions `repository_dispatch` that visibly defers a job; (b) a simulated home appliance that delays. Both with a visible before/after in gCO₂ and €.
7. **Impact ledger** — running total of avoided gCO₂ and € across all responder actions.

### Stretch goals (in strict priority order)

1. **Public shareable status page** — `/status/DK2`, no login. The viral hook.
2. **LLM-written postmortem prose** on top of the deterministic attribution numbers. Never let the model compute; only let it narrate.
3. **Home Assistant responder** using the free Electricity Maps HA tier — a real device, not a simulation.
4. **Multi-zone workload placement** — "move this job to FR, save 340 gCO₂/kWh."
5. **Prometheus exporter** exposing `grid_slo_error_budget_remaining_ratio`, with a Grafana burn-rate panel. Ten seconds of this during the architecture reveal buys enormous credibility with engineering judges.
6. **Severity from price** — a SEV1 when carbon *and* price are both bad.

### Architecture

```
Electricity Maps API v4
   │  (server-side only; auth-token never leaves the backend)
   ▼
collector.py  ── APScheduler, 5-min poll
   │   carbon-intensity/{latest,forecast}
   │   electricity-mix/latest?breakdownType=flow-traced
   │   electricity-source/{wind,solar,gas,coal,nuclear}/history
   │   electricity-flows/{latest,forecast}
   │   price-day-ahead/combined
   │   net-load/forecast
   ▼
DuckDB  (grid.duckdb)
   ├── observations        raw signals, 60d pre-seeded
   ├── baselines           rolling 10d mean/σ per zone per hour-of-day
   ├── slos                zone → objective, window, threshold
   ├── incidents           open/closed, severity, attribution JSON
   └── actions             responder, runbook, gCO2 avoided, € avoided
   ▼
engine/  ── slo.py · attribution.py · incidents.py · runbooks.py
   ▼
FastAPI  (/zones /incidents /incidents/{id}/postmortem /responders /ledger)
   ▼
Lovable Cloud Edge Function  (proxy + cache + CORS)
   ▼
Lovable React app  (shadcn/ui, Recharts, MapLibre, Supabase Realtime)
```

**The two algorithms that carry the technical weight:**

*Attribution.* Flow-traced carbon intensity is `CI = Σᵢ(mixᵢ × EFᵢ) / Σᵢ mixᵢ`. To decompose `ΔCI` between t₀ and t₁, compute each component's marginal contribution and normalise so the parts sum exactly to the whole (a Shapley-style symmetric decomposition over sources and import partners avoids ordering bias). It's linear algebra, it's exact, and it's defensible. **Call it a decomposition, not causal inference, before anyone else does.** Owning that distinction on stage reads as rigour; being caught on it reads as hand-waving.

*Burn-rate alerting.* Take the Google SRE Workbook's multi-window multi-burn-rate scheme literally: a fast-burn alert (14.4× budget consumption over 1h, confirmed by 5m) and a slow-burn alert (6× over 6h, confirmed by 30m), evaluated against a 28-day carbon budget. It suppresses noise, catches real events, and — crucially — is the *correct* answer, not a gag.

### Open-source integrations, honestly assessed

| Component | What it does | Mature? | License | Integration cost | % of project | What you build |
|---|---|---|---|---|---|---|
| **DuckDB** | Embedded analytical store | Yes | MIT | Trivial (you know it) | ~10% | The schema and the rolling-baseline queries |
| **FastAPI** | HTTP layer | Yes | MIT | Trivial | ~5% | The endpoints |
| **APScheduler** | Polling | Yes | MIT | Trivial | ~2% | Backoff and caching policy |
| **prometheus_client** | Metrics export | Yes | Apache-2.0 | Low | ~3% (stretch) | The grid SLO metric names |
| **MapLibre GL** | Map rendering | Yes | BSD-3 | Medium | ~8% | Zone styling by status |
| **Natural Earth** | Country boundaries | Yes | Public domain | Low | ~3% | — |
| **Home Assistant** | Real device responder | Yes | Apache-2.0 | Medium | ~5% (stretch) | The runbook adapter |
| **Lovable + Cloud** | Entire frontend + backend-for-frontend | Yes | Proprietary | Low | ~30% | Prompts, layout, the postmortem component |
| **Carbon Aware SDK** | Carbon-aware scheduling API | Yes (GSF *Graduated*) | MIT | Medium | 0% | **Skip it.** It abstracts away exactly the EM-specific signals you want to show off |
| **grid-aware-websites** (GWF) | Grid-responsive frontend | Yes | Open source — **verify at repo** | Low | 0% | **Skip it.** Using it invites the comparison you don't want |

**A licensing warning worth taking seriously:** `electricitymaps-contrib` is **AGPL-3.0**. Its `geo/` directory contains the zone geometries and they are tempting. If you pull that GeoJSON into a hosted web app you are arguably in AGPL network-copyleft territory. For a hackathon demo this is unlikely to matter; if you intend to continue afterwards, **use Natural Earth boundaries instead** and avoid the question entirely. Mentioning that you thought about this, unprompted, is the kind of detail that separates you from twenty other teams.

### Data / API plan

**Signals, by priority:**
1. `carbon-intensity/forecast?horizonHours=24` — predicted incidents (assume 24h; request 72h and degrade gracefully)
2. `electricity-mix/latest?breakdownType=flow-traced` — attribution input
3. `electricity-flows/latest` + `/forecast` — the import attribution, i.e. the wow moment
4. `electricity-source/{wind,solar,gas,coal}/history` — the "wind ramped down" narrative
5. `price-day-ahead/combined?horizonHours=24` — surplus events and severity
6. `carbon-intensity/past-range` — 28-day baselines and error budgets
7. `net-load/forecast` — stress signal

**Zones:** DK1, DK2 (home turf, and the judges' own footer says "West Denmark"), DE, FR, PL, ES, NO, SE. Deliberately spans very clean, very dirty, and very volatile.

**Rate-limit strategy:** poll server-side every 5 minutes, cache in DuckDB, serve everything to the browser from your own API. Never call Electricity Maps from client code. If a call fails, serve the last good value with an `isStale` flag — and **show the stale badge in the UI**, because degrading gracefully in front of SREs is itself a flex.

**Three-tier data fallback:**
1. Live trial API (primary)
2. Free Carbon Intensity Level API — works for all zones, forever, no trial (secondary)
3. Pre-seeded 60-day DuckDB cache with a `--replay` flag (guaranteed)

Tier 3 means your demo cannot fail. Build it first.

### UX concept

Deliberately, unmistakably a status page — a visual language every engineer already reads fluently.

- **Board:** dark, dense, monospaced numerals. A vertical list of zones with coloured status pills and a 90-day uptime-style ribbon along each row — except the ribbon is *carbon compliance*, not uptime. Instantly familiar, instantly wrong in the right way.
- **Zone page:** big current number, SLO statement in plain English ("DK2 commits to <150 gCO₂eq/kWh, 95% of hours"), and the burn-down chart. One accent colour. No gauges.
- **Incident page:** the money shot. A timeline down the left. A waterfall attribution chart in the centre showing each source and each neighbour's contribution to the delta. Prose summary at the top in the voice of a real postmortem. Responder actions listed at the bottom with their measured effect.
- **Responders:** cards. Each with a toggle and a "fires when" condition.
- **One deliberate flourish for the Lovable judge:** the postmortem should be *printable* and gorgeous. That's the screenshot.

### Demo script — 3 minutes, timed

**0:00–0:20 — Visual hook.** Board on screen, live, updating. *"This is a status page. Not for a website — for the European electricity grid. Right now Denmark East is degraded, and Spain is in surplus: they are paying people to consume electricity."* Do not explain anything yet. Let it move.

**0:20–0:45 — Problem.** *"In the first quarter of this year, European power markets cleared 1,223 hours at negative prices — double last year. Around forty terawatt-hours of clean power will be thrown away this season; that's Greater London for a year. Meanwhile data centres can't get connected because there's no capacity. The gap isn't generation and it isn't demand. It's that nothing gets told."*

**0:45–2:00 — Use it live.** Click DK2. *"Every zone gets an SLO — this one commits to under 150 grams, 95% of hours. It's burned 63% of its error budget this month."* Trigger the replay. An incident opens; a phone or Slack pane visibly receives the page. *"And here's the part I actually care about."* Open the postmortem. *"Wind fell 3.1 gigawatts. Seventy-one percent of the spike came in over the interconnector from Germany. We can only say that because Electricity Maps flow-traces every kilowatt-hour to its origin."* Then the runbook fires: a GitHub Actions job defers, and a home appliance delays. *"Forty-one kilograms of CO₂, and eleven euros, on one event."*

**2:00–2:40 — Architecture.** One diagram. *"Python collector into DuckDB, five-minute cadence. Attribution is an exact additive decomposition over the flow-traced mix — a decomposition, not causal inference, and I'll happily argue about the difference. Alerting is the Google SRE Workbook's multi-window burn-rate algorithm, applied unmodified to a carbon budget. Frontend is Lovable, key lives in an edge function. Everything you just saw replays from a local cache, which is why it worked."*

**2:40–3:00 — Vision.** *"Ofgem is consulting on making flexibility a condition of getting connected. Ireland already requires it. Flexibility is about to stop being a virtue and start being a contract term — and when it does, everyone will need to prove it. Every grid gets a status page. Every load gets a grid SLO. That's BROWNOUT."*

### Development plan (assuming ~08:30 start, 16:30 hard stop, 17:00 pitch)

| Time | Work | Non-negotiable output |
|---|---|---|
| Before | Collector, DuckDB seed, API key, replay harness | Demo works offline |
| 08:30–09:00 | Confirm brief/tracks; re-aim if needed; freeze scope | One-sentence pitch written down |
| 09:00–10:30 | SLO engine + incident detection over cached data | Incidents open and close correctly |
| 10:30–12:00 | Attribution engine + postmortem JSON | Contributions sum to 100% |
| 12:00–13:00 | Lovable: board + zone page (prompt-driven) | Something on screen |
| 13:00–14:00 | Lovable: incident page + waterfall chart | The money shot exists |
| 14:00–15:00 | Responders + runbooks + impact ledger | **Feature freeze at 15:00** |
| 15:00–15:30 | Live wiring, stale-data badges, error states | Nothing crashes |
| 15:30–16:30 | **Rehearse the pitch four times, out loud, timed** | Under 3:00 every time |
| 16:30 | Stop. Close the laptop. | — |

The 15:00 freeze and the four rehearsals are the two decisions most likely to win or lose this. Every judge write-up I found says the same thing, and every hackathon team ignores it.

### What to prepare BEFORE the hackathon

**Check the rules first.** Some hackathons require all code to be written on the day. If so, the prep below becomes "practice runs you throw away" — which is still worth doing, because the practice is what makes you fast.

1. **Start the 14-day Electricity Maps trial around 5–8 September, not now.** A trial started in August expires before the event. This is the single highest-consequence logistical detail in this document.
2. **On day one of the trial, enumerate what you actually got.** Which zones, which signals, which `horizonHours`. Design for 24h; treat 72h as a bonus.
3. **Register for the free Carbon Intensity Level API** (`forms.electricitymaps.com/carbon-aware`) and create the **free Home Assistant account**. Two independent zero-cost fallbacks.
4. **Pull 60 days of history for all eight zones into `grid.duckdb`** — carbon intensity, flow-traced mix, per-source, flows, day-ahead price. Loop the 10-day `past-range` cap. Commit the file.
5. **Find and rehearse two real historical incidents:** a Danish or German evening wind-lull carbon spike, and a Spanish spring midday negative-price surplus. Both actually happened this year. Real events beat synthetic ones and you can name the date on stage.
6. **Build the replay harness** — a flag that plays cached history at 60× into the live pipeline. This is your demo insurance and your Chaos Grid feature at the same time.
7. **Write the attribution decomposition and unit-test it.** Contributions must sum to the total delta within floating-point tolerance. This is the one thing that will silently be wrong at 16:00 if you don't test it at home.
8. **Do one throwaway Lovable project** to learn its prompting rhythm, credit consumption, and Edge Function deployment. Do not learn the tool on the day.
9. **Write the pitch script now.** Rewrite it on the day. Having a structure to edit beats having a blank page at 15:30.
10. **Prepare the architecture diagram as a single image.** One slide, no build animations.

### What must stay flexible until the day

- **The brief and the tracks.** If there's a mandated track, re-skin rather than rebuild: consumer track → "a status page for your home's grid"; markets track → lead with the SURPLUS severity and price-driven SEV1s; AI track → the postmortem is LLM-narrated over deterministic numbers.
- **Team composition.** If you find a designer, hand them the postmortem page and go deeper on the engine. If you find an energy-market specialist, add price-based severity. If you're solo, cut to: board, incident, postmortem, one responder. That still wins on originality.
- **The zone list**, depending on what your trial key actually covers.
- **Whether the responder is a real device.** If someone in the room has a Home Assistant setup, use it. Real hardware in a software demo is disproportionately memorable.
- **The name.** If BROWNOUT lands badly in the room, GridPager is a two-minute find-and-replace.

### Connecting the three days — without forcing it

This works, and it works honestly:

- **9 Sept (security, monitoring, scanning):** status pages, alerting, blast radius, and incident response are native security-operations concepts. The grid is critical infrastructure; framing grid events with SOC vocabulary is a legitimate transfer, not a stretch. If you learn something about detection-engineering thresholds that day, it applies directly to your burn-rate windows.
- **10 Sept (GitHub, AI, modern software):** your GitHub Actions `repository_dispatch` responder comes straight from that day. So does the Claude Code workflow that builds the engine, and the Lovable–Claude MCP integration for driving the frontend.
- **11 Sept:** the payoff.

Mention this in one sentence during the pitch if it's a multi-event crowd — "this is what happens when you spend Wednesday on monitoring, Thursday on GitHub, and Friday on the grid" — and skip it entirely if it isn't. Don't build anything you wouldn't otherwise build just to make the connection true.

---

## What I'd want you to verify before 11 September

Because I couldn't find the official material, these are the questions that could change the recommendation:

1. Is there a mandated track structure? (Changes the skin, not the substance.)
2. Is the judging rubric published? If "technical implementation" is weighted heavily, push the attribution engine harder. If "business potential" dominates, lead with the Ofgem/Ireland regulatory framing.
3. Must all code be written on the day? (Changes the prep plan materially.)
4. Is team formation on the day or beforehand?
5. What exactly is provided — API keys with what plan, Lovable credits, compute?
6. How long is the pitch, and is there a demo screen or a video submission?
7. Who is judging?

If any of those answers surprise you, send them over and I'll re-run the ranking against the real criteria rather than my model of them.
