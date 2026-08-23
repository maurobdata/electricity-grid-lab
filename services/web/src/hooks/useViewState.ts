/**
 * The view state, bound to the address bar.
 *
 * One hook owns what the app is looking at. Everything that wants to change it — a control,
 * a finding, the agent — goes through {@link ViewController.dispatch}, so there is exactly
 * one path and it is the tested one.
 *
 * **The URL is a projection, not a second copy.** State changes, then the URL is rewritten
 * from it. Nothing reads the URL back except on first load and on Back/Forward, which is
 * what stops a link and a click from disagreeing about what is on screen.
 *
 * `replaceState` rather than `pushState`, deliberately. Choosing a signal is not navigation,
 * and a page that stacks a history entry every time somebody drags a control turns the Back
 * button into a chore. The address bar stays shareable; the history stays useful.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { Mode } from "@/lib/api";
import type { ViewIntent, ViewState } from "@/lib/viewState";
import { apply, canApply, fromQuery, toQuery } from "@/lib/viewState";

export interface ViewController {
  view: ViewState;
  /** Apply an intent from anywhere: a control, a finding, the agent. */
  dispatch: (intent: ViewIntent) => void;
  /** Change one field directly, for ordinary controls that need no explaining. */
  set: <K extends keyof ViewState>(key: K, value: ViewState[K]) => void;
  clearHighlight: () => void;
  /** Why this intent cannot be carried out right now, or null when it can. */
  blocked: (intent: ViewIntent) => string | null;
}

export function useViewState(mode: Mode, onSeek?: (to: string) => void): ViewController {
  const [view, setView] = useState<ViewState>(() =>
    fromQuery(typeof window === "undefined" ? "" : window.location.search),
  );

  /*
   * Refs, so `dispatch` can be stable.
   *
   * `mode` changes on every status poll and `onSeek` is an inline closure, so putting
   * either in a dependency list would rebuild `dispatch` constantly and re-render every
   * consumer holding it. The view is mirrored for the same reason: `dispatch` needs to read
   * the current state to decide whether a seek is possible, and closing over the state
   * value directly would make it stale the moment anything changed.
   */
  const modeRef = useRef(mode);
  modeRef.current = mode;

  const seekRef = useRef(onSeek);
  seekRef.current = onSeek;

  const viewRef = useRef(view);
  viewRef.current = view;

  useEffect(() => {
    const query = toQuery(view);
    const next = `${window.location.pathname}${query ? `?${query}` : ""}`;
    if (next !== `${window.location.pathname}${window.location.search}`) {
      window.history.replaceState(null, "", next);
    }
  }, [view]);

  // Back and Forward are the one case where the URL leads. Without this the address bar
  // would change and the page would not, which is worse than not supporting them at all.
  useEffect(() => {
    const onPop = () => setView(fromQuery(window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  const dispatch = useCallback((intent: ViewIntent) => {
    if (canApply(intent, viewRef.current, modeRef.current) !== null) return;

    setView((current) => apply(current, intent));

    // `seek` is not view state: the clock lives on the server, so the reducer ignores it
    // and the caller performs it. Done here rather than in the reducer, which stays pure.
    if (intent.kind === "seek" && intent.at) seekRef.current?.(intent.at);
  }, []);

  const set = useCallback(<K extends keyof ViewState>(key: K, value: ViewState[K]) => {
    setView((current) => ({ ...current, [key]: value }));
  }, []);

  const clearHighlight = useCallback(() => {
    setView((current) => (current.highlight ? { ...current, highlight: undefined } : current));
  }, []);

  const blocked = useCallback(
    (intent: ViewIntent) => canApply(intent, viewRef.current, modeRef.current),
    [],
  );

  return { view, dispatch, set, clearHighlight, blocked };
}
