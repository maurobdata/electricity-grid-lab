/**
 * What the app is currently looking at, as one serializable object.
 *
 * The lab began as panels that each polled an endpoint about a zone, with the selection
 * spread across half a dozen `useState` hooks in `App.tsx`. That is a dashboard shape, and
 * it has a specific limitation: **nothing except the user can change what is on screen.**
 *
 * Three things need to. A deterministic finding knows which window is worth looking at. The
 * agent knows which panel its answer is about. A URL should be able to reopen a view
 * somebody shared. All three want the same thing — "show me *this*" — so all three go
 * through one type, {@link ViewIntent}, applied by one reducer.
 *
 * The rules that make it work:
 *
 * - **State is data, not behaviour.** {@link apply} is pure and has no React in it, so the
 *   interesting logic is testable without rendering anything.
 * - **An intent is a proposal.** Applying one is always the caller's decision. The agent
 *   emits intents it cannot apply itself (ADR 0010) and the reducer does not know or care
 *   where one came from.
 * - **The URL is a projection of the state, not a second copy of it.** One direction of
 *   truth, so a link and a click cannot disagree.
 *
 * `ViewIntent` mirrors `gridlab.domain.models.ViewIntent` on the server, which is the type
 * both the detectors and the agent construct. Keep the two in step; the server validates
 * against a closed enum, so anything arriving here is already a shape this file knows.
 */

import type { Mode } from "@/lib/api";

/** Panels that can be focused. Mirrors `VIEW_PANELS` in `gridlab/agent/tools.py`. */
export const PANELS = [
  "now",
  "mix",
  "flows",
  "forecast",
  "compare",
  "findings",
  "atlas",
] as const;
export type PanelId = (typeof PANELS)[number];

/** Signals that exist as a series. Mirrors `SERIES_SIGNALS` in `web/routes_grid.py`. */
export const SIGNALS = [
  "carbon_intensity",
  "renewable_percentage",
  "carbon_free_percentage",
  "price",
  "load",
] as const;
export type SignalId = (typeof SIGNALS)[number];

export interface TimeWindow {
  from: string;
  to: string;
}

export interface ViewState {
  zone?: string;
  compareZones: string[];
  signal: SignalId;
  compareSignal: SignalId;
  /** Production vs flow-traced on the mix panel. The gap between them is the point. */
  flowTraced: boolean;
  /** Which panel, if any, is promoted to full width. */
  focused?: PanelId;
  /**
   * A stretch of time the charts should mark.
   *
   * Deliberately separate from `focused`: highlighting the hour an answer is about should
   * not also rearrange the page, and rearranging the page should not silently drop the
   * highlight.
   */
  highlight?: TimeWindow;
}

export const INITIAL_VIEW: ViewState = {
  compareZones: [],
  signal: "carbon_intensity",
  compareSignal: "carbon_intensity",
  flowTraced: true,
};

/* -------------------------------------------------------------------------- */
/* Intents                                                                    */
/* -------------------------------------------------------------------------- */

export type IntentKind =
  | "focus"
  | "select_zone"
  | "set_signal"
  | "highlight_window"
  | "compare"
  | "seek";

/**
 * A proposed change to the view.
 *
 * `reason` is written for the user, not for a log: it is the label on the control that
 * applies the intent. An unexplained view change is disorienting, so there is nowhere to
 * put an intent that cannot say what it is for.
 */
export interface ViewIntent {
  kind: IntentKind;
  reason: string;
  zone?: string | null;
  zones?: string[];
  signal?: string | null;
  panel?: string | null;
  at?: string | null;
  until?: string | null;
}

/** Whether this intent can be carried out at all right now. */
export function canApply(intent: ViewIntent, state: ViewState, mode: Mode): string | null {
  if (intent.kind === "seek" && mode !== "replay") {
    return "There is no clock to move in live mode.";
  }
  if (intent.kind === "seek" && !intent.at) return "No time given.";
  if (intent.kind === "focus" && !isPanel(intent.panel)) return "Unknown panel.";
  if (intent.kind === "set_signal" && !isSignal(intent.signal)) return "Unknown signal.";
  if (intent.kind === "highlight_window" && !intent.at) return "No window given.";
  if (intent.kind === "compare" && (intent.zones?.length ?? 0) < 2) {
    return "A comparison needs at least two zones.";
  }
  void state;
  return null;
}

/**
 * Apply an intent. Pure: same state and intent in, same state out, every time.
 *
 * Unknown or unusable intents return the state **unchanged rather than throwing**. An intent
 * is a suggestion arriving from somewhere else — a server that may be a version ahead, an
 * agent that may have misread the question — and the right response to one this build does
 * not understand is to ignore it, not to break the page.
 */
export function apply(state: ViewState, intent: ViewIntent): ViewState {
  switch (intent.kind) {
    case "select_zone":
      return intent.zone ? { ...state, zone: intent.zone } : state;

    case "set_signal":
      return isSignal(intent.signal) ? { ...state, signal: intent.signal } : state;

    case "focus":
      return isPanel(intent.panel) ? { ...state, focused: intent.panel } : state;

    case "compare": {
      const zones = intent.zones ?? [];
      if (zones.length < 2) return state;
      return { ...state, compareZones: zones, focused: "compare" };
    }

    case "highlight_window": {
      if (!intent.at) return state;
      // A single instant is a window of zero length rather than a special case, so
      // everything downstream can assume both ends exist.
      const next: ViewState = { ...state, highlight: { from: intent.at, to: intent.until ?? intent.at } };
      // A highlight is about a signal when the intent names one, and the chart showing
      // some other signal would mark a stretch of time for no visible reason.
      return isSignal(intent.signal) ? { ...next, signal: intent.signal } : next;
    }

    // `seek` moves the replay clock, which lives on the server. It is not view state, so
    // the reducer deliberately does nothing with it; the caller performs it.
    case "seek":
      return state;

    default:
      return state;
  }
}

export function isPanel(value: unknown): value is PanelId {
  return typeof value === "string" && (PANELS as readonly string[]).includes(value);
}

export function isSignal(value: unknown): value is SignalId {
  return typeof value === "string" && (SIGNALS as readonly string[]).includes(value);
}

/* -------------------------------------------------------------------------- */
/* URL projection                                                             */
/* -------------------------------------------------------------------------- */

/**
 * The view as a query string.
 *
 * Only what differs from {@link INITIAL_VIEW} is written, so a plain visit keeps a clean
 * URL and a shared link carries only what the sharer actually chose.
 */
export function toQuery(state: ViewState): string {
  const params = new URLSearchParams();
  if (state.zone) params.set("zone", state.zone);
  if (state.signal !== INITIAL_VIEW.signal) params.set("signal", state.signal);
  if (state.compareSignal !== INITIAL_VIEW.compareSignal) {
    params.set("compareSignal", state.compareSignal);
  }
  if (state.compareZones.length) params.set("compare", state.compareZones.join(","));
  if (!state.flowTraced) params.set("mix", "production");
  if (state.focused) params.set("focus", state.focused);
  if (state.highlight) params.set("from", state.highlight.from);
  if (state.highlight) params.set("to", state.highlight.to);
  return params.toString();
}

/**
 * Read a view back out of a query string.
 *
 * Every field is validated and anything unrecognised is dropped. A URL is untrusted input —
 * it may be hand-edited, truncated by a chat client, or written by an older build — and a
 * bad one should open the default view rather than a broken one.
 */
export function fromQuery(query: string): ViewState {
  const params = new URLSearchParams(query);
  const zone = params.get("zone") ?? undefined;
  const signal = params.get("signal");
  const compareSignal = params.get("compareSignal");
  const focus = params.get("focus");
  const from = params.get("from");
  const to = params.get("to");

  return {
    ...INITIAL_VIEW,
    ...(zone ? { zone } : {}),
    signal: isSignal(signal) ? signal : INITIAL_VIEW.signal,
    compareSignal: isSignal(compareSignal) ? compareSignal : INITIAL_VIEW.compareSignal,
    compareZones: (params.get("compare") ?? "").split(",").filter(Boolean),
    flowTraced: params.get("mix") !== "production",
    ...(isPanel(focus) ? { focused: focus } : {}),
    ...(from ? { highlight: { from, to: to ?? from } } : {}),
  };
}
