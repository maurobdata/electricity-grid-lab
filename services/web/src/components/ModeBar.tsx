/**
 * The persistent control bar: which mode, which scenario, and the replay transport.
 *
 * Always on screen, never collapsed. Someone watching a demo should never have to wonder
 * whether they are looking at the live grid or a recording — and the person running it
 * should be able to stop on the interesting hour and talk over it, which is why this has
 * a scrubber rather than just a play button.
 */

import { useEffect, useState } from "react";

import { ProvenanceBadge } from "@/components/ProvenanceBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { api, type ScenarioSummary, type Status } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const SPEEDS = [1, 60, 360, 1440];
const SPEED_LABEL: Record<number, string> = {
  1: "real time",
  60: "1h / min",
  360: "6h / min",
  1440: "1 day / min",
};

export function ModeBar({
  status,
  scenarios,
  onChanged,
}: {
  status: Status;
  scenarios: ScenarioSummary[];
  onChanged: () => void;
}) {
  const replay = status.replay;
  const running = replay?.running ?? false;
  const [busy, setBusy] = useState(false);
  const [scrub, setScrub] = useState<number | null>(null);

  // While the clock is running the slider follows it; while dragging, the drag wins.
  useEffect(() => {
    if (scrub === null) return;
    const timer = window.setTimeout(() => setScrub(null), 1200);
    return () => window.clearTimeout(timer);
  }, [scrub]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const window_ = replay?.window;
  const progress = scrub ?? (replay?.progress ?? 0);

  const seekTo = (fraction: number) => {
    if (!window_?.start || !window_.end) return;
    const start = new Date(window_.start).getTime();
    const end = new Date(window_.end).getTime();
    const target = new Date(start + (end - start) * fraction).toISOString();
    void act(() => api.seek(target));
  };

  return (
    <div className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "rounded px-1.5 py-0.5 text-[0.65rem] font-bold uppercase tracking-widest",
              status.mode === "live"
                ? "bg-[var(--color-live)]/15 text-[var(--color-live)]"
                : "bg-[var(--color-recorded)]/15 text-[var(--color-recorded)]",
            )}
          >
            {status.mode}
          </span>
          <ProvenanceBadge provenance={status.provenance} />
        </div>

        {status.notice && (
          <Badge variant="warn" title={status.notice}>
            mode fell back
          </Badge>
        )}

        {replay?.scenario && (
          <>
            <Select
              value={replay.scenario.id}
              disabled={busy}
              onChange={(event) => void act(() => api.loadScenario(event.target.value))}
              className="max-w-[22rem] flex-1"
              aria-label="Scenario"
            >
              {scenarios.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.provenance === "synthetic" ? "◇ " : "● "}
                  {scenario.title}
                </option>
              ))}
            </Select>

            <div className="flex items-center gap-1.5">
              <Button
                onClick={() => void act(() => (running ? api.pause() : api.resume()))}
                disabled={busy}
                aria-label={running ? "Pause" : "Play"}
                size="icon"
              >
                {running ? "❙❙" : "▶"}
              </Button>
              <Select
                value={String(replay.speed ?? 60)}
                disabled={busy}
                onChange={(event) => void act(() => api.setSpeed(Number(event.target.value)))}
                aria-label="Playback speed"
              >
                {SPEEDS.map((speed) => (
                  <option key={speed} value={speed}>
                    {SPEED_LABEL[speed] ?? `${speed}x`}
                  </option>
                ))}
              </Select>
            </div>

            <div className="flex min-w-[16rem] flex-1 items-center gap-2">
              <input
                type="range"
                min={0}
                max={1000}
                value={Math.round(progress * 1000)}
                onChange={(event) => setScrub(Number(event.target.value) / 1000)}
                onMouseUp={(event) => seekTo(Number(event.currentTarget.value) / 1000)}
                onTouchEnd={(event) => seekTo(Number(event.currentTarget.value) / 1000)}
                className="h-1 w-full cursor-pointer appearance-none rounded bg-muted accent-[var(--color-primary)]"
                aria-label="Position in the recorded window"
              />
            </div>
          </>
        )}

        <span className="numeric ml-auto text-xs text-muted-foreground">
          {formatDateTime(status.now)}
        </span>
      </div>

      {replay?.scenario?.provenance === "synthetic" && (
        <div className="border-t border-[var(--color-synthetic)]/30 bg-[var(--color-synthetic)]/10 px-4 py-1 text-center text-[0.7rem] text-[var(--color-synthetic)]">
          Synthetic scenario — every number on this screen was generated, not measured. Run{" "}
          <code className="font-mono">make scenario-live</code> to replay real data.
        </div>
      )}
    </div>
  );
}
