# Electricity Data as Raw Material
### A pre-ideation research atlas — Hack on the Grid 2026

*Objective: not "find the best app," but map what electricity data could become if it stopped being an energy-management product.*

---

## PART 1 — THE RAW MATERIAL

### What the data actually is

The Electricity Maps API exposes a signal set that is much wider than "carbon intensity": carbon intensity (lifecycle and direct), fossil-only carbon intensity, renewable percentage, carbon-free percentage, day-ahead price, day-ahead LMP (preview), electricity mix (production *and* consumption breakdown), electricity flows, electricity source, total load, total reported load, net load, and bucketed "level" signals (beta) that pre-classify a zone as low/medium/high. These come in three temporalities — past, real-time, forecast — at granularities from five minutes to yearly, across hundreds of zones, with 24–72h ahead forecasts available for carbon intensity and power breakdown.

Four properties matter far more than the signal list, and most people miss all four:

**1. Flow-tracing is a provenance engine, not an accounting method.**
Electricity Maps traces imports back through the network to compute a *consumption* mix. That means the data can answer "where did the electricity in this room come from" as an ancestry, not a statistic. This is narrative material. It is closer to a wine appellation or a family tree than to a KPI.

**2. The API ships the prediction and the answer.**
Forecast endpoints and past endpoints cover the same variables. That is a complete scoring loop, for free. Any prediction game needs a ground truth and a published prior — this dataset has both, on a 24-hour cycle, forever.

**3. The zones are a fixed roster with stable identities and head-to-head relationships.**
Hundreds of named entities, each with a personality (Norway = hydro, Poland = coal, France = nuclear, Denmark = wind, Iceland = geothermal), each with directed physical connections to specific neighbours. That is the structure of a sports league, not a spreadsheet.

**4. Volatility is now structural, not exceptional.**
2025 set records for negative pricing across Europe. Germany logged 573 hours of negative day-ahead prices, up 25% year on year; Sweden, the Netherlands, Spain, Belgium, and France each cleared 500+ hours. The share of negative-price hours hit 6–9% in several markets. Germany's *average daily* day-ahead spread in 2025 was around €130/MWh. Since October 2025 the European day-ahead market clears in quarter-hourly intervals, which multiplies the number of discrete resolvable events by four. Q1 2026 EU-27 negative hours more than doubled year on year.

The data is no longer a slow-moving environmental indicator. It is a high-frequency, high-variance, event-dense feed with a public forecast attached.

### Dimensions → human behaviour

Not features. Activities.

| Dimension | Human behaviour it could enable |
|---|---|
| **Geography** | Rooting for a place. Feeling superior to a neighbour. Travelling to somewhere because of its grid. Discovering that a country you'd never think about is the cleanest in Europe today. |
| **Time (hour)** | Waiting. Choosing *when* rather than *whether*. Doing chores at 2am as a flex. Setting a personal ritual around a moment of the day. |
| **Time (season)** | Anticipating a season the way people anticipate hurricane season or the first snow. Dreading Dunkelflaute. Celebrating the first day solar beats coal. |
| **Price** | Bargain-hunting. Bragging about getting paid to run a dryer. Making a bet with a friend. Feeling clever. |
| **Negative prices** | Treating electricity as a *found object* — free stuff, briefly, if you're paying attention. This is a scavenging behaviour, not an optimisation behaviour. |
| **Carbon intensity** | Moral positioning. Guilt. Absolution. Arguing about nuclear at dinner. |
| **Generation mix** | Identifying a place by its fingerprint. Collecting. Comparing. Learning a country by its texture rather than its flag. |
| **Renewables** | Cheering. Watching a record fall. Following a specific wind farm or a weather front as if it were an athlete. |
| **Demand / load** | Seeing a society's schedule — when a country wakes, eats, sleeps. Noticing a holiday from the load curve. Feeling collective. |
| **Net load** | Recognising the shape of a day. Duck curves are visually distinctive; people can learn to read them like handwriting. |
| **Forecasts** | Predicting. Disagreeing with a forecast. Being right. Being right *publicly*. |
| **Cross-border flows** | Feeling dependency, patronage, rescue, and debt between countries. Noticing when a flow reverses. Diplomacy metaphors. |
| **Imports/exports** | Scorekeeping between neighbours. Grudges. "We carried you last night." |
| **Historical events** | Storytelling. Anniversary content. Grief for a decommissioned plant. Reliving the Iberian blackout. |
| **Volatility** | Thrill-seeking. Watching something jump. Screenshotting an extreme. |
| **Anomalies** | Spotting. Collecting. Reporting. Being the first to notice. |
| **Scarcity** | Solidarity, rationing behaviour, civic drama, the pleasure of a shared constraint. |
| **Surplus** | Waste-horror ("we threw that away"), opportunism, festival behaviour. |
| **Uncertainty** | Speculation, argument, hedging, humility. |
| **Correlations** | Detective work. "Why did Belgium spike when the wind died in the North Sea?" |
| **Dependencies** | Alliance-thinking, geopolitics as physics. |
| **Change over time** | Progress narrative, nostalgia, generational comparison ("the grid you were born into"). |

---

## PART 2 — MECHANISM TAXONOMY FROM OTHER WORLDS

Stripped from products, expressed as mechanisms.

### A. Epistemic mechanisms — "I know something"
- **Resolvable prediction.** A question with a date and an answer. (Prediction markets, weather contracts.) The essential ingredient is *settlement*, not stakes.
- **Public prior to disagree with.** Value comes from having an edge against a visible consensus. (Betting lines, market odds, forecast models.)
- **Incomplete information reveal.** Clues released in sequence. (Wordle, Semantle, guessing games.)
- **Discovery.** Finding something that was always there but unnoticed. (Birdwatching, GeoGuessr, flight tracking.)
- **Counterfactual reasoning.** "What if X hadn't happened." (Sports what-ifs, alt-history, Football Manager.)
- **Detective inference.** Explaining a weird observation. (Reddit mystery communities, market post-mortems.)

### B. Agonistic mechanisms — "I beat someone"
- **Head-to-head.** Two entities, one winner, today.
- **Ranking / league table.** Ordinal position, with *lead changes* as the actual product.
- **Relative-to-expectation scoring.** Sports advanced stats. Rewards the underdog's good day. Critically: this creates lead changes where raw levels would be static.
- **Streaks.** Personal record against yourself.
- **Draft / roster ownership.** Fantasy sports. Attachment through *choice*, not through pre-existing loyalty.
- **Territorial control.** Risk, Civ, r/place. Visible, spatial, zero-sum.

### C. Economic mechanisms — "I allocated well"
- **Scarcity under a budget.** Limited resource, competing uses.
- **Arbitrage.** Buy low, sell high, across time or space.
- **Risk/reward asymmetry.** Big call, big consequence.
- **Portfolio construction.** Diversification as an expressive act.
- **Market-making.** Setting a price others trade against — a fundamentally social act.

### D. Temporal mechanisms — "it's time"
- **The drop.** A fixed daily moment when new information lands. This is the single most underrated engagement mechanic in existence. Octopus Agile's ~4pm price publication is a genuine daily ritual for tens of thousands of UK households.
- **One puzzle per day.** Artificial scarcity of play. Wordle's actual innovation.
- **Live event.** Something unfolding right now that you might miss.
- **Season arc.** A long structure with a beginning and end.
- **Time pressure.** Decisions with a shot clock.
- **Ambient glance.** Sub-second consumption. Weather apps, watch faces, wallpapers.

### E. Narrative mechanisms — "then what happened"
- **Protagonist.** Someone/something to attribute agency to.
- **Rivalry.** A persistent grudge with history.
- **Anomaly-as-plot.** The weird event that demands explanation.
- **Named events.** Hurricanes get names. Naming converts a statistic into a character.
- **Serial cliffhanger.** "I wonder what happens tomorrow."

### F. Collection mechanisms — "I have it"
- **Rarity tiers.** Some things are hard to get.
- **Set completion.** The gap in the album is the motivation.
- **Provenance / stamps.** Passport logic. Proof you were there.
- **Minting from reality.** Collectibles generated by real events cannot be farmed — which is exactly what makes them feel real.

### G. Social mechanisms — "look"
- **Spoiler-free share format.** Wordle's grid. The share must be legible *and* contentless.
- **Social comparison.** Same puzzle, different result.
- **Tribe membership.** In-group vocabulary and shared references.
- **Cooperative goal.** A thing only a crowd can do.
- **Public identity.** Your record is visible and persistent.

### H. Somatic / aesthetic mechanisms — "it feels like something"
- **Sonification / synaesthesia.** Data as sound, colour, texture.
- **A creature to care for.** Tamagotchi transfer of concern.
- **Physical object.** An ambient device in a room changes behaviour more than an app.
- **Beauty without comprehension.** People will watch a thing they don't understand if it's gorgeous.

---

## PART 3 — THE STRANGE QUESTION APPLIED

For each mechanism: what if electricity data were the raw material?

- **Resolvable prediction** → Every hour of every day already resolves. Europe generates ~24 settled outcomes per zone per day, or 96 at quarter-hourly resolution. The scoring engine already exists.
- **Public prior** → The day-ahead forecast *is* the betting line. The interesting product isn't predicting the price; it's predicting where the forecast will be **wrong**. Forecast error is the alpha, and it's the thing nobody has ever made legible to a layperson.
- **Incomplete information reveal** → A 24-hour generation-mix curve is an unlabelled fingerprint. Reveal it slowly and you have a deduction game with 200+ possible answers and a new one every day.
- **Discovery** → Somewhere on Earth right now, something strange is happening on a grid. Nobody has ever built the "rare bird alert" for grids.
- **Counterfactual** → Real historical data can be replayed with one assumption swapped. "Germany with its nuclear fleet, April 2025." This is emotionally explosive and completely unbuilt for the public.
- **Head-to-head** → Zone vs zone, one metric, one day. Instantly legible.
- **Ranking** → *Naive rankings are dead on arrival.* Iceland always wins the clean league; Poland always loses. There are no lead changes, so there is no product. Rankings only work when scored **against each zone's own baseline**, which is exactly what sports advanced metrics do.
- **Relative-to-expectation** → "France underperformed its own average by 2.3 sigma today." Now Poland can have a great day and Norway can have a bad one. This single reframe is what makes a league possible.
- **Draft** → Draft five zones. You don't need to already care about Estonia; you care because you *picked* it. Fantasy sports solves electricity's fatal attachment problem.
- **Territory** → Physical flows look territorial but aren't. They're mostly stable, physics-bound, and rarely reverse dramatically. Risk-like conquest is the *weakest* of the game metaphors here (see Part 7).
- **Arbitrage** → A virtual battery on real prices is a complete resource-management game with a real, verifiable P&L. €130/MWh daily spreads mean the game is not trivial and not hopeless.
- **The drop** → Day-ahead auction results land at a fixed time each day. Europe already has a daily reveal moment and almost nobody has dramatised it.
- **Named events** → No European weather-driven scarcity event has ever been named. Hurricanes have names. Dunkelflautes don't. Naming is nearly free and changes everything about how an event is discussed.
- **Collection** → Grid anomalies are unfarmable, timestamped, and rare. A record negative price is a legitimately scarce collectible.
- **Provenance stamps** → Every place you physically go, you consume from a zone. That's a passport.
- **Spoiler-free share** → A 24-hour mix curve renders as a coloured bar or sparkline. It is *already* a shareable glyph.
- **Sonification** → Mix = instrumentation, load = tempo, carbon = key. A country's day becomes a piece of music that is different every day and never repeats.
- **Creature** → A pet whose mood tracks your zone's carbon intensity. The user never sees a number and never learns a unit, and still develops correct intuitions about when the grid is clean.
- **Beauty without comprehension** → 200 zones, colour-coded, animated over a day, is genuinely beautiful and requires zero literacy.

Further provocations worth holding open:

- What if the user's *body clock* were the interface — the app only ever tells you "now" or "wait"?
- What if electricity data were a horoscope?
- What if a grid event triggered a real-world happening (a bar offers free coffee when prices go negative)?
- What if the product were a radio station whose playlist is chosen by the grid?
- What if two people in different countries could compete over whose grid was cleaner *this hour*, as a couples/friends thing?
- What if the map were replaced by a single colour filling the screen?
- What if the product had no map, no chart, no number, and one sentence?

---

## PART 4 — WHAT PEOPLE ALREADY DO (EVIDENCE)

### The honest headline
**A large, genuinely habitual audience for electricity data already exists — and it is almost entirely mediated by money. Every other motivation is nearly unserved.**

### Where real voluntary behaviour exists

**Dynamic-tariff households (strong, real, daily).** Octopus Agile in the UK publishes next-day half-hourly rates around 4pm; customers check them daily and plan around them. There is a whole third-party ecosystem: unofficial iOS apps with Apple Watch complications and Siri shortcuts, Raspberry Pi LED price panels, Home Assistant integrations, battery-management tools, TeslaMate cost integrations. Tibber (Nordics/Germany/Netherlands) has the same pattern, including a customer-built Garmin watch face showing live spot prices. Amber Electric does this in Australia. People on these tariffs post publicly to boast when they get free or negative-priced power.

This is *real habit formation around electricity data*. But note the gating: it requires a dynamic tariff, usually a smart meter, often a battery/EV/heat pump. It's a homeowner-with-hardware hobby. And the motivation is savings plus tinkering pleasure — not curiosity, not competition, not status beyond a small in-group.

**Energy analysts and "energy Twitter/LinkedIn" (moderate).** Ember and similar organisations produce charts that circulate widely. Negative-price milestones get written up repeatedly across trade and mainstream press. Substack analysts publish price post-mortems. Contested topics (who pays for "free" electricity, nuclear vs renewables) generate genuine argument.

**Forecasting competitions (narrow but proof-carrying).** GEFCom and the 2024 Hybrid Energy Forecasting and Trading Competition required daily day-ahead forecasts and market bids, scored on pinball loss and on trading revenue. These prove that *skill exists and is separable from luck* in exactly this data. They are also entirely expert/ML-flavoured — no lay audience.

**Weather prediction markets (the closest mass-market analogue, and it's booming).** Kalshi and Polymarket run daily temperature, snowfall, and rainfall contracts; a single January snowstorm cleared over $6 million on Kalshi. Traders describe temperature contracts as one of the few corners where a genuinely quantitative edge exists, precisely because the underlying is governed by physical models and settles against a hard, verifiable number rather than sentiment. Physical-variable prediction *does* attract non-experts. This is the single best external evidence for the hypothesis.

**Live grid drama (episodic but explosive).** The April 2025 Iberian blackout was followed live by an enormous general audience. Dunkelflaute is now a word civilians use. Grid events *can* be spectator events — they just have to be visible while happening.

### Where almost nobody does anything

**Play.** There is essentially one Wordle-like in this space: *griddle*, a hobby project where you guess a country from its grid-mix visualisation across 20×20 grids, with hints revealed per wrong guess, streaks, and leaderboards. It uses Ember's annual data, not live data. Its own author describes it as a janky pre-alpha he played for hours instead of working — which is a very useful signal about latent appetite.

Everything else described as an "energy game" is a **simulation disconnected from reality**: *Power Grid* (board game, abstract), *Grid Town* (browser sim of a fictional town), NESO's "Balancing the Grid" educational toy, *Green With Energy* on Steam. All fictional grids.

**No shipped product uses live, real electricity data as game state.** That is the biggest single finding in this document.

**Compete.** Outside expert ML leaderboards, there is no public competitive layer over electricity data at all. No leagues, no head-to-heads, no fantasy, no public prediction records.

**Collect.** Nothing.

**Non-monetary curiosity.** Nearly nothing. Outside dynamic-tariff countries, the median European has *no daily relationship whatsoever* with electricity data, and the ones who do have it because of a bill.

---

## PART 5 — WHY WOULD ANYONE COME BACK TOMORROW?

### What genuinely changes every day
- Day-ahead prices clear once per day at a fixed hour. **This is a natural, unexploited daily "drop."**
- Weather regimes shift; forecast error is fresh daily.
- Rankings reshuffle *if scored against baseline* (they don't if scored on raw levels).
- Flows reverse; a country that exported yesterday imports today.
- Negative-price events occur several times a week in season, in multiple zones.
- Records fall regularly — solar peaks, wind records, longest negative streak.
- Seasonal arcs exist: solar season, Dunkelflaute season, hydro melt.

### The honest problem
**Most days are boring, and the boringness is invisible to the designer during a hackathon in September.** Electricity is highly autocorrelated. Tuesday looks like Monday. Any product that relies on "something interesting will happen" will have long dead stretches.

So the return mechanism cannot be "check if something happened." It must be one of:

1. **A question that resolves.** You made a call yesterday; today you find out. This works on boring days, because your prediction is the drama, not the grid.
2. **A streak you own.** Loss aversion works on boring days.
3. **A roster you chose.** Your zones play every day, even quietly.
4. **A daily puzzle that is always new** because the underlying data is always new — even boring data makes a fresh puzzle.
5. **A named ongoing event with an arc.** Storm-tracking logic: the anticipation is the product.
6. **A social obligation.** Someone is waiting for your pick.

The notification worth opening is almost never "carbon intensity is now 240 gCO₂/kWh." It is:
- *"You were right. Nobody else was."*
- *"Prices go negative in your zone for 4 hours tomorrow afternoon."*
- *"Your streak ends in 3 hours."*
- *"Belgium just did something that hasn't happened since 2019."*
- *"Denmark beat Germany for the seventh day running."*

The shareable artefact is almost never a chart. It's a **glyph** (a coloured day-bar), a **verdict** (I called it), or an **absurdity** (a country ran on 137% renewables and gave the surplus away).

---

## PART 6 — LOOK / ACT / PLAY / COMPETE

**A. LOOK — saturated.**
Electricity Maps' own map, national TSO dashboards, gridwatch clones, carbon-intensity widgets, Home Assistant cards. Extremely well served. Any new dashboard is dead on arrival at a hackathon.

**B. ACT — partially served, heavily gated.**
Smart charging, battery optimisation, appliance scheduling, carbon-aware compute scheduling. Real and valuable, but requires hardware, a dynamic tariff, or a data centre. **The unserved part of B is the low-stakes, no-hardware action**: what should a normal person with no battery and a fixed tariff *do* today? Almost nobody has answered this, partly because the honest answer is often "nothing much" — which is a design problem, not a dead end. Reframing from *save* to *time* (bread, laundry, a shower, a bath, a run, a charge) is nearly virgin territory.

**C. PLAY — nearly empty.**
One hobby Wordle-like on annual data. Everything else is fiction. **The entire category of "play with live grid data" is open.**

**D. COMPETE — empty.**
Only expert forecasting competitions. No consumer competitive layer exists anywhere.

**C and D are the white continents. B is a coastline with unexplored inlets.**

---

## PART 7 — THE GAMING/PREDICTION HYPOTHESIS: ATTEMPTED DEMOLITION

*Hypothesis: Electricity Maps contains the ingredients for something closer to Risk / fantasy sports / prediction markets / trading / live sport than to a dashboard.*

### The case against (taken seriously)

**1. Persistence makes prediction boring.**
Grid variables are heavily autocorrelated. A naive "same as yesterday, adjusted for the published forecast" strategy captures most of the variance. If everyone can copy the public forecast, skill differentials collapse and the game becomes a coin flip on residuals. **This is the strongest objection.**
*Rebuttal:* This is also true of weather markets, which are booming anyway — because the game is played on the *residual*, and residuals are where the interesting physics lives. Renewable forecast errors are precisely what drive negative-price events. Design the game on forecast error, spreads, and event occurrence, never on levels.

**2. There is no pre-existing rooting interest.**
Sports work because you already love a team. Nobody wakes up caring about Belgium's carbon intensity. **This is the actual binding constraint, and it is more dangerous than any data limitation.**
*Rebuttal:* Fantasy sports solved exactly this problem — attachment through *drafting*, not through pre-existing loyalty. People who don't watch football care intensely about a running back they picked. Any electricity competition must manufacture ownership in the first ten seconds.

**3. Outcomes are illegible.**
gCO₂/kWh is not a felt quantity. Most people cannot tell whether 180 is good.
*Rebuttal:* Solvable, and the API already helps — the "level" signals bucket zones into low/medium/high. But it means any number-forward design is at risk. The winning designs will use ordinal, comparative, or sensory encodings, not units.

**4. Settlement risk.**
Data is estimated for some zones, revised after the fact, and occasionally delayed. Any competitive product where a score changes retroactively will lose trust instantly. This is a real, underrated engineering hazard for a one-day build.
*Rebuttal:* Constrain to zones with strong direct reporting and to signals that settle cleanly (day-ahead price is auction-settled and does not get revised).

**5. Feedback is too slow for a session.**
A day-ahead call resolves in 24+ hours. That's terrible for a five-minute demo and worse for a first session.
*Rebuttal:* Nested loops. An instant deduction/puzzle layer that resolves in 30 seconds, wrapped around a slow prediction layer that resolves tomorrow. Wordle resolves instantly; the *streak* is the slow loop.

**6. Territory/Risk mechanics are the weakest analogue.**
Cross-border flows look like conquest but behave like plumbing. Direction is set by price differentials and physics, changes are usually undramatic, and interconnector capacity is fixed. There is no agency, no strategy, and few surprising reversals. A Risk-like map would be visually seductive and mechanically inert. **Partially disproven — this specific sub-hypothesis should be dropped.**

**7. Static rankings.**
Iceland is always cleanest. Poland is always dirtiest. A naive league has no lead changes and therefore no reason to return. **Disproven as stated — but repaired by relative-to-expectation scoring.**

**8. Would it be fun for five minutes / five days / as a habit?**
- Five minutes: yes, easily — a deduction puzzle or a head-to-head pick is instantly fun.
- Five days: yes, *if* something resolves and a streak exists.
- A habit: unproven, and the honest answer is that nobody knows, because nobody has tried. The existence of a hobbyist who played his own janky grid-guessing game "for hours" is a data point of exactly one.

### Verdict

**Supported, with two amputations and one amendment.**

Amputated: **territorial control** (flows aren't conquest) and **live-sport spectating** (too slow, too illegible, no stakes, and the drama is discontinuous).

Amended: the strongest structural analogues, in order, are
1. **Fantasy sports** — solves attachment, tolerates boring days, has a natural season.
2. **Daily deduction puzzle** — solves instant legibility and shareability, needs no domain knowledge.
3. **Prediction/market mechanics on residuals** — has genuine skill, verified by the existence of professional forecasting competitions and by the success of physical-variable weather markets.
4. **Resource-management/arbitrage sim on real prices** — €130/MWh average daily spread means real decisions with real consequences.

The properties that make it promising, specifically:
- **The API contains both forecast and outcome** → a free, permanent scoring engine.
- **Event density is now high** → 500–600 negative-price hours per year in multiple zones; quarter-hourly resolution since Oct 2025.
- **The roster is fixed, named, and characterful** → league structure without needing to invent entities.
- **Weather is a shared, public, exogenous driver** → an amateur can form a hypothesis from a weather app, which makes skill *accessible* rather than *expert-gated*.
- **There is a natural daily drop moment** → anticipation infrastructure already exists, unexploited.

The property that could kill it: **nobody has a reason to care which zone wins.** Solve that in ten seconds or the whole thing collapses.

*(No real-money mechanics. Play-money, reputation, and streaks carry all the same psychology without the harm — and weather markets suggest the prediction itself, not the payout, is what people find compelling.)*

---

## PART 8 — 50+ RESEARCH HYPOTHESES (DELIBERATELY STRANGE)

**Entertainment & spectator**
1. Named scarcity events, tracked like hurricanes.
2. A daily 60-second "grid weather report" in vertical video.
3. Live commentary over a real Dunkelflaute as it develops.
4. A live blackout-anniversary re-broadcast, minute by minute.
5. Zone rivalries with persistent head-to-head records and grudge pages.
6. Grid "player cards" with advanced stats.
7. An annual awards show for grids (Most Improved, Biggest Choke).
8. Post-match analysis of yesterday's weirdest hour.

**Games & competition**
9. Guess-the-zone from an unlabelled 24h mix curve.
10. Draw tomorrow's price curve with your finger; scored on shape distance.
11. Fantasy league where you draft zones and score against baseline.
12. Daily head-to-head: two zones, one metric, pick a winner.
13. Virtual battery trading on real prices, ranked P&L.
14. Play the system operator for five minutes on a real historical day.
15. Guess the year *and* the country from a mix alone.
16. Co-op puzzle: a crowd collectively predicts a continent's day.
17. Spot the anomaly in a wall of 200 live sparklines.
18. A game where the only input is "now" or "later."
19. Blind taste test: which of these two days had lower emissions?
20. Speedrun: find the cleanest hour in Europe in under 10 seconds.

**Prediction & markets (play money only)**
21. A daily question that resolves at the auction.
22. Make markets on grid propositions against other players.
23. Forecast-error league: beat the official forecast, not the outcome.
24. Calibration scoring — reward honest uncertainty, not bravado.
25. A public track record you carry like a chess rating.

**Collection & identity**
26. Collectible cards minted from real, timestamped anomalies.
27. An electron passport: stamps for every zone you've consumed from.
28. Set completion: witness all 12 generation types live.
29. Rare-event alerts, birdwatching-style.
30. Your birth-grid: the mix on the day you were born.

**Art & sensory**
31. Sonification: mix as instrumentation, load as tempo.
32. A radio station whose playlist the grid selects.
33. A single full-screen colour that *is* the grid right now.
34. Generative art minted daily from your zone's curve.
35. A physical ambient object — a lamp, a stone, a clock hand.
36. Grid as weather-textile: knit a scarf, one row per day.
37. A perfume/flavour metaphor: today's grid tastes like…
38. Choreography driven by cross-border flows.

**Social & community**
39. Long-distance couples competing on whose grid is cleaner.
40. Office/flat-share leagues.
41. A subreddit-style feed where anomalies get explained by the crowd.
42. Group chat bot that posts the daily glyph.
43. City-vs-city civic challenges.
44. A cooperative goal only achievable if enough people shift together.

**Education & narrative**
45. Counterfactual replayer: real history, one assumption swapped.
46. "Grid you were born into" vs "grid your child will inherit."
47. A serialised daily story where the protagonist is a country.
48. Teach a country's economy from its load curve alone.
49. Explain a holiday by the dip in demand.
50. A grid horoscope — absurd on purpose, correct underneath.

**Ritual & habit**
51. A morning "when should I do the thing today" single answer.
52. A bread/laundry/bath timer keyed to the cleanest window.
53. A bar that gives free coffee when prices go negative.
54. A daily glyph you screenshot and post, Wordle-style.
55. A Tamagotchi whose mood is your grid's carbon intensity.

**Genuinely absurd**
56. Grid-based dating: matched by compatible consumption curves.
57. A country's grid rendered as a face whose expression changes.
58. Fantasy funeral for retiring power plants.
59. Betting on which neighbour rescues whom tonight.
60. A screensaver that is 200 zones breathing.

---

## PART 9 — THE IDEA ATLAS

Rather than a full 11×11×6×6×8 matrix (mostly empty), here are the **coordinate combinations that actually have tension in them** — where the axes reinforce rather than cancel.

| # | Motivation | Interaction | Temporality | Sociality | Output | Why this cell is alive |
|---|---|---|---|---|---|---|
| 1 | Prediction + status | Predict | Daily (drop) | Leaderboard | Score | The forecast/outcome pair is a free scoring engine; the drop is a free ritual |
| 2 | Competition + entertainment | Compete | Daily, season | Versus | Ranking | Fantasy solves attachment; baseline-relative scoring creates lead changes |
| 3 | Curiosity + learning | Explore | Real-time | Solo | Story | You learn a country by its texture, not its flag |
| 4 | Discovery + status | Collect | Real-time | Community | Collection | Anomalies are unfarmable and timestamped — genuinely rare |
| 5 | Entertainment | Observe | Daily | Public | Story | Named events + arcs; hurricane logic |
| 6 | Money (play) + control | Trade | Hourly | Leaderboard | Score | €130/MWh spreads make arbitrage non-trivial and non-hopeless |
| 7 | Utility + control | Decide | Hourly | Solo | Decision | The un-gated version: no hardware, one sentence, "now or later" |
| 8 | Learning + counterfactual | Simulate | Historical | Public | Simulation | Real data, one swapped assumption — argument-generating |
| 9 | Entertainment + curiosity | Observe | Real-time | Solo | Map | Beauty without literacy; no numbers at all |
| 10 | Status + social | Share | Daily | Public | Glyph | The 24h curve is already a shareable, spoiler-free mark |
| 11 | Environmental + play | Create | Daily | Solo | Art | Generative art from a curve that never repeats |
| 12 | Curiosity + identity | Explore | Historical | Solo | Story | Your birth-grid; provenance as autobiography |
| 13 | Competition | Predict | Forecast horizon | Cooperative | Prediction | Crowd forecast vs official forecast — a collective epistemic project |
| 14 | Control + entertainment | Optimize | Historical | Versus | Score | Play the operator on a real past day; everyone gets the same day |

**Dead cells worth naming:** anything (observe × real-time × solo × map) that isn't visually extraordinary is the existing product. Anything (optimize × real-time × solo × decision) requires hardware most people don't have. Anything (compete × territory) is mechanically inert.

---

## PART 10 — WHITE SPACES

Areas where the data is rich, existing products are weak, behaviour could plausibly emerge, the visuals are strong, it's one-day buildable, and it explains in 10 seconds.

1. **Live data as game state.** Every existing energy game runs on a fictional grid. Nothing plays on today's real one.
2. **The day-ahead drop as a dramatic moment.** A fixed daily information release with zero ceremony built around it.
3. **Forecast error as the subject.** Everyone publishes forecasts; nobody has made *being wrong* legible, trackable, or entertaining.
4. **Baseline-relative performance.** Sports invented advanced stats to make bad teams interesting. Electricity has no equivalent — every ranking is raw and therefore frozen.
5. **Attachment-by-drafting.** No mechanism anywhere lets a person *choose* a grid to care about.
6. **Named events.** Weather names storms. Energy names nothing. Free narrative infrastructure, unclaimed.
7. **Anomalies as collectibles.** Timestamped, verifiable, unfarmable rarity — and nobody has minted a single one.
8. **The no-hardware action.** Everything actionable assumes a battery, an EV, or a tariff. The person with none of those has no product at all.
9. **Provenance as identity.** Flow-tracing can tell you where your electricity came from as an ancestry. This is used for corporate accounting and never for wonder.
10. **Non-numeric interfaces.** Levels, colours, sounds, creatures. Almost every product in this space leads with a number and a unit.
11. **The public counterfactual.** Real history, one variable swapped, rendered instantly. Politically explosive, technically simple, entirely unbuilt for laypeople.
12. **Two-person social forms.** Everything is solo or global. Nothing is *you and one other person*.
13. **Spoiler-free share glyphs.** The 24h curve is a natural Wordle-grid analogue and nobody uses it that way.
14. **Cross-zone simultaneity.** 200 places, same instant, wildly different states. This is inherently astonishing and almost never dramatised.

---

## PART 11 — 20 CONCEPT SEEDS

---

**1. THE REVEAL**

*Human behaviour:* Wait for a daily announcement and find out if you were right.
*Core mechanic:* Before the day-ahead auction publishes, you draw or pick tomorrow's price/carbon shape. Tomorrow you're scored.
*Electricity mechanic:* Day-ahead price + published forecast + settled outcome.
*Why return:* Your call resolves at a fixed time every day. The drama is yours, not the grid's — so boring days still work.
*10-second explanation:* "Guess tomorrow's electricity, find out at lunchtime."
*Wow moment:* The countdown hits zero, the real curve draws itself over your guess.
*Why Electricity Maps:* Forecast and outcome in one API, for hundreds of zones.
*Main risk:* Copying the public forecast may be near-optimal, flattening skill.

---

**2. WATTFOLIO**

*Human behaviour:* Draft a team and follow it all season.
*Core mechanic:* Pick five zones. Each day they score against their own 30-day baseline. Trades, waivers, a season table.
*Electricity mechanic:* Renewable %, carbon intensity, and net load, scored as z-scores rather than levels.
*Why return:* You own these zones. They play every day, even quietly.
*10-second explanation:* "Fantasy football, but the players are countries' power grids."
*Wow moment:* Poland has a monster wind day and beats Norway. Nobody expects that to be possible.
*Why Electricity Maps:* Only source with a consistent, comparable roster of hundreds of zones.
*Main risk:* Baseline-relative scoring is the whole trick and is hard to explain in ten seconds.

---

**3. GRIDLE**

*Human behaviour:* Solve today's puzzle, keep the streak, post the glyph.
*Core mechanic:* An unlabelled 24-hour generation-mix curve from *yesterday, somewhere*. Six guesses. Hints reveal load, then flows, then continent.
*Electricity mechanic:* Live daily mix as a fingerprint.
*Why return:* New real day, new puzzle, forever. Streak loss aversion.
*10-second explanation:* "Wordle, but you guess the country from its electricity."
*Wow moment:* You realise you can *recognise* France by its flat nuclear floor.
*Why Electricity Maps:* Daily, comparable, hundreds of zones.
*Main risk:* griddle already exists in near-adjacent form; differentiation rests entirely on live-daily vs annual data.

---

**4. STORM NAMES**

*Human behaviour:* Follow a developing event and talk about it by name.
*Core mechanic:* An algorithm names each multi-day scarcity or surplus event ("Dunkelflaute Ingrid"), tracks its path across zones, and closes it with a post-mortem.
*Electricity mechanic:* Sustained low renewable output / high price spread across connected zones.
*Why return:* Events have arcs. You check on Ingrid.
*10-second explanation:* "We name European energy droughts like hurricanes and track them."
*Wow moment:* A named event visibly crawls across the map over four days.
*Why Electricity Maps:* Cross-zone comparability is what turns local weather into a continental event.
*Main risk:* Event frequency may be too low outside winter — a September demo could have nothing to show.

---

**5. RESIDUE**

*Human behaviour:* Prove you know something the professionals don't.
*Core mechanic:* You never predict the outcome — you predict where the *official forecast* will be wrong, and in which direction.
*Electricity mechanic:* Forecast vs actual carbon intensity / renewable output.
*Why return:* A permanent, public calibration rating.
*10-second explanation:* "Bet against the forecast, not the weather."
*Wow moment:* A leaderboard showing amateurs who consistently beat the model on specific zones.
*Why Electricity Maps:* Publishes both forecast and actual, so error is directly computable.
*Main risk:* Conceptually one layer too abstract for a general audience.

---

**6. FLOW**

*Human behaviour:* Watch something beautiful without understanding it.
*Core mechanic:* No chart, no number, no map legend. The whole screen is 200 zones breathing in real colour, and you can fall into any one of them.
*Electricity mechanic:* Live carbon-free percentage as pure colour and motion.
*Why return:* Ambient. It's your wallpaper.
*10-second explanation:* "The planet's electricity, as a living colour field."
*Wow moment:* Dawn sweeping west across Europe as solar comes up, visible as a colour wave.
*Why Electricity Maps:* Simultaneous global coverage at hourly-or-better resolution.
*Main risk:* It's a screensaver. Beautiful, but is it a product?

---

**7. THE SWITCH**

*Human behaviour:* Ask one question and get one answer.
*Core mechanic:* Full screen. One word: **NOW** or **WAIT**. Optionally, one line: "wait until 2pm." That's the entire app.
*Electricity mechanic:* Carbon-intensity level signal + forecast horizon.
*Why return:* You ask it every time you're about to run something.
*10-second explanation:* "Should I run the washing machine now? It says yes or no."
*Wow moment:* The judge asks a question and the answer is one word, with nothing else on screen.
*Why Electricity Maps:* Forecast + level signals mean no numeracy required anywhere.
*Main risk:* Nearly exists; extremely likely another team builds a variant.

---

**8. ANOMALY MUSEUM**

*Human behaviour:* Collect rare things and show people.
*Core mechanic:* A detector mints a card whenever something statistically weird happens. Cards have rarity, timestamp, zone, and a plain-language description. You collect what happens while you're watching.
*Electricity mechanic:* Outlier detection across price, mix, flows, and load.
*Why return:* You can only catch today's anomalies today.
*10-second explanation:* "Pokémon cards, but each one is a real weird thing that happened on the grid."
*Wow moment:* A card mints live during the demo.
*Why Electricity Maps:* Cross-zone, multi-signal history to define "weird" statistically.
*Main risk:* If nothing weird happens during judging, the demo is dead.

---

**9. THE UNDERSTUDY**

*Human behaviour:* Try to do a hard job and fail entertainingly.
*Core mechanic:* You're the operator for a real historical day, compressed to five minutes. Decisions every "hour." At the end, your day is scored against what actually happened.
*Electricity mechanic:* Real historical load, mix, flows, and prices as the scenario.
*Why return:* A new real day every day; everyone plays the same one.
*10-second explanation:* "Run a country's power grid for five minutes. Yesterday's, for real."
*Wow moment:* "You blacked out Belgium at 6pm. The real operators didn't."
*Why Electricity Maps:* Historical hourly data across zones with imports and exports.
*Main risk:* Simulating operator decisions credibly in one day is very hard; risks becoming fake.

---

**10. PROVENANCE**

*Human behaviour:* Find out where something you're using came from.
*Core mechanic:* Point at where you are. Get the ancestry of the electricity in the room right now — as a lineage with named origins and border crossings.
*Electricity mechanic:* Flow-traced consumption mix.
*Why return:* It changes hour by hour. Different at breakfast than at midnight.
*10-second explanation:* "Where did the electricity in this room come from? Here's its family tree."
*Wow moment:* "Your laptop is running partly on a Norwegian river, via Denmark, from four hours ago."
*Why Electricity Maps:* Flow-tracing is their signature methodology; nobody else does it comparably.
*Main risk:* One-shot wonder. Astonishing once, then what?

---

**11. HEAD TO HEAD**

*Human behaviour:* Pick a side in a two-way fight.
*Core mechanic:* Every day, two zones, one metric, one tap. Persistent rivalry records build over the season.
*Electricity mechanic:* Any comparable signal, chosen daily for maximum uncertainty.
*Why return:* Ten seconds a day, plus a running record you're invested in.
*10-second explanation:* "France or Germany today? Tap one."
*Wow moment:* The all-time head-to-head table, with grudges.
*Why Electricity Maps:* Consistent methodology makes cross-country comparison honest.
*Main risk:* Too thin to be a product on its own.

---

**12. WHAT IF**

*Human behaviour:* Argue about history.
*Core mechanic:* Take a real period. Swap one assumption (a fleet still running, a interconnector never built, double the solar). Re-run the real data. Watch the counterfactual redraw.
*Electricity mechanic:* Historical mix + flows + emissions factors, recomputed.
*Why return:* Endless questions; each one is an argument.
*10-second explanation:* "Replay last winter as if Germany still had its nuclear plants."
*Wow moment:* Two curves, real and counterfactual, diverging in front of the room.
*Why Electricity Maps:* Long consistent history with emissions factors and flows.
*Main risk:* The counterfactual is a naive substitution and an expert will call it out in 30 seconds.

---

**13. GRID SOUND**

*Human behaviour:* Listen to something and feel it.
*Core mechanic:* A zone's day becomes a piece of music. Mix chooses instruments, load sets tempo, carbon sets the key. Every day is a new composition that has never existed.
*Electricity mechanic:* Mix + load + carbon intensity as musical parameters.
*Why return:* Today's track. Yesterday's track. Your country's track.
*10-second explanation:* "Listen to what your country's electricity sounded like today."
*Wow moment:* Norway sounds like Norway. Poland sounds like Poland. Everyone hears it immediately.
*Why Electricity Maps:* Comparable multi-source breakdown across countries.
*Main risk:* Delightful, weightless, and hard to argue is *about* anything.

---

**14. BATTERY**

*Human behaviour:* Buy low, sell high, brag.
*Core mechanic:* You have a virtual battery. Charge and discharge against yesterday's real prices. Ranked P&L, same prices for everyone.
*Electricity mechanic:* Day-ahead price volatility; ~€130/MWh average daily spread.
*Why return:* New prices daily; a running balance.
*10-second explanation:* "You own a battery. Make money on real electricity prices."
*Wow moment:* Live leaderboard where the best human beats a naive strategy by 3×.
*Why Electricity Maps:* Day-ahead price across many zones in one schema.
*Main risk:* This is a known genre in energy trading; risks feeling like a training tool.

---

**15. GRID PET**

*Human behaviour:* Care for something.
*Core mechanic:* A creature lives in your zone. It's energetic when the grid is clean, sluggish when it isn't. It never shows a number. You feed it by using power at the right time.
*Electricity mechanic:* Live carbon-intensity level signal.
*Why return:* It's alive and it changes.
*10-second explanation:* "A pet that's happy when your country's electricity is clean."
*Wow moment:* A user with no energy knowledge correctly predicts a clean hour, because the pet taught them.
*Why Electricity Maps:* Level signals give a non-numeric, zone-relative classification out of the box.
*Main risk:* Cute, but does it actually teach anything true, or just anthropomorphise noise?

---

**16. PASSPORT**

*Human behaviour:* Collect places you've been.
*Core mechanic:* Wherever you physically are, you're consuming from a zone. Get a stamp. Stamps have rarity. Some zones are nearly unreachable.
*Electricity mechanic:* Zone lookup by coordinates + live mix at the moment of stamping.
*Why return:* Travel, and the map fills in.
*10-second explanation:* "A passport that stamps which power grids you've used."
*Wow moment:* Someone's stamp shows the exact mix at the hour they landed in Reykjavik.
*Why Electricity Maps:* Global zone geometry and lat/lon lookup.
*Main risk:* Only rewards travellers; most users' collections never grow.

---

**17. THE LEAGUE TABLE NOBODY ASKED FOR**

*Human behaviour:* Read a ranking and feel something about it.
*Core mechanic:* Every day, an automatically generated, slightly absurd league table with a headline. "Most dependent on the kindness of neighbours." "Flakiest grid in Europe."
*Electricity mechanic:* Flows, load variance, mix concentration.
*Why return:* A fresh, funny, arguable ranking daily.
*10-second explanation:* "A stupid daily league table about electricity that's completely true."
*Wow moment:* A table so pointed that people immediately want to defend their country.
*Why Electricity Maps:* Consistent, comparable metrics make absurd rankings defensible.
*Main risk:* It's a content feed. Is it a product?

---

**18. SHAPE**

*Human behaviour:* Draw, then be judged on your drawing.
*Core mechanic:* Draw tomorrow's curve freehand. Scored by shape distance, not point accuracy. Your drawing is the share artefact.
*Electricity mechanic:* Day-ahead price or net load curve.
*Why return:* Your drawing vs reality, daily.
*10-second explanation:* "Draw tomorrow's power prices with your finger. See how close you were."
*Wow moment:* Overlaying a room full of hand-drawn curves and finding the crowd average beats most individuals.
*Why Electricity Maps:* Clean settled curves, many zones, plus a forecast to grade against.
*Main risk:* Shape-scoring is fiddly and may feel arbitrary and unfair.

---

**19. SIMULTANEITY**

*Human behaviour:* Be astonished by scale.
*Core mechanic:* One instant. 200 places. Sorted, ranked, and juxtaposed so the extremes sit next to each other. You scrub through time and the whole world reorders.
*Electricity mechanic:* Cross-zone simultaneous state.
*Why return:* The order changes constantly; the extremes are always different.
*10-second explanation:* "Right now, the cleanest and dirtiest electricity on Earth, side by side."
*Wow moment:* Scrubbing 24 hours and watching the whole planet resort itself.
*Why Electricity Maps:* Only dataset with genuinely simultaneous, comparable global coverage.
*Main risk:* Perilously close to being a dashboard with better art direction.

---

**20. TWO OF US**

*Human behaviour:* Compete with one specific person you know.
*Core mechanic:* You and one other person, in different places. Every day, whose grid was cleaner, and whose *choices* were better relative to what was available locally. A private, permanent record.
*Electricity mechanic:* Zone-relative performance, so a Pole can beat a Norwegian.
*Why return:* Someone is waiting for you.
*10-second explanation:* "Me vs my brother in Berlin, every day, on electricity."
*Wow moment:* The relative scoring makes a coal-country player win, and the room immediately understands why that's fair.
*Why Electricity Maps:* Comparable zone baselines are the only thing that makes this fair.
*Main risk:* Requires two people to adopt it, which is the hardest possible cold-start.

---

## PART 12 — DESTROYING THEM

Judged as a hostile hackathon judge: *is it a dashboard, a chatbot, an optimizer, an existing feature, an obvious build, an existing startup? Is the electricity data essential? Would it survive without the theme? Is it fun? Memorable? Demoable in 60 seconds? Would another team build it? Is there a reason to return?*

**KILLED**

- **#7 THE SWITCH** — This is an optimizer with a nice haircut. Carbon-aware scheduling is a solved, commercially served problem, adjacent to Electricity Maps' actual business. Three other teams will build a version of this. *Dead.*
- **#19 SIMULTANEITY** — It is a dashboard. A gorgeous, well-art-directed dashboard, and it is competing directly with Electricity Maps' own map, which is better. *Dead.*
- **#6 FLOW** — Same problem, less information. A screensaver has no return mechanism and no reason to exist beyond the first ten seconds. *Dead as a project; keep as a visual layer for something else.*
- **#16 PASSPORT** — Cold collection: most users get one stamp and never another. Depends on travel, so the loop is monthly at best. Also, it's basically a check-in app with an energy skin. *Dead.*
- **#10 PROVENANCE** — Genuinely wonderful for exactly one viewing. There is no day two. *Dead as a product; the single best 15-second hook in this entire document, so keep it as an onboarding moment inside something else.*
- **#9 THE UNDERSTUDY** — The simulation layer is a lie you'd have to build in a day, and any energy person in the room will know it's a lie within 30 seconds. High risk of being both hard and fake. *Dead unless radically simplified.*
- **#12 WHAT IF** — Same failure mode: the counterfactual engine is either naive (and gets destroyed by an expert) or too hard to build honestly in a day. Also politically flammable in a way that distracts from the mechanic. *Dead at hackathon scale.*
- **#17 THE LEAGUE TABLE NOBODY ASKED FOR** — It's a content feed and, in practice, an LLM writing captions over sorted arrays. That's a chatbot with a table. *Dead.*

**WOUNDED — survive only with a specific fix**

- **#3 GRIDLE** — griddle already exists. Fails "would another team build this?" instantly, because *someone already did*. Survives **only** if it moves decisively to live daily data (yesterday's real curve, not annual mix) and adds a social layer. The daily-live version is genuinely different — but you must know the prior art exists and say so first.
- **#4 STORM NAMES** — Mechanically beautiful, seasonally fatal. In September, there may be no event to name, and a demo with no event is a demo with nothing. Survives only with a historical replay mode for the demo. Also: naming is 90% of the value and 10% of the work, which is either the best or worst thing about it.
- **#8 ANOMALY MUSEUM** — Excellent concept, terrible demo risk. Also: "anomaly detection" is where every team reaches for statistics and produces false positives. Survives only if the anomaly definitions are hand-crafted, few, and unambiguous.
- **#5 RESIDUE** — The sharpest *idea* here and the hardest to explain. If a judge doesn't understand it in ten seconds, it dies on stage. Survives only if wrapped in a concrete daily question. Also: is anyone but a forecasting nerd going to enjoy this?
- **#13 GRID SOUND** — Charming and completely weightless. Fails "is it useful," fails "reason to return," passes "memorable" enormously. Survives only if the sonification is *diagnostic* — if you can genuinely hear a Dunkelflaute — rather than decorative.
- **#15 GRID PET** — Real danger of being a cute skin over a single API call. The electricity data is doing almost no work. Survives only if the pet's behaviour teaches a *specific, correct, non-obvious* intuition.
- **#14 BATTERY** — Would survive fine without the electricity theme (it's a trading sim). Genre-familiar; energy people have seen this. Survives as a strong build, weak concept.
- **#11 HEAD TO HEAD** — Too thin to stand alone. Survives as a *mechanic inside* #2, not as a product.
- **#20 TWO OF US** — The relative-scoring insight is excellent. The two-sided cold start is the worst possible adoption problem for a one-day demo. Survives only if demoed as pre-seeded.
- **#18 SHAPE** — The interaction is delightful and the share artefact is strong. Scoring is the weak point and will feel arbitrary. Survives if the scoring is visibly, obviously fair.

**STANDING**

- **#1 THE REVEAL** — Survives the strongest attack, which is "the public forecast makes this trivial," *because* that objection is answerable by scoring against the forecast rather than the outcome. Not a dashboard, not a chatbot, not an optimizer. Demoable in 20 seconds. Genuine daily return mechanism. The electricity data is essential (nothing else gives you a public prior plus a guaranteed daily settlement). Main open question remains whether the skill gap is wide enough to be interesting.
- **#2 WATTFOLIO** — Survives because it solves the single hardest problem identified in this research (no pre-existing rooting interest) using a mechanism proven to work at enormous scale. Nobody has built it. Electricity data is essential — you need a comparable roster of hundreds of entities with daily performance, which exists in exactly one place. The risk is explanation time: baseline-relative scoring is the whole trick and it is not a ten-second idea.

**The pattern in the survivors:** both convert electricity data into *a personal stake that resolves daily*. Everything that died either showed the data (dashboard), acted on the data (optimizer), decorated the data (art), or described the data (feed).

---

## FINAL SECTIONS

### The 5 most interesting unexplored territories

1. **Forecast error as public entertainment.** Everyone in energy produces forecasts. Nobody has made *the gap between prediction and reality* into something a layperson can watch, score, and enjoy. It is the richest, least-touched vein in the dataset, and it is structurally guaranteed to renew every single day.

2. **Baseline-relative competition between places.** Raw rankings are frozen and therefore dead. Relative-to-expectation scoring — the innovation that made bad sports teams interesting — has never been applied to grids. It unlocks lead changes, upsets, and the possibility that a coal country can have a great day. Almost everything competitive downstream depends on this one idea.

3. **Manufactured attachment.** Nobody has ever given a person a reason to care about a specific grid. Drafting, adopting, being assigned, inheriting, or betting on a zone are all untried. Solving attachment is worth more than any data sophistication.

4. **Naming and narrating events.** Meteorology learned a century ago that named events get followed. Energy has no naming convention, no event registry, no arcs, no protagonists. The infrastructure cost is near zero and the narrative return is very high.

5. **Non-numeric grid literacy.** Level signals, colours, creatures, sounds, and ordinal comparisons can teach correct intuitions to people who will never look at gCO₂/kWh. The entire field leads with numbers. The people who don't read numbers are the entire unserved market.

### The 5 biggest misconceptions about electricity-data products

1. **"People engage with this because they care about climate."** The evidence says otherwise. The largest genuinely habitual audience — dynamic-tariff households — engages because of *money and tinkering pleasure*. Carbon is a secondary rationalisation for most of them. Building for climate motivation targets a small, already-converted group.

2. **"Real-time is the valuable temporality."** Real-time produces glancing, not returning. The *day-ahead reveal* produces anticipation, and anticipation is what makes habits. The most engaging moment in European electricity is an auction result published at a fixed hour, and almost nobody has built anything around it.

3. **"The map is the interesting part."** The map is a legibility crutch and it's already been built, well, by the people running the hackathon. The interesting objects are the *time series*, the *forecast error*, and the *relationships between zones*. Spatial thinking actively misleads here — it's what makes people reach for Risk-like mechanics that the physics won't support.

4. **"The problem is that electricity is invisible."** It isn't invisibility, it's the absence of *protagonists and stakes*. Weather is also invisible, and people follow it obsessively — because it has named events, consequences, and a daily forecast you can disagree with. Electricity has all three ingredients available and uses none of them.

5. **"The right action is to use less."** Increasingly the right action is to use *at the right time*, and sometimes to use *more* — negative prices mean the system is paying people to consume. A product built on the reduce-consumption frame will give wrong advice several hundred hours a year and will miss the most delightful thing in the whole dataset: sometimes electricity is free and you should go use it.

### Questions I still cannot answer

**About the data, practically:**
1. What tier of API access will hackathon participants actually get? The free tier is limited to carbon intensity and power breakdown for a *single zone* — which would eliminate every multi-zone concept here. This is the highest-leverage unknown in the entire document and should be your first question on the day.
2. Are day-ahead price and electricity flows available to participants, or commercial-only?
3. How often are historical values *revised* after publication, and by how much? Any competitive product where yesterday's score changes is broken.
4. Can forecasts be retrieved retrospectively — i.e. can I fetch "what was the forecast for Tuesday, as of Monday"? Without this, forecast-error concepts cannot be built or backtested at all.
5. Which zones are estimated versus directly reported, and does the API flag it per-record? Estimated zones are unfit for competition.
6. What is the true publication latency for "actual" values, per zone?

**About human behaviour, genuinely unknown:**
7. Is there any real skill gap in lay prediction of grid variables at a 24-hour horizon, once the public forecast is available to everyone? Nobody has measured this. It's the crux of the whole prediction hypothesis and I cannot resolve it from research alone.
8. Would anyone develop attachment to a drafted zone, or does fantasy sports work only because the underlying sport is *already* watched by the player?
9. How many consecutive boring days can a daily grid product survive before churn?
10. Does non-numeric grid literacy actually transfer — do people who learn from a colour or a creature make better real decisions, or just feel like they do?
11. Is the "free electricity" moment (negative prices) emotionally powerful to people who don't have a dynamic tariff and therefore can't capture it? Or does knowing about free electricity you can't access just produce irritation?
12. Does an energy-professional judge reward domain sophistication or naïve delight? These point in opposite directions, and the entire portfolio above tilts toward delight.

**About the exercise itself:**
13. Is the absence of play/competition products in this space evidence of an unexploited opportunity, or evidence that many people have tried and quietly failed? I found no failure graveyard — but I also wouldn't expect to. Absence of evidence here is weak evidence.
