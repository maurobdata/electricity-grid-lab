/**
 * A small time-series chart, hand-rolled in SVG.
 *
 * No chart library, for three reasons that all point the same way:
 *
 * 1. the shapes needed here are two lines and a band — a library would be mostly unused;
 * 2. the forecast-versus-actual overlay wants exact control of which series is drawn
 *    dashed, which is clipped where, and where the "now" divider sits;
 * 3. the synthetic hatch and the estimated-point markers are the honesty contract, and
 *    they are easier to get exactly right in raw SVG than through a theming API.
 *
 * If a future product needs brushing, zoom or stacked areas, replace this with Recharts
 * rather than growing it. It is meant to be small enough to throw away.
 */

import { useId, useMemo, useState } from "react";

import type { Provenance, ScalarObservation } from "@/lib/api";
import { TIME_ZONE_LABEL, formatNumber, formatTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface SeriesSpec {
  points: ScalarObservation[];
  color: string;
  label: string;
  /** Dashed is the convention here for "predicted", solid for "happened". */
  dashed?: boolean;
}

interface Props {
  series: SeriesSpec[];
  provenance?: Provenance;
  unit?: string;
  /** Drawn as a vertical divider — the boundary between what happened and what is expected. */
  nowAt?: string;
  height?: number;
  /** Pin the lower bound to zero. Right for percentages, wrong for prices, which go below. */
  zeroBased?: boolean;
  /**
   * A stretch of time to mark, drawn behind everything else.
   *
   * Set when a finding or an agent answer is about a particular window. Deliberately a
   * band rather than a crop: the point is to show *where* in the day the thing happens,
   * which is lost the moment the surrounding hours are thrown away.
   */
  highlight?: { from: string; to: string };
  className?: string;
  emptyMessage?: string;
}

const PADDING = { top: 10, right: 8, bottom: 18, left: 38 };

export function TimeSeries({
  series,
  provenance,
  unit,
  nowAt,
  height = 168,
  zeroBased = false,
  highlight,
  className,
  emptyMessage = "No data",
}: Props) {
  const gradientId = useId();
  const [hover, setHover] = useState<number | null>(null);

  const model = useMemo(() => {
    const all = series.flatMap((s) => s.points);
    if (all.length === 0) return null;

    const times = all.map((p) => new Date(p.at).getTime());
    const values = all.map((p) => p.value);

    const tMin = Math.min(...times);
    const tMax = Math.max(...times);
    let vMin = Math.min(...values);
    let vMax = Math.max(...values);

    if (zeroBased) vMin = Math.min(0, vMin);
    // A price series that dips below zero must show the zero line: "the grid is paying
    // you" is the single most counter-intuitive thing this data does, and a chart that
    // floats the axis hides it.
    if (vMin < 0) vMax = Math.max(vMax, 0);

    const span = vMax - vMin || 1;
    const pad = span * 0.08;
    vMin -= pad;
    vMax += pad;

    return { tMin, tMax: tMax === tMin ? tMin + 1 : tMax, vMin, vMax };
  }, [series, zeroBased]);

  if (!model) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-lg border border-dashed border-border",
          "text-xs text-muted-foreground",
          className,
        )}
        style={{ height }}
      >
        {emptyMessage}
      </div>
    );
  }

  const width = 520; // viewBox units; the SVG scales to its container
  const plotWidth = width - PADDING.left - PADDING.right;
  const plotHeight = height - PADDING.top - PADDING.bottom;

  const x = (iso: string) =>
    PADDING.left +
    ((new Date(iso).getTime() - model.tMin) / (model.tMax - model.tMin)) * plotWidth;
  const y = (value: number) =>
    PADDING.top + (1 - (value - model.vMin) / (model.vMax - model.vMin)) * plotHeight;

  const ticks = axisTicks(model.vMin, model.vMax);

  // The series with the most points drives the hover readout, so scrubbing follows the
  // denser of forecast and actual rather than whichever happens to be first.
  const primary = series.reduce(
    (best, s) => (s.points.length > (best?.points.length ?? 0) ? s : best),
    series[0],
  );

  return (
    <div className={cn("relative", className)}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height }}
        role="img"
        aria-label={series.map((s) => s.label).join(" and ")}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          const px = ((event.clientX - rect.left) / rect.width) * width;
          if (!primary || primary.points.length === 0) return;
          let nearest = 0;
          let best = Infinity;
          primary.points.forEach((point, index) => {
            const distance = Math.abs(x(point.at) - px);
            if (distance < best) {
              best = distance;
              nearest = index;
            }
          });
          setHover(nearest);
        }}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={series[0]?.color ?? "#38bdf8"} stopOpacity="0.28" />
            <stop offset="100%" stopColor={series[0]?.color ?? "#38bdf8"} stopOpacity="0" />
          </linearGradient>
        </defs>

        {highlight &&
          (() => {
            /*
             * A window that does not intersect the data is not drawn at all.
             *
             * This used to clamp to the plot edges so a partly-visible window still marked
             * the part that was on screen. That is right for an overlap and badly wrong for
             * a window that misses entirely: switching from an August recording to the May
             * scenario left an August highlight pinned to the right-hand edge as a two-pixel
             * sliver, which reads as "something happens at the very end of this window".
             * Nothing is more misleading than a mark that looks meaningful and is not.
             */
            const from = new Date(highlight.from).getTime();
            const to = new Date(highlight.to).getTime();
            if (Math.max(from, to) < model.tMin || Math.min(from, to) > model.tMax) return null;

            const left = Math.max(PADDING.left, Math.min(x(highlight.from), width - PADDING.right));
            const right = Math.max(PADDING.left, Math.min(x(highlight.to), width - PADDING.right));
            // A zero-length window is an instant, not nothing: give it enough width to see.
            const bandWidth = Math.max(Math.abs(right - left), 2);
            return (
              <rect
                x={Math.min(left, right)}
                y={PADDING.top}
                width={bandWidth}
                height={plotHeight}
                className="fill-primary/15 stroke-primary/40"
                strokeWidth={0.5}
              />
            );
          })()}

        {ticks.map((tick) => (
          <g key={tick}>
            <line
              x1={PADDING.left}
              x2={width - PADDING.right}
              y1={y(tick)}
              y2={y(tick)}
              stroke="currentColor"
              className={cn(
                "text-border",
                // Zero gets a brighter rule. Below it, the price is negative.
                tick === 0 && "text-muted-foreground",
              )}
              strokeWidth={tick === 0 ? 1 : 0.5}
            />
            <text
              x={PADDING.left - 6}
              y={y(tick) + 3}
              textAnchor="end"
              className="fill-muted-foreground text-[9px]"
            >
              {formatNumber(tick, Math.abs(tick) < 10 && tick !== 0 ? 1 : 0)}
            </text>
          </g>
        ))}

        {nowAt && x(nowAt) > PADDING.left && x(nowAt) < width - PADDING.right && (
          <g>
            <line
              x1={x(nowAt)}
              x2={x(nowAt)}
              y1={PADDING.top}
              y2={height - PADDING.bottom}
              stroke="currentColor"
              className="text-muted-foreground"
              strokeWidth={1}
              strokeDasharray="2 3"
            />
            <text
              x={x(nowAt) + 3}
              y={PADDING.top + 8}
              className="fill-muted-foreground text-[8px] uppercase tracking-wider"
            >
              now
            </text>
          </g>
        )}

        {series.map((spec, index) => {
          if (spec.points.length === 0) return null;
          const path = spec.points
            .map((p, i) => `${i === 0 ? "M" : "L"}${x(p.at).toFixed(1)},${y(p.value).toFixed(1)}`)
            .join(" ");

          const first = spec.points[0]!;
          const last = spec.points[spec.points.length - 1]!;
          const area = `${path} L${x(last.at).toFixed(1)},${(height - PADDING.bottom).toFixed(1)} L${x(first.at).toFixed(1)},${(height - PADDING.bottom).toFixed(1)} Z`;

          return (
            <g key={spec.label}>
              {index === 0 && !spec.dashed && <path d={area} fill={`url(#${gradientId})`} />}
              <path
                d={path}
                fill="none"
                stroke={spec.color}
                strokeWidth={1.75}
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={spec.dashed ? "4 3" : undefined}
                opacity={spec.dashed ? 0.85 : 1}
              />
              {/* Modelled points get a hollow marker. On a mostly-estimated series this
                  turns into a visibly dotted line, which is the honest impression. */}
              {spec.points
                .filter((p) => p.is_estimated)
                .map((p) => (
                  <circle
                    key={`${spec.label}-${p.at}`}
                    cx={x(p.at)}
                    cy={y(p.value)}
                    r={1.6}
                    fill="var(--color-background)"
                    stroke={spec.color}
                    strokeWidth={0.9}
                  />
                ))}
            </g>
          );
        })}

        {hover !== null && primary?.points[hover] && (
          <line
            x1={x(primary.points[hover]!.at)}
            x2={x(primary.points[hover]!.at)}
            y1={PADDING.top}
            y2={height - PADDING.bottom}
            stroke="currentColor"
            className="text-foreground/30"
            strokeWidth={1}
          />
        )}

        <text
          x={PADDING.left}
          y={height - 5}
          className="fill-muted-foreground text-[9px]"
        >
          {formatTime(new Date(model.tMin).toISOString())}
        </text>
        {/* The zone, once, rather than on every tick. Without it the axis reads as local
            time and silently disagrees with the finding headlines, which the server
            composes in UTC. */}
        <text
          x={(PADDING.left + width - PADDING.right) / 2}
          y={height - 5}
          textAnchor="middle"
          className="fill-muted-foreground/70 text-[8px]"
        >
          {TIME_ZONE_LABEL}
        </text>
        <text
          x={width - PADDING.right}
          y={height - 5}
          textAnchor="end"
          className="fill-muted-foreground text-[9px]"
        >
          {formatTime(new Date(model.tMax).toISOString())}
        </text>
      </svg>

      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.65rem] text-muted-foreground">
        {series.map((spec) => (
          <span key={spec.label} className="inline-flex items-center gap-1.5">
            <svg width="14" height="4" aria-hidden>
              <line
                x1="0"
                y1="2"
                x2="14"
                y2="2"
                stroke={spec.color}
                strokeWidth="2"
                strokeDasharray={spec.dashed ? "3 2" : undefined}
              />
            </svg>
            {spec.label}
          </span>
        ))}
        {hover !== null && primary?.points[hover] && (
          <span className="numeric ml-auto text-foreground">
            {formatTime(primary.points[hover]!.at)} ·{" "}
            {formatNumber(primary.points[hover]!.value, 1)}
            {unit ? ` ${unit}` : ""}
          </span>
        )}
      </div>

      {provenance === "synthetic" && (
        <div
          className="hatched pointer-events-none absolute inset-0 rounded-lg"
          aria-hidden
          title="Synthetic data — generated, not measured."
        />
      )}
    </div>
  );
}

/** Four or five round-ish gridlines across the range. */
function axisTicks(min: number, max: number): number[] {
  const span = max - min;
  if (span <= 0) return [min];

  const rough = span / 4;
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= rough) ?? magnitude;

  const ticks: number[] = [];
  for (let t = Math.ceil(min / step) * step; t <= max; t += step) {
    ticks.push(Math.abs(t) < step / 1000 ? 0 : t);
  }
  return ticks;
}
