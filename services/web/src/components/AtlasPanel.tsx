/**
 * Cheap versus clean, across every grid the token can reach.
 *
 * One zone's price/carbon divergence is an observation. The same number computed for
 * forty-one European zones is a different kind of object — it says where the disagreement
 * has consequences, where it barely exists, and where clean happens to be nearly free.
 *
 * **Sorted by avoidable carbon, not by correlation**, and that default is the whole lesson
 * of the first sweep. Rank correlation is scale-free: NO-NO3 scored -0.85 on 24 August 2026
 * over a carbon range of three points, so choosing its clean window buys 2.7 gCO₂eq/kWh for
 * a 95 EUR/MWh premium. Ranking on the coefficient puts that zone first. Ranking on what the
 * choice avoids puts Croatia first, at 120 gCO₂eq/kWh for 70 EUR/MWh — a trade somebody
 * could reasonably make either way. So both numbers are shown on every row, because neither
 * can be read without the other.
 *
 * **Deliberately not a map.** Electricity Maps' own map is better than anything built here,
 * and every research pass reached that conclusion independently (ADR 0006).
 */

import { PanelShell } from "@/components/PanelShell";
import { Select } from "@/components/ui/select";
import type { Atlas, AtlasZone } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PanelId, ViewIntent } from "@/lib/viewState";

const SORTS = [
  { key: "carbon_avoided", label: "Carbon you could avoid" },
  { key: "price_premium", label: "What avoiding it costs" },
  { key: "correlation", label: "Least agreement" },
  { key: "zone", label: "Zone name" },
] as const;

export function AtlasPanel({
  atlas,
  unavailable,
  sort,
  onSortChange,
  onIntent,
  currentZone,
  availableZones,
  focused,
  onToggleFocus,
}: {
  atlas: Atlas | undefined;
  unavailable?: boolean;
  sort: string;
  onSortChange: (next: string) => void;
  onIntent?: (intent: ViewIntent) => void;
  currentZone?: string;
  /**
   * Zones the lab can actually open right now.
   *
   * The atlas sweeps forty-one live zones; a replay scenario holds two. Without this, every
   * row looked clickable and thirty-nine of them silently did nothing — the reducer set the
   * zone and the reconciliation effect put it straight back. A control that appears to work
   * and does not is worse than one that explains why it cannot.
   */
  availableZones: string[];
  focused?: boolean;
  onToggleFocus?: (id: PanelId) => void;
}) {
  const open = new Set(availableZones);
  const scored = (atlas?.zones ?? []).filter((z) => z.status === "ok");
  const unscored = (atlas?.zones ?? []).filter((z) => z.status !== "ok");
  const peak = Math.max(1, ...scored.map((z) => Math.abs(z.carbon_avoided ?? 0)));

  return (
    <PanelShell
      id="atlas"
      title="Across the grids"
      subtitle={
        atlas
          ? `${atlas.summary.zones_scored} zones · swept ${atlas.computed_at.slice(0, 16).replace("T", " ")} UTC`
          : undefined
      }
      numericSubtitle
      provenance={atlas?.summary.provenance}
      focused={focused}
      onToggleFocus={onToggleFocus}
      unavailable={
        unavailable
          ? "No sweep yet. `make atlas` builds one — it needs an Electricity Maps token, and there is no replay equivalent: one zone's numbers can be replayed, a picture of every grid cannot."
          : !atlas
            ? "Loading…"
            : undefined
      }
    >
      <>
        <Select
          value={sort}
          onChange={(event) => onSortChange(event.target.value)}
          className="mb-3"
          aria-label="Sort the atlas"
        >
          {SORTS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </Select>

        <div className="space-y-1">
          {scored.map((zone) => (
            <AtlasRow
              key={zone.zone}
              zone={zone}
              peak={peak}
              current={zone.zone === currentZone}
              loadable={open.has(zone.zone)}
              onClick={
                onIntent && open.has(zone.zone)
                  ? () =>
                      onIntent({
                        kind: "select_zone",
                        zone: zone.zone,
                        reason: `look at ${zone.zone} on its own`,
                      })
                  : undefined
              }
            />
          ))}
        </div>

        {unscored.length > 0 && (
          /* Kept rather than dropped. "No day-ahead market here" is a fact about coverage,
             and hiding it would make the atlas look more complete than it is. */
          <p className="mt-3 text-[0.65rem] text-muted-foreground">
            {unscored.length} zone{unscored.length === 1 ? "" : "s"} could not be scored:{" "}
            {unscored.map((z) => `${z.zone} (${z.status.replace("no_", "no ")})`).join(", ")}
          </p>
        )}

        {atlas && (
          <p className="mt-3 border-t border-border pt-2 text-[0.65rem] text-muted-foreground">
            {atlas.summary.caveats[0]}
          </p>
        )}
      </>
    </PanelShell>
  );
}

function AtlasRow({
  zone,
  peak,
  current,
  loadable,
  onClick,
}: {
  zone: AtlasZone;
  peak: number;
  current: boolean;
  loadable: boolean;
  onClick?: () => void;
}) {
  const avoided = zone.carbon_avoided ?? 0;
  const width = (Math.abs(avoided) / peak) * 100;
  // A wide carbon range is what makes the correlation meaningful. Narrow ones are muted so
  // a striking coefficient over a three-point spread does not draw the eye first.
  const thin = (zone.carbon_spread ?? 0) < 20;

  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      title={
        `${zone.zone}: carbon ranges ${formatNumber(zone.carbon_spread ?? 0)} gCO₂eq/kWh over the window. ` +
        `Choosing the cleanest block instead of the cheapest avoids ${formatNumber(avoided)} gCO₂eq/kWh ` +
        `and costs ${formatNumber(zone.price_premium ?? 0)} ${zone.price_unit ?? "EUR/MWh"}. ` +
        `Rank correlation ${zone.correlation ?? "n/a"} (${zone.agreement ?? "unknown"}).` +
        (loadable
          ? ""
          : ` The lab is not holding ${zone.zone} right now — the atlas is a live sweep, and a` +
            ` replay scenario carries only the zones it recorded.`)
      }
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs transition-colors",
        onClick && "hover:bg-accent",
        !loadable && "cursor-default",
        current && "bg-primary/10 ring-1 ring-ring",
      )}
    >
      <span
        className={cn("numeric w-16 shrink-0 truncate", !loadable && "text-muted-foreground")}
      >
        {zone.zone}
      </span>

      <span className="relative h-3 flex-1">
        <span
          className={cn(
            "absolute inset-y-0 left-0 rounded-sm transition-all duration-500",
            thin ? "bg-muted-foreground/30" : "bg-[var(--color-live)]/70",
          )}
          style={{ width: `${width}%` }}
        />
      </span>

      <span className="numeric w-20 shrink-0 text-right">
        {formatNumber(avoided)} g
      </span>
      <span className="numeric hidden w-24 shrink-0 text-right text-muted-foreground sm:inline">
        +{formatNumber(zone.price_premium ?? 0)}
      </span>
      <span
        className={cn(
          "numeric w-14 shrink-0 text-right",
          thin ? "text-muted-foreground/50" : "text-muted-foreground",
        )}
      >
        {zone.correlation === null || zone.correlation === undefined
          ? "—"
          : formatNumber(zone.correlation, 2)}
      </span>
    </button>
  );
}
