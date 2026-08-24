/**
 * The same signal, the same instant, several places.
 *
 * Simultaneity is the point. Two hundred places in wildly different states at the same
 * moment is inherently astonishing, and almost never shown.
 *
 * The caveat the API returns with every comparison is repeated here rather than dropped,
 * because it is the difference between a useful panel and a misleading one: **ranking
 * zones on raw values produces a frozen table.** Norway's hydro wins every day and Poland's
 * coal loses every day, so nothing changes and there is no reason to look twice. Anything
 * built on top of this that wants a *league* has to score each zone against its own
 * baseline. This panel deliberately does not pretend otherwise.
 */

import { PanelShell } from "@/components/PanelShell";
import { Badge } from "@/components/ui/badge";
import { Select } from "@/components/ui/select";
import type { Comparison, ZoneInfo } from "@/lib/api";
import { carbonBand, formatNumber, zoneLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PanelId } from "@/lib/viewState";

const SIGNALS = [
  { key: "carbon_intensity", label: "Carbon intensity", unit: "gCO₂eq/kWh", lowerIsBetter: true },
  { key: "renewable_percentage", label: "Renewable", unit: "%", lowerIsBetter: false },
  { key: "carbon_free_percentage", label: "Carbon-free", unit: "%", lowerIsBetter: false },
  { key: "price", label: "Day-ahead price", unit: "/MWh", lowerIsBetter: true },
  { key: "load", label: "Load", unit: "MW", lowerIsBetter: false },
] as const;

export function ComparePanel({
  comparison,
  zones,
  selected,
  onToggleZone,
  signal,
  onSignalChange,
  focused,
  onToggleFocus,
}: {
  comparison: Comparison | undefined;
  zones: ZoneInfo[];
  selected: string[];
  onToggleZone: (zone: string) => void;
  signal: string;
  onSignalChange: (next: string) => void;
  focused?: boolean;
  onToggleFocus?: (id: PanelId) => void;
}) {
  const spec = SIGNALS.find((s) => s.key === signal) ?? SIGNALS[0];

  const rows = Object.entries(comparison?.zones ?? {})
    .map(([zone, observation]) => ({ zone, observation }))
    .sort((a, b) => {
      if (!a.observation) return 1;
      if (!b.observation) return -1;
      return spec.lowerIsBetter
        ? a.observation.value - b.observation.value
        : b.observation.value - a.observation.value;
    });

  const peak = Math.max(
    1,
    ...rows.map((row) => Math.abs(row.observation?.value ?? 0)),
  );

  return (
    <PanelShell
      id="compare"
      title="Compare zones"
      subtitle="Same instant, different places"
      provenance={comparison?.provenance}
      focused={focused}
      onToggleFocus={onToggleFocus}
    >
      <>
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          <Select
            value={signal}
            onChange={(event) => onSignalChange(event.target.value)}
            aria-label="Comparison signal"
          >
            {SIGNALS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </Select>
          {zones.map((zone) => (
            <button
              key={zone.key}
              onClick={() => onToggleZone(zone.key)}
              className={cn(
                "rounded-md border px-1.5 py-0.5 text-[0.65rem] transition-colors",
                selected.includes(zone.key)
                  ? "border-primary/50 bg-primary/15 text-primary"
                  : "border-border text-muted-foreground hover:bg-accent",
              )}
              title={zone.name}
            >
              {zone.key}
            </button>
          ))}
        </div>

        {selected.length < 2 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            Pick at least two zones.
          </p>
        ) : rows.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">Loading…</p>
        ) : (
          <div className="space-y-1.5">
            {rows.map(({ zone, observation }) => {
              const value = observation?.value;
              const color =
                signal === "carbon_intensity"
                  ? carbonBand(value).color
                  : "var(--color-primary)";
              return (
                <div key={zone} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-24 shrink-0 truncate text-muted-foreground"
                    title={zoneLabel(zone, zones.find((z) => z.key === zone)?.name)}
                  >
                    {zone}
                  </span>
                  <div className="h-4 flex-1 overflow-hidden rounded-sm bg-muted/50">
                    {value != null && (
                      <div
                        className="h-full rounded-sm transition-all duration-500"
                        style={{
                          width: `${(Math.abs(value) / peak) * 100}%`,
                          backgroundColor: color,
                          opacity: 0.75,
                        }}
                      />
                    )}
                  </div>
                  <span className="numeric w-24 shrink-0 text-right">
                    {value != null ? formatNumber(value, spec.unit === "/MWh" ? 2 : 0) : "—"}
                    {observation?.is_estimated && (
                      <Badge variant="warn" className="ml-1">
                        est
                      </Badge>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <p className="mt-3 rounded-md border border-border bg-muted/40 px-2.5 py-2 text-[0.7rem] text-muted-foreground">
          Raw values. Ranking zones on these flatters hydro and punishes coal permanently —
          Iceland always wins, Poland always loses, and the table never changes. A league
          worth returning to has to score each zone against its own baseline.
        </p>
      </>
    </PanelShell>
  );
}
