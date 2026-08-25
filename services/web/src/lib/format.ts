/**
 * Units, colours and the small judgements about how a number should read.
 *
 * Kept out of components so that "how do we describe carbon intensity" is answered once.
 */

import type { Provenance } from "@/lib/api";

/**
 * Carbon-intensity bands, gCO2eq/kWh.
 *
 * These are presentation bands, not Electricity Maps' own `*-level` signals. Theirs are
 * relative to each zone's rolling baseline, which is the better idea for a consumer
 * product and a worse one for a lab where you want to compare Norway with Poland on the
 * same scale. The boundaries are conventional rather than authoritative, and the number is
 * always shown next to the colour so nothing rests on the band alone.
 */
const CARBON_BANDS: [number, string, string][] = [
  [80, "cleanest", "Very clean"],
  [180, "clean", "Clean"],
  [320, "moderate", "Moderate"],
  [500, "dirty", "Dirty"],
  [Infinity, "dirtiest", "Very dirty"],
];

export function carbonBand(value: number | null | undefined) {
  if (value == null) return { key: "moderate", label: "Unknown", color: "var(--color-muted-foreground)" };
  const band = CARBON_BANDS.find(([limit]) => value < limit) ?? CARBON_BANDS[CARBON_BANDS.length - 1]!;
  return { key: band[1], label: band[2], color: `var(--color-grid-${band[1]})` };
}

/** Generation sources, coloured so a mix chart reads the same way every time. */
const SOURCE_COLORS: Record<string, string> = {
  wind: "#38bdf8",
  solar: "#facc15",
  hydro: "#22d3ee",
  nuclear: "#a78bfa",
  geothermal: "#fb7185",
  biomass: "#84cc16",
  gas: "#fb923c",
  coal: "#78716c",
  oil: "#a16207",
  unknown: "#475569",
  "battery storage discharge": "#2dd4bf",
  "hydro storage discharge": "#06b6d4",
};

export function sourceColor(source: string) {
  return SOURCE_COLORS[source] ?? SOURCE_COLORS.unknown!;
}

/** Sources that emit CO2 when burned. Used only for ordering and a summary share. */
const FOSSIL = new Set(["coal", "gas", "oil"]);
export const isFossil = (source: string) => FOSSIL.has(source);

export const PROVENANCE_LABEL: Record<Provenance, string> = {
  live: "Live",
  recorded: "Recorded",
  synthetic: "Synthetic",
};

export const PROVENANCE_BLURB: Record<Provenance, string> = {
  live: "Measured now, straight from the Electricity Maps API.",
  recorded: "Real API responses, captured earlier and replayed. Real, but not now.",
  synthetic: "Generated. Plausibly shaped and entirely made up — never present it as real.",
};

export function formatNumber(value: number | null | undefined, digits = 0) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-GB", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPower(mw: number | null | undefined) {
  if (mw == null) return "—";
  const magnitude = Math.abs(mw);
  if (magnitude >= 1000) return `${formatNumber(mw / 1000, 1)} GW`;
  return `${formatNumber(mw, magnitude < 10 ? 1 : 0)} MW`;
}

/**
 * Everything on this page is UTC, and says so.
 *
 * This used to render in the browser's own zone, on the argument that "the evening peak"
 * means something locally and nothing in UTC. That argument does not survive contact with
 * the rest of the system, for two reasons.
 *
 * **The browser's zone is not the grid's zone.** Reading DK-DK2 from Brussels rendered
 * Danish data in Belgian time — a third arbitrary zone, not the local time of anything on
 * screen. The lab shows several zones at once and the atlas shows forty-one; there is no
 * single local time for that page.
 *
 * **The server renders times too, and it cannot know yours.** Finding headlines are
 * composed in `analysis/events.py` in UTC. With the client on local time, a chip said
 * "by Mon 11:00" and the band it highlighted sat under an axis reading 13:00. Both numbers
 * were right and the page contradicted itself.
 *
 * So: one convention, and it is visible. `UTC` is appended wherever a full timestamp is
 * shown, and charts carry it once on the axis rather than on every tick.
 */
export const TIME_ZONE_LABEL = "UTC";

export function formatTime(iso: string) {
  return new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
}

export function formatDateTime(iso: string, { withZone = true } = {}) {
  const text = new Date(iso).toLocaleString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  });
  return withZone ? `${text} ${TIME_ZONE_LABEL}` : text;
}

export function formatRelative(iso: string, now: Date = new Date()) {
  const minutes = Math.round((now.getTime() - new Date(iso).getTime()) / 60000);
  if (Math.abs(minutes) < 1) return "just now";
  if (Math.abs(minutes) < 60) return minutes > 0 ? `${minutes}m ago` : `in ${-minutes}m`;
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) return hours > 0 ? `${hours}h ago` : `in ${-hours}h`;
  return formatDateTime(iso);
}

/** Zone keys are not obvious. `DK-DK2` should read as somewhere a person could stand. */
export function zoneLabel(key: string, name?: string) {
  return name && name !== key ? name : key;
}
