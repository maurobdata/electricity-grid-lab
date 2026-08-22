/**
 * Typed client for the Grid Lab API.
 *
 * The shapes here mirror `services/api/src/gridlab/domain/models.py` and the payload
 * builders in `web/routes_grid.py`. They are hand-written rather than generated: the
 * surface is small, and a generator would be another moving part to keep running.
 *
 * Two fields appear on almost everything and must never be dropped on the way to a screen:
 * `provenance` says whether a value was measured, replayed or generated, and `is_estimated`
 * says whether Electricity Maps modelled it rather than observing it.
 */

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export type Provenance = "live" | "recorded" | "synthetic";
export type Mode = "live" | "replay";

export interface Observation {
  zone: string;
  at: string;
  provenance: Provenance;
  is_estimated: boolean;
  estimation_method: string | null;
  is_stale: boolean;
  updated_at: string | null;
}

export interface ScalarObservation extends Observation {
  value: number;
}

export interface CarbonIntensity extends ScalarObservation {
  emission_factor_type: string | null;
  flow_traced: boolean | null;
}

export interface Price extends ScalarObservation {
  currency: string;
  unit: string;
  /** `nordpool.com` for a settled auction price, or Electricity Maps' own modelled value. */
  source: string | null;
}

export interface MixEntry {
  source: string;
  power_mw: number | null;
  percent: number | null;
}

export interface MixBreakdown extends Observation {
  entries: MixEntry[];
  /** True when imports have been traced to their origin, false for domestic production. */
  flow_traced: boolean;
  total_mw: number | null;
}

export interface FlowEdge {
  counterpart_zone: string;
  /** Positive is export, negative is import. */
  net_flow_mw: number;
}

export interface Flows extends Observation {
  edges: FlowEdge[];
  net_import_mw: number;
}

export interface GridSnapshot {
  zone: string;
  at: string;
  provenance: Provenance;
  carbon_intensity: CarbonIntensity | null;
  renewable_percentage: ScalarObservation | null;
  carbon_free_percentage: ScalarObservation | null;
  price: Price | null;
  mix: MixBreakdown | null;
  flows: Flows | null;
  load: ScalarObservation | null;
  /** Signals asked for and not returned. Distinct from signals never requested. */
  unavailable: string[];
}

export interface Series {
  zone: string;
  signal: string;
  granularity: string;
  horizon_hours: number | null;
  /** When a forecast was issued. Null for history. Without it, no outcome comparison. */
  issued_at: string | null;
  provenance: Provenance;
  estimated_fraction: number;
  points: (ScalarObservation & Partial<Price> & Partial<CarbonIntensity>)[];
}

export interface ScenarioSummary {
  id: string;
  title: string;
  description: string;
  provenance: Provenance;
  start: string;
  end: string;
  zones: string[];
  notes: string;
}

export interface ReplayState {
  scenario: ScenarioSummary | null;
  running?: boolean;
  speed?: number;
  progress?: number;
  window?: { start: string; end: string | null };
}

export interface Status {
  version: string;
  mode: Mode;
  requested_mode: Mode;
  now: string;
  provenance: Provenance;
  zones: string[];
  has_electricity_maps_token: boolean;
  has_anthropic_key: boolean;
  notice?: string;
  replay?: ReplayState;
  cache?: Record<string, unknown>;
}

export interface ZoneInfo {
  key: string;
  name: string;
}

export interface SignalAccess {
  signal: string;
  reachable: boolean;
  temporalities: string[];
  horizons: number[];
  note: string | null;
}

export interface Capabilities {
  source: "probe" | "unprobed";
  has_token: boolean;
  message?: string;
  note?: string;
  configured_zones?: string[];
  zone_count?: number;
  tier_counts?: Record<string, number>;
  signals?: SignalAccess[];
  warnings?: string[];
  probed_at?: string;
}

export interface Comparison {
  signal: string;
  at: string;
  provenance: Provenance;
  zones: Record<string, ScalarObservation | null>;
  note: string;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(path: string, params?: Record<string, string | number | boolean>) {
  const url = new URL(`/api/v1${path}`, BASE);
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, String(value));
  }

  const response = await fetch(url, { headers: { accept: "application/json" } });
  if (!response.ok) {
    // 404 is routine here rather than exceptional: a plan without day-ahead price, or a
    // zone missing from the current scenario. The detail carries what was available, so
    // it is preserved for the panel to show instead of a bare failure.
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = await response.text().catch(() => undefined);
    }
    throw new ApiError(response.status, `${response.status} on ${path}`, detail);
  }
  return (await response.json()) as T;
}

async function post<T>(path: string, params?: Record<string, string | number>) {
  const url = new URL(`/api/v1${path}`, BASE);
  for (const [key, value] of Object.entries(params ?? {})) {
    url.searchParams.set(key, String(value));
  }
  const response = await fetch(url, { method: "POST" });
  if (!response.ok) throw new ApiError(response.status, `${response.status} on ${path}`);
  return (await response.json()) as T;
}

export const api = {
  status: () => get<Status>("/status"),
  capabilities: () => get<Capabilities>("/capabilities"),
  zones: () => get<{ mode: Mode; provenance: Provenance; zones: ZoneInfo[] }>("/zones"),

  now: (zone: string) => get<GridSnapshot>(`/grid/${encodeURIComponent(zone)}/now`),
  mix: (zone: string, flowTraced: boolean) =>
    get<MixBreakdown>(`/grid/${encodeURIComponent(zone)}/mix`, { flow_traced: flowTraced }),
  flows: (zone: string) => get<Flows>(`/grid/${encodeURIComponent(zone)}/flows`),
  forecast: (zone: string, signal: string, horizonHours: number) =>
    get<Series>(`/grid/${encodeURIComponent(zone)}/forecast`, {
      signal,
      horizon_hours: horizonHours,
    }),
  history: (zone: string, signal: string, start?: string, end?: string) =>
    get<Series>(`/grid/${encodeURIComponent(zone)}/history`, {
      signal,
      ...(start ? { start } : {}),
      ...(end ? { end } : {}),
    }),
  compare: (zones: string[], signal: string) =>
    get<Comparison>("/compare", { zones: zones.join(","), signal }),

  scenarios: () =>
    get<{ current: string | null; scenarios: ScenarioSummary[] }>("/replay/scenarios"),
  loadScenario: (id: string) => post<ReplayState>("/replay/scenario", { id }),
  pause: () => post<ReplayState>("/replay/pause"),
  resume: () => post<ReplayState>("/replay/resume"),
  seek: (to: string) => post<ReplayState>("/replay/seek", { to }),
  setSpeed: (multiplier: number) => post<ReplayState>("/replay/speed", { multiplier }),
};
