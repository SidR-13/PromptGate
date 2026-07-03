import { ScoreBar } from "./ScoreBar";

export interface VersionStat {
  version: number;
  run_count: number;
  shipped: number;
  // Runs where GET /v1/locale-checks returned an empty list — locale checks
  // were never run, so they count as not shipped (fail-closed). Distinct from
  // a fetch failure (which leaves no map entry). Surfaced in the UI so that
  // "0% ship rate" from unevaluated runs doesn't look like a quality regression
  // — same intent as the score=0.0 gap annotation on the trend chart.
  unevaluated_count: number;
}

interface Props {
  stats: VersionStat[];
  loading: boolean;
}

export function VersionShipRateTable({ stats, loading }: Props) {
  if (loading) {
    return (
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        Computing ship rates…
      </p>
    );
  }

  if (stats.length === 0) {
    return (
      <p style={{ color: "var(--color-text-muted)", fontSize: "0.875rem" }}>
        No versions with runs yet.
      </p>
    );
  }

  const rates = stats.map((s) =>
    s.run_count === 0 ? 0 : (s.shipped / s.run_count) * 100
  );
  const maxRate = Math.max(...rates);

  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem" }}>
      <thead>
        <tr
          style={{
            borderBottom: `1px solid var(--color-border)`,
            color: "var(--color-text-secondary)",
            textAlign: "left",
          }}
        >
          <th style={{ padding: "0.375rem 1rem 0.375rem 0", fontWeight: 500 }}>Version</th>
          <th style={{ padding: "0.375rem 1rem 0.375rem 0", fontWeight: 500 }}>Runs</th>
          <th style={{ padding: "0.375rem 1rem 0.375rem 0", fontWeight: 500 }}>Shipped</th>
          <th style={{ padding: "0.375rem 0 0.375rem 0", fontWeight: 500 }}>Ship rate</th>
        </tr>
      </thead>
      <tbody>
        {stats.map((s, i) => {
          const rate = rates[i];
          const isGood = rate >= 80;
          const isBad = rate < 50;
          const isBest = rate === maxRate && maxRate > 0;
          const barColor = isBad
            ? "var(--color-text-danger)"
            : isGood
            ? "var(--color-text-success)"
            : "var(--color-text-warning)";
          return (
            <tr
              key={s.version}
              style={{
                borderBottom: `1px solid var(--color-border)`,
                boxShadow: isBest ? "inset 3px 0 0 var(--color-text-success)" : undefined,
              }}
            >
              <td style={{ padding: "0.375rem 1rem 0.375rem 0.5rem" }}>v{s.version}</td>
              <td
                style={{
                  padding: "0.375rem 1rem 0.375rem 0",
                  color: "var(--color-text-secondary)",
                }}
              >
                {s.run_count}
              </td>
              <td
                style={{
                  padding: "0.375rem 1rem 0.375rem 0",
                  color: "var(--color-text-secondary)",
                }}
              >
                {s.shipped}
              </td>
              <td style={{ padding: "0.375rem 0 0.375rem 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <ScoreBar
                    value={rate}
                    max={100}
                    barColor={barColor}
                    width={72}
                    label={`${rate.toFixed(0)}%`}
                  />
                  {s.unevaluated_count > 0 && (
                    <span
                      style={{ fontSize: "0.75rem", color: "var(--color-text-muted)" }}
                      title={`${s.unevaluated_count} run${s.unevaluated_count === 1 ? "" : "s"} have no locale checks — run POST /v1/evaluate-locale to include them`}
                    >
                      ({s.unevaluated_count} not locale-evaluated)
                    </span>
                  )}
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
