/**
 * The Electricity Lab shell.
 *
 * One zone in focus, with everything the lab knows about it, plus a comparison across
 * several. Deliberately a single scrolling page rather than routed views: this is an
 * instrument panel for exploring what the data can do, and the product that eventually
 * grows out of it will not have this shape.
 *
 * See `docs/adr/0007-defer-product-decision.md` — the layout is a workbench, not a design.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { CapabilityStrip } from "@/components/CapabilityStrip";
import { ComparePanel } from "@/components/ComparePanel";
import { FlowsPanel } from "@/components/FlowsPanel";
import { ForecastPanel } from "@/components/ForecastPanel";
import { MixPanel } from "@/components/MixPanel";
import { ModeBar } from "@/components/ModeBar";
import { NowPanel } from "@/components/NowPanel";
import { Select } from "@/components/ui/select";
import { pollInterval, useQuery } from "@/hooks/useApi";
import { api } from "@/lib/api";
import { zoneLabel } from "@/lib/format";

export default function App() {
  const [zone, setZone] = useState<string>();
  const [flowTraced, setFlowTraced] = useState(true);
  const [seriesSignal, setSeriesSignal] = useState("carbon_intensity");
  const [compareSignal, setCompareSignal] = useState("carbon_intensity");
  const [compareZones, setCompareZones] = useState<string[]>([]);
  const [reload, setReload] = useState(0);

  const bump = useCallback(() => setReload((n) => n + 1), []);

  // Status drives the poll rate, so replay at 60x refreshes fast enough to look alive
  // while live mode stays gentle on an API with no published rate limit.
  const status = useQuery(() => api.status(), [reload], { intervalMs: 2000 });
  const mode = status.data?.mode ?? "replay";
  const speed = status.data?.replay?.speed ?? 1;
  const interval = pollInterval(mode, speed);

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

  // Follow the data rather than holding a stale selection: switching scenarios changes
  // which zones exist, and a zone that has gone away would otherwise 404 every panel.
  useEffect(() => {
    if (zones.length === 0) return;
    if (!zone || !zones.some((z) => z.key === zone)) setZone(zones[0]!.key);
    setCompareZones((current) => {
      const kept = current.filter((key) => zones.some((z) => z.key === key));
      return kept.length >= 2 ? kept : zones.slice(0, 4).map((z) => z.key);
    });
  }, [zones, zone]);

  const enabled = Boolean(zone);
  const common = { intervalMs: interval, enabled, refreshToken: reload };

  const snapshot = useQuery(() => api.now(zone!), [scenarioId, zone], common);
  const mix = useQuery(() => api.mix(zone!, flowTraced), [scenarioId, zone, flowTraced], common);
  // The opposite breakdown, fetched quietly so the panel can quantify the difference
  // between the two views rather than making the reader toggle back and forth.
  const otherMix = useQuery(
    () => api.mix(zone!, !flowTraced),
    [scenarioId, zone, !flowTraced],
    common,
  );
  const flows = useQuery(() => api.flows(zone!), [scenarioId, zone], common);

  const history = useQuery(
    () => api.history(zone!, seriesSignal),
    [scenarioId, zone, seriesSignal],
    common,
  );
  const forecast = useQuery(
    () => api.forecast(zone!, seriesSignal, 72),
    [scenarioId, zone, seriesSignal],
    common,
  );

  const comparison = useQuery(
    () => api.compare(compareZones, compareSignal),
    [scenarioId, compareZones.join(","), compareSignal],
    { ...common, enabled: compareZones.length >= 2 },
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
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold">Grid Lab</h1>
            <p className="text-xs text-muted-foreground">
              Real Electricity Maps data — a foundation, not a product.
            </p>
          </div>
          <Select
            value={zone ?? ""}
            onChange={(event) => setZone(event.target.value)}
            className="h-9 min-w-[16rem] text-sm"
            aria-label="Zone"
          >
            {zones.map((option) => (
              <option key={option.key} value={option.key}>
                {option.name} ({option.key})
              </option>
            ))}
          </Select>
        </header>

        {snapshot.data && (
          <NowPanel
            snapshot={snapshot.data}
            zoneName={zoneName}
            now={status.data.now}
            stale={snapshot.stale}
          />
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          <MixPanel
            mix={mix.data}
            other={otherMix.data}
            flowTraced={flowTraced}
            onToggle={setFlowTraced}
            unavailable={mix.status === 404}
          />
          <FlowsPanel flows={flows.data} unavailable={flows.status === 404} />
        </div>

        <ForecastPanel
          history={history.data}
          forecast={forecast.data}
          signal={seriesSignal}
          onSignalChange={setSeriesSignal}
          now={status.data.now}
          forecastUnavailable={forecast.status === 404}
        />

        <ComparePanel
          comparison={comparison.data}
          zones={zones}
          selected={compareZones}
          onToggleZone={(key) =>
            setCompareZones((current) =>
              current.includes(key)
                ? current.filter((existing) => existing !== key)
                : [...current, key],
            )
          }
          signal={compareSignal}
          onSignalChange={setCompareSignal}
        />

        <CapabilityStrip capabilities={capabilities.data} />

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
