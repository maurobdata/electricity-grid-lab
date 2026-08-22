/**
 * What the configured token can actually reach.
 *
 * Collapsed to one line until opened, because it is reference rather than monitoring — but
 * present, because "why is there no price for this zone?" is the question this lab will be
 * asked most often, and the answer is almost always here.
 *
 * The measured finding it exists to surface: the free tier is limited by *depth*, not
 * breadth. 350 zones are reachable; arbitrary history is not.
 */

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Capabilities } from "@/lib/api";
import { cn } from "@/lib/utils";

export function CapabilityStrip({ capabilities }: { capabilities: Capabilities | undefined }) {
  const [open, setOpen] = useState(false);
  if (!capabilities) return null;

  const probed = capabilities.source === "probe";
  const reachable = capabilities.signals?.filter((signal) => signal.reachable) ?? [];
  const missing = capabilities.signals?.filter((signal) => !signal.reachable) ?? [];

  return (
    <Card>
      <CardHeader className="cursor-pointer" onClick={() => setOpen((value) => !value)}>
        <div>
          <CardTitle>Token capability</CardTitle>
          <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
            {probed ? (
              <>
                {capabilities.zone_count} zones · {reachable.length} of{" "}
                {capabilities.signals?.length} signals reachable
              </>
            ) : (
              "Not probed"
            )}
          </p>
        </div>
        <Badge variant={probed ? "default" : "warn"}>{open ? "hide" : "details"}</Badge>
      </CardHeader>

      {open && (
        <CardContent>
          {!probed ? (
            <p className="text-xs text-muted-foreground">{capabilities.message}</p>
          ) : (
            <>
              {capabilities.tier_counts && (
                <div className="mb-3 flex flex-wrap gap-1.5">
                  {Object.entries(capabilities.tier_counts)
                    .sort()
                    .map(([tier, count]) => (
                      <Badge key={tier} variant="outline" title={TIER_HINT[tier] ?? ""}>
                        Tier {tier}: {count}
                      </Badge>
                    ))}
                </div>
              )}

              <ul className="grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
                {capabilities.signals?.map((signal) => (
                  <li
                    key={signal.signal}
                    className="flex items-baseline gap-2 text-[0.7rem]"
                    title={signal.note ?? undefined}
                  >
                    <span
                      className={cn(
                        "h-1.5 w-1.5 shrink-0 rounded-full",
                        signal.reachable ? "bg-[var(--color-live)]" : "bg-muted-foreground/40",
                      )}
                    />
                    <span
                      className={cn(
                        "truncate",
                        signal.reachable ? "text-foreground" : "text-muted-foreground/60",
                      )}
                    >
                      {signal.signal}
                    </span>
                    <span className="numeric ml-auto shrink-0 text-muted-foreground">
                      {signal.temporalities.join(" ") || "—"}
                    </span>
                  </li>
                ))}
              </ul>

              {missing.length > 0 && (
                <p className="mt-2 text-[0.65rem] text-muted-foreground">
                  Unreachable signals are not bugs — they are what this plan does not include.
                </p>
              )}

              {capabilities.warnings?.map((warning) => (
                <p
                  key={warning}
                  className="mt-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-2.5 py-2 text-[0.7rem] text-amber-200"
                >
                  {warning}
                </p>
              ))}
            </>
          )}
        </CardContent>
      )}
    </Card>
  );
}

const TIER_HINT: Record<string, string> = {
  A: "Measured hourly. Suitable for comparison and scoring.",
  B: "Partially measured.",
  C: "Monthly or yearly estimates only — not comparable with Tier A.",
  unknown: "No tier reported.",
};
