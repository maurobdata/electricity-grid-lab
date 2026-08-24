/**
 * What the lab found before anybody asked.
 *
 * A dashboard waits to be interrogated: it shows everything, ranks nothing, and leaves the
 * reader to notice that tonight's price goes below zero — which they will not, because
 * noticing is work and a panel of charts gives no reason to start.
 *
 * This is the answer to that. Every chip is a deterministic finding from
 * `gridlab/analysis/events.py` — arithmetic, no language model, computed on every poll for
 * nothing — and clicking one dispatches the {@link ViewIntent} it carries, which moves the
 * charts to the moment it is about. Same mechanism the agent uses to propose a view, so
 * a finding and an answer steer the interface identically.
 *
 * The empty state matters as much as the full one. A quiet grid is quiet, and saying so is
 * a real answer; inventing something to fill the rail would make every other chip worth
 * less.
 */

import { useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { narrate, type Finding, type Findings, type Narration } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ViewIntent } from "@/lib/viewState";

/** A word per detector, so a reader can tell the kinds apart at a glance. */
const KIND_LABEL: Record<string, string> = {
  negative_price: "Negative price",
  carbon_swing: "Carbon swing",
  renewable_surge: "Renewable surge",
  import_dependence: "Imported power",
  cheap_clean_divergence: "Cheap ≠ clean",
};

const KIND_TONE: Record<string, string> = {
  negative_price: "border-sky-500/40 bg-sky-500/10 text-sky-300",
  carbon_swing: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  renewable_surge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  import_dependence: "border-violet-500/40 bg-violet-500/10 text-violet-300",
  cheap_clean_divergence: "border-rose-500/40 bg-rose-500/10 text-rose-300",
};

export function FindingsRail({
  findings,
  unavailable,
  onIntent,
  activeId,
}: {
  findings: Findings | undefined;
  unavailable?: boolean;
  onIntent: (intent: ViewIntent, findingId: string) => void;
  activeId?: string;
}) {
  const items = findings?.findings ?? [];

  /*
   * Explanations, fetched on demand and remembered.
   *
   * On demand because each is a model call, and a rail of five findings that narrated
   * itself on arrival would spend five calls to answer a question nobody asked. Remembered
   * because the server caches by finding id and this avoids even the round trip.
   */
  const [explained, setExplained] = useState<Record<string, Narration | "loading">>({});
  const [open, setOpen] = useState<string>();

  const explain = (finding: Finding) => {
    setOpen((current) => (current === finding.id ? undefined : finding.id));
    if (explained[finding.id]) return;
    setExplained((current) => ({ ...current, [finding.id]: "loading" }));
    void narrate(finding)
      .then((n) => setExplained((current) => ({ ...current, [finding.id]: n })))
      .catch(() =>
        setExplained((current) => ({
          ...current,
          // Never a dead end: the finding's own words are always available.
          [finding.id]: { id: finding.id, text: finding.detail, source: "template", cached: false },
        })),
      );
  };

  const showing = open ? explained[open] : undefined;

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Worth a look</CardTitle>
          <p className="mt-0.5 text-[0.7rem] text-muted-foreground">
            Found by arithmetic, not by a model. Click one to see the moment it is about.
          </p>
        </div>
        {items[0] && <ProvenanceBadge provenance={items[0].derived.provenance} />}
      </CardHeader>

      <CardContent>
        {items.length === 0 ? (
          <p className="py-1 text-xs text-muted-foreground">
            {unavailable
              ? "Nothing to analyse for this zone yet."
              : "Nothing unusual in this window. A quiet grid is a real answer — nothing is invented to fill this space."}
          </p>
        ) : (
          /*
           * A horizontal rail that scrolls rather than wrapping. Findings are ranked, so
           * the leftmost is the one to read first, and wrapping would bury that ordering in
           * a block of equal-looking cards. On a phone it becomes a swipe.
           */
          <div className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1">
            {items.map((finding) => (
              <FindingChip
                key={finding.id}
                finding={finding}
                active={finding.id === activeId}
                explaining={open === finding.id}
                onClick={() => finding.intent && onIntent(toIntent(finding), finding.id)}
                onExplain={() => explain(finding)}
              />
            ))}
          </div>
        )}

        {open && (
          <div className="mt-2 rounded-lg border border-border bg-muted/30 p-2.5 text-xs">
            {showing === "loading" || showing === undefined ? (
              <span className="text-muted-foreground">Working out why…</span>
            ) : (
              <>
                <p className="leading-snug">{showing.text}</p>
                <p className="mt-1.5 text-[0.65rem] text-muted-foreground">
                  {showing.source === "model"
                    ? "Written by a model from the finding above — it adds no numbers of its own, and any it invented would have been discarded."
                    : "The detector's own wording. " + (showing.note ?? "")}
                </p>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FindingChip({
  finding,
  active,
  explaining,
  onClick,
  onExplain,
}: {
  finding: Finding;
  active: boolean;
  explaining: boolean;
  onClick: () => void;
  onExplain: () => void;
}) {
  const clickable = Boolean(finding.intent);
  return (
    <div
      role="group"
      // A caveat is not decoration: it is what the number is *not*, written where the
      // limitation was known. Surfaced on hover rather than buried in a response body.
      title={[finding.detail, ...finding.derived.caveats].filter(Boolean).join("\n\n")}
      className={cn(
        "min-w-[15rem] max-w-[22rem] shrink-0 snap-start rounded-lg border p-2.5 text-left transition-colors",
        "border-border bg-muted/30",
        active && "ring-2 ring-ring",
      )}
    >
      <span
        className={cn(
          "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[0.6rem] font-medium",
          KIND_TONE[finding.kind] ?? "border-border text-muted-foreground",
        )}
      >
        {KIND_LABEL[finding.kind] ?? finding.kind.replace(/_/g, " ")}
      </span>

      <p className="mt-1.5 text-xs leading-snug">{finding.headline}</p>

      {finding.evidence.length > 0 && (
        <p className="numeric mt-1.5 text-[0.65rem] text-muted-foreground">
          {finding.evidence
            .slice(0, 2)
            .map((e) => `${e.label} ${formatNumber(e.value)}${e.unit ? ` ${e.unit}` : ""}`)
            .join(" · ")}
        </p>
      )}

      <div className="mt-2 flex gap-1.5">
        <button
          onClick={onClick}
          disabled={!clickable}
          className={cn(
            "rounded-md border border-border px-1.5 py-0.5 text-[0.65rem] transition-colors",
            clickable ? "hover:bg-accent" : "cursor-default opacity-40",
          )}
        >
          Show me
        </button>
        <button
          onClick={onExplain}
          title="Ask the agent why this is happening. One model call, then cached."
          className={cn(
            "rounded-md border border-border px-1.5 py-0.5 text-[0.65rem] transition-colors hover:bg-accent",
            explaining && "bg-accent text-foreground",
          )}
        >
          Why?
        </button>
      </div>
    </div>
  );
}

/**
 * A finding's intent, in the client's own shape.
 *
 * The server sends `null` for absent fields and the reducer expects them missing or
 * undefined; normalising here keeps that difference out of every call site.
 */
function toIntent(finding: Finding): ViewIntent {
  const intent = finding.intent!;
  return {
    kind: intent.kind as ViewIntent["kind"],
    reason: intent.reason,
    zone: intent.zone ?? undefined,
    zones: intent.zones?.length ? intent.zones : undefined,
    signal: intent.signal ?? undefined,
    panel: intent.panel ?? undefined,
    at: intent.at ?? undefined,
    until: intent.until ?? undefined,
  };
}
