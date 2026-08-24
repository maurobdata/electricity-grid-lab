/**
 * The generation mix, with the flow-tracing toggle.
 *
 * This is the panel that justifies choosing Electricity Maps over any other source, so the
 * toggle is not a settings checkbox tucked away somewhere — it is the first control, and
 * the difference between the two answers is computed and shown rather than left for the
 * viewer to spot by flicking back and forth.
 *
 *   Production   — what this zone generated.
 *   Flow-traced  — what is actually in the socket, with imports traced back to origin.
 *
 * On DK-DK2 those differ by around fourteen points of wind. That gap *is* the story: a
 * grid can generate a great deal of wind and still be consuming somebody else's coal.
 */

import { useMemo } from "react";

import { PanelShell } from "@/components/PanelShell";
import { Button } from "@/components/ui/button";
import type { MixBreakdown } from "@/lib/api";
import { formatNumber, formatPower, isFossil, sourceColor } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PanelId } from "@/lib/viewState";

export function MixPanel({
  mix,
  other,
  flowTraced,
  onToggle,
  unavailable,
  focused,
  onToggleFocus,
}: {
  mix: MixBreakdown | undefined;
  /** The other breakdown, when loaded — used only to quantify the difference. */
  other: MixBreakdown | undefined;
  flowTraced: boolean;
  onToggle: (next: boolean) => void;
  unavailable?: boolean;
  focused?: boolean;
  onToggleFocus?: (id: PanelId) => void;
}) {
  const entries = useMemo(
    () =>
      [...(mix?.entries ?? [])]
        .filter((entry) => (entry.percent ?? 0) > 0.05)
        .sort((a, b) => (b.percent ?? 0) - (a.percent ?? 0)),
    [mix],
  );

  const fossilShare = entries
    .filter((entry) => isFossil(entry.source))
    .reduce((sum, entry) => sum + (entry.percent ?? 0), 0);

  // The headline comparison. Wind is the right probe for Denmark; for a nuclear-heavy
  // zone the largest mover is more informative, so pick whichever source moved most.
  const divergence = useMemo(() => {
    if (!mix || !other) return null;
    const byOther = new Map(other.entries.map((e) => [e.source, e.percent ?? 0]));
    let best: { source: string; here: number; there: number; delta: number } | null = null;
    for (const entry of mix.entries) {
      const here = entry.percent ?? 0;
      const there = byOther.get(entry.source) ?? 0;
      const delta = Math.abs(here - there);
      if (delta > (best?.delta ?? 0.5)) best = { source: entry.source, here, there, delta };
    }
    return best;
  }, [mix, other]);

  return (
    <PanelShell
      id="mix"
      title="Generation mix"
      numericSubtitle
      subtitle={
        mix?.total_mw != null
          ? `${formatPower(mix.total_mw)} total · ${formatNumber(fossilShare, 1)}% fossil`
          : undefined
      }
      provenance={mix?.provenance}
      isEstimated={mix?.is_estimated}
      isStale={mix?.is_stale}
      focused={focused}
      onToggleFocus={onToggleFocus}
    >
      {/* The toggle stays reachable even with nothing to show, so a reader who lands on an
          unavailable breakdown can switch to the one that exists. */}
      <>
        <div className="mb-3 inline-flex rounded-lg border border-border bg-muted/50 p-0.5">
          <Button
            variant="ghost"
            onClick={() => onToggle(false)}
            className={cn("rounded-md", !flowTraced && "bg-primary/15 text-primary")}
            title="What this zone generated."
          >
            Production
          </Button>
          <Button
            variant="ghost"
            onClick={() => onToggle(true)}
            className={cn("rounded-md", flowTraced && "bg-primary/15 text-primary")}
            title="What is available here once imports are traced back to their origin."
          >
            Flow-traced
          </Button>
        </div>

        {unavailable || !mix ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            {unavailable ? "Not available for this zone." : "Loading…"}
          </p>
        ) : (
          <>
            <div className="flex h-7 w-full overflow-hidden rounded-md">
              {entries.map((entry) => (
                <div
                  key={entry.source}
                  className="h-full transition-all duration-500"
                  style={{
                    width: `${entry.percent ?? 0}%`,
                    backgroundColor: sourceColor(entry.source),
                  }}
                  title={`${entry.source}: ${formatNumber(entry.percent ?? 0, 1)}% (${formatPower(entry.power_mw)})`}
                />
              ))}
            </div>

            <ul className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
              {entries.map((entry) => (
                <li key={entry.source} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{ backgroundColor: sourceColor(entry.source) }}
                  />
                  <span className="truncate text-muted-foreground">{entry.source}</span>
                  <span className="numeric ml-auto tabular-nums">
                    {formatNumber(entry.percent ?? 0, 1)}%
                  </span>
                </li>
              ))}
            </ul>

            {divergence && divergence.delta >= 1 && (
              <p className="mt-3 rounded-md border border-border bg-muted/40 px-2.5 py-2 text-[0.7rem] text-muted-foreground">
                <span className="font-medium text-foreground">
                  {formatNumber(divergence.delta, 1)} points of {divergence.source}
                </span>{" "}
                separate the two views — {formatNumber(divergence.here, 1)}% here versus{" "}
                {formatNumber(divergence.there, 1)}%{" "}
                {flowTraced ? "as generated" : "once imports are traced"}. Only flow-tracing
                can tell you which one is in the socket.
              </p>
            )}
          </>
        )}
      </>
    </PanelShell>
  );
}
