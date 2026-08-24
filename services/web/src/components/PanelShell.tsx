/**
 * The frame every panel sits in.
 *
 * Five panels had each hand-rolled the same header — a title, a small grey subtitle, and a
 * cluster of provenance and estimation badges pushed to the right — in three slightly
 * different ways. That is the sort of duplication that costs nothing until the day the
 * honesty contract changes, at which point the badge has to be found and fixed in five
 * places and will be fixed in four.
 *
 * So the shell owns the parts that must not drift:
 *
 * - **the provenance badge**, which is the whole reason a reader can trust the number;
 * - **the estimated and stale flags**, which qualify it;
 * - **the unavailable state**, so "your plan does not include this" reads differently from
 *   "there is nothing here";
 * - **the focus affordance**, so every panel can be expanded the same way.
 *
 * Panels keep their own content and their own controls. This is a frame, not a template.
 */

import type { ReactNode } from "react";

import { ProvenanceBadge, ValueFlags } from "@/components/ProvenanceBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Provenance } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PanelId } from "@/lib/viewState";

export interface PanelShellProps {
  id: PanelId;
  title: ReactNode;
  subtitle?: ReactNode;
  /** Tabular-figures styling for the subtitle. Right when it is mostly numbers. */
  numericSubtitle?: boolean;

  provenance?: Provenance;
  isEstimated?: boolean;
  isStale?: boolean;
  estimationMethod?: string | null;

  /** Extra header content, placed before the badges. */
  actions?: ReactNode;

  /** Why this panel has nothing to show. Renders instead of the children. */
  unavailable?: ReactNode;

  focused?: boolean;
  onToggleFocus?: (id: PanelId) => void;

  className?: string;
  children?: ReactNode;
}

export function PanelShell({
  id,
  title,
  subtitle,
  numericSubtitle,
  provenance,
  isEstimated,
  isStale,
  estimationMethod,
  actions,
  unavailable,
  focused,
  onToggleFocus,
  className,
  children,
}: PanelShellProps) {
  return (
    <Card className={cn(focused && "ring-1 ring-ring", className)}>
      <CardHeader>
        <div className="min-w-0">
          <CardTitle>{title}</CardTitle>
          {subtitle != null && (
            <p
              className={cn(
                "mt-0.5 text-[0.7rem] text-muted-foreground",
                numericSubtitle && "numeric",
              )}
            >
              {subtitle}
            </p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {actions}
          <ValueFlags isEstimated={isEstimated} isStale={isStale} method={estimationMethod} />
          {provenance && <ProvenanceBadge provenance={provenance} />}
          {onToggleFocus && (
            <button
              onClick={() => onToggleFocus(id)}
              title={focused ? "Show every panel again" : "Show only this panel"}
              aria-label={focused ? "Show every panel again" : "Show only this panel"}
              aria-pressed={focused}
              className={cn(
                "rounded-md border border-border px-1.5 py-0.5 text-[0.65rem] leading-none",
                "text-muted-foreground transition-colors hover:bg-accent",
                // Big enough to hit with a thumb without enlarging the header on desktop.
                "min-h-[1.75rem] min-w-[1.75rem]",
                focused && "bg-accent text-foreground",
              )}
            >
              {focused ? "↙" : "↗"}
            </button>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {unavailable != null ? (
          /*
           * Deliberately not styled as an error. A signal this plan cannot reach is a fact
           * about the plan, not a fault — and a red panel would teach a demo audience to
           * read a perfectly working lab as broken.
           */
          <p className="py-1 text-xs text-muted-foreground">{unavailable}</p>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}
