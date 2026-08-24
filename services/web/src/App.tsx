/**
 * The Electricity Lab shell.
 *
 * One zone in focus, with everything the lab knows about it, plus a comparison across
 * several. Deliberately a single scrolling page rather than routed views: this is an
 * instrument panel for exploring what the data can do, and the product that eventually
 * grows out of it will not have this shape.
 *
 * See `docs/adr/0007-defer-product-decision.md` — the layout is a workbench, not a design.
 *
 * **What the app is looking at lives in one object**, not in a handful of `useState` calls
 * scattered here. That is what lets something other than the user change it: a finding
 * knows which window is worth seeing, the agent knows which panel its answer is about, and
 * a URL can reopen a view somebody shared. All three go through the same reducer, in
 * `lib/viewState.ts`, and none of them can do anything a control here could not.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { AgentPanel } from "@/components/AgentPanel";
import { CapabilityStrip } from "@/components/CapabilityStrip";
import { ComparePanel } from "@/components/ComparePanel";
import { FindingsRail } from "@/components/FindingsRail";
import { FlowsPanel } from "@/components/FlowsPanel";
import { ForecastPanel } from "@/components/ForecastPanel";
import { MixPanel } from "@/components/MixPanel";
import { ModeBar } from "@/components/ModeBar";
import { NowPanel } from "@/components/NowPanel";
import { Select } from "@/components/ui/select";
import { pollInterval, useQuery } from "@/hooks/useApi";
import { useViewState } from "@/hooks/useViewState";
import { api } from "@/lib/api";
import { zoneLabel } from "@/lib/format";
import { isSignal, type PanelId, type ViewIntent } from "@/lib/viewState";

export default function App() {
  const [reload, setReload] = useState(0);
  const [activeFinding, setActiveFinding] = useState<string>();

  const bump = useCallback(() => setReload((n) => n + 1), []);

  // Status drives the poll rate, so replay at 60x refreshes fast enough to look alive
  // while live mode stays gentle on an API with no published rate limit.
  const status = useQuery(() => api.status(), [reload], { intervalMs: 2000 });
  const mode = status.data?.mode ?? "replay";
  const speed = status.data?.replay?.speed ?? 1;
  const interval = pollInterval(mode, speed);

  // Seeking is the one intent the client cannot satisfy alone: the replay clock lives on
  // the server, so the hook hands it back here to be performed.
  const seek = useCallback(
    (to: string) => {
      void api.seek(to).then(bump);
    },
    [bump],
  );

  const { view, dispatch, set, clearHighlight, blocked } = useViewState(mode, seek);

  const onFindingIntent = useCallback(
    (intent: ViewIntent, findingId: string) => {
      setActiveFinding(findingId);
      dispatch(intent);
    },
    [dispatch],
  );

  const onAgentIntent = useCallback(
    (intent: ViewIntent) => {
      setActiveFinding(undefined);
      dispatch(intent);
    },
    [dispatch],
  );

  /*
   * Focus promotes one panel and hides the rest.
   *
   * Pressing the control on the panel already focused returns to the full board, so the
   * affordance is its own way out — the alternative is a mode you can enter and not leave.
   * On a phone this is the difference between reading one thing and scrolling past six.
   */
  const toggleFocus = useCallback(
    (panel: PanelId) => set("focused", view.focused === panel ? undefined : panel),
    [set, view.focused],
  );

  const shows = useCallback(
    (panel: PanelId) => view.focused === undefined || view.focused === panel,
    [view.focused],
  );

  /*
   * Every data query is keyed on the scenario as well as the zone.
   *
   * Two scenarios can both contain DK-DK2, so zone alone is not identity: without the
   * scenario in the key, switching between them would leave one recording's numbers on
   * screen under the other one's provenance badge.
   *
   * `reload` is deliberately *not* part of the key — it is a refresh signal. Pausing the
   * clock should re-read the state, not blank the page.
   */
  const scenarioId = status.data?.replay?.scenario?.id ?? status.data?.mode ?? "unknown";

  const zonesQuery = useQuery(() => api.zones(), [scenarioId], { refreshToken: reload });
  const zones = useMemo(() => zonesQuery.data?.zones ?? [], [zonesQuery.data]);

  const scenarios = useQuery(() => api.scenarios(), [], { refreshToken: reload });
  const capabilities = useQuery(() => api.capabilities(), [], { refreshToken: reload });

  const zone = view.zone;

  // Follow the data rather than holding a stale selection: switching scenarios changes
  // which zones exist, and a zone that has gone away would otherwise 404 every panel.
  useEffect(() => {
    if (zones.length === 0) return;
    if (!zone || !zones.some((z) => z.key === zone)) set("zone", zones[0]!.key);
    set(
      "compareZones",
      (() => {
        const kept = view.compareZones.filter((key) => zones.some((z) => z.key === key));
        return kept.length >= 2 ? kept : zones.slice(0, 4).map((z) => z.key);
      })(),
    );
    // `view.compareZones` is read but deliberately not a dependency: this effect exists to
    // reconcile the selection with the zone list, and re-running it whenever the selection
    // changes would fight the user for control of it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zones, zone, set]);

  const enabled = Boolean(zone);
  const common = { intervalMs: interval, enabled, refreshToken: reload };

  const snapshot = useQuery(() => api.now(zone!), [scenarioId, zone], common);
  const mix = useQuery(
    () => api.mix(zone!, view.flowTraced),
    [scenarioId, zone, view.flowTraced],
    common,
  );
  // The opposite breakdown, fetched quietly so the panel can quantify the difference
  // between the two views rather than making the reader toggle back and forth.
  const otherMix = useQuery(
    () => api.mix(zone!, !view.flowTraced),
    [scenarioId, zone, !view.flowTraced],
    common,
  );
  const flows = useQuery(() => api.flows(zone!), [scenarioId, zone], common);

  const history = useQuery(
    () => api.history(zone!, view.signal),
    [scenarioId, zone, view.signal],
    common,
  );
  const forecast = useQuery(
    () => api.forecast(zone!, view.signal, 72),
    [scenarioId, zone, view.signal],
    common,
  );

  const findings = useQuery(() => api.findings(zone!), [scenarioId, zone], common);

  const comparison = useQuery(
    () => api.compare(view.compareZones, view.compareSignal),
    [scenarioId, view.compareZones.join(","), view.compareSignal],
    { ...common, enabled: view.compareZones.length >= 2 },
  );

  if (status.error && !status.data) {
    return <Disconnected message={status.error.message} onRetry={bump} />;
  }
  if (!status.data) return <Splash />;

  const zoneName = zoneLabel(zone ?? "", zones.find((z) => z.key === zone)?.name);

  return (
    <div className="min-h-full">
      <ModeBar
        status={status.data}
        scenarios={scenarios.data?.scenarios ?? []}
        onChanged={bump}
      />

      <main className="mx-auto max-w-[1400px] space-y-4 px-4 py-4">
        <header className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
          <div>
            <h1 className="text-lg font-semibold">Grid Lab</h1>
            <p className="text-xs text-muted-foreground">
              Real Electricity Maps data — a foundation, not a product.
            </p>
          </div>
          <Select
            value={zone ?? ""}
            onChange={(event) => set("zone", event.target.value)}
            className="h-9 w-full text-sm sm:w-auto sm:min-w-[16rem]"
            aria-label="Zone"
          >
            {zones.map((option) => (
              <option key={option.key} value={option.key}>
                {option.name} ({option.key})
              </option>
            ))}
          </Select>
        </header>

        <FindingsRail
          findings={findings.data}
          unavailable={findings.status === 404}
          onIntent={onFindingIntent}
          activeId={activeFinding}
        />

        {view.focused && (
          /* A focused board hides five panels. Without a way back that is a trap, and the
             control that got you here is on a panel you may have scrolled past. */
          <button
            onClick={() => set("focused", undefined)}
            className="w-full rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:bg-accent"
          >
            Showing one panel · show all
          </button>
        )}

        {shows("now") && snapshot.data && (
          <NowPanel
            snapshot={snapshot.data}
            zoneName={zoneName}
            now={status.data.now}
            stale={snapshot.stale}
            focused={view.focused === "now"}
            onToggleFocus={toggleFocus}
          />
        )}

        {/* Side by side only where there is room for both. Below `lg` they stack, which is
            the whole of the mobile layout for this pair. */}
        <div className="grid gap-4 lg:grid-cols-2">
          {shows("mix") && (
            <MixPanel
              mix={mix.data}
              other={otherMix.data}
              flowTraced={view.flowTraced}
              onToggle={(next) => set("flowTraced", next)}
              unavailable={mix.status === 404}
              focused={view.focused === "mix"}
              onToggleFocus={toggleFocus}
            />
          )}
          {shows("flows") && (
            <FlowsPanel
              flows={flows.data}
              unavailable={flows.status === 404}
              focused={view.focused === "flows"}
              onToggleFocus={toggleFocus}
            />
          )}
        </div>

        {shows("forecast") && (
          <ForecastPanel
            history={history.data}
            forecast={forecast.data}
            signal={view.signal}
            onSignalChange={(next) => dispatch({ kind: "set_signal", signal: next, reason: next })}
            now={status.data.now}
            forecastUnavailable={forecast.status === 404}
            highlight={view.highlight}
            onClearHighlight={clearHighlight}
            focused={view.focused === "forecast"}
            onToggleFocus={toggleFocus}
          />
        )}

        {shows("compare") && (
          <ComparePanel
            comparison={comparison.data}
            zones={zones}
            selected={view.compareZones}
            onToggleZone={(key) =>
              set(
                "compareZones",
                view.compareZones.includes(key)
                  ? view.compareZones.filter((existing) => existing !== key)
                  : [...view.compareZones, key],
              )
            }
            signal={view.compareSignal}
            // Narrowed rather than cast: the panel hands back a raw `string` from a
            // `<select>`, and the view state only admits signals that exist.
            onSignalChange={(next) => isSignal(next) && set("compareSignal", next)}
            focused={view.focused === "compare"}
            onToggleFocus={toggleFocus}
          />
        )}

        {!view.focused && (
          <>
            <AgentPanel zone={zone} onIntent={onAgentIntent} blocked={blocked} />
            <CapabilityStrip capabilities={capabilities.data} />
          </>
        )}

        <footer className="pt-2 pb-6 text-[0.65rem] text-muted-foreground">
          Data from Electricity Maps. Every value on this page carries its provenance; nothing
          is padded or interpolated to fill a gap.
        </footer>
      </main>
    </div>
  );
}

function Splash() {
  return (
    <div className="flex min-h-full items-center justify-center text-sm text-muted-foreground">
      Connecting to the lab…
    </div>
  );
}

function Disconnected({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex min-h-full items-center justify-center px-4">
      <div className="max-w-md rounded-xl border border-destructive/40 bg-destructive/10 p-5 text-sm">
        <h1 className="font-semibold text-destructive">Cannot reach the API</h1>
        <p className="mt-2 text-muted-foreground">
          The lab could not talk to <code className="font-mono">/api/v1</code>. If you started
          the stack with <code className="font-mono">make up</code>, give it a few seconds and
          retry.
        </p>
        <p className="numeric mt-2 text-[0.7rem] text-muted-foreground">{message}</p>
        <button
          onClick={onRetry}
          className="mt-3 rounded-md border border-border px-2 py-1 text-xs hover:bg-accent"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
