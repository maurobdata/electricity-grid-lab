/**
 * The forward view, laid over what actually happened.
 *
 * History is drawn solid, the forecast dashed, with a divider at the current clock. The
 * point of putting them on one axis is the overlap: wherever a forecast reaches into hours
 * that have since happened, the gap between the two lines is visible directly.
 *
 * On a key without `past-range` there is usually no overlap yet, because history stops
 * roughly where the forecast begins. The panel says so rather than leaving the absence to
 * be misread as agreement — recording daily is what eventually produces the overlap.
 */

import { useMemo } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { TimeSeries } from "@/components/charts/TimeSeries";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/select";
import type { Series } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";

const SIGNALS = [
  { key: "carbon_intensity", label: "Carbon intensity", unit: "gCO₂eq/kWh", zeroBased: true },
  { key: "renewable_percentage", label: "Renewable", unit: "%", zeroBased: true },
  { key: "carbon_free_percentage", label: "Carbon-free", unit: "%", zeroBased: true },
  { key: "price", label: "Day-ahead price", unit: "/MWh", zeroBased: false },
  { key: "load", label: "Load", unit: "MW", zeroBased: true },
] as const;

export function ForecastPanel({
  history,
  forecast,
  signal,
  onSignalChange,
  now,
  forecastUnavailable,
  highlight,
  onClearHighlight,
}: {
  history: Series | undefined;
  forecast: Series | undefined;
  signal: string;
  onSignalChange: (next: string) => void;
  now: string;
  forecastUnavailable?: boolean;
  /** A window a finding or the agent asked to be marked. */
  highlight?: { from: string; to: string };
  onClearHighlight?: () => void;
}) {
  const spec = SIGNALS.find((s) => s.key === signal) ?? SIGNALS[0];

  const overlap = useMemo(() => {
    if (!history?.points.length || !forecast?.points.length) return null;

    const actuals = new Map(history.points.map((p) => [p.at.slice(0, 13), p.value]));
    const pairs = forecast.points
      .map((p) => ({ predicted: p.value, actual: actuals.get(p.at.slice(0, 13)) }))
      .filter((pair): pair is { predicted: number; actual: number } => pair.actual != null);

    if (pairs.length === 0) return null;
    const error =
      pairs.reduce((sum, pair) => sum + Math.abs(pair.predicted - pair.actual), 0) /
      pairs.length;
    return { count: pairs.length, meanAbsoluteError: error };
  }, [history, forecast]);

  const series = [
    ...(history?.points.length
      ? [{ points: history.points, color: "#38bdf8", label: "Actual" }]
      : []),
    ...(forecast?.points.length
      ? [{ points: forecast.points, color: "#facc15", label: "Forecast", dashed: true }]
      : []),
  ];

  const provenance = history?.provenance ?? forecast?.provenance;
  const estimated = Math.max(history?.estimated_fraction ?? 0, forecast?.estimated_fraction ?? 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Forecast vs actual</CardTitle>
          {forecast?.issued_at && (
            <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
              Forecast issued {formatDateTime(forecast.issued_at)}
              {forecast.horizon_hours ? ` · ${forecast.horizon_hours}h horizon` : ""}
            </p>
          )}
        </div>
        <div className="flex items-center gap-1.5">
          {estimated > 0 && (
            <Badge
              variant="warn"
              title="Share of points Electricity Maps modelled rather than measured."
            >
              {formatNumber(estimated * 100)}% est
            </Badge>
          )}
          {provenance && <ProvenanceBadge provenance={provenance} />}
        </div>
      </CardHeader>

      <CardContent>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Select
            value={signal}
            onChange={(event) => onSignalChange(event.target.value)}
            aria-label="Signal"
          >
            {SIGNALS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </Select>

          {/* A highlight arrived from somewhere else — a finding, or the agent — so there
              has to be a visible way back out of it. A mark the reader cannot remove is a
              mark they will assume is part of the data. */}
          {highlight && onClearHighlight && (
            <button
              onClick={onClearHighlight}
              className="rounded-md border border-border px-2 py-1 text-[0.7rem] text-muted-foreground hover:bg-accent"
              title="Stop marking this window"
            >
              Clear highlight
            </button>
          )}
        </div>

        <TimeSeries
          series={series}
          provenance={provenance}
          unit={spec.unit}
          nowAt={now}
          zeroBased={spec.zeroBased}
          highlight={highlight}
          emptyMessage={
            forecastUnavailable ? "No forecast for this signal" : "No data in this window"
          }
        />

        <p className="mt-2 text-[0.7rem] text-muted-foreground">
          {overlap ? (
            <>
              <span className="font-medium text-foreground">
                {formatNumber(overlap.meanAbsoluteError, 1)} {spec.unit}
              </span>{" "}
              mean absolute error across {overlap.count} overlapping hour
              {overlap.count === 1 ? "" : "s"}.
            </>
          ) : (
            <>
              The forecast and the actuals do not overlap yet, so there is nothing to score.
              History reaches back about as far as the forecast reaches forward. Record again
              tomorrow and today&rsquo;s forecast will land on top of tomorrow&rsquo;s actuals.
            </>
          )}
        </p>
      </CardContent>
    </Card>
  );
}
