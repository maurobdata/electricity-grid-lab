/**
 * The view-state reducer.
 *
 * This is the one piece of front-end logic worth testing on its own: it is pure, it has no
 * React in it, and three different things drive it — a control, a deterministic finding,
 * and the agent. A bug here is a bug in all three at once, and it would show up as an
 * interface that quietly ignores you rather than as anything that looks broken.
 *
 * The cases below are mostly about *not* doing things: not applying an intent this build
 * cannot honour, not throwing on one it does not recognise, not writing defaults into a
 * shared URL, and not trusting a query string somebody may have edited by hand.
 */

import { describe, expect, it } from "vitest";

import {
  INITIAL_VIEW,
  apply,
  canApply,
  fromQuery,
  isPanel,
  isSignal,
  toQuery,
  type ViewIntent,
  type ViewState,
} from "@/lib/viewState";

const base: ViewState = { ...INITIAL_VIEW, zone: "DK-DK2" };

function intent(over: Partial<ViewIntent> & Pick<ViewIntent, "kind">): ViewIntent {
  return { reason: "because", ...over } as ViewIntent;
}

describe("apply", () => {
  it("is pure — the input state is never mutated", () => {
    const before = { ...base };
    apply(base, intent({ kind: "select_zone", zone: "DE" }));
    expect(base).toEqual(before);
  });

  it("selects a zone", () => {
    expect(apply(base, intent({ kind: "select_zone", zone: "DE" })).zone).toBe("DE");
  });

  it("changes the signal only to one that exists", () => {
    expect(apply(base, intent({ kind: "set_signal", signal: "price" })).signal).toBe("price");
    expect(apply(base, intent({ kind: "set_signal", signal: "vibes" })).signal).toBe(
      base.signal,
    );
  });

  it("focuses a panel only if the panel exists", () => {
    expect(apply(base, intent({ kind: "focus", panel: "mix" })).focused).toBe("mix");
    expect(apply(base, intent({ kind: "focus", panel: "dashboard" })).focused).toBeUndefined();
  });

  it("compares several zones and brings the comparison forward", () => {
    const next = apply(base, intent({ kind: "compare", zones: ["DK-DK2", "DE"] }));
    expect(next.compareZones).toEqual(["DK-DK2", "DE"]);
    expect(next.focused).toBe("compare");
  });

  it("refuses a comparison of fewer than two zones", () => {
    expect(apply(base, intent({ kind: "compare", zones: ["DE"] }))).toBe(base);
  });

  describe("highlight_window", () => {
    it("marks the window", () => {
      const next = apply(
        base,
        intent({ kind: "highlight_window", at: "2026-08-24T09:00:00Z", until: "2026-08-24T13:00:00Z" }),
      );
      expect(next.highlight).toEqual({
        from: "2026-08-24T09:00:00Z",
        to: "2026-08-24T13:00:00Z",
      });
    });

    it("treats a single instant as a zero-length window rather than a special case", () => {
      const next = apply(base, intent({ kind: "highlight_window", at: "2026-08-24T09:00:00Z" }));
      expect(next.highlight).toEqual({
        from: "2026-08-24T09:00:00Z",
        to: "2026-08-24T09:00:00Z",
      });
    });

    it("switches signal when the intent names one", () => {
      // A price window marked on a carbon chart is a band with no visible reason.
      const next = apply(
        base,
        intent({ kind: "highlight_window", at: "2026-08-24T09:00:00Z", signal: "price" }),
      );
      expect(next.signal).toBe("price");
    });

    it("leaves the signal alone when the intent names none", () => {
      const next = apply(base, intent({ kind: "highlight_window", at: "2026-08-24T09:00:00Z" }));
      expect(next.signal).toBe(base.signal);
    });

    it("does nothing without a time", () => {
      expect(apply(base, intent({ kind: "highlight_window" }))).toBe(base);
    });
  });

  it("leaves seek to the caller, because the clock lives on the server", () => {
    // The reducer stays pure; performing a seek is an effect and belongs outside it.
    expect(apply(base, intent({ kind: "seek", at: "2026-08-24T09:00:00Z" }))).toBe(base);
  });

  it("ignores an intent it does not recognise rather than throwing", () => {
    // Intents arrive from a server that may be a version ahead. Returning the state
    // unchanged degrades the feature; throwing takes the page down with it.
    const unknown = { kind: "teleport", reason: "why not" } as unknown as ViewIntent;
    expect(apply(base, unknown)).toBe(base);
  });
});

describe("canApply", () => {
  it("permits an ordinary highlight in replay", () => {
    expect(
      canApply(intent({ kind: "highlight_window", at: "2026-08-24T09:00:00Z" }), base, "replay"),
    ).toBeNull();
  });

  it("refuses a seek in live mode, where there is no clock to move", () => {
    const why = canApply(intent({ kind: "seek", at: "2026-08-24T09:00:00Z" }), base, "live");
    expect(why).toMatch(/live mode/);
  });

  it("permits a seek in replay", () => {
    expect(canApply(intent({ kind: "seek", at: "2026-08-24T09:00:00Z" }), base, "replay")).toBeNull();
  });

  it("gives a reason rather than a bare false", () => {
    // The reason is shown on the disabled control, so it has to be readable.
    for (const bad of [
      intent({ kind: "focus", panel: "nope" }),
      intent({ kind: "set_signal", signal: "nope" }),
      intent({ kind: "highlight_window" }),
      intent({ kind: "compare", zones: ["DE"] }),
    ]) {
      const why = canApply(bad, base, "replay");
      expect(why).toBeTruthy();
      expect(why!.length).toBeGreaterThan(5);
    }
  });
});

describe("URL projection", () => {
  it("writes nothing for a default view", () => {
    expect(toQuery(INITIAL_VIEW)).toBe("");
  });

  it("omits fields that match the default, so a shared link carries only real choices", () => {
    const query = toQuery({ ...base, signal: "price" });
    expect(query).toContain("zone=DK-DK2");
    expect(query).toContain("signal=price");
    expect(query).not.toContain("compareSignal");
    expect(query).not.toContain("mix=");
  });

  it("round-trips a fully populated view", () => {
    const view: ViewState = {
      zone: "DE",
      compareZones: ["DE", "DK-DK2"],
      signal: "price",
      compareSignal: "load",
      flowTraced: false,
      focused: "mix",
      highlight: { from: "2026-08-24T09:00:00Z", to: "2026-08-24T13:00:00Z" },
    };
    expect(fromQuery(toQuery(view))).toEqual(view);
  });

  it("round-trips the default view", () => {
    expect(fromQuery(toQuery(INITIAL_VIEW))).toEqual(INITIAL_VIEW);
  });

  describe("reading an untrusted query string", () => {
    // A URL may be hand-edited, truncated by a chat client, or written by an older build.
    // A bad one must open the default view, never a broken one.
    it("drops an unknown signal", () => {
      expect(fromQuery("signal=vibes").signal).toBe(INITIAL_VIEW.signal);
    });

    it("drops an unknown panel", () => {
      expect(fromQuery("focus=dashboard").focused).toBeUndefined();
    });

    it("survives an empty string", () => {
      expect(fromQuery("")).toEqual(INITIAL_VIEW);
    });

    it("survives junk", () => {
      expect(() => fromQuery("=&&?x")).not.toThrow();
    });

    it("ignores empty entries in the compare list", () => {
      expect(fromQuery("compare=DE,,DK-DK2,").compareZones).toEqual(["DE", "DK-DK2"]);
    });

    it("treats a lone `from` as a zero-length window", () => {
      expect(fromQuery("from=2026-08-24T09:00:00Z").highlight).toEqual({
        from: "2026-08-24T09:00:00Z",
        to: "2026-08-24T09:00:00Z",
      });
    });
  });
});

describe("guards", () => {
  it("recognises real panels and signals only", () => {
    expect(isPanel("mix")).toBe(true);
    expect(isPanel("dashboard")).toBe(false);
    expect(isPanel(undefined)).toBe(false);
    expect(isSignal("price")).toBe(true);
    expect(isSignal(null)).toBe(false);
  });
});
