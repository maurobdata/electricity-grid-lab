/**
 * Polling data access.
 *
 * Deliberately small and dependency-free rather than TanStack Query. What this needs is a
 * poll, a last-good value, and an honest error — three behaviours, none of which justify a
 * cache library in a foundation whose product is undecided.
 *
 * The one rule that matters: **never blank a panel that has already shown something.** A
 * failed refresh keeps the previous value and raises a flag; the panel then says the value
 * is stale rather than going empty. That is the same contract `LiveSource` follows on the
 * server, and it is what makes the lab usable on venue wifi.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/lib/api";

export interface Query<T> {
  data: T | undefined;
  error: Error | undefined;
  /** True only before the first successful load. Never true again after data arrives. */
  loading: boolean;
  /** True when the last refresh failed but an earlier value is still on screen. */
  stale: boolean;
  /** Status code when the failure was an HTTP error, so callers can treat 404 as "absent". */
  status: number | undefined;
  refresh: () => void;
}

export function useQuery<T>(
  fetcher: () => Promise<T>,
  /** What the answer is *about*. A change here means a different question, so the previous
   *  answer is discarded rather than shown while the new one loads. */
  deps: readonly unknown[],
  options: {
    intervalMs?: number;
    enabled?: boolean;
    /**
     * Forces a refetch without discarding what is on screen.
     *
     * Distinct from `deps` on purpose. Pausing the replay clock should re-read the state
     * without blanking every panel; loading a different scenario should blank them,
     * because the numbers are then about something else. Conflating the two gives you one
     * behaviour and the wrong one either way.
     */
    refreshToken?: unknown;
  } = {},
): Query<T> {
  const { intervalMs = 0, enabled = true, refreshToken } = options;

  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [stale, setStale] = useState(false);
  const [loading, setLoading] = useState(enabled);
  const [status, setStatus] = useState<number>();
  const [tick, setTick] = useState(0);

  // Kept in a ref so the polling effect does not need `fetcher` in its dependency list —
  // callers pass an inline closure, which would otherwise restart the timer every render.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const hasData = useRef(false);

  /*
   * Keeping the last good value is right across *refreshes of the same question*, and
   * wrong across a change of question.
   *
   * Switching to a scenario with different zones once left the comparison panel showing
   * the previous scenario's numbers — still badged `recorded` — underneath a banner
   * announcing that everything on screen was synthetic. Exactly the confusion the
   * provenance contract exists to prevent, produced by the mechanism meant to protect it.
   *
   * So identity is tracked separately from freshness: when the deps change, the answer is
   * to a different question and the old one is discarded.
   */
  const identity = safeKey(deps);
  const lastIdentity = useRef(identity);
  if (lastIdentity.current !== identity) {
    lastIdentity.current = identity;
    hasData.current = false;
    // Render-phase state updates are legitimate here: React re-renders immediately with
    // the new values rather than committing the stale ones and correcting in an effect.
    setData(undefined);
    setError(undefined);
    setStatus(undefined);
    setStale(false);
    setLoading(enabled);
  }

  useEffect(() => {
    if (!enabled) {
      // A disabled query holds nothing. Leaving the previous answer visible is the same
      // bug in a different shape.
      hasData.current = false;
      setData(undefined);
      setLoading(false);
      return;
    }

    let cancelled = false;
    let timer: number | undefined;

    const run = async () => {
      try {
        const result = await fetcherRef.current();
        if (cancelled) return;
        setData(result);
        hasData.current = true;
        setError(undefined);
        setStatus(undefined);
        setStale(false);
      } catch (caught) {
        if (cancelled) return;
        const err = caught instanceof Error ? caught : new Error(String(caught));
        setError(err);
        setStatus(err instanceof ApiError ? err.status : undefined);
        // Keep whatever is already on screen. Only mark it stale.
        setStale(hasData.current);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void run();
    if (intervalMs > 0) timer = window.setInterval(run, intervalMs);

    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, intervalMs, enabled, tick, refreshToken]);

  const refresh = useCallback(() => setTick((n) => n + 1), []);

  return { data, error, loading, stale, status, refresh };
}

/** A stable string for a dependency list, tolerant of values JSON cannot represent. */
function safeKey(deps: readonly unknown[]): string {
  return deps
    .map((dep) => {
      if (dep == null) return String(dep);
      if (typeof dep === "object") {
        try {
          return JSON.stringify(dep);
        } catch {
          return "[unserialisable]";
        }
      }
      return String(dep);
    })
    .join("|");
}

/**
 * How often to re-poll, in milliseconds.
 *
 * Replay runs at a speed multiplier, so wall-clock polling has to be faster to keep up:
 * at 60x an hour of simulated time passes in a minute, and a 30-second poll would skip
 * most of it. Live data updates hourly at best and sits behind a five-minute server-side
 * cache, so polling harder than that only burns requests.
 */
export function pollInterval(mode: "live" | "replay", speed = 1) {
  if (mode === "live") return 60_000;
  return Math.max(1000, Math.round(30_000 / Math.max(speed, 1)));
}
