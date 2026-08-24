# Running the demo

Written to be followed under time pressure by someone who has not read the rest of the
repository today.

The governing decision is [ADR 0004](adr/0004-live-vs-replay-clock.md): **demo the
recording, not the live grid.** The grid will not do anything interesting on cue, the venue
wifi is not yours, and a recording made this morning is real data that happens to be
reliable. Keep a live toggle for anyone who challenges it.

---

## The day before

- [ ] `make scenario-live` — and check the output says **`price forward: N points`**. A
      recording without it cannot show the cheap-versus-clean comparison, which is most of
      the story.
- [ ] `git status` clean, everything committed.
- [ ] `make test` and `make lint` green.
- [ ] Charge the laptop. Bring the charger.

## The morning of

Do these in order. The whole sequence is about five minutes.

```bash
make probe          # what the key can reach today — re-check if it is a new key
make scenario-live  # this morning's recording, with forward price
make atlas          # the cross-zone sweep, ~40 zones, under a minute
```

Then point the lab at what you just recorded:

```bash
# .env
GRIDLAB_SCENARIO=dk-dk2-<today>
```

...or leave `GRIDLAB_SCENARIO` blank, which resolves to the newest recording on disk.

```bash
make up && make web
make demo           # sanity check in the terminal before trusting the browser
```

**Verify before you rely on it:**

- [ ] The mode bar reads **replay** and the badge says **recorded** — not synthetic.
- [ ] `Across the grids` says **live** while every other panel says **recorded**. That is
      correct, not a bug, and somebody will ask: the atlas is a sweep of the live API run
      this morning, while the panels are replaying a recording. Two kinds of real data,
      each labelled as what it is — which is the badge doing exactly its job.
- [ ] `Worth a look` has chips in it.
- [ ] The forecast panel draws both lines.
- [ ] `Across the grids` lists zones and names the sweep time.
- [ ] The agent answers one question. If it does not, the rest still works.

## What to show

The order matters. Each step earns the next.

1. **Worth a look.** The lab has already found things — arithmetically, before anyone
   asked. Read one chip aloud. This is what a dashboard cannot do.
2. **Click a chip.** The charts move to the moment it is about. Navigation, not decoration.
3. **Cheap versus clean.** The cheapest window and the cleanest window, and how far apart
   they are. Say the mechanism: price is set by the marginal unit through uniform-price
   auction clearing; carbon intensity is a flow-traced average over consumption. Different
   functions of the same grid.
4. **Across the grids.** The same calculation for forty-one zones. Croatia at the top; the
   Italian zones where the clean choice costs almost nothing. Say that ranking on the
   correlation would have put a zone whose carbon moves three points first — and that the
   spread is on every row for exactly that reason.
5. **Ask the agent.** Its working renders inline. Every number it says came from a tool
   call visible on the screen.
6. **The forward price is not a forecast.** It cleared at noon. It is a settled auction
   result waiting for its delivery hour.

## When something breaks

**The agent is down or the key is exhausted.** Everything else works. The findings, the
divergence and the atlas are arithmetic and need no model — say so, because it is the
point. The agent panel says it has no key rather than hanging.

**No wifi.** Nothing needed for the demo touches the network. Replay reads a committed
file; the atlas is a file on disk. The whole test suite passes with `--network none`, which
is the same claim tested rather than asserted.

**A panel is empty.** Read the message rather than reloading — the lab distinguishes "your
plan does not include this" from "nobody asked". A 404 on `price/forward` means the
scenario predates it; re-record.

**The browser will not cooperate.** `make demo` narrates the whole thing in the terminal:
the walk, the cleared prices, the cheap-versus-clean comparison, and the findings.

**Someone challenges the recording.** Switch `GRIDLAB_MODE=live`, `make restart`. Same code
path — [ADR 0004](adr/0004-live-vs-replay-clock.md) — so nothing about the interface
changes except the badge.

---

## Say these, and do not say the others

**Say:**

- Every value carries where it came from. `live`, `recorded` or `synthetic`, on the badge,
  in the payload, and in every screenshot.
- The findings are deterministic. No model was asked, and none could have invented them.
- Forward price is an auction result, not a prediction.
- The carbon figure is a flow-traced *average* over consumption. Shifting demand changes
  the *marginal* unit, which is a different quantity — so avoided carbon here is an
  accounting difference, not a measured abatement. **Raise this before a judge does.**
- The atlas is one day, in one direction. A zone that agrees today may not tomorrow.

**Do not say:**

- ~~"We shift your load to the green hour."~~ That is the saturated genre, and it is the one
  exposed by the marginal-versus-average critique.
- ~~"This zone imports X% of its electricity."~~ The flow-traced breakdown's total is not a
  verified consumption figure; that is why the lab reports megawatts.
- ~~Any number in `€/tCO₂`.~~ Nothing computes one. Dividing the two deltas would be a
  shadow carbon price, which is a product thesis the project has not adopted
  ([ADR 0007](adr/0007-defer-product-decision.md)).
- ~~"The agent is sandboxed from the network."~~ It is tool-constrained and
  filesystem-isolated. Egress is open, and [ADR 0005](adr/0005-agent-sandbox-container.md)
  says so plainly rather than overclaiming.

---

## Known gaps, if asked

- **Forecast versus outcome is not shown.** It needs two consecutive daily recordings
  joined, and nothing joins them yet. The data to do it is being collected daily.
- **No historical depth.** `past` and `past-range` are 401 on this plan
  ([ADR 0008](adr/0008-history-not-breadth-is-the-constraint.md)). Everything here is the
  trailing day and the next.
- **Narration explains, it does not verify.** A narration mentioning a number the finding
  did not contain is discarded — but its *reasoning* is not checked, and it has been
  observed getting a causal direction wrong.
- **The PWA service worker is unverified.** It builds correctly; activation has only been
  tried in an embedded browser that refuses to register one.
