import type { ProvKind, Provenance } from "../api/types";

const HELP: Record<ProvKind, string> = {
  live: "Live: fetched from the provider just now",
  scheduled: "Scheduled: from a published timetable or fare chart",
  estimated: "Estimated: modeled by KogniSync, may differ",
};

export function ProvenanceBadge({ kind, provenance }: { kind?: ProvKind; provenance?: Provenance }) {
  const k = provenance?.kind ?? kind ?? "estimated";
  const stale = provenance?.stale;
  const title = [HELP[k], provenance?.source && `Source: ${provenance.source}`, stale && "Live data went stale"]
    .filter(Boolean)
    .join(". ");
  return (
    <span className={`prov prov--${k}`} title={title}>
      {stale ? "stale" : k}
    </span>
  );
}
