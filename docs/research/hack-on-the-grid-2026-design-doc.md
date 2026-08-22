# Hack on the Grid 2026 — Product & Game Design Research
### Electricity Maps × Lovable · Copenhagen Climate Week · 11 September 2026

---

## 0. How to read this document

This is a research-and-decision document, not a spec. It moves from raw material → precedent → design space → elimination → one committed concept. Sections 1–9 are the argument. Sections 10–20 are the design. Sections 21–26 are execution.

**One finding overrides everything else and I want it on page one:** the hackathon has published two tracks, and *neither of them is a game*. This changes the strategy materially. See §1.2.

---

## 1. Executive summary

### 1.1 The recommendation

Build **CHARGE** — a daily, real-data flexibility puzzle.

You are handed one battery and one real day on one real grid. Before the day runs, you see only the *forecast*. You paint a 24-hour charge/discharge schedule. You commit. Then the day plays out in twenty seconds against what **actually happened**, hour by hour, and two meters fill in parallel: **money earned** and **carbon moved**. At the end, the game reveals the mathematically perfect schedule laid over yours, and scores you against it like golf: par, birdie, double bogey.

That's the whole game. It takes ninety seconds to play and years to master, because the thing you are actually getting better at is *reading a grid*.

### 1.2 The strategic finding that shapes everything

The official event page defines two tracks: **Sustainability & impact** (carbon-aware automation, smart EV charging, footprint tools) and **Power markets** (BESS charge/discharge optimizers, day-ahead arbitrage signals, cross-border visualizers, "tools that turn complex market data into something anyone can read"). Judging will almost certainly follow those tracks.

A pure entertainment game has no track. It would be judged as an outlier — memorable, possibly, but unplaceable.

CHARGE is engineered to sit **exactly on top of the Power markets track** while being a genuine game. It *is* a BESS charge/discharge optimizer. It *is* a day-ahead arbitrage tool. It is literally the thing the track asks for — "turn complex market data into something anyone can read" — except the reading happens through your hands instead of your eyes. The pitch line writes itself:

> "You asked for a BESS optimizer. We built one where the optimizer is a human, and by hour six they've become one."

This is the single highest-leverage decision in the whole document. Do not pitch it as a game. Pitch it as **an intuition trainer for grid flexibility, delivered as a game.** Same artifact, radically different reception.

### 1.3 Why this and not something else

- The energy-game genre is **saturated on the builder axis** (place power plants, watch a city) and **empty on the operator axis** (commit a schedule, live with the consequences). §5 documents this.
- Builder games can be made with fake data. Operator games cannot — the whole tension comes from real weather being surprising. This is the test for "is electricity essential or decorative," and CHARGE passes it hard.
- The educational literature is unambiguous that learning happens when the learning content *is* the core mechanic, not when it's wrapped around one (§4). In CHARGE, "understand the duck curve" and "score well" are the same action.
- Historical replay makes the demo bulletproof against a boring grid on the day (§18).
- It fits one working day of building. §19 scopes it honestly and §11's kill-list shows what dies first.

---

## 2. What makes electricity uniquely interesting as a game medium

Most "real data games" fail because the data is static (population, GDP, flags) — it can only ever be trivia. Electricity data has five properties that trivia data doesn't:

**1. It has a correct answer that changes every hour.** Chess has one optimal move per position. So does a battery. At 03:00 in a windy DK1 night, charging is right. At 03:00 in a still December night, charging is expensive and dirty. The grid manufactures fresh puzzles forever, for free, in 200+ zones.

**2. It is knowable in advance — but only approximately.** Electricity Maps ships 72-hour forecasts for mix, carbon intensity, load and price. This is the rarest and most valuable game property in the whole dataset: **the player can be given foresight that is good but imperfect.** That single fact creates commitment, risk, regret, and skill. Perfect information is a spreadsheet. Zero information is a slot machine. Good-but-imperfect information is a *game*.

**3. Two scores that usually agree and sometimes viciously don't.** Price and carbon intensity are correlated (wind is cheap and clean) but decouple constantly — cheap nuclear France is clean, cheap coal Poland at 4am is not; a negative-price hour in a gas-marginal system can be cheap and dirty at once. Every time they diverge, the player experiences the real policy tension of the energy transition without being told about it.

**4. Physical constraints that are simple to state and hard to master.** Round-trip efficiency (you lose ~10-15% of everything you store), state of charge (you cannot sell what you didn't buy), cycle limits (degradation is real). Three rules. Enormous strategic depth. This is the "easy to learn, difficult to master" signature.

**5. Genuine drama, verifiable.** Europe recorded a documented surge in below-zero pricing: DK1 alone logged 441 negative-price hours in 2025 (up from 375 in 2024), EU-27 day-ahead markets cleared 1,223 negative hours in Q1 2026 — more than double Q1 2025 — and Spain passed its entire 2025 total by June 2026. Germany's 2025 minimum touched -250 €/MWh. These are not abstractions; they are *levels*, already designed by physics and markets, sitting in the ten years of history the hackathon is opening up.

The property electricity **doesn't** have, and which most people assume it does: it is not naturally a *territory*. The map is where everyone's imagination goes first, and the map is a trap (§6.1).

---

## 3. Research: what makes complex-system games work

Rather than list games, here are the extracted principles and which games prove them.

**Legible causality with delayed cost.** *Frostpunk* is remembered because a decision at hour 2 kills people at hour 30, and you can trace the line. *Factorio* likewise: today's shortcut is tomorrow's spaghetti. The player must be able to *reconstruct* the causal chain afterwards, or the lesson doesn't land. → CHARGE's post-day replay overlay exists precisely for this.

**The optimum must exist and be discoverable.** *Factorio*'s ratios, *Opus Magnum*'s efficiency histograms, and speedrunning all share this: there is a known-better solution, visible, taunting. This converts a one-shot experience into a practice loop. Notably, *Opus Magnum* shows you histograms of everyone else's solutions — social pressure without competition. → CHARGE computes the perfect-hindsight schedule and shows it. This is the design's engine.

**Meaningful decisions are decisions with irreversible cost.** *Civilization*'s tech tree matters because you can't have both. Battery state of charge is a naturally perfect version: energy spent at 09:00 is unavailable at 19:00. No artificial scarcity needed — physics supplies it.

**Compression of time creates emotion.** *SimCity*'s satisfaction comes from watching consequences accelerate. Twenty-four hours in twenty seconds is the right compression: fast enough to feel like a run, slow enough to feel each hour land.

**Short sessions with a shared object create ritual.** *Wordle*'s real innovation wasn't the word game (Mastermind, 1970); it was **everyone solving the same puzzle today**, plus a spoiler-free share format. This turned a solo puzzle into a social event. *Worldle, Globle, Chartle, Pyramiddle, GDPdle* have all copied the shell — which proves the shell works and simultaneously proves that shell-alone is now commodity (§5.3).

**Systems that reward hypothesis-testing.** *Kerbal Space Program* teaches orbital mechanics because failed launches are diagnosable. *Zachtronics* games teach programming because the machine's behaviour is inspectable. The learning is in the debugging, not the winning.

**Why do these stay interesting after five minutes?** In every case: because the player forms a *theory* of the system, tests it, and is proven partly wrong in a way that suggests a better theory. That loop — theory, commitment, surprise, revision — is the actual engine. Everything else is presentation.

---

## 4. Educational game-design insights

The literature here is more decisive than most people assume, and it points at exactly one design principle.

**Intrinsic integration (Habgood & Ainsworth, 2011).** The landmark study built three versions of the same game, *Zombie Division*, differing only in whether the mathematics was embedded in the core mechanic (attack the skeleton with the divisor that divides its number cleanly) or bolted alongside it. The intrinsically integrated version produced significantly better learning outcomes. A 2022 pre-registered replication (n=210, ACM CHI PLAY) found the same effect and attributed the mechanism to **attention** — integrated designs direct attention onto the learning content, rather than merely motivating players to tolerate it. Notably, learning was higher *without* players spending more time on the task.

The practical test that follows: **could you swap the subject matter out and leave the game intact?** If yes, the integration is extrinsic and the education is decoration. A quiz bolted to a dashboard fails this test. Points-and-badges gamification fails this test. A battery scheduler where the physics of storage *is* the rule set passes it — you cannot remove electricity from CHARGE and still have a game, because the puzzle is the price curve.

**Corollaries the literature supports:**

- **Tangential learning** (Portnow) — players voluntarily research context they encountered inside play. Design for it: name the zone, name the date, let the curious click through to the real thing.
- **Progressive complexity via level design, not tutorials.** Introduce one variable per level. CHARGE does this by *zone*: a windy zone teaches volatility, a solar zone teaches the duck curve, a nuclear zone teaches flatness, a coal zone teaches the money/carbon divorce. The curriculum is disguised as a world tour.
- **Failure must be cheap and fast.** Ninety-second rounds mean a bad run costs nothing but a better hypothesis.
- **Do not explain before the player has a question.** Explanation lands when it answers something the player just experienced. Every piece of text in CHARGE appears *after* the relevant surprise, never before.

---

## 5. What already exists

### 5.1 The saturated space: build-a-grid tycoons

*Power to the People*, *Power Network Tycoon* (built by an actual power engineer, with load balancing and physics-based calculations), *Green With Energy*, *electrobillion*, *Power the Grid*, plus dozens of itch.io entries and the classic *Power Grid* board game (Friese, 2004) and its 2026 *Recharged* edition. Assessment: **crowded, competent, and closed.** Anything a hackathon team builds in a day in this genre will be a worse version of a shipped game. Also, critically, none of these need real data — they run on invented economies, which proves real data is not what makes them work.

### 5.2 The thin space: energy education games

*Find the Energy* and similar — exploration + quest + info-card structures. Honest, worthy, and almost entirely extrinsic by the Habgood test: you travel somewhere and are *told* things. This is the failure mode the brief explicitly wants to avoid.

### 5.3 The commoditized space: daily data-guessing games

*Worldle*, *Globle*, *Countryle*, *Chartle* (guess the country from a time series), *Pyramiddle*, *GDPdle*, plus aggregator farms hosting twenty variants each. An "Energle — guess the country from its electricity mix" is the most obvious idea in this entire problem space and would take about forty minutes to build. **Assessment: kill it.** It is derivative, it teaches recognition rather than understanding, and at least one judge will have seen five of them.

### 5.4 The professional space: arbitrage optimization

Rich literature and tooling — day-ahead bidding under price uncertainty, round-trip efficiency modelling, degradation-aware dispatch, RL agents, commercial optimizers (Montel, KYOS, Flex Power). Every one of these is built **for professionals, as software that does the thinking for you.** There is no consumer-legible, playable version. Nobody has built the version where a human does it, badly, and gets better.

### 5.5 The white space

| Axis | Occupied? |
|---|---|
| Build infrastructure over time | Heavily |
| Read a dashboard | Heavily |
| Guess a country from data | Heavily |
| Educational tour with info cards | Moderately |
| Professional dispatch optimization | Heavily (as tools, not play) |
| **Commit a schedule under forecast uncertainty, settle against reality** | **Essentially empty** |
| **Dual-objective play (money vs. carbon) with real divergence** | **Essentially empty** |
| **Real historical grid days as designed levels** | **Essentially empty** |

---

## 6. Unexplored opportunities, and one trap

### 6.1 The map trap

Every energy-data brainstorm converges on a world map with glowing zones. Resist it. On a map, electricity data is a *colour* — decorative, and the interaction degrades to hovering. Electricity Maps *already* has the definitive map, and it is better than anything a hackathon will build. Competing with the host's own flagship product on its home turf is a losing pitch. **Use time as the primary axis, not space.** The 24-hour curve is where the drama lives.

### 6.2 The genuinely unexploited properties

- **Forecast error as a game mechanic.** Nobody plays with this. Everyone treats forecasts as ground truth.
- **Negative prices as a comedy beat.** Being paid to consume is genuinely funny and genuinely instructive. It is also frequent enough to build levels around.
- **The same hour scored two ways.** Money and carbon disagreeing is the entire energy-policy debate compressed into one tooltip.
- **Ten years of history as a level library.** Storm Malik. The 2022 price crisis. Iberian solar noon. These are pre-designed, free, and dramatic.
- **Cross-border flow as a plot twist** — your "clean" hour was clean because a neighbour exported nuclear to you. Flow-tracing makes this visible and it is a real "oh!" moment.

---

## 7. Fifteen experience directions

Condensed. Each differs at the level of player motivation, not skin.

**D1. The Flexibility Operator (→ becomes CHARGE).** Fantasy: you run a battery. Activity: commit an hourly schedule against a forecast, settle against reality. Electricity role: the price/carbon curve *is* the puzzle. Learning: storage economics, duck curves, forecast error, merit order. Motivation: par scoring against a computable optimum. Replay: new zone, new day, forever. Social: shared daily puzzle + score share. Real world: it's a real job. Demo: excellent — 20-second settlement is visual and tense.

**D2. Grid Golf.** As D1 but explicitly a course structure: 9 zones = 9 holes, cumulative score vs. par. Same core; different framing. Folded into D1's progression.

**D3. Forecast Duel.** Predict tomorrow's peak/trough/renewable share; scored when reality lands. Beautifully honest, terrible demo — the payoff is 24 hours later.

**D4. Control Room (co-op).** Real-time supply/demand balancing, frequency drifts, blackouts. High tension, but degrades into a reflex game; the learning is thinner than it looks, and multiplayer in one day is a scope trap.

**D5. Carbon Heist.** Schedule energy-hungry jobs (AI training run, EV fleet, factory) into clean hours across zones. Genuinely on-track for Sustainability & impact. Weaker moment-to-moment tension than D1 — no settlement drama, since scheduling a job is one decision, not a curve.

**D6. Interconnector.** Two players run neighbouring zones and trade across a constrained link. Elegant, teaches flow-tracing and congestion. Multiplayer scope kills it for a one-day build; excellent post-hackathon expansion.

**D7. The Household.** Small-scale: heat pump, EV, dishwasher, tariff. Relatable and directly actionable. But the decision space is tiny and the numbers are small — hard to make dramatic in a demo.

**D8. Grid Archaeology.** Given an unlabelled 24h curve, deduce zone, season, weather. Detective fiction with real data. Delightful for experts, opaque for everyone else. Great as a *side mode*.

**D9. Merit Order.** Drag generators into dispatch order to clear demand at least cost; discover the clearing price. Teaches the single most misunderstood concept in power markets. Static, though — one puzzle type. Good as a mini-game inside a larger frame.

**D10. Blackout 1965.** Narrative replay of real grid failures, decision points, branching. Emotionally strong, but it's an interactive story — replay value near zero, and heavy content authoring.

**D11. The Trader's Desk.** Full market sim, bids, positions, P&L. Too complex to learn in a demo, and it drops the carbon dimension which is the moral centre of the event.

**D12. Grid Pet / Tamagotchi.** A creature that thrives on clean electricity, tied to your real zone in real time. Charming, sticky, mobile-native. But the interaction is passive — you don't decide anything, you just check in. Fails the "make decisions, see consequences" requirement.

**D13. Weather Front.** A weather system sweeps Europe; predict where wind will land and pre-position. Gorgeous, but requires weather data outside the Electricity Maps scope and is hard to ground.

**D14. Zone Draft / Fantasy Grid.** Draft a portfolio of real zones; score weekly on their actual carbon-free percentage. Fantasy-football mechanics, asynchronous, very social. Slow feedback; passive week-to-week.

**D15. The Curve Painter.** Freeform: draw the demand curve you wish existed, and the sim shows what generation would be needed and what it would cost/emit. Sandbox, no goal, no mastery.

---

## 8. Top three

**A. CHARGE (D1+D2).** Battery scheduling under forecast uncertainty, dual-scored, par against a solvable optimum, daily shared puzzle, zones as levels.

**B. Carbon Heist (D5).** Place workloads into clean windows across zones and time; score = carbon avoided vs. deadline pressure.

**C. Control Room (D4).** Real-time balancing against live load and mix; keep the lights on.

---

## 9. Critical comparison

| Criterion | A · CHARGE | B · Carbon Heist | C · Control Room |
|---|---|---|---|
| Fun in 90 seconds | **High** — commit, watch, regret | Medium — scheduling is calm | High — but adrenal, not thoughtful |
| Depth after 10 plays | **High** — optimum is hard | Medium | Low — reflexes plateau |
| Intrinsic integration | **Total** | High | Medium — you learn to react, not to reason |
| Electricity essential? | **Yes** — synthetic data ruins it | Yes | Partly — could be faked |
| Track fit | **Power markets, exactly** | Sustainability, well | Neither, really |
| Buildable in one day | **Yes** | Yes | Risky (real-time loop, failure states) |
| Demo-safe if grid is boring | **Yes** — historical replay | Yes | **No** — live drama can't be summoned |
| Differentiation | **High** — white space | Medium — carbon-aware scheduling is a known category | Medium |
| Memorable after 20 demos | **Yes** — "the golf one" | Medium | Yes, but as spectacle |
| Path beyond the hackathon | Training tool, top-of-funnel, curriculum | Real product, but crowded | Museum installation |

**B** is the strongest *product* and the weakest *experience* — carbon-aware scheduling already exists commercially, and the play is placid. **C** is the strongest *spectacle* and the weakest *learning*. **A** wins on every axis that the brief actually asked about.

---

## 10. The winning concept: CHARGE

> **One battery. One real day. You get the forecast — reality gets the last word.**

### 10.1 Why it wins

It is the only one of the three where **getting better at the game is definitionally the same act as getting better at reading a grid.** There is no gap to bridge, no lesson to bolt on. The scoreboard is the curriculum.

It is also the only one that is simultaneously a legitimate answer to a published track, a genuine game, and demo-proof. That triple is rare and it is worth more than sophistication.

### 10.2 Naming

`CHARGE` is the working title — short, imperative, doubles as verb and noun. Alternatives worth a coin-flip on the day: **Negawatt**, **Par for the Curve**, **Duck** (energy people will grin; nobody else will), **Flexer**. Pick in the morning, don't relitigate.

---

## 11. Why it is fun

- **Commitment creates stakes.** You lock a schedule and cannot touch it. Everything after that is watching your judgment be tested.
- **The 20-second settlement is a slot-machine pull with a brain.** Hour by hour, the money meter and the carbon meter move. You feel the 07:00 price spike arrive whether or not you were ready.
- **Par is merciless and fair.** "You scored 61% of optimal" is a number that itches. Golf has run on this for four hundred years.
- **The reveal produces involuntary noise.** The optimal schedule drops over yours. You see you discharged one hour early and gave away 40% of the day's value. That sound — the *"oh, come on"* — is the product.
- **Negative prices are a joke that pays out.** The first time a player realises they got *paid to charge* and then *sold it at a peak*, they will tell someone.
- **Ninety seconds means "one more."** The cheapest replay loop in games.

---

## 12. Why it teaches

Every scoring rule maps to a real concept, and no concept is ever explained before the player has felt it:

| The player learns | Because the mechanic forces it |
|---|---|
| Storage arbitrage | Buy-low/sell-high is literally how you score |
| Round-trip efficiency | You get back 90% of what you store, every time, visibly |
| The duck curve | Solar zones punish evening unpreparedness |
| Wind volatility & night troughs | DK1 nights are cheap in a way solar zones never are |
| Negative pricing & oversupply | Some hours *pay you* to charge |
| Merit order & marginal generation | Carbon and price diverge exactly where the marginal plant changes |
| Forecast error | The forecast said 40 €/MWh; the day delivered 95 |
| Opportunity cost / state of charge | A full battery at 23:00 is a wasted day |
| Flow-tracing & imports | Your cleanest hour was clean because of a neighbour |
| Why flexibility is valuable at all | You *feel* the value of a MWh moved through time |

That last row is the real payload. Most people cannot explain why storage matters. After six rounds of CHARGE, they can, and nobody told them.

---

## 13. Why Electricity Maps data is essential

Not decorative. Load-bearing, in four distinct ways:

1. **Forecast vs. actual is only possible with both.** Electricity Maps ships 72-hour forecasts *and* matching historical actuals for the same signals — carbon intensity, mix, load, day-ahead price. The core mechanic requires both series to exist for the same hours in the same schema. Very few sources give you that pairing.
2. **Dual scoring requires price and carbon from one methodology.** Flow-traced carbon intensity plus day-ahead price, same zone, same timestamps, same granularity. Stitching two providers would produce mismatched timestamps and a broken game.
3. **Zones-as-levels requires global, comparable coverage.** DK1 vs ES vs FR vs PL vs NO only work as a curriculum because the data is normalized across all of them.
4. **Ten years of history is the level library.** The hackathon opens exactly this. A synthetic price curve would be *less* fun, because it would be smooth, and the entire pleasure of the game comes from real weather doing something unreasonable.

If you remove Electricity Maps from CHARGE, you do not have a worse game. You have no game.

---

## 14. Core game loop

```
 SETUP        A zone + a date. Battery: 100 MWh / 50 MW / 90% round-trip.
                ↓
 BRIEF        You see the FORECAST curve for the day: price and carbon intensity.
              (24 hourly bars. Nothing else. No advice.)
                ↓
 PLAN         Paint the 24 hours: CHARGE / IDLE / DISCHARGE.
              Live constraint feedback: state of charge, cycle count.
                ↓
 COMMIT       Locked. No takebacks.
                ↓
 SETTLE       20 seconds. Hour by hour against ACTUAL data.
              € meter and CO₂ meter fill in real time. Forecast ghost
              vs. actual bar visible as each hour resolves.
                ↓
 SCORE        Your result vs. perfect-hindsight optimum. Par / birdie / bogey.
                ↓
 REVEAL       Optimal schedule overlaid on yours. One sentence of context,
              earned: "You charged through the 14:00 negative-price hour —
              that hour paid €31/MWh to take power. The optimum charged twice."
                ↓
 NEXT         New hole. Or share. Or retry.
```

**Scoring.** Two meters, one score.
`Score = normalize(€ captured) × 0.5 + normalize(CO₂ displaced) × 0.5`, each normalized against the single-objective optimum for that day. Which means: **you cannot max both.** The money-optimal schedule is never the carbon-optimal schedule. The player must choose a philosophy every single day, and the game never tells them which is right. That refusal to moralize is what makes it feel like a game rather than a lecture — and it is also, precisely, the real dilemma.

**Par.** Computed by a straightforward dynamic program over 24 hours × discretized state-of-charge levels. This is a small amount of code and it is the most valuable code in the project: it turns a toy into a sport.

---

## 15. First-time user experience

Second-by-second. This is the part most hackathon projects get wrong.

**0–3s.** One screen. A 24-bar curve, gold-to-red, labelled `DK1 · Denmark West · Tuesday 4 February`. Below it, an empty 24-cell strip. A battery icon at 50%. Headline: *"Buy low. Sell high. Don't burn the planet."*

**3–10s.** The first cell pulses. The player clicks it. It turns blue (CHARGE) and the battery ticks up. **No tutorial.** The mechanic is the affordance.

**10–35s.** They paint. They notice the cheap trough at 03:00 and fill it. They notice the evening spike and discharge into it. They have just performed arbitrage without knowing the word. The carbon curve is drawn faintly behind the price curve — they may or may not notice yet that it doesn't have the same shape. (They will, later, and it will annoy them productively.)

**35s.** COMMIT. Button is large and slightly ominous.

**35–55s.** Settlement. The playhead sweeps. Here is the first designed surprise: **at 08:00 the actual price comes in 60% above forecast**, because the wind dropped. Their carefully-planned charge window was expensive. The meter visibly hesitates.

**55–65s.** Score: *64% of par*. Not a failure. Not a win. An itch.

**65–80s.** Reveal. The optimum's blue blocks sit two hours to the left of theirs. Single line of text: *"The forecast was wrong about the wind. The optimum charged earlier and cheaper."* This is the moment the player learns that forecasts are estimates — a thing they intellectually knew and have now *felt*.

**80s.** Two buttons: **Retry this day** and **Next zone**. Most people press Retry. That is the whole business model of the game, emotionally.

---

## 16. Progression system

Zones are levels, and each zone is a lesson wearing a costume. Order matters:

1. **DK1 · Denmark West** — wind volatility, night troughs, frequent negative hours. *Teaches: the basic arbitrage shape.* (And it is the home grid — a nice local touch in Copenhagen.)
2. **ES · Spain** — the duck curve at full strength; midday solar collapse, brutal evening ramp. *Teaches: solar shapes and the evening peak.*
3. **FR · France** — flat, nuclear-dominated, low carbon, thin spreads. *Teaches: that some grids offer you almost nothing, and why. The player's tactics fail and they must ask why.*
4. **PL · Poland** — coal-heavy. Money and carbon come apart violently. *Teaches: marginal emissions; the cheapest hour is not the cleanest hour.*
5. **DE · Germany** — big, mixed, deeply negative price events. *Teaches: extremes and curtailment.*
6. **Storm day (dated, real)** — a genuine historical extreme event. *Teaches: forecast error at maximum.*

**Difficulty curve** comes from three dials, not from artificial gates:
- **Forecast noise** — early zones use days where forecast and actual agreed; later ones use days where they didn't.
- **Constraint tightening** — cycle limits from 2/day down to 1/day; efficiency from 92% to 85%.
- **Objective weighting** — early rounds are money-only (simpler), then carbon is introduced, then both.

**Mastery signal.** A running "vs. par" average, and a personal best per zone. No XP. No badges. No currency. The score is the reward, because the score is honest.

---

## 17. Collaboration and social model

**Do not build multiplayer.** Real-time multiplayer in a one-day build is where good hackathon projects go to die.

**Do build the asynchronous social layer**, which is nearly free:

- **The daily hole.** Everyone in the world gets the same zone and the same date each day. This is the entire Wordle mechanism and it costs one row in a database.
- **Spoiler-free share string.** Copy-paste, no image generation:
  ```
  CHARGE #47 · DK1 · 4 Feb
  ⚡🟦🟦⬜⬜🟧🟧⬜⬜⬜🟦🟦⬜⬜⬜⬜🟧🟧⬜⬜⬜⬜⬜⬜
  💶 71% par   🌱 88% par   Score 79
  ```
- **Leaderboard for the day.** One table. Names optional.

**Does collaboration deepen understanding?** For the MVP, no — and I'd cut it on that basis. Post-hackathon, yes, in exactly one form: **the Interconnector mode (D6)**, where two players run neighbouring zones sharing a constrained link, and discover that their optimal strategies interfere. *That* would teach something a solo game cannot — that the grid is a commons. Note it as the roadmap headline; build none of it on the day.

---

## 18. Real-time vs. history

**Ship historical replay as the primary mode. Ship live as the garnish.**

| Mode | Verdict |
|---|---|
| **Historical replay (curated days)** | **Primary.** Full control over drama. Forecast and actual both exist and are settled. Demo-proof. Repeatable. Fair — everyone plays the same day. |
| Daily puzzle (yesterday) | **Secondary.** Auto-generates content forever; yesterday's actuals are final by the time you play. Perfect for the social loop. |
| Live / today, forecast-only | **Garnish.** A "Play today's forecast for DK1 — come back tomorrow to settle" mode. One screen. Proves live integration to judges, costs almost nothing, and creates a genuine return-tomorrow hook. |
| Pure real-time (settle as it happens) | **Reject.** Hour-long waits. No. |

**The boring-grid problem is solved by construction.** Pre-select six to ten historically dramatic days and cache them as static JSON before the event. On 11 September at 18:00, whatever the North Sea is doing is irrelevant to your demo. Then use *one* live call on stage to prove the pipeline is real — the live-forecast garnish mode does exactly this in three seconds.

---

## 19. MVP scope for one hackathon day

**Must ship (the demo dies without these):**
- One screen: forecast curve + 24-cell schedule painter + battery state.
- Commit → 20-second animated settlement against actual data.
- Dual meters (€ and CO₂) filling live.
- Perfect-hindsight optimizer (DP) → par score.
- Reveal overlay: optimum vs. yours, plus one generated sentence of context.
- Three pre-cached zone-days: DK1, ES, PL.

**Should ship (in the last two hours, if healthy):**
- Three more zone-days including one storm day.
- Share string + clipboard copy.
- One live API call for a "today's forecast" mode.

**Explicitly out of scope, and say so on stage:**
- Accounts, auth, persistent leaderboards.
- Mobile-optimized layout (demo on a laptop; make it *look* fine on mobile, don't make it work).
- Multiplayer, anything.
- Cycle-degradation modelling, intraday markets, ancillary services, bid curves. Round-trip efficiency and a cycle cap are enough physics.
- A world map. (Say this out loud to the team at 09:15 and again at 13:00.)

**Rough shape of the day:**

| Time | Focus |
|---|---|
| 09:00–10:00 | Fetch and cache all zone-day data. **Do this first.** Nothing else matters if the data isn't local. |
| 10:00–12:00 | Schedule painter + settlement engine (pure functions on cached arrays). |
| 12:00–13:00 | Optimizer + par scoring. |
| 13:00–15:00 | Settlement animation and meters — this is where the *feel* lives; give it real time. |
| 15:00–16:00 | Reveal overlay + contextual sentence generation. |
| 16:00–17:00 | Visual polish, zone selection, share string. |
| 17:00–18:00 | **Freeze. Rehearse the demo three times.** Do not add features after 17:00. |

The single biggest risk to the day is treating the settlement animation as "polish." It isn't. It's the product.

---

## 20. The demo

**30-second pitch:**
> "Everyone says we need grid flexibility. Almost nobody can feel what that means. CHARGE gives you a battery and one real day on a real grid — Denmark, last February. You get the forecast. You commit a schedule. Then reality settles, and you find out what your judgment was worth, in euros and in carbon. It's scored like golf, against the mathematically perfect answer. Ninety seconds a round. And after about six rounds, you can read a price curve."

**3-minute demo, beat by beat:**
1. *(0:00)* Open on DK1. "This is a real day. This is the forecast." Paint a deliberately mediocre schedule out loud, narrating naive reasoning. **Invite a judge to place one block.**
2. *(0:45)* Commit. Watch the settlement together. Let the 08:00 forecast miss land without commentary — let the meter hesitate visibly.
3. *(1:15)* Score. "64% of par." Reveal the optimum. "The wind dropped. The forecast was wrong. That's not a bug in the data; that's the actual hardest problem in the energy transition, and you just lost money to it."
4. *(1:45)* Switch to Poland. Play fast. Money score good, carbon score terrible. "Same strategy. Different grid. In Poland the cheapest hour is a coal hour — price and carbon come apart. Nobody explained merit order to you; you just got punished by it."
5. *(2:30)* One live API call: today's DK1 forecast, loading in front of them. "This is live, right now, from Electricity Maps. Come back tomorrow and it settles."
6. *(2:50)* Close: "Ten years of history, two hundred zones. That's a hundred thousand levels we didn't have to design. Electricity Maps already did."

**Emotional target:** one judge saying "let me try" and reaching for the laptop. Design the demo so that's easy to say yes to.

---

## 21. Open-source opportunities

Chosen for time saved, not for impressiveness.

| Need | Use | Why |
|---|---|---|
| App shell | **Lovable** (React + Vite + Tailwind + shadcn/ui, Supabase optional) | It's the co-host's platform, it's genuinely the fastest path to a polished single-page app, and it produces exportable React. Use it. |
| Charts | **Recharts** or hand-rolled SVG | 24 bars. Honestly, hand-rolled SVG gives better control of the settlement animation than any chart library. Consider skipping the dependency. |
| Animation | **Framer Motion** | The settlement sweep and meter fills. This is the one dependency that directly improves the experience. |
| Optimizer | Write it yourself, ~40 lines | DP over 24 hours × ~20 SoC buckets. No library needed. |
| Data caching | Plain JSON files in the repo | Fastest, most reliable, zero infra, works offline if the venue wifi collapses. **Do this.** |
| Persistence (if needed) | **Supabase** via Lovable | Only if you add the daily leaderboard. Skip otherwise. |
| Zone metadata | **electricitymaps-contrib** (GitHub, AGPL-3.0) | Zone keys, names, capacities, exchange configs. Useful reference; mind the licence if you copy code rather than read it. |
| Coordinate→zone (if ever needed) | **electricitymaps/zone-finder** | Not needed for MVP. Noted for completeness. |
| Maps | **Nothing.** | See §6.1. |

---

## 22. Validated data sources

All Electricity Maps rows verified against the official API reference at `app.electricitymaps.com/api/docs/reference` (v4) on 22 August 2026.

| Data | Source | Official? | URL / endpoint | API | Historical | Real-time | Forecast | Licence | Hackathon usable? |
|---|---|---|---|---|---|---|---|---|---|
| Carbon intensity (gCO₂eq/kWh) | Electricity Maps | Yes | `/v4/carbon-intensity/{past, past-range, history, latest, forecast}` | REST, `auth-token` header | Yes (since 2017) | Yes | Yes (6/24/48/72h) | Commercial ToS | **Yes** — event states full API opened |
| Day-ahead price | Electricity Maps | Yes | `/v4/price-day-ahead/{past, past-range, history, latest, combined, actual, forecast}` | REST | Yes | Yes | Yes (to 72h) | Commercial ToS | **Yes** — note: Europe + a few zones only |
| Electricity mix by source | Electricity Maps | Yes | `/v4/electricity-mix/{past, past-range, history, latest, forecast}` | REST | Yes | Yes | Yes | Commercial ToS | Yes |
| Single-source generation | Electricity Maps | Yes | `/v4/electricity-source/<sourceType>/...` (solar, wind, hydro, nuclear, gas, coal, oil, biomass, geothermal, hydro-discharge, battery-discharge) | REST | Yes | Yes | Yes | Commercial ToS | Yes |
| Cross-border flows | Electricity Maps | Yes | `/v4/electricity-flows/{past, past-range, history, latest, forecast}` | REST | Yes | Yes | Yes | Commercial ToS | Yes |
| Renewable % / Carbon-free % | Electricity Maps | Yes | `/v4/renewable-energy/...`, `/v4/carbon-free-energy/...` | REST | Yes | Yes | Yes | Commercial ToS | Yes |
| Total load / reported load / net load | Electricity Maps | Yes | `/v4/total-load/...`, `/v4/total-reported-load/...`, `/v4/net-load/...` | REST | Yes | Yes | Yes | Commercial ToS | Yes |
| Level signals (high/moderate/low) | Electricity Maps | Yes (Beta) | `/v4/carbon-intensity-level/latest` etc. | REST | No | Yes | No | Commercial ToS | Yes — flagged **Beta** |
| Day-ahead LMP (nodal) | Electricity Maps | Yes (Preview) | `/v4/locational-marginal-price-day-ahead/...` | REST, by `node` | Yes | Yes | **No** (returns 400) | Commercial ToS | Not for this project |
| Zone list & access check | Electricity Maps | Yes | `/v4/zones` (no token → all zones; with token → your access) | REST | n/a | n/a | n/a | — | **Yes — call this first on the day** |
| Zone metadata / capacities | electricitymaps-contrib | Yes (community) | github.com/electricitymaps/electricitymaps-contrib | Repo | n/a | n/a | n/a | **AGPL-3.0** (pre-`cb9664f`: MIT) | Reference freely; be careful about copying code |
| Coordinate→zone offline | electricitymaps/zone-finder | Yes | github.com/electricitymaps/zone-finder | Library | n/a | n/a | n/a | Check repo | Not needed |

**Verified parameters and limits:**
- Auth: `auth-token: <key>` header on every request except `/zones`. Basic Auth also supported.
- Temporal granularity: `5_minutes`, `15_minutes`, `hourly` (default), `daily`/`monthly`/`quarterly`/`yearly` (past only).
- **`past-range` is capped at 10 days at hourly granularity, 100 days at daily.** Loop for more. *This directly constrains your pre-caching script — plan for a loop.*
- Forecast horizons: 6 / 24 / 48 / 72 hours, availability plan-dependent. Event page states 72h is open.
- Carbon intensity defaults to **life-cycle** emission factors and **flow-traced** mix; both switchable (`emissionFactorType`, `flowTraced` / `breakdownType`).
- Estimation: results carry `isEstimated` and `estimationMethod`; `disableEstimations=true` suppresses estimated values. **Use `disableEstimations=true` when picking demo days** so you're playing against measured reality, not modelled reality.
- Zone tiers A/B/C by data quality — **build levels only from Tier A zones.** DK1, DE, FR, ES, PL all qualify.
- Published ToS default rate limit: **150 requests/minute.** The free tier is separately limited to ~50 requests/hour and one zone — irrelevant if the event issues full tokens, but relevant to any pre-event prototyping you do on a free key.

**Marked uncertain, verify on the day:**
- Exact token scope issued at the event (which endpoints, which zones, which horizons). `GET /v4/zones` with your token answers this in one call — make it your first action.
- Whether day-ahead price is enabled for every zone you want as a level. Europe is fine; verify per-zone.
- Post-hackathon licensing for anything you publish. The ToS governs; ask the hosts directly rather than assuming.

---

## 23. Technical implementation direction

Deliberately thin, per the brief.

**Medium:** a single-page web app. Lovable is the co-host and the fastest route to polished React + Tailwind; use it, and export to GitHub so the code is yours.

**Architecture:** there barely is one.
- `/data/{zone}-{date}.json` — pre-fetched, containing `forecast[24]` and `actual[24]` for price and carbon intensity, plus mix for flavour text.
- Pure functions: `settle(schedule, actual) → {revenue, co2, socTrace}` and `optimize(actual) → schedule`.
- React state for the schedule. No backend for the MVP.
- One optional live fetch for the "today's forecast" mode.

**Why no backend:** everything the game needs is 24 numbers × a few signals × a few days. That's kilobytes. Static JSON is faster, more reliable on venue wifi, and removes an entire failure class from your demo.

**The one piece of real engineering** is the optimizer. Discretize state of charge into ~20 buckets, run a DP backwards over 24 hours, maximize the objective, respect efficiency and cycle limits. Test it against a hand-solved trivial case before trusting it. If the optimizer is wrong, par is wrong, and the whole game is nonsense.

---

## 24. Risks and assumptions

| Risk | Severity | Mitigation |
|---|---|---|
| **The game reads as "just a chart"** | Critical | Settlement animation and meters are the entire differentiator. Budget two hours for feel, not twenty minutes. If it doesn't produce a physical reaction in a teammate, it isn't done. |
| **Judges want a tool, not a game** | High | Pre-committed framing: *intuition trainer for flexibility*, on the Power markets track. Never open with the word "game." |
| Optimizer bug → nonsense par | High | Unit-test on a hand-solved 4-hour case. Sanity check: par must always ≥ any human schedule. |
| API token scope narrower than expected | Medium | `GET /v4/zones` first thing. Have a fallback zone set. Cache everything by 10:00. |
| Venue wifi | Medium | Everything static and local. Demo works offline except the one live call — and rehearse the demo *with wifi off* to confirm. |
| `past-range` 10-day cap breaks the fetch script | Medium | Known and documented; write the loop. |
| Scope creep toward a map | Medium | Named and banned in §19. Repeat at 13:00. |
| Dual scoring confuses first-time players | Medium | Ship money-only for round one; introduce carbon at round two. Progressive disclosure. |
| It turns out not to be fun | Medium | **Test the core loop on a stranger by 15:00.** Paper prototype it before the event (§25) so this is already answered. |
| Someone else builds a battery optimizer | Low-medium | Likely, actually — it's in the track description. Yours is the one a non-expert can play. That's the whole differentiation; lean on it. |

**Assumptions being made explicit:** that the event issues tokens with 72h forecasts and price data for European zones (stated on the event page); that judging follows the two published tracks; that a laptop demo is acceptable; that the team can build a polished single-page app in a day with AI assistance (the event page explicitly asserts this).

---

## 25. What to prepare before 11 September

**Do:**
1. **Get a free-tier Electricity Maps key now** and make one successful call. Understand the response shape before the day. Free tier is one zone and ~50 req/hour — enough to learn the schema.
2. **Write the fetch-and-cache script in advance.** It's the least creative and most blocking piece of work. It should take a zone and a date range and emit the JSON your game reads. Handle the 10-day `past-range` loop.
3. **Shortlist candidate days.** Use the free tier plus public reporting to identify dramatic dates: a DK1 negative-price day, a big Iberian solar day, a European storm day, a Polish coal-heavy winter day. Have ten candidates so you can pick the best six with real tokens on the morning.
4. **Paper-prototype the loop.** Print a real price curve. Colour 24 boxes with a pen. Compute the score by hand. Do this with someone who doesn't work in energy. If they don't lean in, you've learned something enormous for the price of a printout. **This is the highest-value hour you can spend before the event.**
5. **Build the optimizer and unit-test it.** Pure logic, no data dependency, no reason to do it under time pressure.
6. **Write the 30-second pitch and memorize it.** Not the demo — the pitch. It's ninety words.
7. **Prepare a visual direction.** One dark-mode screen, energy-appropriate palette (deep navy → amber → red for price, green → grey → black for carbon), one strong typeface. Decide before, don't fiddle during.

**Context from the other two events, honestly assessed:** Hacker Night (9 Sep) and the Microsoft engineering/AI/GitHub day (10 Sep) are useful for the trip and for your own skills, but they should have **no influence on this project**. There is a real temptation — after two days of security and DevOps content — to add auth, CI, telemetry, or an "AI agent" to the hackathon build. Resist all of it. Every one of those would consume hours that belong to the settlement animation. The only crossover worth having is GitHub hygiene: a clean repo, a good README, and a live deploy link for the judges.

**Deliberately do not prepare:** the final zone list, the exact visual polish, the scoring weights, the name, or any of the code that touches feel. Those want to be decided with real data in the room.

---

## 26. What should stay flexible until the day

- **Which zone-days become levels.** Pick with real tokens, in the morning, based on which curves are actually dramatic.
- **Scoring weights** between money and carbon. Tune until par feels achievable-but-not-easy — target a first-time score around 60–70% of par.
- **Whether carbon appears in round one** or is introduced in round two. Test on a stranger and let them decide.
- **Settlement speed.** 20 seconds is a guess. It might be 12. It might be 30. Feel it.
- **The name.**
- **Whether the live mode ships at all.** It's a nice-to-have that proves the pipeline; if the clock is tight, drop it and describe it instead.
- **Team roles.** If you find a designer at the event, hand them the settlement screen immediately and go build the optimizer.

---

## Appendix: the one-line test

If at any point during the day someone asks *"should we add X?"*, the answer is determined by a single question:

> **Does X make the twenty seconds after COMMIT better?**

If not, it's a post-hackathon feature. Write it on the roadmap slide and move on.
