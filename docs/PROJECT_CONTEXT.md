# PROJECT_CONTEXT.md

## Electricity Maps Hackathon Project — Canonical Context

> **Purpose:** This document consolidates the relevant context, research, hypotheses, decisions, constraints, and intended working process accumulated before moving the project into local Claude Code development.
>
> **Status:** Working foundation. This is context and a record of hypotheses, not a final product specification.
>
> **Important:** Do not treat any single previous idea as final. The product direction should remain experimentally open until validated through research and prototyping.

---

# 1. Project Context

The project is being prepared for **Hack on the Grid 2026**, a full-day hackathon taking place on **Friday, 11 September 2026** in Copenhagen during Copenhagen Climate Week.

The hackathon is organised by **Electricity Maps and Lovable** and provides access to Electricity Maps' electricity data and APIs.

The event is explicitly intended for a broad audience, including developers, energy professionals, designers, students and first-time builders.

The stated opportunity is to turn real electricity data into working software.

The available Electricity Maps material indicates access to:

- approximately 10 years of historical data;
- real-time electricity data;
- 72-hour forecasts;
- electricity mix;
- prices;
- carbon intensity;
- worldwide grid coverage;
- other grid-related information exposed through the API.

The hackathon has two broad tracks:

### Sustainability & impact
Examples include:
- carbon-aware home and appliance automation;
- smart EV charging;
- tools measuring the footprint of AI or other activities;
- applications helping people act when the grid is clean.

### Power markets
Examples include:
- BESS charge/discharge optimisation;
- day-ahead arbitrage;
- cross-border price and flow visualisation;
- tools making complex market data accessible.

These examples should be considered the obvious/expected solution space, not necessarily the strongest opportunity.

---

# 2. Training Context

The hackathon is the final part of a three-day technical training trip.

### 9 September — Hacker Night
17:00–21:00

Official event:
https://ida.dk/en/arrangementer-og-kurser/arrangementer/hacker-night-366733

Hands-on network and web security, monitoring and scanning, organised by IDA Connect together with Campfire Security, Cyberskills and Aalborg University.

### 10 September — Engineering the Future: A Secure, AI-First Path to GitHub
09:00–16:30

Official event:
https://msevents.microsoft.com/event?id=978663000

Focus:
- engineering;
- security;
- GitHub;
- AI;
- modern development practices.

Organised by Microsoft.

### 11 September — Hack on the Grid
09:00–18:00

Official event:
https://luma.com/hki2v950

Full-day hackathon focused on building prototypes and working software using real electricity data.

Organised by Lovable and Electricity Maps as part of Copenhagen Climate Week.

The first two events are contextual inspiration, not product requirements. Do not force security, AI, GitHub or SRE concepts into the final product unless they genuinely improve it.

---

# 3. Original Product Exploration

The project started from an SRE/engineering perspective because of the desire to leverage existing technical knowledge, but this was deliberately challenged.

Several early concepts were explored, including:

- SRE-oriented electricity observability;
- electricity status pages and SLO-style concepts;
- carbon-aware automation;
- grid-aware infrastructure;
- energy dashboards;
- battery optimisation;
- prediction;
- simulations;
- map-based experiences;
- game concepts inspired by Risk, Civilization, Imperium and SimCity;
- collaborative energy experiences;
- education-oriented products.

A recurring concern was that technically sophisticated infrastructure might be impressive to engineers but not memorable enough for a broad hackathon audience.

The project should therefore optimise for:

**idea + experience + interaction + impact + memorable demo**

rather than:

**architecture complexity + infrastructure sophistication.**

---

# 4. Important Product Philosophy

The project should not be constrained by the creator's professional profile or preferred technologies.

The strongest project may be:

- a game;
- a consumer experience;
- an educational experience;
- a social product;
- a prediction experience;
- a simulation;
- a collaborative tool;
- a creative/visual experience;
- a utility;
- or something not yet considered.

Technology should follow the product.

The project should avoid becoming merely:

- another electricity dashboard;
- another carbon calculator;
- another generic AI chatbot;
- another carbon-aware scheduler;
- another technically impressive SRE platform.

The core question is:

> **What becomes possible when real electricity data becomes programmable, real-time, historical and predictive?**

---

# 5. Research Findings — Important Insights

One of the strongest research outputs concluded that the obvious Electricity Maps use cases are already crowded.

Common/expected directions include:

- carbon-aware scheduling;
- AI/GPU carbon optimisation;
- EV charging;
- home automation;
- battery arbitrage;
- energy dashboards;
- carbon-intensity widgets;
- energy calculators.

These are useful, but they are unlikely to be inherently differentiated at a hackathon where many participants will see the same raw material.

A key research insight was:

> **Judges who work professionally with grid charts are unlikely to be impressed by another chart. They may be impressed by making the same data do something they have never seen before.**

---

# 6. Potentially Underused Electricity Maps Capabilities

Research highlighted several capabilities that may be more interesting than basic carbon intensity:

### Flow tracing / provenance

Electricity Maps can represent the electricity actually available on a grid, accounting for domestic generation and neighbouring flows.

This creates the possibility of answering questions such as:

> Where is the electricity I am using effectively coming from?

This can turn electricity data into a provenance/storytelling mechanism rather than simply a number.

### 72-hour forecasts

The forecast creates a queryable representation of the near future of a grid.

This suggests a major distinction:

**reactive experiences:**
> The grid is clean now.

versus

**anticipatory experiences:**
> The grid is expected to be clean tomorrow afternoon.

The latter may be a more interesting foundation for interaction.

### Historical data

Approximately ten years of historical data can support:

- replay;
- historical scenarios;
- storytelling;
- comparisons;
- event-driven experiences;
- controlled demos.

This is also useful because a hackathon demo should not depend on whatever happens to occur in the live grid during the presentation.

---

# 7. Behavioural / Engagement Research

Research into energy feedback and eco-feedback suggests a significant challenge:

People often initially engage with energy information but gradually stop paying attention.

One research output described this as a progression from:

> curiosity to cupboard

where engagement with energy displays declines over time.

Naive gamification does not necessarily solve the problem.

A more promising pattern identified in research was **time-bound collective events with a meaningful outcome**.

A cited example was Octopus Energy's demand-shifting / Saving Sessions model, where large numbers of customers participated in time-limited events.

The strategic implication is important:

> The problem may not be showing electricity information better. The problem may be creating a reason for people to care at a specific moment.

This led to an important conceptual shift:

**ambient awareness → actionable anticipation → collective moments**

rather than simply:

**dashboard → user checks dashboard → user forgets dashboard.**

---

# 8. White-Space Hypotheses

The strongest research output identified four potentially interesting seams:

1. **Anticipation instead of observation**
   - Use the forecast to help users act before conditions change.

2. **Provenance instead of intensity**
   - Turn flow-traced electricity into a story rather than just a carbon number.

3. **Collective moments instead of individual optimisation**
   - Create shared events around grid conditions.

4. **Delivery into existing habits instead of demanding a new habit**
   - Integrate electricity intelligence into tools people already use.

These are hypotheses, not final requirements.

---

# 9. Windfall — Current Strongest Product Hypothesis

One research phase independently proposed a concept called:

# Windfall

Core idea:

> **The grid, delivered as a calendar.**

Instead of building another dashboard, create a subscribable calendar feed containing useful future electricity windows based on the user's grid.

Example events:

- "Windfall — 82% wind, cheapest hour of the week"
- "Dirty peak — imported German coal"
- "Best window to charge / run laundry / train the model"

Each event could include:

- forecast information;
- electricity mix;
- carbon context;
- price context;
- provenance / flow-tracing story;
- link back to the relevant map;
- optional collective "commit" behaviour.

The concept attempts to solve the attention problem by entering an existing habit (calendar) rather than requiring the user to repeatedly visit a new dashboard.

The strongest demo hypothesis was:

1. show a QR code;
2. audience joins;
3. Danish grid conditions appear in participants' calendars;
4. a shared event can show how many people have committed to a particular window;
5. the room itself becomes part of the demo.

This is compelling but remains a hypothesis.

---

# 10. Other Important Concepts Explored

### Prediction tournament

A public forecasting game where users predict future grid conditions and are scored against reality.

Potential strengths:
- strong use of forecasts;
- clear feedback loop;
- inherently measurable;
- potentially good fit for technically sophisticated audiences.

Potential weakness:
- may appeal mainly to people who already care about energy.

### Provenance / "Radio Windfall"

Use flow-traced electricity to tell stories about where electricity is coming from.

Potential strengths:
- unusual use of Electricity Maps;
- strong artistic / storytelling potential;
- potentially memorable.

Potential weakness:
- unclear repeat-use value.

### Real electricity battery game

A game/simulator based on real electricity prices.

Potential strengths:
- teaches electricity markets;
- directly uses real data.

Potential weakness:
- may feel like a simulator rather than a broadly compelling product.

### Energy / society game

A Civilization/SimCity/Imperium-like experience where electricity is a core system.

Potential strengths:
- highly visual;
- educational;
- interactive;
- potentially very accessible;
- potentially socially engaging.

Potential weakness:
- could become a generic strategy game with electricity painted on top;
- requires careful design so that electricity is essential to the gameplay.

This direction should not be assumed to be the final product.

---

# 11. Current Product Principle

A strong final product should ideally satisfy:

> **People interact because it is genuinely interesting or useful; they learn because understanding electricity helps them interact better.**

Education should emerge from interaction rather than from passive information delivery.

The strongest possible experience would allow someone unfamiliar with electricity to gradually understand:

- renewable variability;
- demand;
- storage;
- price;
- carbon intensity;
- electricity mix;
- flows;
- interconnection;
- forecasts;
- timing;
- resilience;
- energy trade-offs.

without feeling like they are studying.

---

# 12. Current Technical Foundation Hypothesis

Regardless of the final product, it is useful to create a reusable foundation above Electricity Maps.

The proposed conceptual stack is:

```text
Electricity Maps
       ↓
Electricity / Grid Domain Layer
       ↓
Application / Experience Layer
       ↓
AI Agent Layer
       ↓
User
```

The project should remain flexible enough that the experience layer can become:

- Windfall;
- game;
- collaborative experience;
- prediction experience;
- or another validated concept.

---

# 13. Proposed Local Foundation

The current intention is to create a local-first, containerized PWA that can run with a simple command.

The initial application should provide an "Electricity Lab" rather than pretending the final product is already known.

Desired early capabilities:

- PWA shell;
- local development;
- real Electricity Maps data;
- zone selection;
- current conditions;
- forecasts;
- useful visualisation;
- clean Electricity Maps API abstraction;
- optional exploration of the existing Electricity Maps web experience;
- replay/simulation capability;
- minimal AI agent;
- clean documentation;
- tests;
- containerized development.

The existing Electricity Maps application may initially be used as a reference or exploration surface.

Do not make an iframe/redirect to the existing Electricity Maps application a core architectural dependency without verifying technical and legal feasibility.

---

# 14. Electricity Maps Adapter

The application should not scatter Electricity Maps API calls throughout the UI.

Create a domain-facing adapter / client abstraction.

Conceptually:

```text
get_latest(zone)
get_forecast(zone)
get_mix(zone)
get_price(zone)
get_flows(zone)
get_history(zone, start, end)
compare_zones(...)
```

Exact endpoints must be verified against the official Electricity Maps developer documentation.

Never invent endpoints.

Credentials must be supplied through environment variables and never committed.

---

# 15. Live vs Replay

A reusable simulation/replay abstraction is considered valuable.

Conceptually:

```text
              Electricity Maps
                    |
                  Adapter
                    |
              Grid Domain Model
                    |
          +---------+---------+
          |                   |
       LIVE MODE          REPLAY MODE
```

This allows:

- real-time operation;
- historical scenarios;
- controlled demonstrations;
- deterministic testing;
- potentially synthetic scenarios.

This is particularly useful for the hackathon because the live grid may not produce a spectacular event during the demo.

---

# 16. AI Agent Direction

The project may contain a containerized AI agent inspired by the principles in:

**A Common-Sense Guide to AI Engineering**

and its associated examples/repository.

The supplied material includes examples around:

- tool-equipped chatbots;
- OpenAI tool calling;
- agentic RAG;
- automated evaluations;
- production traces / evaluation workflows.

The goal is not to copy the repository blindly, but to use it as reference material for an agent architecture based on:

```text
Model
+
Tools
+
Knowledge
+
Evaluation / Tracing
```

The agent should initially have explicit, narrowly scoped tools such as:

```text
get_current_grid()
get_forecast()
get_mix()
get_price()
get_flows()
query_history()
compare_zones()
```

Do not provide unrestricted system access.

---

# 17. Agent + UI Direction

A possible future evolution is an agent that can work collaboratively with the user through the application's UI.

Potential stages:

### Agent v0
Read and explain Electricity Maps data.

### Agent v1
Use structured grid tools.

### Agent v2
Use tools to update or manipulate the application's UI.

### Agent v3
Potentially operate semi-autonomously toward a user-defined objective.

The final role of the agent is intentionally undefined.

It could become:

- advisor;
- teammate;
- narrator;
- analyst;
- opponent;
- researcher;
- guide;
- autonomous participant.

Do not decide this prematurely.

---

# 18. OpenClaw / Crowbot Inspiration

OpenClaw:
https://openclaw.ai/

The project may take inspiration from autonomous/containerized agent systems, particularly the concept of an agent that can work continuously with tools and a shared environment.

However, the project should not attempt to recreate a full OpenClaw-class system.

Start with a narrow, controlled Electricity Agent and expand only if the product experience benefits from it.

---

# 19. Design Philosophy

The project should follow:

### UX > architecture

### Product > technology

### Game / experience > dashboard

### Real data > simulated numbers

### Simple core loop > feature count

### Reusable foundation > premature final product

### Explicit tools > unrestricted agents

### Evidence > assumptions

### Demoability > infrastructure complexity

---

# 20. Hackathon Strategy

The project should be designed around a one-day hackathon reality.

A successful prototype should ideally demonstrate:

1. a real Electricity Maps data source;
2. a clear user interaction;
3. a meaningful consequence of the data;
4. something visually memorable;
5. an obvious reason why Electricity Maps is essential;
6. a coherent story in under a few minutes.

The final project should not attempt to build a complete enterprise platform during the hackathon.

The technical foundation should instead make it possible to rapidly build a polished vertical slice once the final concept is selected.

---

# 21. Research Workflow

The project has deliberately gone through several rounds of independent exploration.

Important methodological decision:

Do not overfit future ideation to previously generated ideas.

When conducting further research:

- treat current concepts as hypotheses;
- search independently;
- validate against real users/products/data;
- identify existing competition;
- kill weak ideas;
- allow new concepts to replace existing ones.

The final product should emerge from evidence and experimentation.

---

# 22. Current Decision Status

### Confirmed

- Participate in Hack on the Grid.
- Build a real project using Electricity Maps data.
- Prepare locally before the hackathon.
- Use Claude Code as the main local development environment.
- Establish a clean repository and documentation.
- Build a reusable Electricity Maps integration layer.
- Experiment with an AI agent.
- Keep the final product direction flexible.
- Prioritize experience and demo quality over architectural complexity.

### Strong hypotheses

- Anticipation may be more powerful than passive observation.
- Forecasts are an underused interaction surface.
- Collective actions may produce stronger engagement than individual eco-feedback.
- Flow provenance may be more compelling than raw carbon intensity.
- Existing habits may be better delivery mechanisms than another dashboard.
- Windfall is currently a strong product hypothesis.

### Explicitly NOT decided

- final product;
- game vs non-game;
- Windfall vs another direction;
- exact UI;
- exact technology stack;
- exact agent role;
- multiplayer model;
- deployment architecture;
- final branding.

---

# 23. Suggested Development Phases

## Phase 0 — Project migration

Create:

- repository;
- `CLAUDE.md`;
- this `PROJECT_CONTEXT.md`;
- research documents;
- architecture notes;
- decision records.

## Phase 1 — Electricity Lab

Build:

- PWA;
- Electricity Maps adapter;
- real data;
- zone selection;
- forecast;
- basic visualization;
- live/replay abstraction.

## Phase 2 — Agent Sandbox

Build:

- agent runtime;
- explicit Electricity Maps tools;
- structured outputs;
- tracing;
- initial evaluations.

## Phase 3 — Experience Exploration

Prototype competing ideas quickly.

Potential candidates include:

- Windfall;
- prediction;
- cooperative experience;
- game;
- education;
- another concept discovered through research.

## Phase 4 — Vertical Slice

Select one concept and build the smallest polished experience that proves it.

## Phase 5 — Hackathon Preparation

Prepare:

- reproducible local setup;
- seeded/demo data;
- live API integration;
- controlled demo scenario;
- screenshots/assets;
- pitch;
- fallback mode.

---

# 24. Working Rules for Claude Code

When this project is opened in Claude Code:

1. Read this file before making architectural decisions.
2. Read the other research documents available in the repository.
3. Treat this document as context, not as an immutable specification.
4. Clearly distinguish facts, hypotheses and decisions.
5. Do not silently invent Electricity Maps API capabilities.
6. Verify official documentation before implementing integrations.
7. Avoid premature architecture.
8. Prefer small reversible changes.
9. Keep the project runnable locally.
10. Keep secrets out of Git.
11. Add tests around domain logic and external API adapters.
12. Document meaningful architectural/product decisions.
13. Preserve the ability to change the final product direction.
14. Prefer a working vertical slice over abstract infrastructure.
15. Never optimize technical sophistication at the expense of the user experience.

---

# 25. Immediate Next Step

The immediate goal is NOT to build Windfall, a game, or the final hackathon product.

The immediate goal is:

> **Create a clean, local, extensible Electricity Lab foundation that can consume real Electricity Maps data and provide a safe, tool-based AI agent environment for rapidly experimenting with future experiences.**

Once that foundation works, the project can evolve toward whichever concept proves strongest.

---

# 26. Official / Relevant References

### Hack on the Grid
https://luma.com/hki2v950

### Electricity Maps
https://app.electricitymaps.com/

### Electricity Maps Developer Hub
https://app.electricitymaps.com/developer-hub/api/getting-started

### Hacker Night
https://ida.dk/en/arrangementer-og-kurser/arrangementer/hacker-night-366733

### Microsoft — Engineering the Future
https://msevents.microsoft.com/event?id=978663000

### A Common-Sense Guide to AI Engineering
https://pragprog.com/titles/jwpaieng/a-common-sense-guide-to-ai-engineering/

### OpenClaw
https://openclaw.ai/

---

# 27. Final Project North Star

The project should ultimately answer:

> **Can real electricity data become the foundation for an experience that people genuinely want to interact with — and that makes them understand electricity, energy systems and sustainability better as a consequence?**

The answer is not known yet.

The purpose of the foundation is to make discovering that answer fast, cheap and technically repeatable.
