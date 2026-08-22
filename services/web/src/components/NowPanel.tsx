/**
 * Everything known about one zone, right now.
 *
 * Carbon intensity gets the large number and the colour, because it is the signal the rest
 * of the lab is organised around. The others sit beside it at equal weight.
 *
 * Signals the API reports as unavailable are rendered as explicitly missing rather than
 * omitted. "Your plan does not include day-ahead price" and "nobody asked for it" look
 * identical if you simply leave the card out, and only one of those is worth acting on.
 */

import { ProvenanceBadge, ValueFlags } from "@/components/ProvenanceBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { GridSnapshot, ScalarObservation } from "@/lib/api";
import {
  carbonBand,
  formatDateTime,
  formatNumber,
  formatPower,
  formatRelative,
} from "@/lib/format";
import { cn } from "@/lib/utils";

export function NowPanel({
  snapshot,
  zoneName,
  now,
  stale,
}: {
  snapshot: GridSnapshot;
  zoneName: string;
  /** The lab's clock — wall time when live, the scenario position when replaying. */
  now: string;
  stale?: boolean;
}) {
  const carbon = snapshot.carbon_intensity;
  const band = carbonBand(carbon?.value);
  const missing = new Set(snapshot.unavailable);

  // Age is measured against the lab's clock, not the browser's. During replay those are
  // hours or months apart, and comparing a replayed reading to wall time produced a
  // confident "24h ago" that described nothing at all.
  //
  // The subject is the reading, not the request: `snapshot.at` is just when we asked,
  // which in replay is always "now" by construction. `carbon.at` is the hour the value
  // belongs to, so its age says something real — how far into the hour the grid is.
  const reading = carbon?.at ?? snapshot.at;
  const clock = new Date(now);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Now · {zoneName}</CardTitle>
          <p
            className="numeric mt-0.5 text-[0.7rem] text-muted-foreground"
            title={`Reading timestamped ${formatDateTime(reading)}`}
          >
            {formatDateTime(now)}
            <span className="text-muted-foreground/60">
              {" · reading "}
              {formatRelative(reading, clock)}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <ValueFlags
            isEstimated={carbon?.is_estimated}
            isStale={stale || carbon?.is_stale}
            method={carbon?.estimation_method}
          />
          <ProvenanceBadge provenance={snapshot.provenance} />
        </div>
      </CardHeader>

      <CardContent>
        <div className="flex items-end gap-3">
          <div
            className="numeric text-5xl leading-none font-semibold tabular-nums"
            style={{ color: band.color }}
          >
            {carbon ? formatNumber(carbon.value) : "—"}
          </div>
          <div className="pb-1">
            <div className="text-xs text-muted-foreground">gCO₂eq/kWh</div>
            <div className="text-xs font-medium" style={{ color: band.color }}>
              {band.label}
            </div>
          </div>
        </div>

        {carbon && (
          <p className="mt-1.5 text-[0.7rem] text-muted-foreground">
            {carbon.flow_traced ? "Flow-traced consumption" : "Domestic production"}
            {carbon.emission_factor_type ? ` · ${carbon.emission_factor_type} factors` : ""}
          </p>
        )}

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Metric
            label="Renewable"
            observation={snapshot.renewable_percentage}
            missing={missing.has("renewable_percentage")}
            format={(v) => `${formatNumber(v)}%`}
          />
          <Metric
            label="Carbon-free"
            observation={snapshot.carbon_free_percentage}
            missing={missing.has("carbon_free_percentage")}
            format={(v) => `${formatNumber(v)}%`}
          />
          <Metric
            label="Day-ahead"
            observation={snapshot.price}
            missing={missing.has("price")}
            missingHint="Europe plus a few zones, and often outside a free plan."
            format={(v) => formatNumber(v, 2)}
            suffix={
              snapshot.price ? `${snapshot.price.currency}/${snapshot.price.unit}` : undefined
            }
            // Being paid to consume is the most counter-intuitive thing in this dataset.
            // It should be impossible to scroll past.
            highlight={snapshot.price != null && snapshot.price.value < 0}
            highlightNote="Negative — the grid is paying you to consume."
          />
          <Metric
            label="Load"
            observation={snapshot.load}
            missing={missing.has("load")}
            format={(v) => formatPower(v)}
          />
        </div>

        {snapshot.price?.source && (
          <p className="mt-2 text-[0.65rem] text-muted-foreground">
            Price source: {snapshot.price.source}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({
  label,
  observation,
  missing,
  missingHint,
  format,
  suffix,
  highlight,
  highlightNote,
}: {
  label: string;
  observation: ScalarObservation | null;
  missing: boolean;
  missingHint?: string;
  format: (value: number) => string;
  suffix?: string;
  highlight?: boolean;
  highlightNote?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-muted/40 px-2.5 py-2",
        highlight && "border-amber-500/50 bg-amber-500/10",
      )}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-[0.65rem] tracking-wide text-muted-foreground uppercase">
          {label}
        </span>
        <ValueFlags
          isEstimated={observation?.is_estimated}
          isStale={observation?.is_stale}
          method={observation?.estimation_method}
        />
      </div>

      {observation ? (
        <>
          <div
            className={cn(
              "numeric mt-0.5 text-xl font-semibold",
              highlight && "text-amber-300",
            )}
          >
            {format(observation.value)}
          </div>
          {suffix && <div className="text-[0.65rem] text-muted-foreground">{suffix}</div>}
          {highlight && highlightNote && (
            <div className="mt-0.5 text-[0.65rem] text-amber-300">{highlightNote}</div>
          )}
        </>
      ) : (
        <div className="mt-0.5">
          <div className="text-xl font-semibold text-muted-foreground/50">—</div>
          <div className="text-[0.65rem] text-muted-foreground" title={missingHint}>
            {missing ? "not available here" : "no data"}
          </div>
        </div>
      )}
    </div>
  );
}
