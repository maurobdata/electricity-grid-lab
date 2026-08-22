/**
 * Where a number came from.
 *
 * This is the component the whole honesty contract rests on, so it is deliberately not
 * subtle. `synthetic` gets its own colour, its own word, and — wherever a chart is drawn
 * from generated data — a diagonal hatch behind it, so that even a cropped screenshot with
 * no legend still reads as "not real".
 *
 * The rule from `CLAUDE.md`: never let synthetic data look measured.
 */

import { Badge } from "@/components/ui/badge";
import type { Provenance } from "@/lib/api";
import { PROVENANCE_BLURB, PROVENANCE_LABEL } from "@/lib/format";
import { cn } from "@/lib/utils";

const DOT: Record<Provenance, string> = {
  live: "bg-[var(--color-live)]",
  recorded: "bg-[var(--color-recorded)]",
  synthetic: "bg-[var(--color-synthetic)]",
};

const TONE: Record<Provenance, string> = {
  live: "border-[var(--color-live)]/40 text-[var(--color-live)] bg-[var(--color-live)]/10",
  recorded:
    "border-[var(--color-recorded)]/40 text-[var(--color-recorded)] bg-[var(--color-recorded)]/10",
  synthetic:
    "border-[var(--color-synthetic)]/50 text-[var(--color-synthetic)] bg-[var(--color-synthetic)]/15",
};

export function ProvenanceBadge({
  provenance,
  className,
}: {
  provenance: Provenance;
  className?: string;
}) {
  return (
    <Badge
      variant="outline"
      className={cn(TONE[provenance], className)}
      title={PROVENANCE_BLURB[provenance]}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          DOT[provenance],
          // Only live data pulses. A recording is real but finished; nothing about it is
          // arriving, and animating it would suggest otherwise.
          provenance === "live" && "animate-pulse",
        )}
      />
      {PROVENANCE_LABEL[provenance]}
    </Badge>
  );
}

/**
 * The two qualifiers that ride along with a value.
 *
 * `estimated` means Electricity Maps modelled it rather than measuring it — common, and
 * disqualifying for anything that scores or ranks. `stale` means our own last refresh
 * failed and this is the previous value.
 */
export function ValueFlags({
  isEstimated,
  isStale,
  method,
  className,
}: {
  isEstimated?: boolean;
  isStale?: boolean;
  method?: string | null;
  className?: string;
}) {
  if (!isEstimated && !isStale) return null;
  return (
    <span className={cn("inline-flex gap-1", className)}>
      {isEstimated && (
        <Badge
          variant="warn"
          title={
            method
              ? `Modelled by Electricity Maps, not measured (${method}).`
              : "Modelled by Electricity Maps, not measured."
          }
        >
          est
        </Badge>
      )}
      {isStale && (
        <Badge variant="danger" title="The last refresh failed. This is the previous value.">
          stale
        </Badge>
      )}
    </span>
  );
}
