/**
 * Cross-border exchange, per neighbour.
 *
 * A diverging bar from a centre line: exports to the right, imports to the left. That
 * reads faster than a signed number, and it makes the asymmetric case obvious — a zone
 * simultaneously importing from one neighbour and exporting to another is the normal
 * state, not an anomaly.
 *
 * Deliberately not a map. Electricity Maps' own map is better than anything built here
 * would be, and every research pass reached the same conclusion independently.
 */

import { PanelShell } from "@/components/PanelShell";
import type { Flows } from "@/lib/api";
import { formatPower } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { PanelId } from "@/lib/viewState";

export function FlowsPanel({
  flows,
  unavailable,
  focused,
  onToggleFocus,
}: {
  flows: Flows | undefined;
  unavailable?: boolean;
  focused?: boolean;
  onToggleFocus?: (id: PanelId) => void;
}) {
  const edges = [...(flows?.edges ?? [])].sort(
    (a, b) => Math.abs(b.net_flow_mw) - Math.abs(a.net_flow_mw),
  );
  const peak = Math.max(1, ...edges.map((edge) => Math.abs(edge.net_flow_mw)));
  const netImport = flows?.net_import_mw ?? 0;

  return (
    <PanelShell
      id="flows"
      title="Cross-border flows"
      numericSubtitle
      subtitle={
        flows
          ? `${netImport >= 0 ? "Net importer" : "Net exporter"} · ${formatPower(Math.abs(netImport))}`
          : undefined
      }
      provenance={flows?.provenance}
      isEstimated={flows?.is_estimated}
      isStale={flows?.is_stale}
      focused={focused}
      onToggleFocus={onToggleFocus}
      unavailable={
        unavailable
          ? "Not available for this zone."
          : !flows
            ? "Loading…"
            : undefined
      }
    >
      <>
        {edges.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            No interconnector data.
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              {edges.map((edge) => {
                const exporting = edge.net_flow_mw >= 0;
                const width = (Math.abs(edge.net_flow_mw) / peak) * 50;
                return (
                  <div key={edge.counterpart_zone} className="flex items-center gap-2 text-xs">
                    <span className="numeric w-16 shrink-0 truncate text-muted-foreground">
                      {edge.counterpart_zone}
                    </span>
                    <div className="relative h-4 flex-1">
                      <div className="absolute inset-y-0 left-1/2 w-px bg-border" />
                      <div
                        className={cn(
                          "absolute inset-y-0.5 rounded-sm transition-all duration-500",
                          exporting ? "bg-[var(--color-live)]/70" : "bg-amber-500/70",
                        )}
                        style={
                          exporting
                            ? { left: "50%", width: `${width}%` }
                            : { right: "50%", width: `${width}%` }
                        }
                      />
                    </div>
                    <span
                      className={cn(
                        "numeric w-20 shrink-0 text-right",
                        exporting ? "text-[var(--color-live)]" : "text-amber-400",
                      )}
                    >
                      {formatPower(Math.abs(edge.net_flow_mw))}
                    </span>
                  </div>
                );
              })}
            </div>

            <div className="mt-2 flex justify-between text-[0.65rem] text-muted-foreground">
              <span>← importing from</span>
              <span>exporting to →</span>
            </div>
          </>
        )}
      </>
    </PanelShell>
  );
}
